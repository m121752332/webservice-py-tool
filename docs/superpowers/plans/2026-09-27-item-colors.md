# 專案目錄與連線顏色標記 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 左側專案目錄可用右鍵選單替目錄（資料夾圖示）與連線（名稱文字）標記 8 種顏色之一，存進 `connections.profile`，並隨淺色／深色主題換色。

**Architecture:** 核心層 `ConnectionStore` 只多存一個選填的顏色代號字串；色票（代號 → 淺色／深色色碼）集中在 `theme.py`；`icons.py` 提供資料夾圖示染色與選單色塊；`ConnectionList` 負責套色、右鍵「顏色」子選單並發出訊號；`MainWindow` 收到訊號後寫回 store 並更新單一項目。

**Tech Stack:** Python 3、PySide6（QPainter 合成模式、QActionGroup）、pytest（`QT_QPA_PLATFORM=offscreen`）

**Spec:** `docs/superpowers/specs/2026-09-27-item-colors-design.md`

## Global Constraints

- 註解、docstring、UI 文字、commit 訊息一律繁體中文；識別字用英文
- `src/core/connection_store.py` 不可依賴 PySide6
- 色碼一律集中在 `src/ui/theme.py`，元件不可寫死色碼
- `connections.profile`：未設色的項目**不寫** `color` 鍵；舊檔（無 `color`）可讀；`color` 不合法時視為預設色，**不**觸發損毀備份
- 8 色順序與色碼（淺色／深色）：紅 `#C81E1E`/`#FC8181`、橘 `#B23C0A`/`#FB923C`、黃 `#8A5A00`/`#FACC15`、綠 `#15703A`/`#4ADE80`、青 `#0D6C65`/`#2DD4BF`、藍 `#1D4ED8`/`#6AADFB`、紫 `#7E22CE`/`#C99CFD`、粉紅 `#BE185D`/`#F689C2`
- 顏色代號：`red`、`orange`、`yellow`、`green`、`teal`、`blue`、`purple`、`pink`
- 目錄只染資料夾圖示（名稱不變色）；連線只改名稱顏色（網址不變）；連線不繼承目錄顏色
- 測試指令：`.venv/Scripts/python -m pytest`；lint：`uv run ruff check src tests`
- commit 訊息含中文：先用 Write 工具寫入暫存檔，再 `git commit -F <檔案>`，結尾附 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 不可刪除或清空 `bin/`、`dist/`；不要 push

---

### Task 1: 資料層顏色欄位

**Files:**
- Modify: `src/core/connection_store.py`（`Folder`、`Connection`、`_parse_folders`、`_load`、`_save`，新增 `set_color`、`set_folder_color`）
- Test: `tests/test_connection_store.py`

**Interfaces:**
- Consumes: 無
- Produces:
  - `Folder.color: str | None = None`、`Connection.color: str | None = None`（皆為 dataclass 最後一個欄位）
  - `ConnectionStore.set_color(uuid: str, color: str | None) -> None`
  - `ConnectionStore.set_folder_color(uuid: str, color: str | None) -> None`
  - 兩者 uuid 不存在時丟 `KeyError`；傳入空字串視同 `None`

- [ ] **Step 1: Write the failing tests**

在 `tests/test_connection_store.py` 檔尾加入：

