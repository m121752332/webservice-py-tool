# 連線清單目錄（書籤管理）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 左側連線清單支援單層目錄分組：新增／改名／刪除目錄、拖曳或右鍵移動連線、排序、展開狀態記憶。

**Architecture:** `ConnectionStore` 是唯一資料來源，新增 `Folder` 與 `Connection.folder`，檔案格式只加欄位。`ConnectionList` 由 `QListWidget` 改成 `QTreeWidget`，拖放時不讓 Qt 搬移項目，只以純函式 `resolve_drop` 算出目標並送出訊號；`MainWindow` 收到訊號後更新 store，再以 `_refresh_tree()` 重建整棵樹。

**Tech Stack:** Python 3.14、PySide6（Essentials）6.11、pytest（offscreen 平台）、uv

**Spec:** `docs/superpowers/specs/2026-09-25-connection-folders-design.md`

## Global Constraints

- 舊版 `connections.profile`（沒有 `folders`／`folder` 欄位）必須可直接讀取，所有連線視為在最外層
- 新格式只增加欄位：頂層 `folders`，每筆連線 `folder`（目錄 uuid 或 `null`）
- 單層目錄：目錄不能放進目錄
- 最外層固定目錄在前、連線在後
- 版本號與 `ws_tool.yaml` 不變
- UI 文字使用繁體中文，字串照本計畫原樣使用
- 執行測試一律用 `uv run pytest`
- Commit 訊息用中文：先用 Write 工具把訊息寫到 `.git/COMMIT_MSG_TMP`，再 `git commit -F .git/COMMIT_MSG_TMP`，最後刪除該檔（bash heredoc 會產生亂碼）。訊息結尾加上 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 工作分支：`feat/connection-folders`

---

## File Structure

| 檔案 | 責任 | 變更 |
|---|---|---|
| `src/core/connection_store.py` | `Folder`、`Connection`、`ConnectionStore`：目錄與連線的增刪改、排序、讀寫檔 | 修改 |
| `src/ui/connection_list.py` | `TreeLayout`／`Move`／`resolve_drop`（拖放計算純函式）＋ `ConnectionList` 樹狀元件 | 大幅改寫 |
| `src/ui/theme.py` | QSS 選擇器 `QListWidget` → `QTreeWidget` | 修改 |
| `src/ui/main_window.py` | `_refresh_tree` 與目錄相關訊號處理 | 修改 |
| `README.md` | 介面與快捷鍵說明 | 修改 |
| `tests/test_connection_store.py` | store 測試 | 修改 |
| `tests/test_connection_list.py` | 清單元件與 `resolve_drop` 測試 | 修改 |
| `tests/test_main_window.py` | 主視窗整合測試 | 修改 |

---

### Task 1: 資料層支援目錄

**Files:**
- Modify: `src/core/connection_store.py`
- Test: `tests/test_connection_store.py`

**Interfaces:**
- Consumes: 無
- Produces:
  - `Folder(uuid: str, name: str = "", expanded: bool = True)`（dataclass）
  - `Connection(uuid, name="", url="", methods=[], folder: str | None = None)`
  - `ConnectionStore.folders() -> list[Folder]`
  - `ConnectionStore.get_folder(uuid: str) -> Folder | None`
  - `ConnectionStore.add(folder: str | None = None) -> Connection`
  - `ConnectionStore.add_folder(name: str) -> Folder`
  - `ConnectionStore.rename_folder(uuid: str, name: str) -> None`
  - `ConnectionStore.remove_folder(uuid: str) -> None`
  - `ConnectionStore.set_folder_expanded(uuid: str, expanded: bool) -> None`
  - `ConnectionStore.move_connection(uuid: str, folder: str | None, index: int) -> None`
  - `ConnectionStore.move_folder(uuid: str, index: int) -> None`
  - 不存在的 uuid 一律拋 `KeyError`

- [ ] **Step 1: 修改既有測試的預期檔案內容**

`tests/test_connection_store.py`：

1. import 改成：
```python
from src.core.connection_store import Connection, ConnectionStore, Folder
```

2. `test_missing_file_creates_empty_profile` 的最後一個 JSON 斷言改成：
```python
    assert read_json(path) == {"folders": [], "connections": []}
```

3. `test_add_persists_blank_connection` 的 JSON 斷言改成：
```python
    assert read_json(path) == {
        "folders": [],
        "connections": [{"uuid": conn.uuid, "name": "", "url": "", "method": [], "folder": None}],
    }
```

4. `test_corrupt_file_is_backed_up` 與 `test_string_method_is_treated_as_corrupt` 最後的 `assert read_json(path) == {"connections": []}` 都改成：
```python
    assert read_json(path) == {"folders": [], "connections": []}
```

5. `test_reads_legacy_profile` 最後加一行：
```python
    assert store.folders() == []
```

- [ ] **Step 2: 新增目錄相關測試**

附加到 `tests/test_connection_store.py` 檔尾：

