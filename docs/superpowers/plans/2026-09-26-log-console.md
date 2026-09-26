# 主控台（Console）記錄面板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在主視窗右側下方加入可收合的主控台面板，即時顯示 loguru 記錄（7 個等級篩選、搜尋、清除、複製），側欄「主控台」按鈕與 Ctrl+` 可切換。

**Architecture:** `src/core/log_buffer.py` 以 loguru function sink 把記錄收進執行緒安全的環狀暫存並通知 listener（不依賴 Qt）；`src/ui/log_console.py` 的 `LogBridge` 把 listener 回呼轉成 Qt 訊號，`ConsolePanel` 以 QueuedConnection 接收並顯示；`MainWindow` 把右側改成上下 `QSplitter`（stack ＋ 面板），開關狀態與篩選存在 `settings.ini`。

**Tech Stack:** Python 3.14、PySide6、loguru 0.7.3、pytest（`QT_QPA_PLATFORM=offscreen`）

**Spec:** `docs/superpowers/specs/2026-09-26-log-console-design.md`

## Global Constraints

- 每個原始碼檔開頭 `# -*- coding: utf-8 -*-`，接著一段繁體中文模組 docstring
- 註解、docstring、UI 文字、commit 訊息一律繁體中文；識別字用英文
- `src/core/` 不可 import PySide6
- 顏色一律來自 `src/ui/theme.py` 色票，元件不寫死顏色
- `ws_tool.yaml`、`connections.profile` 格式不變；`settings.ini` 只新增 `console/visible`、`console/height`、`console/levels`
- `MainWindow` 新增的建構參數皆選填，舊呼叫方式可用
- 7 個等級依序：`TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL`；預設篩選 `debug,info,success`
- 測試指令：`.venv/Scripts/python -m pytest`（專案根目錄 `D:\GITLocal\webservice-py-tool`）；開工前基線 298 passed
- **commit 訊息含中文：先用 Write 工具寫入 `.git/COMMIT_MSG_TMP.txt`，再 `git commit -F .git/COMMIT_MSG_TMP.txt` 後刪除暫存檔**；不要用 heredoc／`-m` 組中文訊息。訊息結尾加一行空行與 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 以 Python 腳本改寫檔案時用二進位模式（`open(p, "rb")`／`"wb"`），避免 Windows 把 LF 轉成 CRLF
- 不要 push

---

## File Structure

| 檔案 | 動作 | 職責 |
|---|---|---|
| `src/core/log_buffer.py` | 新增 | `LEVELS`、`LogEntry`、`normalize_level`、`LogBuffer`（sink、暫存、listener） |
| `src/ui/theme.py` | 修改 | `LevelColor`、`ThemePalette.levels/level_alphas/level()`、主控台與等級鈕 QSS、footer padding |
| `src/ui/settings_page.py` | 修改 | `palette_colors()` 只傳字串欄位 |
| `src/ui/log_console.py` | 新增 | `ConsoleSettings`、`LogBridge`、`ConsolePanel` |
| `src/ui/icons.py` | 修改 | `console_icon()` |
| `src/ui/main_window.py` | 修改 | 右側 splitter、footer 按鈕、Ctrl+`、設定頁只鎖連線清單、補記錄點 |
| `src/ws_tool.py` | 修改 | `setup_logging()`、啟動記錄、傳 settings／buffer 給 MainWindow |
| `tests/test_log_buffer.py` | 新增 | LogBuffer 測試 |
| `tests/test_log_console.py` | 新增 | ConsoleSettings、LogBridge、ConsolePanel 測試 |
| `tests/test_theme.py`、`tests/test_settings_page.py`、`tests/test_main_window.py`、`tests/test_entry_point.py` | 修改 | 對應新增案例 |

---

### Task 1: 記錄暫存 `LogBuffer`

**Files:**
- Create: `src/core/log_buffer.py`
- Test: `tests/test_log_buffer.py`

**Interfaces:**
- Consumes: 無
- Produces:
  - `LEVELS: tuple[str, ...]`、`LEVEL_NO: dict[str, int]`、`DEFAULT_CAPACITY = 5000`、`SINK_OPTIONS: dict`
  - `LogEntry(seq: int, time: datetime, level: str, message: str)`（frozen）
  - `normalize_level(name: str, no: int) -> str`
  - `LogBuffer(capacity=DEFAULT_CAPACITY)`：`write(message)`、`snapshot() -> list[LogEntry]`、`clear()`、`add_listener(cb)`、`remove_listener(cb)`、`attach() -> int`

- [ ] **Step 1: 寫失敗測試**

`tests/test_log_buffer.py`：

```python
# -*- coding: utf-8 -*-
import threading

import pytest
from loguru import logger

from src.core.log_buffer import LEVELS, LogBuffer, normalize_level


@pytest.fixture
def make_buffer():
    handler_ids = []

    def make(capacity=100):
        buffer = LogBuffer(capacity)
        handler_ids.append(buffer.attach())
        return buffer

    yield make
    for handler_id in handler_ids:
        logger.remove(handler_id)


def test_levels_are_loguru_builtin_levels_in_severity_order():
    assert LEVELS == ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")


@pytest.mark.parametrize("name,no", [
    ("TRACE", 5), ("DEBUG", 10), ("INFO", 20), ("SUCCESS", 25), ("WARNING", 30), ("ERROR", 40), ("CRITICAL", 50),
])
def test_builtin_levels_are_kept(name, no):
    assert normalize_level(name, no) == name


@pytest.mark.parametrize("no,expected", [(35, "WARNING"), (1, "TRACE"), (60, "CRITICAL"), (22, "INFO")])
def test_custom_levels_map_to_highest_builtin_not_above(no, expected):
    assert normalize_level("NOTICE", no) == expected


def test_captures_every_level_including_trace(make_buffer):
    buffer = make_buffer()
    logger.trace("t")
    logger.debug("d")
    logger.info("i")
    logger.success("s")
    logger.warning("w")
    logger.error("e")
    logger.critical("c")
    entries = buffer.snapshot()
    assert [e.level for e in entries] == list(LEVELS)
    assert [e.message for e in entries] == ["t", "d", "i", "s", "w", "e", "c"]
    assert [e.seq for e in entries] == sorted(e.seq for e in entries)
    assert all(e.time.tzinfo is not None for e in entries)


def test_message_is_formatted_with_arguments(make_buffer):
    buffer = make_buffer()
    logger.info("讀取 WSDL · URL={}", "http://x/ws?WSDL")
    assert buffer.snapshot()[-1].message == "讀取 WSDL · URL=http://x/ws?WSDL"


def test_exception_traceback_is_appended(make_buffer):
    buffer = make_buffer()
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("爆炸")
    message = buffer.snapshot()[-1].message
    assert message.startswith("爆炸\nTraceback")
    assert message.endswith("ZeroDivisionError: division by zero")


def test_oldest_entries_dropped_over_capacity(make_buffer):
    buffer = make_buffer(capacity=3)
    for i in range(5):
        logger.info("m{}", i)
    assert [e.message for e in buffer.snapshot()] == ["m2", "m3", "m4"]


def test_clear_empties_buffer(make_buffer):
    buffer = make_buffer()
    logger.info("x")
    buffer.clear()
    assert buffer.snapshot() == []


def test_listener_receives_entries_until_removed(make_buffer):
    buffer = make_buffer()
    received = []
    buffer.add_listener(received.append)
    logger.info("a")
    buffer.remove_listener(received.append)
    logger.info("b")
    assert [e.message for e in received] == ["a"]


def test_failing_listener_does_not_break_logging(make_buffer):
    buffer = make_buffer()
    received = []

    def broken(_entry):
        raise ValueError("listener 壞掉")

    buffer.add_listener(broken)
    buffer.add_listener(received.append)
    logger.info("仍然記錄")
    assert [e.message for e in buffer.snapshot()] == ["仍然記錄"]
    assert [e.message for e in received] == ["仍然記錄"]


def test_concurrent_writes_are_not_lost(make_buffer):
    buffer = make_buffer(capacity=10_000)

    def work(n):
        for i in range(250):
            logger.info("t{}-{}", n, i)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    entries = buffer.snapshot()
    assert len(entries) == 1000
    assert len({e.seq for e in entries}) == 1000
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_log_buffer.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.core.log_buffer'`

- [ ] **Step 3: 實作**

`src/core/log_buffer.py`：