```python
def test_colors_default_to_none_and_are_not_written(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    folder = store.add_folder("F")
    conn = store.add(folder.uuid)
    assert store.get_folder(folder.uuid).color is None
    assert store.get(conn.uuid).color is None
    data = read_json(path)
    assert "color" not in data["folders"][0]  # 未設色不寫入，格式與舊版相同
    assert "color" not in data["connections"][0]


def test_set_colors_persist_reload_and_clear(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    folder = store.add_folder("F")
    conn = store.add(folder.uuid)
    store.set_folder_color(folder.uuid, "blue")
    store.set_color(conn.uuid, "red")
    data = read_json(path)
    assert data["folders"][0]["color"] == "blue"
    assert data["connections"][0]["color"] == "red"
    reloaded = ConnectionStore(path)
    assert reloaded.get_folder(folder.uuid).color == "blue"
    assert reloaded.get(conn.uuid).color == "red"

    store.set_folder_color(folder.uuid, None)
    store.set_color(conn.uuid, "")
    data = read_json(path)
    assert "color" not in data["folders"][0]
    assert "color" not in data["connections"][0]


@pytest.mark.parametrize("value", [123, "", None, ["red"], {"k": "red"}])
def test_invalid_color_is_default_not_corruption(tmp_path, value):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({
        "folders": [{"uuid": "f", "name": "F", "expanded": True, "color": value}],
        "connections": [{"uuid": "u", "name": "", "url": "", "method": [], "folder": "f", "color": value}],
    }), encoding="utf-8")
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is False
    assert store.get_folder("f").color is None
    assert store.get("u").color is None


def test_unknown_color_key_is_kept_by_store(tmp_path):
    """核心層不認識色票，只保證型別；未知代號由 UI 當作預設色顯示"""
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({
        "folders": [],
        "connections": [{"uuid": "u", "name": "", "url": "", "method": [], "color": "magenta"}],
    }), encoding="utf-8")
    assert ConnectionStore(path).get("u").color == "magenta"


def test_removing_folder_keeps_connection_colors(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    folder = store.add_folder("F")
    conn = store.add(folder.uuid)
    store.set_folder_color(folder.uuid, "blue")
    store.set_color(conn.uuid, "green")
    store.remove_folder(folder.uuid)
    moved = store.get(conn.uuid)
    assert (moved.folder, moved.color) == (None, "green")


def test_set_color_unknown_uuid_raises_key_error(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    with pytest.raises(KeyError):
        store.set_color("nope", "red")
    with pytest.raises(KeyError):
        store.set_folder_color("nope", "red")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_connection_store.py -v -k "color"`
Expected: FAIL（`AttributeError: 'Folder' object has no attribute 'color'` 或 `set_folder_color` 不存在）

- [ ] **Step 3: Implement**

`src/core/connection_store.py`：

資料結構加欄位（放在各 dataclass 最後）：

```python
@dataclass
class Folder:
    uuid: str
    name: str = ""
    expanded: bool = True
    color: str | None = None  # 顏色代號（例如 "red"），None 為預設色


@dataclass
class Connection:
    uuid: str
    name: str = ""
    url: str = ""
    methods: list[str] = field(default_factory=list)
    folder: str | None = None  # 所屬目錄 uuid，None 表示最外層
    color: str | None = None  # 顏色代號（例如 "red"），None 為預設色
```

在 `_parse_expanded` 之後新增：

```python
def _parse_color(value) -> str | None:
    """color 欄位：缺少、空字串或非字串一律視為預設色；只影響顯示，不因此判定檔案損毀"""
    return value if isinstance(value, str) and value else None
```

`_parse_folders` 的 `Folder(...)` 加上 `color=_parse_color(item.get("color")),`；`_load` 的 `Connection(...)` 加上 `color=_parse_color(item.get("color")),`。

在「目錄」區段的 `set_folder_expanded` 之後新增：

```python
    def set_folder_color(self, uuid: str, color: str | None) -> None:
        self._find_folder(uuid).color = color or None
        self._save()
```

在「連線」區段的 `set_methods` 之後新增：

```python
    def set_color(self, uuid: str, color: str | None) -> None:
        self._find(uuid).color = color or None
        self._save()
```

`_save` 改用兩個模組層級函式組資料（放在 `_parse_folders` 之後）：

```python
def _folder_data(folder: Folder) -> dict:
    data = {"uuid": folder.uuid, "name": folder.name, "expanded": folder.expanded}
    if folder.color:
        data["color"] = folder.color  # 未設色不寫入，檔案格式與舊版相同
    return data


def _connection_data(conn: Connection) -> dict:
    data = {"uuid": conn.uuid, "name": conn.name, "url": conn.url, "method": conn.methods, "folder": conn.folder}
    if conn.color:
        data["color"] = conn.color
    return data
```

```python
    def _save(self) -> None:
        data = {
            "folders": [_folder_data(folder) for folder in self._folders],
            "connections": [_connection_data(conn) for conn in self._connections],
        }
        # 以下（mkdir、暫存檔寫入、os.replace）維持原樣
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_connection_store.py -v`
Expected: 全部 PASS（含既有測試，例如 `test_add_persists_blank_connection` 的 dict 不含 `color`）

- [ ] **Step 5: Commit**

訊息檔內容：`連線設定檔新增目錄與連線的顏色代號欄位`

```bash
git add src/core/connection_store.py tests/test_connection_store.py
git commit -F <訊息檔>
```

---

### Task 2: 色票

**Files:**
- Modify: `src/ui/theme.py`（在 `DARK` 定義之後新增 `TagColor`、`TAG_COLORS`、`tag_color`）
- Test: `tests/test_theme.py`

