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

from src.utils import uuidutil


@dataclass
class Connection:
    uuid: str
    name: str = ""
    url: str = ""
    methods: list[str] = field(default_factory=list)


def _copy(conn: Connection) -> Connection:
    return replace(conn, methods=list(conn.methods))


def _new_uuid() -> str:
    return str(uuidutil.get_uuid())


class ConnectionStore:
    """連線配置的新增、刪除、修改，每次修改立即寫回檔案"""

    def __init__(self, path):
        self._path = Path(path)
        self._connections: list[Connection] = []
        self.recovered_from_corruption = False
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def backup_path(self) -> Path:
        return self._path.with_name(self._path.name + ".bak")

    def all(self) -> list[Connection]:
        return [_copy(conn) for conn in self._connections]

    def get(self, uuid: str) -> Connection | None:
        for conn in self._connections:
            if conn.uuid == uuid:
                return _copy(conn)
        return None

    def add(self) -> Connection:
        conn = Connection(uuid=_new_uuid())
        self._connections.append(conn)
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

    def _find(self, uuid: str) -> Connection:
        for conn in self._connections:
            if conn.uuid == uuid:
                return conn
        raise KeyError(uuid)

    def _load(self) -> None:
        if not self._path.exists():
            self._save()
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._connections = [
                Connection(
                    uuid=item.get("uuid") or "",
                    name=item.get("name") or "",
                    url=item.get("url") or "",
                    methods=list(item.get("method") or []),
                )
                for item in data["connections"]
            ]
        except (ValueError, KeyError, TypeError, AttributeError) as err:
            # JSONDecodeError、UnicodeDecodeError 都是 ValueError 的子類別
            logger.warning("連線設定檔無法讀取，備份為 {}: {}", self.backup_path, err)
            os.replace(self._path, self.backup_path)
            self._connections = []
            self.recovered_from_corruption = True
            self._save()
            return
        missing = [conn for conn in self._connections if not conn.uuid]
        for conn in missing:
            conn.uuid = _new_uuid()
        if missing:
            self._save()

    def _save(self) -> None:
        data = {"connections": [
            {"uuid": conn.uuid, "name": conn.name, "url": conn.url, "method": conn.methods}
            for conn in self._connections
        ]}
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