```python
def group(store, folder):
    return [conn.uuid for conn in store.all() if conn.folder == folder]


def test_folder_add_rename_expand_persist(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    folder = store.add_folder("TIPTOP")
    assert folder == Folder(folder.uuid, "TIPTOP", True)
    assert len(folder.uuid) == 36
    store.rename_folder(folder.uuid, "ERP")
    store.set_folder_expanded(folder.uuid, False)
    assert ConnectionStore(path).folders() == [Folder(folder.uuid, "ERP", False)]
    assert read_json(path)["folders"] == [{"uuid": folder.uuid, "name": "ERP", "expanded": False}]


def test_get_folder_and_copies(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    uuid = store.add_folder("F").uuid
    assert store.get_folder("nope") is None
    store.get_folder(uuid).name = "changed"
    store.folders()[0].expanded = False
    assert store.get_folder(uuid) == Folder(uuid, "F", True)


def test_add_into_folder_appends_to_its_group(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    folder = store.add_folder("F").uuid
    a = store.add(folder).uuid
    b = store.add().uuid
    c = store.add(folder).uuid
    assert group(store, folder) == [a, c]
    assert group(store, None) == [b]
    saved = read_json(path)["connections"]
    assert [item["folder"] for item in saved] == [folder, None, folder]


def test_remove_folder_moves_connections_to_root_end(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    folder = store.add_folder("F").uuid
    a = store.add(folder).uuid
    b = store.add().uuid
    c = store.add(folder).uuid
    d = store.add().uuid
    store.remove_folder(folder)
    assert store.folders() == []
    assert group(store, None) == [b, d, a, c]


def test_move_connection_between_groups_and_within_group(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    folder = store.add_folder("F").uuid
    a = store.add().uuid
    b = store.add().uuid
    c = store.add(folder).uuid
    store.move_connection(a, folder, 0)
    assert group(store, folder) == [a, c] and group(store, None) == [b]
    store.move_connection(c, folder, 0)
    assert group(store, folder) == [c, a]
    store.move_connection(c, None, 99)  # 超出範圍夾到結尾
    assert group(store, None) == [b, c]
    store.move_connection(a, None, -5)  # 負數夾到開頭
    assert group(store, None) == [a, b, c] and group(store, folder) == []
    assert [conn.uuid for conn in ConnectionStore(path).all()] == [a, b, c]


def test_move_folder(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    f1, f2, f3 = (store.add_folder(name).uuid for name in ("1", "2", "3"))
    store.move_folder(f3, 0)
    assert [f.uuid for f in store.folders()] == [f3, f1, f2]
    store.move_folder(f3, 99)
    assert [f.uuid for f in store.folders()] == [f1, f2, f3]
    store.move_folder(f1, 1)
    assert [f.uuid for f in store.folders()] == [f2, f1, f3]


@pytest.mark.parametrize("action", [
    lambda store: store.add("nope"),
    lambda store: store.rename_folder("nope", "x"),
    lambda store: store.remove_folder("nope"),
    lambda store: store.set_folder_expanded("nope", False),
    lambda store: store.move_folder("nope", 0),
    lambda store: store.move_connection("nope", None, 0),
    lambda store: store.move_connection(store.add().uuid, "nope", 0),
])
def test_unknown_folder_uuid_raises_key_error(tmp_path, action):
    with pytest.raises(KeyError):
        action(ConnectionStore(tmp_path / "c.profile"))


def test_dangling_folder_reference_moves_to_root(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({"folders": [], "connections": [
        {"uuid": "u", "name": "", "url": "", "method": [], "folder": "gone"},
    ]}), encoding="utf-8")
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is False
    assert store.get("u").folder is None
    assert read_json(path)["connections"][0]["folder"] is None


def test_folder_defaults_and_blank_uuid(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({"folders": [{"uuid": "", "name": "F"}], "connections": []}), encoding="utf-8")
    store = ConnectionStore(path)
    folder = store.folders()[0]
    assert len(folder.uuid) == 36
    assert (folder.name, folder.expanded) == ("F", True)
    assert read_json(path)["folders"][0]["uuid"] == folder.uuid


@pytest.mark.parametrize("data", [
    {"folders": "abc", "connections": []},
    {"folders": [1], "connections": []},
    {"folders": [{"uuid": "f", "name": "F", "expanded": "yes"}], "connections": []},
    {"folders": [], "connections": [{"uuid": "u", "name": "", "url": "", "method": [], "folder": ["f"]}]},
])
def test_bad_folder_data_is_treated_as_corrupt(tmp_path, data):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps(data), encoding="utf-8")
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is True
    assert store.all() == [] and store.folders() == []
    assert read_json(path) == {"folders": [], "connections": []}
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `uv run pytest tests/test_connection_store.py -q`
Expected: FAIL，錯誤為 `ImportError: cannot import name 'Folder'`

- [ ] **Step 4: 實作資料層**

`src/core/connection_store.py` 整檔改成：

```python
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
    return str(uuidutil.get_uuid())


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
```

- [ ] **Step 5: 執行測試確認通過**

Run: `uv run pytest tests/test_connection_store.py -q`
Expected: 全部 PASS

- [ ] **Step 6: 確認其他測試未受影響**

Run: `uv run pytest -q`
Expected: 全部 PASS（UI 仍使用 `add()`／`all()`，不受影響）

- [ ] **Step 7: Commit**

訊息：
```
連線設定檔支援目錄：Folder 與連線所屬目錄、移動與排序

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```
```bash
git add src/core/connection_store.py tests/test_connection_store.py
git commit -F .git/COMMIT_MSG_TMP
rm .git/COMMIT_MSG_TMP
```

---

### Task 2: 拖放目標計算純函式 `resolve_drop`

**Files:**
- Modify: `src/ui/connection_list.py`（在 import 與 `class ElidedLabel` 之間加入）
- Test: `tests/test_connection_list.py`

**Interfaces:**
- Consumes: 無
- Produces:
  - 常數 `FOLDER = "folder"`、`CONNECTION = "connection"`、`ABOVE = "above"`、`BELOW = "below"`、`ON = "on"`
  - `TreeLayout(folders: list[str], groups: dict[str | None, list[str]])`，方法 `folder_of(conn_uuid) -> str | None`
  - `Move(kind: str, uuid: str, folder: str | None, index: int)`（frozen dataclass）
  - `resolve_drop(layout, kind, uuid, target_kind, target_uuid, position) -> Move | None`
    - `target_kind`／`target_uuid` 為 `None` 表示放在空白處
    - `Move.index` 是「移除自己之後」在目標群組中的位置，與 `ConnectionStore.move_connection`／`move_folder` 語意一致

- [ ] **Step 1: 寫失敗測試**

附加到 `tests/test_connection_list.py` 檔尾，並在檔案開頭 import 區加上 `import pytest`，把 connection_list 的 import 改成：
```python
from src.ui.connection_list import (
    ABOVE, BELOW, CONNECTION, FOLDER, NO_URL, ON, UNNAMED, ConnectionList, Move, TreeLayout, resolve_drop,
)
```

```python
LAYOUT = TreeLayout(folders=["f1", "f2"], groups={"f1": ["a", "b"], "f2": [], None: ["c", "d"]})


@pytest.mark.parametrize("kind, uuid, target_kind, target_uuid, position, expected", [
    # 連線放到目錄上：放進該目錄最後面（以移除自己後的群組計算）
    (CONNECTION, "c", FOLDER, "f1", ON, Move(CONNECTION, "c", "f1", 2)),
    (CONNECTION, "c", FOLDER, "f2", ON, Move(CONNECTION, "c", "f2", 0)),
    (CONNECTION, "a", FOLDER, "f1", ON, Move(CONNECTION, "a", "f1", 1)),
    # 連線放在連線上方／下方：放到該連線所在群組
    (CONNECTION, "c", CONNECTION, "b", ABOVE, Move(CONNECTION, "c", "f1", 1)),
    (CONNECTION, "c", CONNECTION, "b", BELOW, Move(CONNECTION, "c", "f1", 2)),
    (CONNECTION, "a", CONNECTION, "b", BELOW, Move(CONNECTION, "a", "f1", 1)),
    (CONNECTION, "d", CONNECTION, "c", ABOVE, Move(CONNECTION, "d", None, 0)),
    (CONNECTION, "c", CONNECTION, "d", ON, Move(CONNECTION, "c", None, 1)),
    # 連線放在目錄上方／下方：最外層第一個（最外層固定目錄在前）
    (CONNECTION, "a", FOLDER, "f2", ABOVE, Move(CONNECTION, "a", None, 0)),
    (CONNECTION, "a", FOLDER, "f1", BELOW, Move(CONNECTION, "a", None, 0)),
    # 連線放在空白處：最外層最後面
    (CONNECTION, "a", None, None, ON, Move(CONNECTION, "a", None, 2)),
    (CONNECTION, "c", None, None, ON, Move(CONNECTION, "c", None, 1)),
    # 目錄只在目錄之間排序
    (FOLDER, "f2", FOLDER, "f1", ABOVE, Move(FOLDER, "f2", None, 0)),
    (FOLDER, "f1", FOLDER, "f2", BELOW, Move(FOLDER, "f1", None, 1)),
    (FOLDER, "f1", FOLDER, "f2", ON, Move(FOLDER, "f1", None, 1)),
    (FOLDER, "f2", CONNECTION, "a", BELOW, Move(FOLDER, "f2", None, 1)),
    (FOLDER, "f1", CONNECTION, "c", ABOVE, Move(FOLDER, "f1", None, 1)),
    (FOLDER, "f2", None, None, ON, Move(FOLDER, "f2", None, 1)),
])
def test_resolve_drop(kind, uuid, target_kind, target_uuid, position, expected):
    assert resolve_drop(LAYOUT, kind, uuid, target_kind, target_uuid, position) == expected


@pytest.mark.parametrize("kind, uuid, target_kind, target_uuid, position", [
    (CONNECTION, "a", CONNECTION, "a", ABOVE),  # 放在自己身上
    (FOLDER, "f1", FOLDER, "f1", ON),
    (FOLDER, "f1", CONNECTION, "a", ABOVE),  # 目錄放到自己的連線上
])
def test_resolve_drop_onto_itself_is_ignored(kind, uuid, target_kind, target_uuid, position):
    assert resolve_drop(LAYOUT, kind, uuid, target_kind, target_uuid, position) is None
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_connection_list.py -q`
Expected: FAIL，`ImportError: cannot import name 'ABOVE'`

- [ ] **Step 3: 實作**

`src/ui/connection_list.py`：在最上方 import 區加入 `from dataclasses import dataclass`（放在 PySide6 import 之前，與標準函式庫分組）。在 `_UUID_ROLE = Qt.ItemDataRole.UserRole` 之後、`class ElidedLabel` 之前加入：

```python
FOLDER = "folder"
CONNECTION = "connection"
ABOVE = "above"
BELOW = "below"
ON = "on"