**Interfaces:**
- Consumes: `ThemePalette`、`DARK`（既有）
- Produces:
  - `TagColor(key: str, label: str, light: str, dark: str)`（frozen dataclass）
  - `TAG_COLORS: tuple[TagColor, ...]`（8 色，順序同 Global Constraints）
  - `tag_color(key: str | None, palette: ThemePalette) -> str | None`

- [ ] **Step 1: Write the failing tests**

`tests/test_theme.py` 的 import 改為：

```python
from src.ui.theme import (
    DARK, LIGHT, TAG_COLORS, ThemeManager, ThemeMode, build_qpalette, build_stylesheet, tag_color,
    write_arrow_images,
)
```

檔尾加入（`_contrast` 已定義於本檔）：

```python
def test_tag_colors_are_eight_unique_keys():
    assert [color.key for color in TAG_COLORS] == [
        "red", "orange", "yellow", "green", "teal", "blue", "purple", "pink",
    ]
    assert [color.label for color in TAG_COLORS] == ["紅", "橘", "黃", "綠", "青", "藍", "紫", "粉紅"]


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_tag_colors_meet_contrast_on_list_and_selection(palette):
    for color in TAG_COLORS:
        value = tag_color(color.key, palette)
        assert _contrast(value, palette.bg) >= 4.5, color.key
        assert _contrast(value, palette.surface_hover) >= 4.5, color.key  # 選取列底色


def test_tag_color_picks_theme_variant_and_ignores_unknown():
    assert tag_color("red", LIGHT) == "#C81E1E"
    assert tag_color("red", DARK) == "#FC8181"
    assert tag_color(None, LIGHT) is None
    assert tag_color("magenta", DARK) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_theme.py -v -k tag`
Expected: FAIL（`ImportError: cannot import name 'TAG_COLORS'`）

- [ ] **Step 3: Implement**

`src/ui/theme.py`，緊接在 `DARK = ThemePalette(...)` 之後：

```python
@dataclass(frozen=True)
class TagColor:
    key: str  # 存進 connections.profile 的代號
    label: str  # 右鍵選單顯示名稱
    light: str  # 淺色主題色碼
    dark: str  # 深色主題色碼


# 專案目錄／連線的顏色標記：淺色主題取深色階、深色主題取亮色階，
# 對清單底色 bg 與選取列底色 surface_hover 的對比度皆 ≥ 4.5（見 test_theme）
TAG_COLORS = (
    TagColor("red", "紅", "#C81E1E", "#FC8181"),
    TagColor("orange", "橘", "#B23C0A", "#FB923C"),
    TagColor("yellow", "黃", "#8A5A00", "#FACC15"),  # 淺色主題的亮黃在白底看不清，壓成芥末黃
    TagColor("green", "綠", "#15703A", "#4ADE80"),
    TagColor("teal", "青", "#0D6C65", "#2DD4BF"),
    TagColor("blue", "藍", "#1D4ED8", "#6AADFB"),
    TagColor("purple", "紫", "#7E22CE", "#C99CFD"),
    TagColor("pink", "粉紅", "#BE185D", "#F689C2"),
)


def tag_color(key: str | None, palette: ThemePalette) -> str | None:
    """顏色代號轉成目前主題的色碼；None 或未知代號回傳 None（使用預設色）"""
    for color in TAG_COLORS:
        if color.key == key:
            return color.dark if palette.name == DARK.name else color.light
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_theme.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息檔內容：`新增專案目錄顏色標記的 8 色色票`

```bash
git add src/ui/theme.py tests/test_theme.py
git commit -F <訊息檔>
```

---

### Task 3: 圖示染色與色塊

**Files:**
- Modify: `src/ui/icons.py`（新增 `tinted_icon`、`swatch_icon`）
- Create: `tests/test_icons.py`

**Interfaces:**
- Consumes: 無
- Produces:
  - `tinted_icon(icon: QIcon, color: str) -> QIcon`：保留明暗層次與透明度，色相換成 `color`
  - `swatch_icon(color: str) -> QIcon`：右鍵選單用的圓角方形色塊

- [ ] **Step 1: Write the failing tests**

建立 `tests/test_icons.py`：

```python
# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from src.ui.icons import swatch_icon, tinted_icon