```python
# -*- coding: utf-8 -*-
"""
記錄暫存：以 loguru sink 把記錄收進環狀暫存並通知 listener，供主控台面板顯示（不依賴 Qt）
"""
import itertools
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from loguru import logger

# loguru 7 個內建等級，依嚴重度排列；主控台篩選鈕一個等級一顆
LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
LEVEL_NO = {"TRACE": 5, "DEBUG": 10, "INFO": 20, "SUCCESS": 25, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
DEFAULT_CAPACITY = 5000
# format 只取訊息本身；有例外時 loguru 會自動把 traceback 接在後面。diagnose=False 避免印出變數值
SINK_OPTIONS = dict(level="TRACE", format="{message}", colorize=False, backtrace=False, diagnose=False)


@dataclass(frozen=True)
class LogEntry:
    seq: int  # 寫入順序（遞增），面板用來避免 snapshot 與即時通知重複
    time: datetime
    level: str  # LEVELS 其中之一
    message: str  # 含例外 traceback（多行）


def normalize_level(name: str, no: int) -> str:
    """內建等級原樣回傳；自訂等級歸到數值不超過它的最高內建等級（低於 TRACE 時為 TRACE）"""
    if name in LEVEL_NO:
        return name
    result = LEVELS[0]
    for level in LEVELS:
        if LEVEL_NO[level] <= no:
            result = level
    return result


class LogBuffer:
    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        self._entries: deque[LogEntry] = deque(maxlen=capacity)
        self._listeners: list[Callable[[LogEntry], None]] = []
        self._lock = threading.Lock()
        self._seq = itertools.count(1)

    def attach(self) -> int:
        """註冊為 loguru sink，回傳 handler id（移除時用 logger.remove）"""
        return logger.add(self.write, **SINK_OPTIONS)

    def write(self, message) -> None:
        """loguru sink：message 是已格式化的字串（結尾帶換行），record 帶原始欄位"""
        try:
            level = message.record["level"]
            with self._lock:
                entry = LogEntry(
                    next(self._seq), message.record["time"],
                    normalize_level(level.name, level.no), str(message).rstrip("\n"),
                )
                self._entries.append(entry)
                listeners = list(self._listeners)
        except Exception:
            return  # 記錄動作不可以把主流程弄壞
        for listener in listeners:
            try:
                listener(entry)
            except Exception:
                pass  # 單一 listener 失敗不影響其他 listener 與記錄本身

    def snapshot(self) -> list[LogEntry]:
        with self._lock:
            return list(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def add_listener(self, callback: Callable[[LogEntry], None]) -> None:
        with self._lock:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[LogEntry], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_log_buffer.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息：`新增記錄暫存 LogBuffer：以 loguru sink 收集 7 個等級的記錄`

```bash
git add src/core/log_buffer.py tests/test_log_buffer.py
git commit -F .git/COMMIT_MSG_TMP.txt && rm .git/COMMIT_MSG_TMP.txt
```

---

### Task 2: 主題：等級配色、主控台 QSS、footer 寬度

**Files:**
- Modify: `src/ui/theme.py`（`XmlColors` 之後新增 `LevelColor`；`ThemePalette` 加欄位與方法；`LIGHT`/`DARK`；`_QSS`；`build_stylesheet`）
- Modify: `src/ui/settings_page.py:25-27`（`palette_colors`）
- Test: `tests/test_theme.py`、`tests/test_settings_page.py`

**Interfaces:**
- Consumes: `src.core.log_buffer.LEVELS`
- Produces:
  - `LevelColor(fg: str, hover: str, on: str)`（frozen）
  - `ThemePalette.levels: tuple[LevelColor, ...]`（順序同 `LEVELS`）、`ThemePalette.level_alphas: tuple[float, float, float]`、`ThemePalette.level(name: str) -> LevelColor`
  - QSS objectName／屬性：`QWidget#ConsolePanel`、`QLabel#ConsoleTitle`、`QLineEdit#ConsoleSearch`、`QPlainTextEdit#ConsoleView`、`QPushButton[variant="level"][level="<LEVEL>"]`、`QPushButton[variant="footer"]:checked`

- [ ] **Step 1: 寫失敗測試**

`tests/test_theme.py` 的 import 改為：

```python
from src.core.log_buffer import LEVELS
from src.ui.theme import (
    DARK, LIGHT, ThemeManager, ThemeMode, build_qpalette, build_stylesheet, write_arrow_images,
)
```

檔尾新增：

```python
def _luminance(color: str) -> float:
    channels = [int(color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_level_colors_cover_all_levels_and_are_distinct(palette):
    assert len(palette.levels) == len(LEVELS)
    assert len({color.fg for color in palette.levels}) == len(LEVELS)
    assert palette.level("ERROR") is palette.levels[LEVELS.index("ERROR")]


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_level_colors_meet_contrast(palette):
    for name, color in zip(LEVELS, palette.levels):
        assert _contrast(color.fg, palette.surface) >= 4.5, name
        assert _contrast(color.on, color.fg) >= 4.5, name


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_stylesheet_has_rules_for_every_level(palette, tmp_path):
    qss = build_stylesheet(palette, write_arrow_images(palette.text_muted, tmp_path))
    for name, color in zip(LEVELS, palette.levels):
        selector = f'QPushButton[variant="level"][level="{name}"]'
        assert f"{selector}:checked {{ background: {color.fg}; color: {color.on};" in qss
        assert f"{selector}:checked:hover {{ background: {color.hover};" in qss
        assert f"{selector} {{ color: {color.fg}; background: rgba(" in qss


def test_palettes_stay_hashable():
    hash(LIGHT)
    hash(DARK)
```

`tests/test_settings_page.py` 的 `test_palette_colors_excludes_name_and_xml` 改為：

```python
def test_palette_colors_excludes_name_and_xml():
    colors = palette_colors(DARK)
    assert "name" not in colors and "xml" not in colors
    assert "levels" not in colors and "level_alphas" not in colors
    assert all(isinstance(value, str) for value in colors.values())
    assert colors["surface"] == DARK.surface
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_theme.py tests/test_settings_page.py -q`
Expected: FAIL，`AttributeError: 'ThemePalette' object has no attribute 'levels'`

- [ ] **Step 3: 實作 `theme.py`**

import 區加入：

```python
from src.core.log_buffer import LEVELS
```

`XmlColors` 之後新增：

```python
@dataclass(frozen=True)
class LevelColor:
    fg: str  # 主色：勾選按鈕底色、未勾選按鈕文字色、記錄行的等級欄位色
    hover: str  # 勾選按鈕懸浮時的底色
    on: str  # 勾選按鈕（實心底）上的文字色
```

`ThemePalette` 最後（`xml: XmlColors` 之後）新增欄位與方法：

```python
    levels: tuple[LevelColor, ...]  # 順序同 log_buffer.LEVELS；用 tuple 讓 ThemePalette 維持可 hash
    level_alphas: tuple[float, float, float]  # 未勾選等級鈕：淡底、懸浮淡底、外框的不透明度

    def level(self, name: str) -> LevelColor:
        return self.levels[LEVELS.index(name)]
```

`LIGHT` 的 `xml=...` 之後加：

```python
    levels=(
        LevelColor(fg="#0E7490", hover="#155E75", on="#FFFFFF"),  # TRACE
        LevelColor(fg="#64748B", hover="#475569", on="#FFFFFF"),  # DEBUG
        LevelColor(fg="#2563EB", hover="#1D4ED8", on="#FFFFFF"),  # INFO
        LevelColor(fg="#15803D", hover="#166534", on="#FFFFFF"),  # SUCCESS
        LevelColor(fg="#B45309", hover="#92400E", on="#FFFFFF"),  # WARNING（#D97706 白字對比不足）
        LevelColor(fg="#DC2626", hover="#B91C1C", on="#FFFFFF"),  # ERROR
        LevelColor(fg="#A21CAF", hover="#86198F", on="#FFFFFF"),  # CRITICAL（洋紅，與 ERROR 區隔）
    ),
    level_alphas=(0.12, 0.24, 0.35),
```

`DARK` 的 `xml=...` 之後加：

```python
    levels=(
        LevelColor(fg="#22D3EE", hover="#67E8F9", on="#042F36"),  # TRACE
        LevelColor(fg="#94A3B8", hover="#CBD5E1", on="#0F172A"),  # DEBUG
        LevelColor(fg="#60A5FA", hover="#93C5FD", on="#0B1B33"),  # INFO
        LevelColor(fg="#4ADE80", hover="#86EFAC", on="#052E16"),  # SUCCESS
        LevelColor(fg="#FBBF24", hover="#FCD34D", on="#1F1300"),  # WARNING
        LevelColor(fg="#F87171", hover="#FCA5A5", on="#2A0A0A"),  # ERROR
        LevelColor(fg="#E879F9", hover="#F0ABFC", on="#3B0764"),  # CRITICAL
    ),
    level_alphas=(0.16, 0.30, 0.45),
```