@dataclass
class TreeLayout:
    """清單目前的結構：目錄順序，以及各群組（目錄 uuid，None 為最外層）內的連線順序"""
    folders: list[str]
    groups: dict[str | None, list[str]]

    def folder_of(self, conn_uuid: str) -> str | None:
        for folder, members in self.groups.items():
            if conn_uuid in members:
                return folder
        raise KeyError(conn_uuid)


@dataclass(frozen=True)
class Move:
    kind: str  # FOLDER 或 CONNECTION
    uuid: str
    folder: str | None  # 連線的目標目錄；目錄移動時為 None
    index: int  # 移除自己之後，在目標群組中的位置


def resolve_drop(layout: TreeLayout, kind: str, uuid: str, target_kind: str | None,
                 target_uuid: str | None, position: str) -> Move | None:
    """計算拖放結果；target 為 None 表示放在空白處，放到自己身上時回傳 None"""
    if kind == FOLDER:
        return _resolve_folder_drop(layout, uuid, target_kind, target_uuid, position)
    return _resolve_connection_drop(layout, uuid, target_kind, target_uuid, position)


def _resolve_connection_drop(layout, uuid, target_kind, target_uuid, position) -> Move | None:
    if target_uuid == uuid:
        return None
    if target_kind == CONNECTION:
        folder = layout.folder_of(target_uuid)
        members = [member for member in layout.groups[folder] if member != uuid]
        return Move(CONNECTION, uuid, folder, members.index(target_uuid) + (0 if position == ABOVE else 1))
    if target_kind == FOLDER and position != ON:
        return Move(CONNECTION, uuid, None, 0)  # 最外層固定目錄在前、連線在後
    folder = target_uuid if target_kind == FOLDER else None
    members = [member for member in layout.groups[folder] if member != uuid]
    return Move(CONNECTION, uuid, folder, len(members))


def _resolve_folder_drop(layout, uuid, target_kind, target_uuid, position) -> Move | None:
    others = [folder for folder in layout.folders if folder != uuid]
    if target_kind == CONNECTION:
        # 放到連線上：視為放在該連線所屬目錄之後；最外層連線則放到所有目錄最後面
        target_uuid = layout.folder_of(target_uuid)
        position = BELOW
    if target_uuid is None:
        return Move(FOLDER, uuid, None, len(others))
    if target_uuid == uuid:
        return None
    return Move(FOLDER, uuid, None, others.index(target_uuid) + (0 if position == ABOVE else 1))
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_connection_list.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息：
```
新增拖放目標計算 resolve_drop

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```
```bash
git add src/ui/connection_list.py tests/test_connection_list.py
git commit -F .git/COMMIT_MSG_TMP
rm .git/COMMIT_MSG_TMP
```

---

### Task 3: 連線清單改為樹狀元件

**Files:**
- Modify: `src/ui/connection_list.py`（整檔改寫，保留 Task 2 的程式碼）
- Modify: `src/ui/theme.py:135-138`
- Modify: `src/ui/main_window.py`（改用 `set_tree`，F2 改呼叫 `request_delete_current`）
- Test: `tests/test_connection_list.py`、`tests/test_main_window.py`

**Interfaces:**
- Consumes: Task 1 的 `Folder`、`Connection.folder`、`ConnectionStore.folders()`；Task 2 的 `TreeLayout`、`resolve_drop`、常數
- Produces（`ConnectionList`）：
  - 屬性：`search_edit`、`tree`（`QTreeWidget` 子類別，取代 `list_view`）、`add_button`、`add_folder_button`
  - `FOLDER_UNNAMED = "未命名目錄"`
  - `set_tree(folders: list[Folder], connections: list[Connection], select_uuid: str | None = None)`：取代 `set_connections`；選取順序為 `select_uuid` → 重建前的目前項目 → 第一筆連線（取第一個仍存在者）
  - `select(uuid)`：可選連線或目錄；目標在收合的目錄內時先展開該目錄
  - `current_uuid() -> str | None`：只回傳連線
  - `current_folder() -> str | None`
  - `edit_folder(uuid)`、`request_delete_current()`
  - `update_connection`、`item_widget`、`visible_uuids`、`clear_search`、`set_busy`：語意不變
  - 訊號：`selectionChanged(str)`、`addRequested()`、`addFolderRequested()`、`deleteRequested(str)`、`deleteFolderRequested(str)`、`folderRenamed(str, str)`、`folderExpandedChanged(str, bool)`、`connectionMoved(str, object, int)`、`folderMoved(str, int)`
  - `tree.itemDropped(object, object, str)`：拖曳項目、放下處項目（None 為空白處）、`ABOVE`／`BELOW`／`ON`
- Produces（`MainWindow`）：`_refresh_tree(select_uuid: str | None = None) -> None`

- [ ] **Step 1: 調整既有測試**

`tests/test_connection_list.py`：

1. import 區改成：
```python
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView

from src.core.connection_store import Connection, Folder
from src.ui.connection_list import (
    ABOVE, BELOW, CONNECTION, FOLDER, FOLDER_UNNAMED, NO_URL, ON, UNNAMED, ConnectionList, Move, TreeLayout,
    resolve_drop,
)
```
2. `make_list` 內的 `widget.set_connections(CONNECTIONS, select_uuid=select)` 改成 `widget.set_tree([], CONNECTIONS, select_uuid=select)`。
3. `test_delete_key_requests_delete_of_current` 的 `widget.list_view` 改成 `widget.tree`。
4. `test_set_busy_disables_interaction` 改成：
```python
def test_set_busy_disables_interaction(qapp):
    widget, _ = make_list()
    widget.set_busy(True)
    assert not widget.tree.isEnabled()
    assert not widget.add_button.isEnabled() and not widget.add_folder_button.isEnabled()
    widget.set_busy(False)
    assert widget.tree.isEnabled()
    assert widget.add_button.isEnabled() and widget.add_folder_button.isEnabled()
```
5. `test_set_connections_empty` 改成：
```python
def test_set_tree_empty(qapp):
    widget, _ = make_list()
    widget.set_tree([], [])
    assert widget.current_uuid() is None
    assert widget.visible_uuids() == []
```

`tests/test_main_window.py` 的 `test_busy_state_disables_other_actions`：兩處 `window.connection_list.list_view` 改成 `window.connection_list.tree`。

- [ ] **Step 2: 寫樹狀行為的失敗測試**

附加到 `tests/test_connection_list.py`（放在 `resolve_drop` 測試之前或之後皆可）：