def two_tone(left: str | None, right: str) -> QIcon:
    """20x20 圖示：左半 left（None 為透明）、右半 right"""
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    if left:
        painter.fillRect(0, 0, 10, 20, QColor(left))
    painter.fillRect(10, 0, 10, 20, QColor(right))
    painter.end()
    return QIcon(pixmap)


def test_tinted_icon_keeps_transparency_and_takes_color(qapp):
    image = tinted_icon(two_tone(None, "#FFFFFF"), "#C81E1E").pixmap(20, 20).toImage()
    assert image.pixelColor(2, 10).alpha() == 0
    assert image.pixelColor(15, 10) == QColor("#C81E1E")  # 白色 × 指定色 = 指定色


def test_tinted_icon_keeps_shading(qapp):
    image = tinted_icon(two_tone("#808080", "#FFFFFF"), "#1D4ED8").pixmap(20, 20).toImage()
    darker, lighter = image.pixelColor(5, 10), image.pixelColor(15, 10)
    assert darker.value() < lighter.value()  # 原圖較暗的部分染色後仍較暗
    assert abs(darker.hueF() - lighter.hueF()) < 0.02  # 色相一致


def test_swatch_icon_is_filled_with_color(qapp):
    image = swatch_icon("#15703A").pixmap(12, 12).toImage()
    assert image.pixelColor(6, 6) == QColor("#15703A")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_icons.py -v`
Expected: FAIL（`ImportError: cannot import name 'swatch_icon'`）

- [ ] **Step 3: Implement**

`src/ui/icons.py`：import 改為

```python
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
```

模組 docstring 改為 `"""介面圖示：以 QPainter 繪製的漸層向量圖（不依賴外部圖檔），以及資料夾染色、選單色塊"""`。

在常數區加入：

```python
SWATCH_SIZE = 12  # 右鍵選單色塊
```

檔尾加入：

```python
def tinted_icon(icon: QIcon, color: str) -> QIcon:
    """保留原圖示的明暗層次與透明度，把色相換成 color（有顏色標記的資料夾用）

    作法：轉灰階後以 Multiply 疊上指定色，再用原圖 alpha 裁切輪廓
    """
    sizes = icon.availableSizes() or [QSize(ICON_SIZES[0], ICON_SIZES[0])]
    tinted = QIcon()
    for size in sizes:
        source = icon.pixmap(size).toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        image = source.convertToFormat(QImage.Format.Format_Grayscale8).convertToFormat(
            QImage.Format.Format_ARGB32_Premultiplied
        )
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        painter.fillRect(image.rect(), QColor(color))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, source)
        painter.end()
        tinted.addPixmap(QPixmap.fromImage(image))
    return tinted


def swatch_icon(color: str) -> QIcon:
    """右鍵選單「顏色」各項目前方的圓角方形色塊"""
    pixmap = QPixmap(SWATCH_SIZE, SWATCH_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRectF(0, 0, SWATCH_SIZE, SWATCH_SIZE), 3, 3)
    painter.end()
    return QIcon(pixmap)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_icons.py -v`
Expected: 3 PASS。若 `test_tinted_icon_keeps_transparency_and_takes_color` 在右半邊差 1 個色階（灰階轉換的捨入），改用逐通道 `abs(a - b) <= 1` 比較，不要改演算法。

- [ ] **Step 5: Commit**

訊息檔內容：`新增資料夾圖示染色與選單色塊圖示`

```bash
git add src/ui/icons.py tests/test_icons.py
git commit -F <訊息檔>
```

---

### Task 4: 連線清單套用顏色

**Files:**
- Modify: `src/ui/connection_list.py`
- Test: `tests/test_connection_list.py`

**Interfaces:**
- Consumes: `Folder.color`、`Connection.color`（Task 1）；`TAG_COLORS`、`tag_color`、`LIGHT`、`ThemePalette`（Task 2）；`tinted_icon`（Task 3）
- Produces:
  - `ConnectionList.__init__(self, parent=None, palette: ThemePalette = LIGHT)`
  - `ConnectionList.set_palette(palette: ThemePalette) -> None`
  - `ConnectionList.set_item_color(uuid: str, color: str | None) -> None`（目錄或連線，不重建樹、不發任何訊號）
  - `ConnectionList.item_color(uuid: str) -> str | None`（目前存的代號，不存在回傳 None）
  - `ConnectionItemWidget.set_title_color(color: str | None) -> None`

- [ ] **Step 1: Write the failing tests**

`tests/test_connection_list.py` 的 import 加入：

```python
from PySide6.QtWidgets import QAbstractItemView, QStyle