`_QSS` 內 footer 規則的 padding 由 `6px 12px` 改為 `6px 7px`（三顆 footer 按鈕才放得進 236 px），並在 footer 規則之後加 checked 狀態：

```
QPushButton[variant="footer"] {
    background: $surface; border: 1px solid $border; border-radius: 8px;
    padding: 6px 7px; font-size: 10.5pt; font-weight: 600;
}
QPushButton[variant="footer"]:hover { background: $surface_hover; border-color: $accent; }
QPushButton[variant="footer"]:checked { background: $surface_hover; border-color: $accent; }
```

`_QSS` 在 `QStatusBar { ... }` 之前加主控台規則：

```
QWidget#ConsolePanel { background: $surface; border-top: 1px solid $border; }
QLabel#ConsoleTitle { font-weight: 600; }
QLineEdit#ConsoleSearch { padding: 3px 8px; }
QPlainTextEdit#ConsoleView {
    background: $surface; border: none; padding: 2px;
    font-family: "Cascadia Mono", "Consolas"; font-size: 9.5pt;
}
QPushButton[variant="level"] { border-radius: 8px; padding: 1px 8px; font-size: 8.5pt; font-weight: 600; }
```

`_QSS` 定義之後新增等級鈕樣板與產生函式：

```python
# 每個等級 4 條規則；border-radius 必須小於按鈕高度一半（8px），否則 Qt 會畫成直角
_LEVEL_QSS = Template("""
QPushButton[variant="level"][level="$level"] { color: $fg; background: $tint; border: 1px solid $edge; }
QPushButton[variant="level"][level="$level"]:hover { background: $tint_hover; border-color: $fg; }
QPushButton[variant="level"][level="$level"]:checked { background: $fg; color: $on; border-color: $fg; }
QPushButton[variant="level"][level="$level"]:checked:hover { background: $hover; border-color: $hover; }
""")


def _rgba(color: str, alpha: float) -> str:
    qcolor = QColor(color)
    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {alpha})"


def _level_stylesheet(palette: ThemePalette) -> str:
    """主控台等級鈕：勾選為實心等級色，未勾選為同色淡底（由 fg 換算，不另外寫死）"""
    tint, tint_hover, edge = palette.level_alphas
    return "".join(
        _LEVEL_QSS.substitute(
            level=name, fg=color.fg, hover=color.hover, on=color.on,
            tint=_rgba(color.fg, tint), tint_hover=_rgba(color.fg, tint_hover), edge=_rgba(color.fg, edge),
        )
        for name, color in zip(LEVELS, palette.levels)
    )
```

`build_stylesheet` 最後一行改為：

```python
    return _QSS.substitute(values | buttons | arrows) + _level_stylesheet(palette)
```

- [ ] **Step 4: 實作 `settings_page.palette_colors`**

```python
def palette_colors(palette: ThemePalette) -> dict[str, str]:
    """傳給外掛的色票：只含顏色字串（排除 name、xml、levels 等非字串欄位）"""
    return {
        f.name: getattr(palette, f.name) for f in fields(palette)
        if f.name != "name" and isinstance(getattr(palette, f.name), str)
    }
```

（保留原本 docstring 的用意；若原函式已有 docstring，改寫成上面這句。）

- [ ] **Step 5: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_theme.py tests/test_settings_page.py tests/test_settings_editor_plugin.py -q`
Expected: 全部 PASS

- [ ] **Step 6: 跑全部測試確認無回歸**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

訊息：`主題新增 7 個記錄等級配色與主控台樣式，縮小 footer 按鈕寬度`

```bash
git add src/ui/theme.py src/ui/settings_page.py tests/test_theme.py tests/test_settings_page.py
git commit -F .git/COMMIT_MSG_TMP.txt && rm .git/COMMIT_MSG_TMP.txt
```

---

### Task 3: `ConsoleSettings` 與 `LogBridge`

**Files:**
- Create: `src/ui/log_console.py`（本 Task 只放設定與 bridge，Task 4 再加面板）
- Test: `tests/test_log_console.py`

**Interfaces:**
- Consumes: `LEVELS`、`LogBuffer`、`LogEntry`（Task 1）
- Produces:
  - `DEFAULT_LEVELS = frozenset({"DEBUG", "INFO", "SUCCESS"})`、`DEFAULT_HEIGHT = 220`、`HEIGHT_MIN = 120`、`HEIGHT_MAX = 2000`
  - `parse_levels(value) -> frozenset[str]`、`format_levels(levels) -> str`
  - `ConsoleSettings(settings: QSettings | None = None)`：`visible() -> bool`、`set_visible(bool)`、`height() -> int`、`set_height(int)`、`levels() -> frozenset[str]`、`set_levels(Iterable[str])`
  - `LogBridge(buffer, parent=None)`：`entryAdded = Signal(object)`、`detach()`

- [ ] **Step 1: 寫失敗測試**

`tests/test_log_console.py`：

```python
# -*- coding: utf-8 -*-
import threading

import pytest
from loguru import logger
from PySide6.QtCore import QSettings

from src.core.log_buffer import LogBuffer
from src.ui.log_console import DEFAULT_HEIGHT, DEFAULT_LEVELS, ConsoleSettings, LogBridge
from tests.helpers import wait_until


@pytest.fixture
def ini(tmp_path):
    return tmp_path / "settings.ini"


@pytest.fixture
def buffer():
    buffer = LogBuffer()
    handler_id = buffer.attach()
    yield buffer
    logger.remove(handler_id)


def qsettings(path):
    return QSettings(str(path), QSettings.Format.IniFormat)


# ---------- ConsoleSettings ----------

def test_settings_defaults_when_keys_missing(ini):
    settings = ConsoleSettings(qsettings(ini))
    assert settings.visible() is False
    assert settings.height() == DEFAULT_HEIGHT
    assert settings.levels() == DEFAULT_LEVELS == {"DEBUG", "INFO", "SUCCESS"}


def test_settings_round_trip(ini):
    ConsoleSettings(qsettings(ini)).set_visible(True)
    ConsoleSettings(qsettings(ini)).set_height(300)
    ConsoleSettings(qsettings(ini)).set_levels({"CRITICAL", "DEBUG"})
    settings = ConsoleSettings(qsettings(ini))
    assert settings.visible() is True
    assert settings.height() == 300
    assert settings.levels() == {"DEBUG", "CRITICAL"}


def test_settings_levels_written_in_severity_order(ini):
    ConsoleSettings(qsettings(ini)).set_levels({"ERROR", "TRACE", "INFO"})
    assert qsettings(ini).value("console/levels") == "trace,info,error"


def test_settings_reads_hand_edited_levels(ini):
    # 手動編輯、未加引號的逗號清單，QSettings 會讀成 list
    ini.write_text("[console]\nlevels=debug,info,success,critical\n", encoding="utf-8")
    assert ConsoleSettings(qsettings(ini)).levels() == {"DEBUG", "INFO", "SUCCESS", "CRITICAL"}


def test_settings_single_hand_edited_level(ini):
    ini.write_text("[console]\nlevels=error\n", encoding="utf-8")
    assert ConsoleSettings(qsettings(ini)).levels() == {"ERROR"}


def test_settings_empty_levels_means_all_hidden(ini):
    ConsoleSettings(qsettings(ini)).set_levels(set())
    assert ConsoleSettings(qsettings(ini)).levels() == frozenset()


def test_settings_ignores_unknown_levels_and_spaces(ini):
    ini.write_text("[console]\nlevels=\" Debug , bogus,ERROR \"\n", encoding="utf-8")
    assert ConsoleSettings(qsettings(ini)).levels() == {"DEBUG", "ERROR"}


@pytest.mark.parametrize("raw", ["abc", "5", "99999"])
def test_settings_invalid_height_falls_back(ini, raw):
    ini.write_text(f"[console]\nheight={raw}\n", encoding="utf-8")
    assert ConsoleSettings(qsettings(ini)).height() == DEFAULT_HEIGHT


def test_settings_without_qsettings_keeps_values_in_memory():
    settings = ConsoleSettings()
    assert settings.levels() == DEFAULT_LEVELS
    settings.set_visible(True)
    settings.set_levels({"ERROR"})
    assert settings.visible() is True
    assert settings.levels() == {"ERROR"}