```python
FOLDERS = [Folder("f1", "TIPTOP", True), Folder("f2", "", False)]
TREE = [
    Connection("u1", "正式區", "http://prod/ws?WSDL", [], "f1"),
    Connection("u2", "測試區", "http://test/ws?WSDL", []),
    Connection("u4", "報表", "http://report/ws?WSDL", [], "f2"),
    Connection("u5", "備援", "http://backup/ws?WSDL", [], "f1"),
]


def make_tree(select=None):
    widget = ConnectionList()
    received = []
    widget.selectionChanged.connect(received.append)
    widget.set_tree(FOLDERS, TREE, select_uuid=select)
    return widget, received


def top_level(widget):
    return [widget.tree.topLevelItem(i) for i in range(widget.tree.topLevelItemCount())]


def uuid_of(item):
    return item.data(0, Qt.ItemDataRole.UserRole)


def child_uuids(item):
    return [uuid_of(item.child(i)) for i in range(item.childCount())]


def folder_item(widget, folder_uuid):
    return next(item for item in top_level(widget) if uuid_of(item) == folder_uuid)


def record(signal):
    calls = []
    signal.connect(lambda *args: calls.append(args))
    return calls


def test_tree_places_folders_first_and_connections_inside(qapp):
    widget, received = make_tree()
    items = top_level(widget)
    assert [uuid_of(item) for item in items] == ["f1", "f2", "u2"]
    assert child_uuids(items[0]) == ["u1", "u5"]
    assert child_uuids(items[1]) == ["u4"]
    assert (items[0].text(0), items[1].text(0)) == ("TIPTOP", FOLDER_UNNAMED)
    assert items[0].isExpanded() and not items[1].isExpanded()
    assert widget.current_uuid() == "u1"
    assert received == ["u1"]


def test_selecting_folder_emits_blank_and_reports_current_folder(qapp):
    widget, received = make_tree()
    widget.select("f1")
    assert received[-1] == ""
    assert widget.current_uuid() is None
    assert widget.current_folder() == "f1"
    widget.select("u5")
    assert widget.current_folder() == "f1"
    widget.select("u2")
    assert widget.current_folder() is None


def test_selecting_connection_in_collapsed_folder_expands_it(qapp):
    widget, _ = make_tree()
    changes = record(widget.folderExpandedChanged)
    widget.select("u4")
    assert folder_item(widget, "f2").isExpanded()
    assert changes == [("f2", True)]


def test_set_tree_keeps_current_selection(qapp):
    widget, _ = make_tree("u2")
    widget.set_tree(FOLDERS, TREE)
    assert widget.current_uuid() == "u2"
    widget.select("f1")
    widget.set_tree(FOLDERS, TREE)
    assert widget.current_folder() == "f1" and widget.current_uuid() is None


def test_clicking_folder_toggles_and_reports(qapp):
    widget, _ = make_tree()
    changes = record(widget.folderExpandedChanged)
    item = folder_item(widget, "f1")
    widget.tree.itemClicked.emit(item, 0)
    assert not item.isExpanded()
    widget.tree.itemClicked.emit(item, 0)
    assert item.isExpanded()
    assert changes == [("f1", False), ("f1", True)]


def test_rename_folder_emits_trimmed_name(qapp):
    widget, _ = make_tree()
    renamed = record(widget.folderRenamed)
    item = folder_item(widget, "f1")
    item.setText(0, "  ERP  ")
    assert item.text(0) == "ERP"
    assert renamed == [("f1", "ERP")]


def test_blank_rename_restores_previous_name(qapp):
    widget, _ = make_tree()
    renamed = record(widget.folderRenamed)
    folder_item(widget, "f1").setText(0, "   ")
    folder_item(widget, "f2").setText(0, "")
    assert folder_item(widget, "f1").text(0) == "TIPTOP"
    assert folder_item(widget, "f2").text(0) == FOLDER_UNNAMED
    assert renamed == []


def test_edit_folder_starts_inline_editing(qapp):
    widget, _ = make_tree()
    widget.edit_folder("f2")
    assert widget.current_folder() == "f2"
    assert widget.tree.state() == QAbstractItemView.State.EditingState


def test_filter_shows_matching_connection_under_its_folder(qapp):
    widget, _ = make_tree()
    changes = record(widget.folderExpandedChanged)
    widget.search_edit.setText("REPORT")
    assert widget.visible_uuids() == ["u4"]
    assert folder_item(widget, "f1").isHidden()
    assert not folder_item(widget, "f2").isHidden()
    assert folder_item(widget, "f2").isExpanded()
    widget.search_edit.setText("")
    assert widget.visible_uuids() == ["u1", "u5", "u4", "u2"]
    assert not folder_item(widget, "f2").isExpanded()
    assert changes == []


def test_filter_by_folder_name_shows_all_its_connections(qapp):
    widget, _ = make_tree()
    widget.search_edit.setText("tiptop")
    assert widget.visible_uuids() == ["u1", "u5"]


def test_search_disables_drag(qapp):
    widget, _ = make_tree()
    assert widget.tree.dragEnabled()
    widget.search_edit.setText("prod")
    assert not widget.tree.dragEnabled()
    widget.clear_search()
    assert widget.tree.dragEnabled()


def test_delete_key_on_folder_requests_folder_delete(qapp):
    widget, _ = make_tree()
    widget.select("f2")
    folders, connections = [], []
    widget.deleteFolderRequested.connect(folders.append)
    widget.deleteRequested.connect(connections.append)
    QTest.keyClick(widget.tree, Qt.Key.Key_Delete)
    assert folders == ["f2"] and connections == []


def test_add_folder_button_emits(qapp):
    widget, _ = make_tree()
    requested = []
    widget.addFolderRequested.connect(lambda: requested.append(True))
    widget.add_folder_button.click()
    assert requested == [True]


def test_drop_emits_move_signals(qapp):
    widget, _ = make_tree()
    moved_connections = record(widget.connectionMoved)
    moved_folders = record(widget.folderMoved)
    items = top_level(widget)
    widget.tree.itemDropped.emit(items[2], items[0], ON)  # u2 放到 TIPTOP 上
    widget.tree.itemDropped.emit(items[1], items[0], ABOVE)  # 未命名目錄移到 TIPTOP 前
    widget.tree.itemDropped.emit(items[2], items[2], ABOVE)  # 放回自己身上
    assert moved_connections == [("u2", "f1", 2)]
    assert moved_folders == [("f2", 0)]
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `uv run pytest tests/test_connection_list.py -q`
Expected: FAIL，`ImportError: cannot import name 'FOLDER_UNNAMED'`

- [ ] **Step 4: 改寫 `src/ui/connection_list.py`**

整檔改成（Task 2 的 `TreeLayout`／`Move`／`resolve_drop` 原樣保留）：

```python
# -*- coding: utf-8 -*-
"""
左側連線清單：目錄分組、搜尋、選取、新增、刪除、拖曳排序
"""
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.connection_store import Connection, Folder

UNNAMED = "未命名"
FOLDER_UNNAMED = "未命名目錄"
NO_URL = "尚未設定網址"
_UUID_ROLE = Qt.ItemDataRole.UserRole
_KIND_ROLE = Qt.ItemDataRole.UserRole + 1

FOLDER = "folder"
CONNECTION = "connection"
ABOVE = "above"
BELOW = "below"
ON = "on"


@dataclass
class TreeLayout:
    """清單目前的結構：目錄順序，以及各群組（目錄 uuid，None 為最外層）內的連線順序"""
    folders: list[str]
    groups: dict[str | None, list[str]]

    def folder_of(self, conn_uuid: str) -> str | None:
        for folder, members in self.groups.items():
            if conn_uuid in members:
                return folder
        raise KeyError(conn_uuid)


@dataclass(frozen=True)
class Move:
    kind: str  # FOLDER 或 CONNECTION
    uuid: str
    folder: str | None  # 連線的目標目錄；目錄移動時為 None
    index: int  # 移除自己之後，在目標群組中的位置


def resolve_drop(layout: TreeLayout, kind: str, uuid: str, target_kind: str | None,
                 target_uuid: str | None, position: str) -> Move | None:
    """計算拖放結果；target 為 None 表示放在空白處，放到自己身上時回傳 None"""
    if kind == FOLDER:
        return _resolve_folder_drop(layout, uuid, target_kind, target_uuid, position)
    return _resolve_connection_drop(layout, uuid, target_kind, target_uuid, position)


def _resolve_connection_drop(layout, uuid, target_kind, target_uuid, position) -> Move | None:
    if target_uuid == uuid:
        return None
    if target_kind == CONNECTION:
        folder = layout.folder_of(target_uuid)
        members = [member for member in layout.groups[folder] if member != uuid]
        return Move(CONNECTION, uuid, folder, members.index(target_uuid) + (0 if position == ABOVE else 1))
    if target_kind == FOLDER and position != ON:
        return Move(CONNECTION, uuid, None, 0)  # 最外層固定目錄在前、連線在後
    folder = target_uuid if target_kind == FOLDER else None
    members = [member for member in layout.groups[folder] if member != uuid]
    return Move(CONNECTION, uuid, folder, len(members))