from src.ui.theme import DARK, LIGHT
```

檔尾加入：

```python
COLORED_FOLDERS = [Folder("f1", "TIPTOP", True, "blue"), Folder("f2", "", False)]
COLORED_TREE = [
    Connection("u1", "正式區", "http://prod/ws?WSDL", [], "f1", "red"),
    Connection("u2", "測試區", "http://test/ws?WSDL", []),
]


def make_colored(palette=LIGHT):
    widget = ConnectionList(palette=palette)
    widget.set_tree(COLORED_FOLDERS, COLORED_TREE)
    return widget


def title_color(widget, uuid):
    title = widget.item_widget(uuid).title
    title.ensurePolished()
    return title.palette().color(title.foregroundRole()).name().upper()


def folder_icon(widget, uuid):
    return folder_item(widget, uuid).icon(0).pixmap(18, 18).toImage()


def plain_folder_icon(widget):
    return widget.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon).pixmap(18, 18).toImage()


def test_connection_title_uses_tag_color_only_on_name(qapp):
    widget = make_colored()
    assert title_color(widget, "u1") == "#C81E1E"
    assert title_color(widget, "u2") != "#C81E1E"
    assert widget.item_widget("u1").subtitle.styleSheet() == ""  # 網址不變色
    assert widget.item_color("u1") == "red" and widget.item_color("u2") is None


def test_folder_icon_is_tinted_and_restored(qapp):
    widget = make_colored()
    assert folder_icon(widget, "f1") != plain_folder_icon(widget)
    assert folder_icon(widget, "f2") == plain_folder_icon(widget)
    widget.set_item_color("f1", None)
    assert folder_icon(widget, "f1") == plain_folder_icon(widget)


def test_set_item_color_updates_single_item_without_signals(qapp):
    widget = make_colored()
    renamed = record(widget.folderRenamed)
    widget.set_item_color("u2", "green")
    widget.set_item_color("f2", "pink")
    assert title_color(widget, "u2") == "#15703A"
    assert widget.item_color("f2") == "pink"
    assert renamed == []  # 設圖示／資料會觸發 itemChanged，不能被當成改名


def test_unknown_color_key_shows_default(qapp):
    widget = make_colored()
    widget.set_item_color("u1", "magenta")
    assert title_color(widget, "u1") == title_color(widget, "u2")


def test_set_palette_recolors_items(qapp):
    widget = make_colored()
    light_icon = folder_icon(widget, "f1")
    widget.set_palette(DARK)
    assert title_color(widget, "u1") == "#FC8181"
    assert folder_icon(widget, "f1") != light_icon


def test_update_connection_applies_color(qapp):
    widget = make_colored()
    widget.update_connection(Connection("u2", "測試區", "http://test/ws?WSDL", [], None, "teal"))
    assert title_color(widget, "u2") == "#0D6C65"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_connection_list.py -v -k "color or palette"`
Expected: FAIL（`TypeError: ConnectionList.__init__() got an unexpected keyword argument 'palette'`）

- [ ] **Step 3: Implement**

`src/ui/connection_list.py`：

import 加入：

```python
from src.ui.icons import tinted_icon
from src.ui.theme import LIGHT, ThemePalette, tag_color
```

角色常數（`_KIND_ROLE` 之後）：

```python
_COLOR_ROLE = Qt.ItemDataRole.UserRole + 2  # 顏色代號，None 為預設色
```

`ConnectionItemWidget` 新增方法：

```python
    def set_title_color(self, color: str | None) -> None:
        """有顏色標記時名稱改用該色；None 回到全域 QSS 的一般文字色"""
        self.title.setStyleSheet(f"color: {color};" if color else "")
```

`ConnectionList.__init__` 簽章與開頭：

```python
    def __init__(self, parent=None, palette: ThemePalette = LIGHT):
        super().__init__(parent)
        self._palette = palette
        self._folder_names: dict[str, str] = {}
```

「對外介面」區段（`update_connection` 之後）新增：

```python
    def set_item_color(self, uuid: str, color: str | None) -> None:
        """更新單一目錄或連線的顏色標記（不重建整棵樹）"""
        item = self._item_for(uuid)
        if item is not None:
            self._set_color(item, color)

    def item_color(self, uuid: str) -> str | None:
        item = self._item_for(uuid)
        return item.data(0, _COLOR_ROLE) if item is not None else None

    def set_palette(self, palette: ThemePalette) -> None:
        """切換主題：依各項目的顏色代號改用新主題的色碼"""
        self._palette = palette
        blocked = self.tree.blockSignals(True)
        for item in self._iter_items():
            self._paint_color(item)
        self.tree.blockSignals(blocked)