# ---------- LogBridge ----------

def test_bridge_emits_entries_from_any_thread(qapp, buffer):
    bridge = LogBridge(buffer)
    received = []
    bridge.entryAdded.connect(lambda entry: received.append(entry.message))
    logger.info("主執行緒")
    worker = threading.Thread(target=lambda: logger.warning("背景執行緒"))
    worker.start()
    worker.join()
    wait_until(lambda: "背景執行緒" in received)
    assert received == ["主執行緒", "背景執行緒"]


def test_bridge_detach_stops_emitting(qapp, buffer):
    bridge = LogBridge(buffer)
    received = []
    bridge.entryAdded.connect(lambda entry: received.append(entry.message))
    bridge.detach()
    logger.info("不應收到")
    assert received == []
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_log_console.py -q`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.ui.log_console'`

- [ ] **Step 3: 實作**

`src/ui/log_console.py`：

```python
# -*- coding: utf-8 -*-
"""
主控台：把 loguru 記錄即時顯示在主視窗下方的面板（等級篩選、搜尋、清除、複製）
"""
from collections.abc import Iterable

from PySide6.QtCore import QObject, QSettings, Signal

from src.core.log_buffer import LEVELS, LogBuffer, LogEntry

DEFAULT_LEVELS = frozenset({"DEBUG", "INFO", "SUCCESS"})
DEFAULT_HEIGHT = 220
HEIGHT_MIN, HEIGHT_MAX = 120, 2000
KEY_VISIBLE = "console/visible"
KEY_HEIGHT = "console/height"
KEY_LEVELS = "console/levels"


def parse_levels(value) -> frozenset[str]:
    """settings.ini 的等級設定轉成集合；手動編輯的逗號清單會被 QSettings 讀成 list，兩種都接受"""
    if isinstance(value, (list, tuple)):
        value = ",".join(map(str, value))
    names = (part.strip().upper() for part in str(value or "").split(","))
    return frozenset(name for name in names if name in LEVELS)


def format_levels(levels: Iterable[str]) -> str:
    """依嚴重度排序、小寫、逗號分隔，方便手動編輯"""
    chosen = set(levels)
    return ",".join(level.lower() for level in LEVELS if level in chosen)


class ConsoleSettings:
    """settings.ini 的 console/* 設定；未提供 QSettings 時只存在記憶體（測試與舊呼叫端用）"""

    def __init__(self, settings: QSettings | None = None):
        self._settings = settings
        self._memory: dict[str, object] = {}

    def _value(self, key: str):
        if self._settings is None:
            return self._memory.get(key)
        return self._settings.value(key) if self._settings.contains(key) else None

    def _set(self, key: str, value) -> None:
        if self._settings is None:
            self._memory[key] = value
            return
        self._settings.setValue(key, value)
        self._settings.sync()

    def visible(self) -> bool:
        return str(self._value(KEY_VISIBLE)).lower() == "true"

    def set_visible(self, visible: bool) -> None:
        self._set(KEY_VISIBLE, bool(visible))

    def height(self) -> int:
        try:
            height = int(self._value(KEY_HEIGHT))
        except (TypeError, ValueError):
            return DEFAULT_HEIGHT
        return height if HEIGHT_MIN <= height <= HEIGHT_MAX else DEFAULT_HEIGHT

    def set_height(self, height: int) -> None:
        self._set(KEY_HEIGHT, int(height))

    def levels(self) -> frozenset[str]:
        """鍵不存在才用預設值；空字串代表使用者把全部等級都關掉"""
        value = self._value(KEY_LEVELS)
        return DEFAULT_LEVELS if value is None else parse_levels(value)

    def set_levels(self, levels: Iterable[str]) -> None:
        self._set(KEY_LEVELS, format_levels(levels))


class LogBridge(QObject):
    """LogBuffer 的 listener：把任何執行緒寫入的記錄轉成 Qt 訊號"""

    entryAdded = Signal(object)  # LogEntry

    def __init__(self, buffer: LogBuffer, parent=None):
        super().__init__(parent)
        self._buffer = buffer
        buffer.add_listener(self._on_entry)

    def detach(self) -> None:
        self._buffer.remove_listener(self._on_entry)

    def _on_entry(self, entry: LogEntry) -> None:
        try:
            self.entryAdded.emit(entry)
        except RuntimeError:
            pass  # 程式關閉過程中 QObject 可能已被刪除，比照 workers.py
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_log_console.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息：`新增主控台設定 ConsoleSettings 與跨執行緒記錄訊號 LogBridge`

```bash
git add src/ui/log_console.py tests/test_log_console.py
git commit -F .git/COMMIT_MSG_TMP.txt && rm .git/COMMIT_MSG_TMP.txt
```

---

### Task 4: 主控台面板 `ConsolePanel`

**Files:**
- Modify: `src/ui/log_console.py`（加入面板）
- Test: `tests/test_log_console.py`（加入面板案例）

**Interfaces:**
- Consumes: Task 1 的 `LEVELS`、`DEFAULT_CAPACITY`、`LogBuffer`、`LogEntry`；Task 2 的 `ThemePalette.level()`、`LIGHT`、`DARK`；Task 3 的 `LogBridge`；`src.ui.effects.styled_button`
- Produces:
  - `ConsolePanel(buffer: LogBuffer, palette: ThemePalette, levels: Iterable[str], parent=None)`
  - 訊號：`closeRequested()`、`levelsChanged(object)`（frozenset[str]）
  - 方法：`levels() -> frozenset[str]`、`set_levels(levels)`、`set_search(text)`、`visible_text() -> str`、`set_palette(palette)`、`clear()`、`copy_visible()`、`detach()`
  - 公開屬性：`level_buttons: dict[str, QPushButton]`、`search_edit`、`clear_button`、`copy_button`、`close_button`、`view`（QPlainTextEdit）
  - `format_entry(entry) -> tuple[str, str, str]`

- [ ] **Step 1: 寫失敗測試**

`tests/test_log_console.py` import 區改為：

```python
# -*- coding: utf-8 -*-
import threading
from datetime import datetime, timezone

import pytest
from loguru import logger
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtGui import QGuiApplication, QTextCursor

from src.core.log_buffer import LEVELS, LogBuffer, LogEntry
from src.ui.log_console import (
    DEFAULT_HEIGHT, DEFAULT_LEVELS, ConsolePanel, ConsoleSettings, LogBridge, format_entry,
)
from src.ui.theme import DARK, LIGHT
from tests.helpers import wait_until
```

檔尾新增：

```python
# ---------- ConsolePanel ----------

@pytest.fixture
def make_panel(qapp, buffer):
    panels = []

    def make(levels=DEFAULT_LEVELS, palette=LIGHT):
        panel = ConsolePanel(buffer, palette, levels)
        panels.append(panel)
        return panel

    yield make
    for panel in panels:
        panel.detach()
        panel.deleteLater()


def flush(panel, text):
    """等待 QueuedConnection 把記錄送到面板"""
    wait_until(lambda: text in panel.visible_text())


def lines(panel):
    return panel.visible_text().splitlines()


def test_format_entry_aligns_columns_and_indents_continuation():
    entry = LogEntry(1, datetime(2026, 9, 26, 14, 2, 11, 532000, tzinfo=timezone.utc), "INFO", "第一行\n第二行")
    time_text, level_text, message = format_entry(entry)
    assert time_text == "14:02:11.532  "
    assert level_text == "INFO     "
    assert message == "第一行\n" + " " * 23 + "第二行"


def test_panel_shows_entries_logged_before_creation(make_panel):
    logger.info("啟動時的訊息")
    panel = make_panel()
    assert lines(panel)[-1].endswith("INFO     啟動時的訊息")


def test_panel_receives_new_entries_including_background_threads(make_panel):
    panel = make_panel()
    logger.info("主執行緒訊息")
    worker = threading.Thread(target=lambda: logger.success("背景完成"))
    worker.start()
    worker.join()
    flush(panel, "背景完成")
    assert "主執行緒訊息" in panel.visible_text()


def test_panel_does_not_duplicate_snapshot_entries(make_panel, buffer):
    logger.info("只出現一次")
    panel = make_panel()
    flush(panel, "只出現一次")
    for _ in range(5):
        QCoreApplication.processEvents()  # 讓排隊中的即時通知也送達
    assert panel.visible_text().count("只出現一次") == 1


