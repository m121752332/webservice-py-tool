# -*- coding: utf-8 -*-
"""
連線配置存取：讀寫 connections.profile
"""
import json
import os
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

from loguru import logger

from src.utils import uuid_util


@dataclass
class Folder:
    uuid: str
    name: str = ""
    expanded: bool = True


@dataclass
class Connection:
    uuid: str
    name: str = ""
    url: str = ""
    methods: list[str] = field(default_factory=list)
    folder: str | None = None  # 所屬目錄 uuid，None 表示最外層


def _copy(conn: Connection) -> Connection:
    return replace(conn, methods=list(conn.methods))


def _new_uuid() -> str:
    return uuid_util.new_uuid()


def _parse_methods(method) -> list[str]:
    """method 欄位必須是清單；其他型別（例如舊版損毀寫入的字串）視為檔案損毀"""
    if method is None:
        return []
    if not isinstance(method, list):
        raise TypeError(f"method 欄位型別錯誤：{type(method).__name__}")
    return list(method)


def _parse_folder_ref(value) -> str | None:
    """folder 欄位：缺少或空字串表示最外層，其他非字串型別視為檔案損毀"""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise TypeError(f"folder 欄位型別錯誤：{type(value).__name__}")
    return value


def _parse_expanded(value) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"expanded 欄位型別錯誤：{type(value).__name__}")
    return value


def _parse_folders(raw) -> list[Folder]:
    """folders 欄位：缺少時（舊版設定檔）視為沒有目錄，必須是物件清單"""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise TypeError(f"folders 欄位型別錯誤：{type(raw).__name__}")
    return [
        Folder(
            uuid=item.get("uuid") or "",
            name=item.get("name") or "",
            expanded=_parse_expanded(item.get("expanded", True)),
        )
        for item in raw
    ]


class ConnectionStore:
    """目錄與連線配置的新增、刪除、修改、排序，每次修改立即寫回檔案"""

    def __init__(self, path):
        self._path = Path(path)
        self._folders: list[Folder] = []
        self._connections: list[Connection] = []
        self.recovered_from_corruption = False
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def backup_path(self) -> Path:
        return self._path.with_name(self._path.name + ".bak")

    # ---------- 連線 ----------

    def all(self) -> list[Connection]:
        return [_copy(conn) for conn in self._connections]

    def get(self, uuid: str) -> Connection | None:
        for conn in self._connections:
            if conn.uuid == uuid:
                return _copy(conn)
        return None

    def add(self, folder: str | None = None) -> Connection:
        if folder is not None:
            self._find_folder(folder)
        conn = Connection(uuid=_new_uuid(), folder=folder)
        self._connections.append(conn)  # 陣列結尾即該群組的最後面
        self._save()
        return _copy(conn)

    def remove(self, uuid: str) -> None:
        self._connections.remove(self._find(uuid))
        self._save()

    def rename(self, uuid: str, name: str) -> None:
        self._find(uuid).name = name
        self._save()

    def set_url(self, uuid: str, url: str) -> None:
        self._find(uuid).url = url
        self._save()

    def set_methods(self, uuid: str, methods: list[str]) -> None:
        self._find(uuid).methods = list(methods)
        self._save()

    def move_connection(self, uuid: str, folder: str | None, index: int) -> None:
        """移到 folder（None 為最外層）群組的第 index 個位置，index 以移除自己之後的群組計算"""
        conn = self._find(uuid)
        if folder is not None:
            self._find_folder(folder)
        self._connections.remove(conn)
        conn.folder = folder
        group = [other for other in self._connections if other.folder == folder]
        index = max(0, index)
        position = self._connections.index(group[index]) if index < len(group) else len(self._connections)
        self._connections.insert(position, conn)
        self._save()

    # ---------- 目錄 ----------

    def folders(self) -> list[Folder]:
        return [replace(folder) for folder in self._folders]

    def get_folder(self, uuid: str) -> Folder | None:
        for folder in self._folders:
            if folder.uuid == uuid:
                return replace(folder)
        return None

    def add_folder(self, name: str) -> Folder:
        folder = Folder(uuid=_new_uuid(), name=name)
        self._folders.append(folder)
        self._save()
        return replace(folder)

    def rename_folder(self, uuid: str, name: str) -> None:
        self._find_folder(uuid).name = name
        self._save()

    def set_folder_expanded(self, uuid: str, expanded: bool) -> None:
        self._find_folder(uuid).expanded = expanded
        self._save()

    def remove_folder(self, uuid: str) -> None:
        """刪除目錄；裡面的連線維持相對順序，移到最外層連線的最後面"""
        self._folders.remove(self._find_folder(uuid))
        kept = [conn for conn in self._connections if conn.folder != uuid]
        moved = [conn for conn in self._connections if conn.folder == uuid]
        for conn in moved:
            conn.folder = None
        self._connections = kept + moved
        self._save()

    def move_folder(self, uuid: str, index: int) -> None:
        folder = self._find_folder(uuid)
        self._folders.remove(folder)
        self._folders.insert(max(0, index), folder)
        self._save()

    # ---------- 內部 ----------

    def _find(self, uuid: str) -> Connection:
        for conn in self._connections:
            if conn.uuid == uuid:
                return conn
        raise KeyError(uuid)

    def _find_folder(self, uuid: str) -> Folder:
        for folder in self._folders:
            if folder.uuid == uuid:
                return folder
        raise KeyError(uuid)

    def _load(self) -> None:
        if not self._path.exists():
            self._save()
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._folders = _parse_folders(data.get("folders"))
            self._connections = [
                Connection(
                    uuid=item.get("uuid") or "",
                    name=item.get("name") or "",
                    url=item.get("url") or "",
                    methods=_parse_methods(item.get("method")),
                    folder=_parse_folder_ref(item.get("folder")),
                )
                for item in data["connections"]
            ]
        except (ValueError, KeyError, TypeError, AttributeError) as err:
            # JSONDecodeError、UnicodeDecodeError 都是 ValueError 的子類別
            logger.warning("連線設定檔無法讀取，備份為 {}: {}", self.backup_path, err)
            os.replace(self._path, self.backup_path)
            self._folders = []
            self._connections = []
            self.recovered_from_corruption = True
            self._save()
            return
        if self._repair():
            self._save()

    def _repair(self) -> bool:
        """補上缺少的 uuid、把指向不存在目錄的連線移回最外層；有修改時回傳 True"""
        changed = False
        for item in [*self._folders, *self._connections]:
            if not item.uuid:
                item.uuid = _new_uuid()
                changed = True
        folder_ids = {folder.uuid for folder in self._folders}
        for conn in self._connections:
            if conn.folder is not None and conn.folder not in folder_ids:
                conn.folder = None
                changed = True
        return changed

    def _save(self) -> None:
        data = {
            "folders": [
                {"uuid": folder.uuid, "name": folder.name, "expanded": folder.expanded}
                for folder in self._folders
            ],
            "connections": [
                {"uuid": conn.uuid, "name": conn.name, "url": conn.url, "method": conn.methods, "folder": conn.folder}
                for conn in self._connections
            ],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # 先寫暫存檔再取代，寫到一半當掉也不會毀損原檔
        fd, tmp_name = tempfile.mkstemp(prefix=self._path.name + ".", suffix=".tmp", dir=self._path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
            os.replace(tmp_name, self._path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