```

`update_connection` 在 `set_connection(conn)` 之後加一行：

```python
        self._set_color(item, conn.color)
```

`_add_folder_item`：刪除 `item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))`，在 `return item` 前加：

```python
        self._set_color(item, folder.color)
```

`_add_connection_item` 在 `self.tree.setItemWidget(item, 0, widget)` 之後加：

```python
        self._set_color(item, conn.color)
```

「建立項目」區段末尾新增：

```python
    def _set_color(self, item: QTreeWidgetItem, color: str | None) -> None:
        blocked = self.tree.blockSignals(True)  # 設定資料與圖示也會觸發 itemChanged，不是使用者改名
        item.setData(0, _COLOR_ROLE, color)
        self._paint_color(item)
        self.tree.blockSignals(blocked)

    def _paint_color(self, item: QTreeWidgetItem) -> None:
        """目錄染資料夾圖示、連線改名稱顏色；未知代號視為預設色"""
        color = tag_color(item.data(0, _COLOR_ROLE), self._palette)
        if _kind_of(item) == FOLDER:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            item.setIcon(0, tinted_icon(icon, color) if color else icon)
            return
        widget = self.tree.itemWidget(item, 0)
        if widget is not None:
            widget.set_title_color(color)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_connection_list.py -v`
Expected: 全部 PASS。若 `title_color` 拿到的仍是預設色（標籤尚未套用自身 stylesheet），在 `title_color()` 裡先呼叫 `title.style().polish(title)` 再讀 palette；不要改用比對 `styleSheet()` 字串。

- [ ] **Step 5: Commit**

訊息檔內容：`連線清單依顏色代號染色資料夾圖示與連線名稱，並隨主題換色`

```bash
git add src/ui/connection_list.py tests/test_connection_list.py
git commit -F <訊息檔>
```

---

### Task 5: 右鍵「顏色」子選單

**Files:**
- Modify: `src/ui/connection_list.py`（`_context_menu`、`_fill_connection_menu`，新增 `_add_color_menu`、訊號）
- Test: `tests/test_connection_list.py`

**Interfaces:**
- Consumes: `TAG_COLORS`、`tag_color`（Task 2）；`swatch_icon`（Task 3）；`_COLOR_ROLE`、`item_color`（Task 4）
- Produces:
  - `ConnectionList.folderColorChanged = Signal(str, object)`：目錄 uuid、顏色代號或 None
  - `ConnectionList.connectionColorChanged = Signal(str, object)`：連線 uuid、顏色代號或 None
  - 選單順序：連線「移動到、顏色、（分隔線）、刪除」；目錄「新增連線到此目錄、重新命名、顏色、（分隔線）、刪除目錄」

- [ ] **Step 1: Write the failing tests**

先更新兩個既有測試的選單清單斷言：

- `test_connection_menu_moves_into_folder`：`assert list(actions) == ["移動到", "顏色", "刪除"]`
- 目錄選單測試（斷言 `["新增連線到此目錄", "重新命名", "刪除目錄"]` 那一個）：改為 `["新增連線到此目錄", "重新命名", "顏色", "刪除目錄"]`

檔尾加入：

```python
def color_actions(widget, item):
    return actions_by_text(widget._context_menu(item))["顏色"].menu().actions()


def test_color_menu_lists_default_and_eight_colors(qapp):
    widget = make_colored()
    actions = color_actions(widget, folder_item(widget, "f1").child(0))  # u1 為紅色
    assert [action.text() for action in actions] == ["預設", "紅", "橘", "黃", "綠", "青", "藍", "紫", "粉紅"]
    assert [action.text() for action in actions if action.isChecked()] == ["紅"]
    assert actions[0].icon().isNull()
    assert all(not action.icon().isNull() for action in actions[1:])  # 8 色都有色塊
    folder_actions = color_actions(widget, folder_item(widget, "f2"))  # f2 未設色
    assert [action.text() for action in folder_actions if action.isChecked()] == ["預設"]


def test_unknown_color_key_checks_default_in_menu(qapp):
    widget = make_colored()
    widget.set_item_color("u1", "magenta")
    actions = color_actions(widget, folder_item(widget, "f1").child(0))
    assert [action.text() for action in actions if action.isChecked()] == ["預設"]