def test_panel_has_seven_level_buttons_in_order(make_panel):
    panel = make_panel()
    assert list(panel.level_buttons) == list(LEVELS)
    checked = {level for level, button in panel.level_buttons.items() if button.isChecked()}
    assert checked == {"DEBUG", "INFO", "SUCCESS"}


def test_default_filter_hides_other_levels_but_counts_them(make_panel):
    panel = make_panel()
    for level in LEVELS:
        logger.log(level, "{} 訊息", level.lower())
    flush(panel, "success 訊息")
    text = panel.visible_text()
    assert "debug 訊息" in text and "info 訊息" in text and "success 訊息" in text
    assert "trace 訊息" not in text and "error 訊息" not in text and "critical 訊息" not in text
    wait_until(lambda: panel.level_buttons["CRITICAL"].text() == "CRITICAL 1")
    assert panel.level_buttons["TRACE"].text() == "TRACE 1"


def test_each_level_toggles_independently(make_panel):
    panel = make_panel(levels={"SUCCESS"})
    logger.info("一般")
    logger.success("成功")
    logger.critical("嚴重")
    flush(panel, "成功")
    assert "一般" not in panel.visible_text()
    emitted = []
    panel.levelsChanged.connect(emitted.append)
    panel.level_buttons["CRITICAL"].click()
    assert "嚴重" in panel.visible_text() and "一般" not in panel.visible_text()
    assert emitted == [frozenset({"SUCCESS", "CRITICAL"})]
    assert panel.levels() == {"SUCCESS", "CRITICAL"}


def test_set_levels_updates_buttons_without_emitting(make_panel):
    panel = make_panel()
    emitted = []
    panel.levelsChanged.connect(emitted.append)
    panel.set_levels({"ERROR"})
    assert panel.level_buttons["ERROR"].isChecked() and not panel.level_buttons["INFO"].isChecked()
    assert emitted == []


def test_search_is_case_insensitive_and_combines_with_levels(make_panel):
    panel = make_panel()
    logger.info("讀取 WSDL · URL=http://Prod/ws")
    logger.info("執行請求")
    logger.error("prod 連線失敗")
    flush(panel, "執行請求")
    panel.set_search("PROD")
    assert len(lines(panel)) == 1
    assert "http://Prod/ws" in panel.visible_text()
    panel.level_buttons["ERROR"].click()
    assert "prod 連線失敗" in panel.visible_text() and "執行請求" not in panel.visible_text()
    panel.set_search("")
    assert "執行請求" in panel.visible_text()


def test_search_matches_level_name(make_panel):
    panel = make_panel()
    logger.success("讀取完成")
    logger.info("一般")
    flush(panel, "一般")
    panel.set_search("success")
    assert "讀取完成" in panel.visible_text() and "一般" not in panel.visible_text()


def test_typing_in_search_applies_after_delay(make_panel):
    panel = make_panel()
    logger.info("甲")
    logger.info("乙")
    flush(panel, "乙")
    panel.search_edit.setText("甲")
    wait_until(lambda: "乙" not in panel.visible_text())


def test_clear_empties_panel_and_buffer(make_panel, buffer):
    panel = make_panel()
    logger.info("要被清掉")
    flush(panel, "要被清掉")
    panel.clear_button.click()
    assert panel.visible_text() == ""
    assert buffer.snapshot() == []
    assert panel.level_buttons["INFO"].text() == "INFO 0"


def test_copy_copies_only_visible_text(make_panel):
    panel = make_panel()
    logger.info("看得到")
    logger.error("看不到")
    flush(panel, "看得到")
    QGuiApplication.clipboard().setText("原本內容")
    panel.copy_button.click()
    copied = QGuiApplication.clipboard().text()
    assert "看得到" in copied and "看不到" not in copied


def test_copy_does_nothing_when_empty(make_panel):
    panel = make_panel()
    panel.set_levels(set())
    QGuiApplication.clipboard().setText("原本內容")
    panel.copy_button.click()
    assert QGuiApplication.clipboard().text() == "原本內容"


def test_close_button_emits_close_requested(make_panel):
    panel = make_panel()
    requested = []
    panel.closeRequested.connect(lambda: requested.append(True))
    panel.close_button.click()
    assert requested == [True]


def level_color(panel, line_no):
    """回傳第 line_no 行等級欄位的文字顏色（游標停在等級欄第一個字之後）"""
    block = panel.view.document().findBlockByNumber(line_no)
    cursor = QTextCursor(block)
    cursor.setPosition(block.position() + len("14:02:11.532  ") + 1)
    return cursor.charFormat().foreground().color().name().upper()


def test_level_column_uses_palette_color_and_follows_theme(make_panel):
    panel = make_panel(levels={"ERROR"})
    logger.error("失敗")
    flush(panel, "失敗")
    assert level_color(panel, 0) == LIGHT.level("ERROR").fg
    panel.set_palette(DARK)
    assert level_color(panel, 0) == DARK.level("ERROR").fg


def test_auto_scroll_only_when_at_bottom(make_panel):
    panel = make_panel()
    panel.resize(600, 150)
    panel.show()
    for i in range(80):
        logger.info("行 {}", i)
    flush(panel, "行 79")
    bar = panel.view.verticalScrollBar()
    assert bar.maximum() > 0 and bar.value() == bar.maximum()
    bar.setValue(0)
    logger.info("新的一行")
    flush(panel, "新的一行")
    assert bar.value() == 0


def test_panel_trims_to_capacity(make_panel, buffer, monkeypatch):
    import src.ui.log_console as module
    monkeypatch.setattr(module, "DEFAULT_CAPACITY", 10)
    monkeypatch.setattr(module, "TRIM_THRESHOLD", 11)
    panel = make_panel()
    for i in range(12):
        logger.info("第 {} 筆", i)
    flush(panel, "第 11 筆")
    assert len(lines(panel)) == 10
    assert "第 1 筆" not in panel.visible_text() and "第 2 筆" in panel.visible_text()
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_log_console.py -q`
Expected: FAIL，`ImportError: cannot import name 'ConsolePanel'`

- [ ] **Step 3: 實作**

`src/ui/log_console.py` 的 import 區改為：

```python
from collections import Counter
from collections.abc import Iterable

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from src.core.log_buffer import DEFAULT_CAPACITY, LEVELS, LogBuffer, LogEntry
from src.ui.effects import styled_button
from src.ui.theme import ThemePalette
```

常數區（`KEY_LEVELS` 之後）加：

```python
TRIM_THRESHOLD = int(DEFAULT_CAPACITY * 1.1)  # 超過才一次修剪回 DEFAULT_CAPACITY，避免每筆都重建
SEARCH_DELAY_MS = 200
LEVEL_WIDTH = 9  # 最長的 CRITICAL 8 字 + 1 空白
INDENT = " " * (len("HH:MM:SS.mmm  ") + LEVEL_WIDTH)  # 多行訊息後續行對齊訊息欄
MUTED_LEVELS = frozenset({"TRACE", "DEBUG"})
PLAIN_LEVELS = frozenset({"INFO"})
```

`format_levels` 之後加：

```python
def format_entry(entry: LogEntry) -> tuple[str, str, str]:
    """(時間欄、等級欄、訊息)；分成三段方便分別上色"""
    time_text = entry.time.strftime("%H:%M:%S.") + f"{entry.time.microsecond // 1000:03d}"
    return f"{time_text}  ", f"{entry.level:<{LEVEL_WIDTH}}", entry.message.replace("\n", "\n" + INDENT)