def _resolve_folder_drop(layout, uuid, target_kind, target_uuid, position) -> Move | None:
    others = [folder for folder in layout.folders if folder != uuid]
    if target_kind == CONNECTION:
        # 放到連線上：視為放在該連線所屬目錄之後；最外層連線則放到所有目錄最後面
        target_uuid = layout.folder_of(target_uuid)
        position = BELOW
    if target_uuid is None:
        return Move(FOLDER, uuid, None, len(others))
    if target_uuid == uuid:
        return None
    return Move(FOLDER, uuid, None, others.index(target_uuid) + (0 if position == ABOVE else 1))


def _uuid_of(item: QTreeWidgetItem | None) -> str | None:
    return item.data(0, _UUID_ROLE) if item is not None else None


def _kind_of(item: QTreeWidgetItem | None) -> str | None:
    return item.data(0, _KIND_ROLE) if item is not None else None


class ElidedLabel(QLabel):
    """單行標籤，文字過長時以 … 省略"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.contentsRect()
        elided = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, rect.width())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)


class ConnectionItemWidget(QWidget):
    def __init__(self, conn: Connection, parent=None):
        super().__init__(parent)
        self.title = ElidedLabel()
        self.title.setObjectName("ItemTitle")
        self.subtitle = ElidedLabel()
        self.subtitle.setObjectName("ItemSubtitle")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(2)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        self.set_connection(conn)

    def set_connection(self, conn: Connection) -> None:
        self.title.setText(conn.name or UNNAMED)
        self.subtitle.setText(conn.url or NO_URL)
        self.setToolTip(conn.url)


_DROP_POSITIONS = {
    QAbstractItemView.DropIndicatorPosition.AboveItem: ABOVE,
    QAbstractItemView.DropIndicatorPosition.BelowItem: BELOW,
    QAbstractItemView.DropIndicatorPosition.OnItem: ON,
}


class _TreeView(QTreeWidget):
    deletePressed = Signal()
    itemDropped = Signal(object, object, str)  # 拖曳的項目、放下處的項目（None 為空白處）、ABOVE/BELOW/ON

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.deletePressed.emit()
            return
        super().keyPressEvent(event)

    def dropEvent(self, event):
        indicator = self.dropIndicatorPosition()
        target = self.itemAt(event.position().toPoint()) if indicator in _DROP_POSITIONS else None
        # 不交給 Qt 搬移：忽略事件讓拖曳結果為 IgnoreAction，Qt 也就不會刪除來源項目；
        # 實際移動由主視窗更新 store 後重建整棵樹
        event.ignore()
        self.viewport().update()
        self.itemDropped.emit(self.currentItem(), target, _DROP_POSITIONS.get(indicator, ON))


class ConnectionList(QWidget):
    selectionChanged = Signal(str)
    addRequested = Signal()
    addFolderRequested = Signal()
    deleteRequested = Signal(str)
    deleteFolderRequested = Signal(str)
    folderRenamed = Signal(str, str)
    folderExpandedChanged = Signal(str, bool)
    connectionMoved = Signal(str, object, int)
    folderMoved = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder_names: dict[str, str] = {}
        self._folder_expanded: dict[str, bool] = {}

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜尋連線")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)

        self.tree = _TreeView()
        self.tree.setObjectName("ConnectionList")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.currentItemChanged.connect(self._on_current_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemExpanded.connect(lambda item: self._on_expansion_changed(item, True))
        self.tree.itemCollapsed.connect(lambda item: self._on_expansion_changed(item, False))
        self.tree.deletePressed.connect(self.request_delete_current)
        self.tree.itemDropped.connect(self._on_item_dropped)

        self.add_button = QPushButton("+ 新增連線")
        self.add_button.setToolTip("新增連線 (F1)")
        self.add_button.clicked.connect(lambda: self.addRequested.emit())
        self.add_folder_button = QPushButton("+ 新增目錄")
        self.add_folder_button.clicked.connect(lambda: self.addFolderRequested.emit())
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.add_folder_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.tree, 1)
        layout.addLayout(buttons)

    # ---------- 對外介面 ----------

    def set_tree(self, folders: list[Folder], connections: list[Connection], select_uuid: str | None = None) -> None:
        """依 store 資料重建整棵樹；選取 select_uuid，其次是重建前的目前項目，再其次是第一筆連線"""
        previous = _uuid_of(self.tree.currentItem())
        self._folder_names = {folder.uuid: folder.name for folder in folders}
        self._folder_expanded = {folder.uuid: folder.expanded for folder in folders}
        self.tree.blockSignals(True)
        self.tree.clear()
        parents = {folder.uuid: self._add_folder_item(folder) for folder in folders}
        for conn in connections:
            self._add_connection_item(parents.get(conn.folder, self.tree.invisibleRootItem()), conn)
        for folder in folders:
            parents[folder.uuid].setExpanded(folder.expanded)
        self.tree.blockSignals(False)
        self._apply_filter(self.search_edit.text())
        first = connections[0].uuid if connections else None
        target = next((uuid for uuid in (select_uuid, previous, first) if uuid and self._item_for(uuid)), None)
        if target:
            self.select(target)

    def update_connection(self, conn: Connection) -> None:
        item = self._item_for(conn.uuid)
        if item is None:
            return
        self.tree.itemWidget(item, 0).set_connection(conn)
        self._apply_filter(self.search_edit.text())

    def select(self, uuid: str) -> None:
        item = self._item_for(uuid)
        if item is None:
            return
        parent = item.parent()
        if parent is not None and not parent.isExpanded():
            parent.setExpanded(True)
        self.tree.setCurrentItem(item)

    def current_uuid(self) -> str | None:
        item = self.tree.currentItem()
        return _uuid_of(item) if _kind_of(item) == CONNECTION else None

    def current_folder(self) -> str | None:
        """選到目錄時回傳該目錄；選到連線時回傳其所屬目錄（最外層為 None）"""
        item = self.tree.currentItem()
        if _kind_of(item) == FOLDER:
            return _uuid_of(item)
        return _uuid_of(item.parent()) if item is not None else None

    def edit_folder(self, uuid: str) -> None:
        item = self._item_for(uuid)
        if _kind_of(item) != FOLDER:
            return
        self.tree.setCurrentItem(item)
        self.tree.editItem(item, 0)

    def request_delete_current(self) -> None:
        item = self.tree.currentItem()
        if _kind_of(item) == FOLDER:
            self.deleteFolderRequested.emit(_uuid_of(item))
        elif _kind_of(item) == CONNECTION:
            self.deleteRequested.emit(_uuid_of(item))

    def item_widget(self, uuid: str) -> ConnectionItemWidget | None:
        item = self._item_for(uuid)
        return self.tree.itemWidget(item, 0) if _kind_of(item) == CONNECTION else None

    def visible_uuids(self) -> list[str]:
        """未被搜尋篩選掉的連線（依畫面順序，不含目錄）"""
        return [
            _uuid_of(item)
            for item in self._iter_items()
            if _kind_of(item) == CONNECTION
            and not item.isHidden()
            and not (item.parent() is not None and item.parent().isHidden())
        ]

    def clear_search(self) -> None:
        self.search_edit.clear()

    def set_busy(self, busy: bool) -> None:
        for widget in (self.tree, self.add_button, self.add_folder_button):
            widget.setEnabled(not busy)

    # ---------- 建立項目 ----------

    def _add_folder_item(self, folder: Folder) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self.tree)
        item.setData(0, _UUID_ROLE, folder.uuid)
        item.setData(0, _KIND_ROLE, FOLDER)
        item.setText(0, folder.name or FOLDER_UNNAMED)
        item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        return item

    def _add_connection_item(self, parent: QTreeWidgetItem, conn: Connection) -> None:
        item = QTreeWidgetItem(parent)
        item.setData(0, _UUID_ROLE, conn.uuid)
        item.setData(0, _KIND_ROLE, CONNECTION)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)  # 連線不能當作放入目標
        widget = ConnectionItemWidget(conn)
        item.setSizeHint(0, QSize(0, widget.sizeHint().height()))
        self.tree.setItemWidget(item, 0, widget)

    # ---------- 查詢 ----------

    def _iter_items(self):
        root = self.tree.invisibleRootItem()
        for row in range(root.childCount()):
            top = root.child(row)
            yield top
            for child_row in range(top.childCount()):
                yield top.child(child_row)

    def _item_for(self, uuid: str) -> QTreeWidgetItem | None:
        return next((item for item in self._iter_items() if _uuid_of(item) == uuid), None)

    def _layout(self) -> TreeLayout:
        folders, groups = [], {None: []}
        root = self.tree.invisibleRootItem()
        for row in range(root.childCount()):
            item = root.child(row)
            if _kind_of(item) == FOLDER:
                folders.append(_uuid_of(item))
                groups[_uuid_of(item)] = [_uuid_of(item.child(i)) for i in range(item.childCount())]
            else:
                groups[None].append(_uuid_of(item))
        return TreeLayout(folders, groups)

    def _searching(self) -> bool:
        return bool(self.search_edit.text().strip())

    def _matches(self, item: QTreeWidgetItem, keyword: str) -> bool:
        widget = self.tree.itemWidget(item, 0)
        return keyword in f"{widget.title.text()}\n{widget.subtitle.text()}".lower()

    # ---------- 搜尋 ----------

    def _apply_filter(self, text: str) -> None:
        keyword = text.strip().lower()
        self.tree.setDragEnabled(not keyword)  # 篩選後的畫面位置與實際順序不對應
        self.tree.blockSignals(True)  # 搜尋造成的展開／收合不算使用者操作
        root = self.tree.invisibleRootItem()
        for row in range(root.childCount()):
            item = root.child(row)
            if _kind_of(item) == FOLDER:
                self._filter_folder(item, keyword)
            else:
                item.setHidden(bool(keyword) and not self._matches(item, keyword))
        self.tree.blockSignals(False)

    def _filter_folder(self, item: QTreeWidgetItem, keyword: str) -> None:
        if not keyword:
            item.setHidden(False)
            for row in range(item.childCount()):
                item.child(row).setHidden(False)
            item.setExpanded(self._folder_expanded.get(_uuid_of(item), True))
            return
        folder_hit = keyword in item.text(0).lower()
        any_visible = False
        for row in range(item.childCount()):
            child = item.child(row)
            visible = folder_hit or self._matches(child, keyword)
            child.setHidden(not visible)
            any_visible = any_visible or visible
        item.setHidden(not (folder_hit or any_visible))
        item.setExpanded(True)

    # ---------- 事件 ----------

    def _on_current_changed(self, current, _previous) -> None:
        self.selectionChanged.emit(_uuid_of(current) if _kind_of(current) == CONNECTION else "")

    def _on_item_clicked(self, item, _column) -> None:
        if _kind_of(item) == FOLDER:
            item.setExpanded(not item.isExpanded())

    def _on_expansion_changed(self, item, expanded: bool) -> None:
        uuid = _uuid_of(item)
        if _kind_of(item) != FOLDER or self._searching() or self._folder_expanded.get(uuid) == expanded:
            return
        self._folder_expanded[uuid] = expanded
        self.folderExpandedChanged.emit(uuid, expanded)

    def _on_item_changed(self, item, _column) -> None:
        """清單內改名完成：去除前後空白，空白名稱還原為原名"""
        if _kind_of(item) != FOLDER:
            return
        uuid = _uuid_of(item)
        display = self._folder_names.get(uuid) or FOLDER_UNNAMED
        name = item.text(0).strip()
        if not name or name == display:
            self._set_folder_text(item, display)
            return
        self._set_folder_text(item, name)
        self._folder_names[uuid] = name
        self.folderRenamed.emit(uuid, name)
        self._apply_filter(self.search_edit.text())

    def _set_folder_text(self, item: QTreeWidgetItem, text: str) -> None:
        if item.text(0) != text:
            self.tree.blockSignals(True)
            item.setText(0, text)
            self.tree.blockSignals(False)

    def _on_item_dropped(self, dragged, target, position: str) -> None:
        if dragged is None:
            return
        move = resolve_drop(
            self._layout(), _kind_of(dragged), _uuid_of(dragged), _kind_of(target), _uuid_of(target), position
        )
        if move is None:
            return
        if move.kind == FOLDER:
            self.folderMoved.emit(move.uuid, move.index)
        else:
            self.connectionMoved.emit(move.uuid, move.folder, move.index)

    def _show_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if _kind_of(item) != CONNECTION:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("刪除")
        if menu.exec(self.tree.viewport().mapToGlobal(pos)) is delete_action:
            self.deleteRequested.emit(_uuid_of(item))
```

- [ ] **Step 5: 更新 QSS**

`src/ui/theme.py` 第 135-138 行（四行 `QListWidget#ConnectionList ...`）改成：

```
QTreeWidget#ConnectionList { background: transparent; border: none; outline: 0; }
QTreeWidget#ConnectionList::item { border-radius: 6px; margin: 1px 0; padding: 4px 0; border-left: 3px solid transparent; }
QTreeWidget#ConnectionList::item:hover { background: $surface_hover; }
QTreeWidget#ConnectionList::item:selected { background: $surface_hover; color: $text; border-left: 3px solid $accent; }
QTreeWidget#ConnectionList::branch { background: transparent; }
```

- [ ] **Step 6: 主視窗改用 `set_tree`**

`src/ui/main_window.py`：

1. `_build_shortcuts` 的 `("F2", self._on_delete_current),` 改成：
```python
            ("F2", self.connection_list.request_delete_current),
```
2. 刪除整個 `_on_delete_current` 方法。
3. 在 `_load_initial_connections` 之前新增：
```python
    def _refresh_tree(self, select_uuid: str | None = None) -> None:
        """store 結構變動後重建左側清單；未指定 select_uuid 時保留目前選取"""
        self.connection_list.set_tree(self._store.folders(), self._store.all(), select_uuid)
```
4. `_load_initial_connections` 的 `self.connection_list.set_connections(self._store.all())` 改成 `self._refresh_tree()`。
5. `_on_add_requested` 的 `self.connection_list.set_connections(self._store.all(), select_uuid=conn.uuid)` 改成 `self._refresh_tree(conn.uuid)`。
6. `_on_delete_requested` 的 `self.connection_list.set_connections(self._store.all(), select_uuid=keep)` 改成 `self._refresh_tree(keep)`。

- [ ] **Step 7: 執行測試確認通過**

Run: `uv run pytest -q`
Expected: 全部 PASS

- [ ] **Step 8: Commit**

訊息：
```
左側連線清單改為樹狀：目錄顯示、改名、展開記憶、搜尋與拖放

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```
```bash
git add src/ui/connection_list.py src/ui/theme.py src/ui/main_window.py tests/test_connection_list.py tests/test_main_window.py
git commit -F .git/COMMIT_MSG_TMP
rm .git/COMMIT_MSG_TMP
```

---

### Task 4: 右鍵選單

**Files:**
- Modify: `src/ui/connection_list.py`（`_show_context_menu` 改寫，新增 `_context_menu`、`_fill_connection_menu`、`_add_into`）
- Test: `tests/test_connection_list.py`

**Interfaces:**
- Consumes: Task 3 的 `ConnectionList`、`_layout()`、`_folder_names`、`select()`、`edit_folder()`、各訊號
- Produces:
  - 常數 `ROOT_LABEL = "最外層"`
  - `ConnectionList._context_menu(item: QTreeWidgetItem | None) -> QMenu`（測試用；`None` 表示空白處）
  - 「新增連線到此目錄」／空白處「新增連線」：先把目前選取設為目標（目錄或無選取），再送 `addRequested`，主視窗以 `current_folder()` 決定位置

- [ ] **Step 1: 寫失敗測試**

附加到 `tests/test_connection_list.py`：

```python
def actions_by_text(menu):
    return {action.text(): action for action in menu.actions() if action.text()}


def test_connection_menu_moves_into_folder(qapp):
    widget, _ = make_tree()
    moved = record(widget.connectionMoved)
    actions = actions_by_text(widget._context_menu(top_level(widget)[2]))  # u2 在最外層
    assert list(actions) == ["移動到", "刪除"]
    targets = actions_by_text(actions["移動到"].menu())
    assert list(targets) == ["最外層", "TIPTOP", FOLDER_UNNAMED]
    assert not targets["最外層"].isEnabled()
    targets["TIPTOP"].trigger()
    assert moved == [("u2", "f1", 2)]


def test_connection_menu_moves_to_root_and_deletes(qapp):
    widget, _ = make_tree()
    moved = record(widget.connectionMoved)
    deleted = []
    widget.deleteRequested.connect(deleted.append)
    actions = actions_by_text(widget._context_menu(folder_item(widget, "f1").child(0)))  # u1
    targets = actions_by_text(actions["移動到"].menu())
    assert not targets["TIPTOP"].isEnabled()
    targets["最外層"].trigger()
    actions["刪除"].trigger()
    assert moved == [("u1", None, 1)]
    assert deleted == ["u1"]


def test_folder_menu_actions(qapp):
    widget, _ = make_tree("u2")
    added, deleted = [], []
    widget.addRequested.connect(lambda: added.append(widget.current_folder()))
    widget.deleteFolderRequested.connect(deleted.append)
    actions = actions_by_text(widget._context_menu(folder_item(widget, "f2")))
    assert list(actions) == ["新增連線到此目錄", "重新命名", "刪除目錄"]
    actions["新增連線到此目錄"].trigger()
    assert added == ["f2"]
    actions["重新命名"].trigger()
    assert widget.tree.state() == QAbstractItemView.State.EditingState
    actions["刪除目錄"].trigger()
    assert deleted == ["f2"]


def test_blank_area_menu_actions(qapp):
    widget, _ = make_tree("u1")
    added, folders = [], []
    widget.addRequested.connect(lambda: added.append((widget.current_uuid(), widget.current_folder())))
    widget.addFolderRequested.connect(lambda: folders.append(True))
    actions = actions_by_text(widget._context_menu(None))
    assert list(actions) == ["新增連線", "新增目錄"]
    actions["新增連線"].trigger()
    actions["新增目錄"].trigger()
    assert added == [(None, None)]
    assert folders == [True]
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_connection_list.py -q -k menu`
Expected: FAIL，`AttributeError: 'ConnectionList' object has no attribute '_context_menu'`

- [ ] **Step 3: 實作**

`src/ui/connection_list.py`：

1. `from PySide6.QtCore import QSize, Qt, Signal` 改成 `from PySide6.QtCore import QModelIndex, QSize, Qt, Signal`。
2. `NO_URL = "尚未設定網址"` 下一行加入 `ROOT_LABEL = "最外層"`。
3. 整個 `_show_context_menu` 方法改成：

```python
    def _show_context_menu(self, pos) -> None:
        menu = self._context_menu(self.tree.itemAt(pos))
        menu.exec(self.tree.viewport().mapToGlobal(pos))
        menu.deleteLater()

    def _context_menu(self, item: QTreeWidgetItem | None) -> QMenu:
        menu = QMenu(self)
        uuid = _uuid_of(item)
        if _kind_of(item) == CONNECTION:
            self._fill_connection_menu(menu, uuid, _uuid_of(item.parent()))
        elif _kind_of(item) == FOLDER:
            menu.addAction("新增連線到此目錄").triggered.connect(lambda: self._add_into(uuid))
            menu.addAction("重新命名").triggered.connect(lambda: self.edit_folder(uuid))
            menu.addSeparator()
            menu.addAction("刪除目錄").triggered.connect(lambda: self.deleteFolderRequested.emit(uuid))
        else:
            menu.addAction("新增連線").triggered.connect(lambda: self._add_into(None))
            menu.addAction("新增目錄").triggered.connect(lambda: self.addFolderRequested.emit())
        return menu

    def _fill_connection_menu(self, menu: QMenu, uuid: str, here: str | None) -> None:
        layout = self._layout()
        move_menu = menu.addMenu("移動到")
        targets = [(None, ROOT_LABEL)] + [
            (folder, self._folder_names.get(folder) or FOLDER_UNNAMED) for folder in layout.folders
        ]
        for folder, label in targets:
            action = move_menu.addAction(label)
            action.setEnabled(folder != here)
            action.triggered.connect(
                lambda _checked=False, target=folder: self.connectionMoved.emit(uuid, target, len(layout.groups[target]))
            )
        menu.addSeparator()
        menu.addAction("刪除").triggered.connect(lambda: self.deleteRequested.emit(uuid))

    def _add_into(self, folder: str | None) -> None:
        """先選取目標目錄（None 為取消選取，即最外層）再要求新增，主視窗依 current_folder() 決定位置"""
        if folder is None:
            self.tree.setCurrentIndex(QModelIndex())
        else:
            self.select(folder)
        self.addRequested.emit()
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_connection_list.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息：
```
連線清單右鍵選單：移動到目錄、新增、重新命名、刪除目錄

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```
```bash
git add src/ui/connection_list.py tests/test_connection_list.py
git commit -F .git/COMMIT_MSG_TMP
rm .git/COMMIT_MSG_TMP
```

---

### Task 5: 主視窗串接目錄操作

**Files:**
- Modify: `src/ui/main_window.py`
- Modify: `README.md`（「介面」段落）
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: Task 1 的 store 方法；Task 3/4 的 `ConnectionList` 訊號、`current_folder()`、`edit_folder()`、`clear_search()`、`FOLDER_UNNAMED`；Task 3 的 `_refresh_tree()`
- Produces: `NEW_FOLDER_NAME = "新目錄"`；主視窗處理 `addFolderRequested`、`deleteFolderRequested`、`folderRenamed`、`folderExpandedChanged`、`connectionMoved`、`folderMoved`

- [ ] **Step 1: 寫失敗測試**

`tests/test_main_window.py`：

1. import 區加入：
```python
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView
```
（原本的 `from PySide6.QtGui import QGuiApplication` 併入上面這行）

2. 在 `combo_items` 之後加入：
```python
def press_shortcut(window, key):
    shortcut = next(sc for sc in window.findChildren(QShortcut) if sc.key() == QKeySequence(key))
    shortcut.activated.emit()
```

3. `test_busy_state_disables_other_actions` 在 `assert not window.connection_list.tree.isEnabled()` 之後加一行：
```python
    assert not window.connection_list.add_folder_button.isEnabled()
```

4. 附加到檔尾：
```python
def test_add_inside_selected_folder(env):
    seed(env.store)
    folder = env.store.add_folder("TIPTOP").uuid
    window = env.make()
    window.connection_list.select(folder)
    window.connection_list.add_button.click()
    new_uuid = window.connection_list.current_uuid()
    assert env.store.get(new_uuid).folder == folder
    assert window.connection_list.current_folder() == folder


def test_add_folder_starts_rename_and_saves_name(env):
    seed(env.store)
    window = env.make()
    window.connection_list.add_folder_button.click()
    folders = env.store.folders()
    assert [folder.name for folder in folders] == ["新目錄"]
    assert window.connection_list.current_folder() == folders[0].uuid
    assert window.connection_list.tree.state() == QAbstractItemView.State.EditingState
    window.connection_list.tree.currentItem().setText(0, "TIPTOP")
    assert ConnectionStore(env.store.path).get_folder(folders[0].uuid).name == "TIPTOP"


def test_delete_folder_moves_connections_to_root(env):
    conn = seed(env.store, "A")
    folder = env.store.add_folder("TIPTOP").uuid
    env.store.move_connection(conn, folder, 0)
    window = env.make()
    asked = []
    window._confirm = lambda title, text: asked.append(text) or True
    window.connection_list.deleteFolderRequested.emit(folder)
    reloaded = ConnectionStore(env.store.path)
    assert reloaded.folders() == []
    assert reloaded.get(conn).folder is None
    assert asked == ["確定要刪除目錄「TIPTOP」嗎？裡面的 1 筆連線會移到最外層。"]
    assert window.connection_list.current_uuid() == conn
    assert window.notification.text == "已刪除目錄"


def test_delete_empty_folder_asks_short_question(env):
    seed(env.store)
    folder = env.store.add_folder("空的").uuid
    window = env.make()
    asked = []
    window._confirm = lambda title, text: asked.append(text) or False
    window.connection_list.deleteFolderRequested.emit(folder)
    assert asked == ["確定要刪除目錄「空的」嗎？"]
    assert env.store.get_folder(folder) is not None


def test_f2_deletes_selected_folder(env):
    seed(env.store)
    folder = env.store.add_folder("TIPTOP").uuid
    window = env.make()
    window.connection_list.select(folder)
    press_shortcut(window, "F2")
    assert env.store.folders() == []


def test_f2_deletes_selected_connection(env):
    first = seed(env.store, "A")
    second = seed(env.store, "B")
    window = env.make()
    window.connection_list.select(second)
    press_shortcut(window, "F2")
    assert [conn.uuid for conn in env.store.all()] == [first]


def test_move_signals_persist_and_keep_unsaved_edits(env):
    a = seed(env.store, "A")
    b = seed(env.store, "B")
    f1 = env.store.add_folder("F1").uuid
    f2 = env.store.add_folder("F2").uuid
    window = env.make()
    window.connection_list.select(b)
    window.name_edit.setText("B2")  # 尚未觸發 editingFinished
    window.connection_list.connectionMoved.emit(a, f1, 0)
    window.connection_list.folderMoved.emit(f2, 0)
    reloaded = ConnectionStore(env.store.path)
    assert reloaded.get(a).folder == f1
    assert [folder.uuid for folder in reloaded.folders()] == [f2, f1]
    assert reloaded.get(b).name == "B2"
    assert window.connection_list.current_uuid() == b
    assert window.name_edit.text() == "B2"


def test_folder_expansion_persisted(env):
    seed(env.store)
    folder = env.store.add_folder("F").uuid
    window = env.make()
    window.connection_list.folderExpandedChanged.emit(folder, False)
    assert ConnectionStore(env.store.path).get_folder(folder).expanded is False
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_main_window.py -q`
Expected: FAIL（例如 `test_add_inside_selected_folder` 新連線的 folder 為 None、`test_add_folder_starts_rename_and_saves_name` 找不到目錄）

- [ ] **Step 3: 實作**

`src/ui/main_window.py`：

1. import 改成：
```python
from src.ui.connection_list import FOLDER_UNNAMED, UNNAMED, ConnectionList
```
2. `CANCEL_LABEL = "取消"` 下一行加入：
```python
NEW_FOLDER_NAME = "新目錄"
```
3. `_connect_signals` 在 `self.connection_list.deleteRequested.connect(self._on_delete_requested)` 之後加入：
```python
        self.connection_list.addFolderRequested.connect(self._on_add_folder_requested)
        self.connection_list.deleteFolderRequested.connect(self._on_delete_folder_requested)
        self.connection_list.folderRenamed.connect(self._on_folder_renamed)
        self.connection_list.folderExpandedChanged.connect(self._on_folder_expanded_changed)
        self.connection_list.connectionMoved.connect(self._on_connection_moved)
        self.connection_list.folderMoved.connect(self._on_folder_moved)
```
4. `_on_add_requested` 的 `conn = self._store.add()` 改成：
```python
        conn = self._store.add(self.connection_list.current_folder())
```
5. 在 `_on_delete_requested` 方法之後（`# ---------- 背景讀取與執行 ----------` 之前）加入：
```python
    # ---------- 目錄 ----------

    def _on_add_folder_requested(self) -> None:
        if self._pending:
            return
        self._commit_fields()
        self.connection_list.clear_search()  # 避免新目錄被搜尋篩選隱藏
        folder = self._store.add_folder(NEW_FOLDER_NAME)
        self._refresh_tree()
        self.connection_list.edit_folder(folder.uuid)

    @Slot(str, str)
    def _on_folder_renamed(self, uuid: str, name: str) -> None:
        self._store.rename_folder(uuid, name)

    @Slot(str, bool)
    def _on_folder_expanded_changed(self, uuid: str, expanded: bool) -> None:
        self._store.set_folder_expanded(uuid, expanded)

    @Slot(str)
    def _on_delete_folder_requested(self, uuid: str) -> None:
        if self._pending:
            return
        folder = self._store.get_folder(uuid)
        if folder is None:
            return
        count = sum(1 for conn in self._store.all() if conn.folder == uuid)
        text = f"確定要刪除目錄「{folder.name or FOLDER_UNNAMED}」嗎？"
        if count:
            text += f"裡面的 {count} 筆連線會移到最外層。"
        if not self._confirm("刪除目錄", text):
            return
        self._commit_fields()
        self._store.remove_folder(uuid)
        self._refresh_tree()
        self._notify("success", "已刪除目錄")

    @Slot(str, object, int)
    def _on_connection_moved(self, uuid: str, folder, index: int) -> None:
        if self._pending:
            return
        self._commit_fields()  # 重建清單會重新載入欄位，先保存尚未確認的編輯
        self._store.move_connection(uuid, folder, index)
        self._refresh_tree()

    @Slot(str, int)
    def _on_folder_moved(self, uuid: str, index: int) -> None:
        if self._pending:
            return
        self._commit_fields()
        self._store.move_folder(uuid, index)
        self._refresh_tree()
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest -q`
Expected: 全部 PASS

- [ ] **Step 5: 更新 README**

`README.md` 的「## 介面」段落，把前兩行與快捷鍵行改成：
```markdown
* 左側為連線清單（可搜尋、新增、刪除），可用目錄分組：拖曳或右鍵「移動到」把連線放進目錄、拖曳調整順序，右鍵「重新命名」修改目錄名稱
* 左下角「主題」可切換 跟隨系統 / 淺色 / 深色
* 快捷鍵：F1 新增連線、F2 刪除選取的連線或目錄、F3 讀取 WSDL、F5 執行、F6 清空、Ctrl+Shift+F 格式化請求、Esc 離開
```

- [ ] **Step 6: 手動驗證**

Run: `uv run python src/ws_tool.py`

確認：
1. 「+ 新增目錄」建立「新目錄」並直接進入改名，輸入名稱按 Enter 後保留
2. 把連線拖進目錄、拖出到最外層、在目錄內上下調整順序、拖曳目錄排序，重開程式後順序不變
3. 點目錄列展開／收合，重開程式後狀態不變
4. 右鍵連線「移動到 ▸」、右鍵目錄「新增連線到此目錄」「重新命名」「刪除目錄」
5. 刪除有連線的目錄，確認訊息顯示筆數，連線回到最外層
6. 搜尋時符合的目錄自動展開、無法拖曳；清除搜尋後展開狀態恢復
7. 拖放時原項目不會消失（確認 Qt 沒有自行刪除來源項目）

注意：手動測試會修改 `src/app_data/connections.profile`，完成後用 `git diff src/app_data/connections.profile` 檢查，不要把測試資料 commit 進去（必要時 `git checkout src/app_data/connections.profile` 還原前先確認內容）。

- [ ] **Step 7: Commit**

訊息：
```
主視窗串接目錄操作：新增、改名、刪除、移動與展開記憶

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```
```bash
git add src/ui/main_window.py tests/test_main_window.py README.md
git commit -F .git/COMMIT_MSG_TMP
rm .git/COMMIT_MSG_TMP
```