def test_choosing_color_emits_only_when_changed(qapp):
    widget = make_colored()
    connection_changes = record(widget.connectionColorChanged)
    folder_changes = record(widget.folderColorChanged)
    colors = {action.text(): action for action in color_actions(widget, folder_item(widget, "f1").child(0))}
    colors["紅"].trigger()  # 已經是紅色，不發訊號
    colors["綠"].trigger()
    colors["預設"].trigger()
    assert connection_changes == [("u1", "green"), ("u1", None)]
    folder_colors = {action.text(): action for action in color_actions(widget, folder_item(widget, "f1"))}
    folder_colors["藍"].trigger()  # 已經是藍色
    folder_colors["紫"].trigger()
    assert folder_changes == [("f1", "purple")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_connection_list.py -v -k "menu"`
Expected: FAIL（`KeyError: '顏色'` 與選單清單斷言不符）

- [ ] **Step 3: Implement**

`src/ui/connection_list.py`：

import 調整：

```python
from PySide6.QtGui import QActionGroup, QFont, QPainter
from src.ui.icons import swatch_icon, tinted_icon
from src.ui.theme import LIGHT, TAG_COLORS, ThemePalette, tag_color
```

常數區加入：

```python
DEFAULT_COLOR_LABEL = "預設"
```

`ConnectionList` 訊號區加入：

```python
    folderColorChanged = Signal(str, object)  # 目錄 uuid、顏色代號（None 為預設色）
    connectionColorChanged = Signal(str, object)  # 連線 uuid、顏色代號（None 為預設色）
```

`_context_menu`：

```python
    def _context_menu(self, item: QTreeWidgetItem | None) -> QMenu:
        menu = QMenu(self)
        uuid = _uuid_of(item)
        if _kind_of(item) == CONNECTION:
            self._fill_connection_menu(menu, item)
        elif _kind_of(item) == FOLDER:
            menu.addAction("新增連線到此目錄").triggered.connect(lambda: self._add_into(uuid))
            menu.addAction("重新命名").triggered.connect(lambda: self.edit_folder(uuid))
            self._add_color_menu(menu, item)
            menu.addSeparator()
            menu.addAction("刪除目錄").triggered.connect(lambda: self.deleteFolderRequested.emit(uuid))
        else:
            menu.addAction("新增連線").triggered.connect(lambda: self._add_into(None))
            menu.addAction("新增目錄").triggered.connect(lambda: self.addFolderRequested.emit())
        return menu
```

`_fill_connection_menu` 改收 item，並在分隔線前加顏色子選單：

```python
    def _fill_connection_menu(self, menu: QMenu, item: QTreeWidgetItem) -> None:
        uuid, here = _uuid_of(item), _uuid_of(item.parent())
        layout = self._layout()
        move_menu = menu.addMenu("移動到")
        # 以下 targets 與 for 迴圈維持原樣
        ...
        self._add_color_menu(menu, item)
        menu.addSeparator()
        menu.addAction("刪除").triggered.connect(lambda: self.deleteRequested.emit(uuid))
```

新增：

```python
    def _add_color_menu(self, menu: QMenu, item: QTreeWidgetItem) -> None:
        """「顏色」子選單：預設 + 8 色，目前的顏色打勾；未知代號視為預設"""
        uuid = _uuid_of(item)
        key = item.data(0, _COLOR_ROLE)
        current = key if tag_color(key, self._palette) else None
        signal = self.folderColorChanged if _kind_of(item) == FOLDER else self.connectionColorChanged

        def choose(chosen: str | None) -> None:
            if chosen != current:  # 選到目前的顏色不發訊號
                signal.emit(uuid, chosen)

        color_menu = menu.addMenu("顏色")
        group = QActionGroup(color_menu)
        options = [(None, DEFAULT_COLOR_LABEL)] + [(color.key, color.label) for color in TAG_COLORS]
        for value, label in options:
            action = color_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == current)
            group.addAction(action)
            if value is not None:
                action.setIcon(swatch_icon(tag_color(value, self._palette)))
            action.triggered.connect(lambda _checked=False, chosen=value: choose(chosen))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_connection_list.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息檔內容：`目錄與連線右鍵選單新增「顏色」子選單`

```bash
git add src/ui/connection_list.py tests/test_connection_list.py
git commit -F <訊息檔>
```

---