```

檔尾（`LogBridge` 之後）加：

```python
class ConsolePanel(QWidget):
    """主控台面板：第一列標題、搜尋、清除／複製／關閉；第二列 7 顆等級鈕；下方記錄文字區"""

    closeRequested = Signal()
    levelsChanged = Signal(object)  # frozenset[str]

    def __init__(self, buffer: LogBuffer, palette: ThemePalette, levels: Iterable[str], parent=None):
        super().__init__(parent)
        self.setObjectName("ConsolePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._buffer = buffer
        self._palette = palette
        self._levels = frozenset(levels) & frozenset(LEVELS)
        self._search = ""
        self._entries: list[LogEntry] = []
        self._counts: Counter[str] = Counter()
        self._last_seq = 0
        self._visible_count = 0
        self._build_ui()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DELAY_MS)
        self._search_timer.timeout.connect(self._apply_search)
        self.search_edit.textChanged.connect(lambda _text: self._search_timer.start())  # start(int) 會誤收字串參數
        # 一律排入事件迴圈再更新：面板若在 loguru sink 呼叫中同步執行，裡面再寫記錄會觸發 loguru 的重入保護
        self._bridge = LogBridge(buffer, self)
        self._bridge.entryAdded.connect(self._on_entry_added, Qt.ConnectionType.QueuedConnection)
        for entry in buffer.snapshot():
            self._store(entry)
        self._rebuild()

    # ---------- 版面 ----------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(4)

        title = QLabel("主控台")
        title.setObjectName("ConsoleTitle")
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("ConsoleSearch")
        self.search_edit.setPlaceholderText("搜尋記錄…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(220)
        self.clear_button = styled_button("清除", "subtle", "清除主控台記錄")
        self.copy_button = styled_button("複製", "subtle", "複製目前顯示的記錄")
        self.close_button = styled_button("✕", "subtle", "關閉主控台 (Ctrl+`)")
        top = QHBoxLayout()
        top.addWidget(title)
        top.addStretch(1)
        for widget in (self.search_edit, self.clear_button, self.copy_button, self.close_button):
            top.addWidget(widget)

        chips = QHBoxLayout()
        chips.setSpacing(4)
        self.level_buttons: dict[str, QPushButton] = {}
        for level in LEVELS:
            button = QPushButton()
            button.setProperty("variant", "level")
            button.setProperty("level", level)
            button.setCheckable(True)
            button.setChecked(level in self._levels)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"顯示／隱藏 {level} 記錄")
            button.toggled.connect(lambda checked, lv=level: self._on_level_toggled(lv, checked))
            chips.addWidget(button)
            self.level_buttons[level] = button
        chips.addStretch(1)

        self.view = QPlainTextEdit()
        self.view.setObjectName("ConsoleView")
        self.view.setReadOnly(True)
        self.view.setUndoRedoEnabled(False)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        layout.addLayout(top)
        layout.addLayout(chips)
        layout.addWidget(self.view, 1)
        self.clear_button.clicked.connect(self.clear)
        self.copy_button.clicked.connect(self.copy_visible)
        self.close_button.clicked.connect(lambda: self.closeRequested.emit())

    # ---------- 公開介面 ----------

    def levels(self) -> frozenset[str]:
        return self._levels

    def set_levels(self, levels: Iterable[str]) -> None:
        """程式設定篩選（不發出 levelsChanged）"""
        self._levels = frozenset(levels) & frozenset(LEVELS)
        for level, button in self.level_buttons.items():
            button.blockSignals(True)
            button.setChecked(level in self._levels)
            button.blockSignals(False)
        self._rebuild()

    def set_search(self, text: str) -> None:
        """立即套用搜尋（不經延遲），測試與程式呼叫用"""
        self._search_timer.stop()
        self.search_edit.blockSignals(True)
        self.search_edit.setText(text)
        self.search_edit.blockSignals(False)
        self._apply_search()

    def visible_text(self) -> str:
        return self.view.toPlainText()

    def set_palette(self, palette: ThemePalette) -> None:
        self._palette = palette
        self._rebuild()

    def clear(self) -> None:
        """清空面板與 LogBuffer，關掉再開也不會跑回來"""
        self._buffer.clear()
        self._entries.clear()
        self._counts.clear()
        self._rebuild()

    def copy_visible(self) -> None:
        text = self.visible_text()
        if text:
            QGuiApplication.clipboard().setText(text)

    def detach(self) -> None:
        self._bridge.detach()

    # ---------- 記錄 ----------

    def _store(self, entry: LogEntry) -> bool:
        """加入記錄清單；超過上限時修剪並回傳 True（需要重建文字區）"""
        self._entries.append(entry)
        self._last_seq = entry.seq
        self._counts[entry.level] += 1
        if len(self._entries) <= TRIM_THRESHOLD:
            return False
        self._entries = self._entries[-DEFAULT_CAPACITY:]
        self._counts = Counter(e.level for e in self._entries)
        return True

    def _on_entry_added(self, entry: LogEntry) -> None:
        if entry.seq <= self._last_seq:
            return  # 已經從 snapshot 取得
        if self._store(entry):
            self._rebuild()
            return
        self._update_counts()
        if self._matches(entry):
            bar = self.view.verticalScrollBar()
            at_bottom = bar.value() >= bar.maximum()
            cursor = QTextCursor(self.view.document())
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._insert(cursor, entry)
            if at_bottom:
                bar.setValue(bar.maximum())

    def _matches(self, entry: LogEntry) -> bool:
        if entry.level not in self._levels:
            return False
        return not self._search or self._search in f"{entry.level} {entry.message}".lower()

    def _on_level_toggled(self, level: str, checked: bool) -> None:
        self._levels = self._levels | {level} if checked else self._levels - {level}
        self._rebuild()
        self.levelsChanged.emit(self._levels)

    def _apply_search(self) -> None:
        self._search = self.search_edit.text().strip().lower()
        self._rebuild()

    # ---------- 繪製 ----------

    def _update_counts(self) -> None:
        for level, button in self.level_buttons.items():
            button.setText(f"{level} {self._counts[level]}")

    def _rebuild(self) -> None:
        bar = self.view.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum()
        self.view.clear()
        self._visible_count = 0
        cursor = QTextCursor(self.view.document())
        cursor.beginEditBlock()
        for entry in self._entries:
            if self._matches(entry):
                self._insert(cursor, entry)
        cursor.endEditBlock()
        if at_bottom:
            bar.setValue(bar.maximum())
        self._update_counts()

    def _insert(self, cursor: QTextCursor, entry: LogEntry) -> None:
        time_text, level_text, message = format_entry(entry)
        color = self._palette.level(entry.level)
        if self._visible_count:
            cursor.insertText("\n", self._format(self._palette.text))
        cursor.insertText(time_text, self._format(self._palette.text_muted))
        cursor.insertText(level_text, self._format(color.fg, bold=True))
        cursor.insertText(message, self._format(self._message_color(entry.level)))
        self._visible_count += 1

    def _message_color(self, level: str) -> str:
        if level in MUTED_LEVELS:
            return self._palette.text_muted
        if level in PLAIN_LEVELS:
            return self._palette.text
        return self._palette.level(level).fg

    @staticmethod
    def _format(color: str, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        return fmt
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_log_console.py -q`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息：`新增主控台面板 ConsolePanel：7 等級篩選、搜尋、清除、複製與自動捲動`

```bash
git add src/ui/log_console.py tests/test_log_console.py
git commit -F .git/COMMIT_MSG_TMP.txt && rm .git/COMMIT_MSG_TMP.txt
```

---

### Task 5: 主視窗整合

**Files:**
- Modify: `src/ui/icons.py`（新增 `console_icon`）
- Modify: `src/ui/main_window.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: Task 1 `LogBuffer`；Task 3 `ConsoleSettings`；Task 4 `ConsolePanel`
- Produces:
  - `MainWindow(store, service, theme, about, default_timeout, settings_path, parent=None, *, settings: QSettings | None = None, log_buffer: LogBuffer | None = None)`
  - 屬性：`console_panel`、`console_button`、`right_splitter`
  - 方法：`toggle_console()`、`set_console_visible(visible: bool)`
  - 常數：`CONSOLE_SHORTCUT = "Ctrl+\`"`

- [ ] **Step 1: 寫失敗測試**

`tests/test_main_window.py`：

import 區加入：

```python
from src.ui.log_console import ConsoleSettings
from src.core.log_buffer import LogBuffer
from loguru import logger
```

`env` fixture 改為（保留原有內容，新增 `qsettings`、`log_buffer` 與 sink 註冊／移除）：

```python
@pytest.fixture
def env(qapp, tmp_path):
    service = FakeService()
    qsettings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    theme = ThemeManager(qapp, qsettings)
    theme.apply()
    settings_path = write_settings(tmp_path / "ws_tool.yaml")
    log_buffer = LogBuffer()
    handler_id = log_buffer.attach()
    ctx = SimpleNamespace(
        store=ConnectionStore(tmp_path / "connections.profile"), service=service, theme=theme,
        settings_path=settings_path, qsettings=qsettings, log_buffer=log_buffer,
    )
    windows = []

    def make(store=None):
        window = MainWindow(
            store or ctx.store, service, theme, ABOUT, default_timeout=30, settings_path=settings_path,
            settings=qsettings, log_buffer=log_buffer,
        )
        window._confirm = lambda title, text: True
        window._ask_unsaved = lambda: QMessageBox.StandardButton.Discard
        windows.append(window)
        return window

    ctx.make = make
    yield ctx
    if service.gate is not None:
        service.gate.set()
    for window in windows:
        window._confirm = lambda title, text: True
        window._ask_unsaved = lambda: QMessageBox.StandardButton.Discard
        window.close()
        window.deleteLater()
    logger.remove(handler_id)
```

`test_f11_opens_settings_page_and_locks_workspace` 中 `assert not window.sidebar.isEnabled()` 改為 `assert not window.connection_list.isEnabled()`；`test_f11_again_returns_to_workspace` 中 `assert window.sidebar.isEnabled()` 改為 `assert window.connection_list.isEnabled()`。

檔尾新增：

```python
# ---------- 主控台 ----------

def footer_buttons(window):
    footer = window.sidebar.layout().itemAt(2).layout()
    return [footer.itemAt(i).widget() for i in range(footer.count()) if footer.itemAt(i).widget()]


def test_console_button_is_after_about_and_panel_hidden_by_default(env):
    window = env.make()
    assert footer_buttons(window) == [window.theme_button, window.about_button, window.console_button]
    assert window.console_button.text() == "主控台"
    assert window.console_panel.isHidden()
    assert not window.console_button.isChecked()


def test_footer_buttons_fit_sidebar(env):
    window = env.make()
    footer = window.sidebar.layout().itemAt(2).layout()
    buttons = footer_buttons(window)
    needed = sum(b.sizeHint().width() for b in buttons) + footer.spacing() * (len(buttons) - 1)
    margins = window.sidebar.layout().contentsMargins()
    assert needed <= window.sidebar.width() - margins.left() - margins.right()


def test_console_toggles_via_button_shortcut_and_close(env):
    window = env.make()
    window.console_button.click()
    assert not window.console_panel.isHidden() and window.console_button.isChecked()
    assert ConsoleSettings(env.qsettings).visible() is True
    press_shortcut(window, "Ctrl+`")
    assert window.console_panel.isHidden() and not window.console_button.isChecked()
    press_shortcut(window, "Ctrl+`")
    window.console_panel.close_button.click()
    assert window.console_panel.isHidden() and not window.console_button.isChecked()
    assert ConsoleSettings(env.qsettings).visible() is False


def test_console_restores_visibility_levels_and_height(env):
    saved = ConsoleSettings(env.qsettings)
    saved.set_visible(True)
    saved.set_levels({"ERROR", "CRITICAL"})
    saved.set_height(300)
    window = env.make()
    window.resize(1100, 700)
    window.show()
    wait_until(lambda: window.console_panel.height() > 0)
    assert not window.console_panel.isHidden() and window.console_button.isChecked()
    assert window.console_panel.levels() == {"ERROR", "CRITICAL"}
    assert abs(window.console_panel.height() - 300) <= 10


def test_console_level_toggle_is_saved(env):
    window = env.make()
    window.console_panel.level_buttons["ERROR"].click()
    assert ConsoleSettings(env.qsettings).levels() == {"DEBUG", "INFO", "SUCCESS", "ERROR"}


def test_console_height_saved_when_hidden(env):
    window = env.make()
    window.resize(1100, 700)
    window.show()
    window.set_console_visible(True)
    wait_until(lambda: window.console_panel.height() > 0)
    window.right_splitter.setSizes([400, 260])
    expected = window.right_splitter.sizes()[1]
    window.set_console_visible(False)
    assert ConsoleSettings(env.qsettings).height() == expected


def test_console_usable_on_settings_page(env):
    window = env.make()
    open_settings(window)
    press_shortcut(window, "Ctrl+`")
    assert not window.console_panel.isHidden()
    assert window.console_button.isEnabled() and window.theme_button.isEnabled()
    assert not window.connection_list.isEnabled()
    assert shortcut_enabled(window, "Ctrl+`")


def test_console_shows_load_and_run_logs(env):
    seed(env.store)
    window = env.make()
    window.load_button.click()
    wait_until(lambda: "讀取完成" in window.console_panel.visible_text())
    window.run_button.click()
    wait_until(lambda: "請求完成" in window.console_panel.visible_text())
    text = window.console_panel.visible_text()
    assert "INFO     讀取 WSDL · URL=http://prod/ws?WSDL" in text
    assert "SUCCESS  讀取完成 · 2 個方法" in text
    assert "INFO     執行請求" in text
    assert "SUCCESS  請求完成" in text


def test_console_logs_cancel(env):
    seed(env.store)
    env.service.gate = threading.Event()
    window = env.make()
    window.load_button.click()
    window.load_button.click()  # 進行中再按一次 = 取消
    wait_until(lambda: "已取消讀取" in window.console_panel.visible_text())


def test_console_follows_theme(env):
    window = env.make()
    env.theme.set_mode(ThemeMode.DARK)
    assert window.console_panel._palette is DARK
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_main_window.py -q`
Expected: FAIL，`TypeError: MainWindow.__init__() got an unexpected keyword argument 'settings'`

- [ ] **Step 3: 新增 `console_icon()`**

`src/ui/icons.py` 常數區加：

```python
CONSOLE_GRADIENT = ("#10B981", "#0D9488")
```

檔尾加：

```python
def console_icon() -> QIcon:
    """主控台：漸層圓角方塊與白色 >_ 提示字元"""
    pixmap, painter = _canvas()
    painter.setBrush(_gradient(CONSOLE_GRADIENT))
    painter.drawRoundedRect(QRectF(4, 8, 56, 48), 10, 10)
    pen = QPen(QColor("#FFFFFF"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolyline([QPointF(16, 22), QPointF(26, 32), QPointF(16, 42)])
    painter.drawLine(QPointF(32, 43), QPointF(46, 43))
    painter.end()
    return QIcon(pixmap)
```

並把 `QPen` 加進 `from PySide6.QtGui import ...`。

- [ ] **Step 4: 修改 `main_window.py`**

import 區：

```python
from PySide6.QtCore import QSettings, QSize, Qt, Slot
...
from src.core.log_buffer import LogBuffer
...
from src.ui.icons import about_icon, console_icon, theme_icon
from src.ui.log_console import ConsolePanel, ConsoleSettings
```

常數區（`FOOTER_ICON_SIZE` 附近）加：

```python
FOOTER_SPACING = 6  # 三顆 footer 按鈕要塞進 236 px
CONSOLE_SHORTCUT = "Ctrl+`"
CONSOLE_MIN_HEIGHT = 120
```

`__init__` 簽名與開頭：

```python
    def __init__(self, store: ConnectionStore, service, theme: ThemeManager, about: AboutInfo,
                 default_timeout: int, settings_path: Path, parent=None, *,
                 settings: QSettings | None = None, log_buffer: LogBuffer | None = None):
        super().__init__(parent)
        ...（原有欄位）
        self._console_settings = ConsoleSettings(settings)
        self._log_buffer = log_buffer if log_buffer is not None else LogBuffer()
```

（兩行放在 `self._tasks = {}` 之後、`self._build_ui(...)` 之前。）

`__init__` 結尾 `self._load_initial_connections()` 之後加：

```python
        self.set_console_visible(self._console_settings.visible())
```

`_build_ui` 整個改為（原本的 `root.addWidget(self.sidebar)`、`root.addWidget(self.stack, 1)` 由下面取代）：

```python
    def _build_ui(self, default_timeout: int) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = self._build_sidebar()
        self.workspace = self._build_workspace(default_timeout)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.workspace)
        self.settings_page: SettingsPage | None = None  # 首次按 F11 才載入外掛並建立
        self.console_panel = ConsolePanel(self._log_buffer, self._theme.palette, self._console_settings.levels())
        self.console_panel.setMinimumHeight(CONSOLE_MIN_HEIGHT)
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.right_splitter.setChildrenCollapsible(False)
        self.right_splitter.addWidget(self.stack)
        self.right_splitter.addWidget(self.console_panel)
        self.right_splitter.setStretchFactor(0, 1)  # 視窗放大時多出的空間給上方，面板維持高度
        self.right_splitter.setStretchFactor(1, 0)
        self.console_panel.hide()
        root.addWidget(self.sidebar)
        root.addWidget(self.right_splitter, 1)
        self.setCentralWidget(central)

        self.status_state = QLabel()
        self.status_state.setObjectName("StatusState")
        self.status_detail = QLabel()
        self.status_detail.setObjectName("StatusDetail")
        self.statusBar().addWidget(self.status_state)
        self.statusBar().addWidget(self.status_detail, 1)
```

`_build_sidebar` footer 區塊改為：

```python
        self.theme_button = styled_button("主題", "footer", "切換淺色 / 深色主題")
        self.theme_button.setMenu(self._build_theme_menu())
        self.about_button = styled_button("關於", "footer")
        self.console_button = styled_button("主控台", "footer", f"開關主控台 ({CONSOLE_SHORTCUT})")
        self.console_button.setCheckable(True)
        for button, icon in (
            (self.theme_button, theme_icon()), (self.about_button, about_icon()), (self.console_button, console_icon()),
        ):
            button.setIcon(icon)
            button.setIconSize(QSize(FOOTER_ICON_SIZE, FOOTER_ICON_SIZE))
        footer = QHBoxLayout()
        footer.setSpacing(FOOTER_SPACING)
        footer.addWidget(self.theme_button)
        footer.addWidget(self.about_button)
        footer.addWidget(self.console_button)
        footer.addStretch(1)
```

`_build_shortcuts` 的全域快捷鍵迴圈改為：

```python
        for key, handler in (("F11", self._toggle_settings), ("Esc", self._on_escape), (CONSOLE_SHORTCUT, self.toggle_console)):
```

`_connect_signals` 結尾加：

```python
        self.console_button.clicked.connect(self.toggle_console)
        self.console_panel.closeRequested.connect(lambda: self.set_console_visible(False))
        self.console_panel.levelsChanged.connect(self._console_settings.set_levels)
```

在「設定頁」區段之前新增「主控台」區段：

```python
    # ---------- 主控台 ----------

    @Slot()
    def toggle_console(self) -> None:
        self.set_console_visible(self.console_panel.isHidden())

    def set_console_visible(self, visible: bool) -> None:
        if not visible and not self.console_panel.isHidden():
            self._remember_console_height()
        self.console_panel.setVisible(visible)
        self.console_button.setChecked(visible)
        if visible:
            height = self._console_settings.height()
            total = sum(self.right_splitter.sizes()) or self.right_splitter.height()
            self.right_splitter.setSizes([max(total - height, 1), height])
        self._console_settings.set_visible(visible)

    def _remember_console_height(self) -> None:
        height = self.right_splitter.sizes()[1]
        if height > 0:
            self._console_settings.set_height(height)
```

`_set_settings_mode` 內 `self.sidebar.setEnabled(not active)` 改為：

```python
        self.connection_list.setEnabled(not active)
```

docstring 改為：`"""設定頁顯示期間停用連線清單與工作區快捷鍵，避免在看不到的地方送出請求；footer 按鈕（含主控台）維持可用"""`

`_on_theme_changed` 結尾加：

```python
        self.console_panel.set_palette(palette)
```

補記錄點：

- `_on_load_clicked`：`self._start("load", ...)` 之前加 `logger.info("讀取 WSDL · URL={}", url)`
- `_cancel` 改為：

```python
    def _cancel(self) -> None:
        logger.info("已取消{}", "讀取" if self._pending[0] == "load" else "執行")
        self._finish()
        self._set_status("", "已取消")
        self._notify("info", "已取消。背景請求會在逾時後自動結束")
```

- `_on_methods_loaded`：`self._store.set_methods(uuid, methods)` 之前加 `logger.success("讀取完成 · {} 個方法", len(methods))`
- `_on_call_finished`：`logger.info(` 改為 `logger.success(`
- `closeEvent` 在 `self._commit_fields()` 之前加：

```python
        logger.info("程式關閉")
        if not self.console_panel.isHidden():
            self._remember_console_height()
        self.console_panel.detach()
```

- [ ] **Step 5: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_main_window.py -q`
Expected: 全部 PASS

- [ ] **Step 6: 跑全部測試確認無回歸**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

訊息：`主視窗加入主控台面板：側欄按鈕與 Ctrl+\` 切換、狀態存入 settings.ini、補上讀取與取消記錄`

```bash
git add src/ui/icons.py src/ui/main_window.py tests/test_main_window.py
git commit -F .git/COMMIT_MSG_TMP.txt && rm .git/COMMIT_MSG_TMP.txt
```

---

### Task 6: 程式進入點 `setup_logging` 與啟動記錄

**Files:**
- Modify: `src/ws_tool.py`
- Test: `tests/test_entry_point.py`

**Interfaces:**
- Consumes: Task 1 `LogBuffer`；Task 5 `MainWindow(..., settings=, log_buffer=)`
- Produces: `setup_logging(log_dir: Path, config) -> tuple[LogBuffer, list[int]]`（config 需有 `app_log_retention`、`app_log_level`）

- [ ] **Step 1: 寫失敗測試**

`tests/test_entry_point.py` 檔尾新增（檔案已 import `logger`；另在頂端加 `from types import SimpleNamespace`）：

```python
def test_setup_logging_buffer_gets_all_levels_but_run_log_follows_config(tmp_path):
    from src.ws_tool import setup_logging

    config = SimpleNamespace(app_log_retention="1 day", app_log_level="info")
    buffer, handler_ids = setup_logging(tmp_path / "logs", config)
    try:
        logger.trace("追蹤訊息")
        logger.debug("除錯訊息")
        logger.info("一般訊息")
    finally:
        for handler_id in handler_ids:
            logger.remove(handler_id)
    assert [e.message for e in buffer.snapshot()][-3:] == ["追蹤訊息", "除錯訊息", "一般訊息"]
    text = (tmp_path / "logs" / "run.log").read_text(encoding="utf-8")
    assert "一般訊息" in text
    assert "除錯訊息" not in text and "追蹤訊息" not in text
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_entry_point.py -q`
Expected: FAIL，`ImportError: cannot import name 'setup_logging'`

- [ ] **Step 3: 實作**

`src/ws_tool.py` import 區加：

```python
from src.core.log_buffer import LogBuffer  # noqa: E402
```

`resolve_app_dirs` 之後新增：

```python
def setup_logging(log_dir: Path, config) -> tuple[LogBuffer, list[int]]:
    """run.log 依設定檔等級記錄；主控台暫存一律收集 TRACE 以上，回傳暫存與新增的 handler id"""
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logger.add(
        os.path.join(log_dir, "run.log"),
        retention=config.app_log_retention,
        level=str(config.app_log_level).upper(),
    )
    buffer = LogBuffer()
    return buffer, [file_handler, buffer.attach()]
```

`main()` 開頭改為：

```python
def main() -> int:
    config = WebServiceConfig()
    log_dir, data_dir = resolve_app_dirs(config)
    log_buffer, _handlers = setup_logging(log_dir, config)
    logger.info("程式啟動 · {} {}", config.app_name, config.app_version)
    logger.debug("設定檔={} · 連線資料={} · 記錄={}", config.config_path, data_dir, log_dir)
```

（刪除原本的 `log_dir.mkdir(...)` 與 `logger.add(...)`。）

`MainWindow(...)` 呼叫改為：

```python
    window = MainWindow(
        store, SoapService(), theme, about,
        default_timeout=config.app_timeout, settings_path=config.config_path,
        settings=settings, log_buffer=log_buffer,
    )
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_entry_point.py -q`
Expected: 全部 PASS

- [ ] **Step 5: 跑全部測試**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 全部 PASS（298 ＋ 新增案例）

- [ ] **Step 6: Commit**

訊息：`程式進入點拆出 setup_logging 並把記錄暫存接到主控台，補上啟動記錄`

```bash
git add src/ws_tool.py tests/test_entry_point.py
git commit -F .git/COMMIT_MSG_TMP.txt && rm .git/COMMIT_MSG_TMP.txt
```

---

### Task 7: 實機驗證

**Files:** 無程式修改（發現問題時回到對應 Task 修正並補測試）

- [ ] **Step 1: 啟動程式**

Run: `uv run python src/ws_tool.py`

- [ ] **Step 2: 逐項確認**

- 側欄底部三顆按鈕（主題、關於、主控台）同列、沒有被截斷
- 按「主控台」或 Ctrl+` 開關面板，按鈕勾選狀態同步；✕ 可關閉
- 開啟後看得到「程式啟動 · …」；讀取 WSDL、執行請求後出現 INFO／SUCCESS 記錄
- 7 顆等級鈕顏色與設計文件 §6.1 一致，淺色／深色主題切換後顏色跟著變
- 搜尋、清除、複製正常；拖曳分割線調整高度，關閉再開啟高度保留
- F11 設定頁中主控台仍可開關、連線清單停用
- 關閉程式再啟動，面板開關狀態、高度、等級篩選都還原；`settings.ini` 出現 `[console]` 區段

- [ ] **Step 3: 回報結果**

實機驗證的結果（包括不符合預期的地方）以繁體中文回報使用者；不要 push。