### Task 6: 主視窗串接存檔與主題

**Files:**
- Modify: `src/ui/main_window.py`（`_build_sidebar`、`_connect_signals`、`_on_theme_changed`，新增兩個 slot）
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `ConnectionStore.set_color`、`set_folder_color`（Task 1）；`ConnectionList(palette=…)`、`set_item_color`、`item_color`、`set_palette`、`folderColorChanged`、`connectionColorChanged`（Task 4、5）
- Produces: 無（最終整合）

- [ ] **Step 1: Write the failing tests**

`tests/test_main_window.py` 檔尾加入（`seed`、`env`、`ThemeMode`、`ConnectionStore` 皆已 import／定義於本檔）：

```python
def test_item_colors_persist_and_follow_theme(env):
    folder = env.store.add_folder("科林儀器").uuid
    uuid = seed(env.store)
    env.store.move_connection(uuid, folder, 0)
    window = env.make()
    window.connection_list.connectionColorChanged.emit(uuid, "red")
    window.connection_list.folderColorChanged.emit(folder, "blue")

    reloaded = ConnectionStore(env.store.path)
    assert reloaded.get(uuid).color == "red"
    assert reloaded.get_folder(folder).color == "blue"
    assert window.connection_list.item_color(uuid) == "red"
    assert env.make().connection_list.item_color(folder) == "blue"  # 重開後仍在

    env.theme.set_mode(ThemeMode.DARK)
    title = window.connection_list.item_widget(uuid).title
    title.ensurePolished()
    assert title.palette().color(title.foregroundRole()).name().upper() == "#FC8181"


def test_clearing_color_removes_it_from_profile(env):
    uuid = seed(env.store)
    env.store.set_color(uuid, "green")
    window = env.make()
    window.connection_list.connectionColorChanged.emit(uuid, None)
    assert ConnectionStore(env.store.path).get(uuid).color is None
    assert window.connection_list.item_color(uuid) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_main_window.py -v -k color`
Expected: FAIL（顏色沒有寫進 store）

- [ ] **Step 3: Implement**

`src/ui/main_window.py`：

`_build_sidebar`：

```python
        self.connection_list = ConnectionList(palette=self._theme.palette)
```

`_connect_signals` 在 `folderMoved` 那行之後加入：

```python
        self.connection_list.folderColorChanged.connect(self._on_folder_color_changed)
        self.connection_list.connectionColorChanged.connect(self._on_connection_color_changed)
```

在 `_on_folder_expanded_changed` 之後新增：

```python
    @Slot(str, object)
    def _on_folder_color_changed(self, uuid: str, color: str | None) -> None:
        self._store.set_folder_color(uuid, color)
        self.connection_list.set_item_color(uuid, color)

    @Slot(str, object)
    def _on_connection_color_changed(self, uuid: str, color: str | None) -> None:
        self._store.set_color(uuid, color)
        self.connection_list.set_item_color(uuid, color)
```

`_on_theme_changed` 在 `self.console_panel.set_palette(palette)` 之後加入：

```python
        self.connection_list.set_palette(palette)
```

- [ ] **Step 4: Run the full suite and lint**

Run: `.venv/Scripts/python -m pytest -q` 與 `uv run ruff check src tests`
Expected: 全部 PASS、`All checks passed!`

- [ ] **Step 5: Commit**

訊息檔內容：`主視窗串接目錄與連線顏色的存檔與主題切換`

```bash
git add src/ui/main_window.py tests/test_main_window.py
git commit -F <訊息檔>
```

---

### Task 7: 畫面驗證

**Files:** 無程式變更（發現問題才回到對應 Task 修正）

- [ ] **Step 1: 離線截圖檢查**

以 `QT_QPA_PLATFORM=offscreen` 建立 `MainWindow`（淺色與深色各一次），連線清單包含：藍色目錄、未設色目錄、紅色連線（選取中）、未設色連線；存成 PNG 放大檢查：
- 藍色目錄的資料夾圖示是藍色且保有明暗；未設色目錄維持原圖示
- 紅色連線只有名稱變色、網址維持灰色；選取列底色上仍清楚可讀
- 右鍵選單「顏色」色塊與打勾正確

截圖腳本與圖檔放在系統暫存目錄，檢查完刪除，不加入版本控制。

- [ ] **Step 2: 回報使用者實際操作**

請使用者執行 `uv run python src/ws_tool.py`，實際右鍵設色、切換主題、重開程式確認顏色保留。
