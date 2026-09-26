# 工具參數設定編輯器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 F11 把右側工作區換成 pyqtgraph ParameterTree 設定頁，視覺化編輯 `ws_tool.yaml`，保留註解寫回並熱重載 app 基本參數；編輯器以外掛資料夾另外打包。

**Architecture:** 核心邏輯 `src/config/app_settings.py`（不依賴 Qt）負責解析 yaml、以註解作標籤、逐行替換值寫回、分類變更。外掛 `plugins/settings_editor/settings_editor.py` 只把欄位清單轉成 ParameterTree，不 import `src.*`。主程式以 `src/ui/plugin_loader.py` 在執行期載入外掛，`src/ui/settings_page.py` 提供按鈕列與通知，`MainWindow` 以 `QStackedWidget` 切換並熱重載。

**Tech Stack:** Python 3.14、PySide6 6.11、PyYAML、pyqtgraph 0.14.0 + numpy 2.5.3（僅 dev 群組與外掛）、pytest、PyInstaller、uv

**Spec:** `docs/superpowers/specs/2026-09-26-settings-editor-design.md`

## Global Constraints

- 所有原始碼 UTF-8，檔案開頭 `# -*- coding: utf-8 -*-`，模組頂端一段繁體中文 docstring 說明職責
- 註解、docstring、UI 文字、commit 訊息一律繁體中文；識別字用英文
- `src/config/app_settings.py` 不可 import PySide6；`plugins/settings_editor/settings_editor.py` 不可 import `src.*`
- 主程式 `pyproject.toml` 的 `dependencies` 不可加入 pyqtgraph／numpy；只加到 `dev` 群組，版本固定 `pyqtgraph==0.14.0`、`numpy==2.5.3`
- 熱重載欄位固定為 `app.name`、`app.version`、`app.copyright`、`app.img`、`app.timeout`；其餘葉節點皆為「需重新啟動」
- `app.timeout` 範圍 5～120（`TIMEOUT_MIN`、`TIMEOUT_MAX` 定義在 `src/config/app_settings.py`，`main_window.py` 改為 import）
- `app.log.level` 選項：`trace`、`debug`、`info`、`success`、`warning`、`error`、`critical`
- 寫回時未變更的內容逐位元組保留（含註解、空行、行尾註解、`\r\n`、UTF-8 BOM）
- 顏色一律來自 `src/ui/theme.py` 的色票；按鈕沿用 `variant` property + `HoverLift`
- 測試指令：`.venv/Scripts/python -m pytest`（或 `uv run pytest`）；Qt 測試已由 `tests/conftest.py` 設定 offscreen
- commit 訊息含中文：先用 Write 工具寫入暫存檔（例如 `C:\Users\game\AppData\Local\Temp\ws_commit_msg.txt`），再 `git commit -F <該檔>`；不要用 heredoc／printf。訊息結尾加 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 不要 push

---

## 檔案結構

| 檔案 | 動作 | 職責 |
|---|---|---|
| `src/config/app_settings.py` | 新增 | 解析 ws_tool.yaml、標籤、型別、保留註解寫回、變更分類、熱重載值 |
| `plugins/settings_editor/settings_editor.py` | 新增 | 外掛：`SettingsTree`（ParameterTree 包裝） |
| `plugins/settings_editor/gen_host_imports.py` | 新增 | 產生主程式需額外打包的模組清單 |
| `plugins/settings_editor/host_imports.txt` | 新增（產生） | hiddenimports 清單，納入版控 |
| `plugins/settings_editor/build_plugin.py` | 新增 | 建置 `dist/plugins/settings_editor/` |
| `src/ui/plugin_loader.py` | 新增 | 尋找並載入外掛 |
| `src/ui/settings_page.py` | 新增 | 設定頁：按鈕列、通知列、編輯器或佔位畫面 |
| `src/ui/effects.py` | 修改 | 新增 `styled_button`（由 main_window 的 `_button` 移來） |
| `src/ui/theme.py` | 修改 | 新增 `PageTitle`、`Placeholder` QSS |
| `src/ui/main_window.py` | 修改 | `settings_path`、`apply_app_settings`、QStackedWidget、F11／Esc、未存檔詢問 |
| `src/config/web_service_config.py` | 修改 | 新增 `config_path` |
| `src/ws_tool.py` | 修改 | 傳 `settings_path` |
| `build.bat`、`README.md`、`AGENTS.md`、`pyproject.toml`、`uv.lock` | 修改 | 打包、文件、依賴 |
| `tests/helpers.py` | 修改 | 共用 `SETTINGS_YAML`、`write_settings` |
| `tests/test_app_settings.py`、`tests/test_settings_editor_plugin.py`、`tests/test_plugin_loader.py`、`tests/test_settings_page.py`、`tests/test_plugin_build.py` | 新增 | 對應測試 |
| `tests/test_main_window.py`、`tests/test_entry_point.py` | 修改 | 補充測試 |

---

### Task 1: 設定文件核心 `app_settings.py`

**Files:**
- Create: `src/config/app_settings.py`
- Modify: `tests/helpers.py`（檔尾新增）
- Test: `tests/test_app_settings.py`

**Interfaces:**
- Consumes: 無
- Produces:
  - 常數 `TIMEOUT_MIN = 5`、`TIMEOUT_MAX = 120`、`LOG_LEVELS: tuple[str, ...]`、`HOT_RELOAD_KEYS: tuple[str, ...]`
  - `class SettingsError(Exception)`
  - `@dataclass(frozen=True) SettingField(key: str, label: str, kind: str, value: object = None, limits: tuple | None = None)`
  - `@dataclass(frozen=True) SettingsChanges(hot: tuple[str, ...], restart: tuple[str, ...])`
  - `@dataclass(frozen=True) AppSettings(name: str, version: str, copyright: str, img: str, timeout: int)`
  - `class SettingsDocument`：`load(path) -> SettingsDocument`（classmethod）、屬性 `path: Path`、`fields: list[SettingField]`、`values() -> dict[str, object]`、`app_settings() -> AppSettings`、`changes(new_values: dict) -> SettingsChanges`、`render(new_values: dict) -> str`、`save(new_values: dict) -> SettingsDocument`
  - `tests/helpers.py`：`SETTINGS_YAML: str`、`write_settings(path: Path, text: str = SETTINGS_YAML, newline: str = "\n", bom: bool = False) -> Path`

- [ ] **Step 1: 在 `tests/helpers.py` 檔尾加入共用的設定檔範本**

```python
SETTINGS_YAML = (
    "app:\n"
    "  # Name of the application\n"
    "  name: \"TIPTOP WebService Tool\"\n"
    "  # Version of the application\n"
    "  version: \"v3.0.0\"\n"
    "  # Description of the application\n"
    "  copyright: \"Copyright 2026 GameStudio.\"\n"
    "  # APP icon location\n"
    "  img: \"assets/app_icon.ico\"\n"
    "  # APP loading timeout value (seconds)\n"
    "  timeout: 120\n"
    "\n"
    "  # Log path of the application\n"
    "  log:\n"
    "    path: \"app_data/logs\"\n"
    "    level: info\n"
    "    retention: \"10 days\"\n"
    "  # 服務配置檔位置\n"
    "  connection:\n"
    "    path: \"app_data\"\n"
    "    profile: \"connections.profile\"\n"
)


def write_settings(path, text=SETTINGS_YAML, newline="\n", bom=False):
    """寫出測試用 ws_tool.yaml；可指定換行符號與是否加 UTF-8 BOM"""
    data = text.replace("\n", newline).encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)
    return path
```

- [ ] **Step 2: 寫失敗的測試 `tests/test_app_settings.py`**

```python
# -*- coding: utf-8 -*-
from pathlib import Path

import pytest

from src.config import app_settings
from src.config.app_settings import (
    HOT_RELOAD_KEYS,
    LOG_LEVELS,
    TIMEOUT_MAX,
    TIMEOUT_MIN,
    AppSettings,
    SettingsChanges,
    SettingsDocument,
    SettingsError,
)
from tests.helpers import SETTINGS_YAML, write_settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def path(tmp_path):
    return write_settings(tmp_path / "ws_tool.yaml")


@pytest.fixture
def doc(path):
    return SettingsDocument.load(path)


def field(doc, key):
    return next(f for f in doc.fields if f.key == key)


def load_text(tmp_path, text):
    return SettingsDocument.load(write_settings(tmp_path / "t.yaml", text))


def test_fields_follow_document_order(doc):
    assert [f.key for f in doc.fields] == [
        "app", "app.name", "app.version", "app.copyright", "app.img", "app.timeout",
        "app.log", "app.log.path", "app.log.level", "app.log.retention",
        "app.connection", "app.connection.path", "app.connection.profile",
    ]


def test_labels_come_from_comment_directly_above(doc):
    assert field(doc, "app.name").label == "Name of the application"
    assert field(doc, "app.log").label == "Log path of the application"
    assert field(doc, "app.connection").label == "服務配置檔位置"
    assert field(doc, "app.log.path").label == "path"  # 無註解時用 key 名稱
    assert field(doc, "app").label == "app"


def test_multiline_comment_joined_and_blank_line_breaks_block(tmp_path):
    doc = load_text(tmp_path, "a:\n  # 第一行\n  # 第二行\n  b: 1\n  # 孤立註解\n\n  c: 2\n")
    assert field(doc, "a.b").label == "第一行\n第二行"
    assert field(doc, "a.c").label == "c"


def test_kinds_and_special_fields(doc, tmp_path):
    assert field(doc, "app").kind == "group"
    assert field(doc, "app.name").kind == "str"
    timeout = field(doc, "app.timeout")
    assert (timeout.kind, timeout.value, timeout.limits) == ("int", 120, (TIMEOUT_MIN, TIMEOUT_MAX))
    level = field(doc, "app.log.level")
    assert (level.kind, level.value, level.limits) == ("list", "info", LOG_LEVELS)
    other = load_text(tmp_path, "a:\n  enabled: true\n  ratio: 1.5\n  count: 3\n")
    assert [(f.kind, f.value) for f in other.fields[1:]] == [("bool", True), ("float", 1.5), ("int", 3)]


def test_uppercase_log_level_shown_lowercase_and_not_rewritten(tmp_path):
    text = SETTINGS_YAML.replace("level: info", "level: INFO")
    doc = load_text(tmp_path, text)
    assert field(doc, "app.log.level").value == "info"
    assert doc.changes({"app.log.level": "info"}) == SettingsChanges(hot=(), restart=())
    assert doc.render({"app.log.level": "info"}) == text


def test_values_and_app_settings(doc):
    assert doc.values()["app.connection.profile"] == "connections.profile"
    assert "app.log" not in doc.values()
    assert doc.app_settings() == AppSettings(
        name="TIPTOP WebService Tool", version="v3.0.0", copyright="Copyright 2026 GameStudio.",
        img="assets/app_icon.ico", timeout=120,
    )


def test_render_without_changes_is_identical(doc):
    assert doc.render({}) == SETTINGS_YAML
    assert doc.render(doc.values()) == SETTINGS_YAML


def test_repo_config_loads_and_round_trips():
    path = ROOT / "src" / "app_data" / "ws_tool.yaml"
    doc = SettingsDocument.load(path)
    assert doc.render({}) == path.read_bytes().decode("utf-8")


def test_save_changes_only_values_and_keeps_comments(doc, path):
    doc.save({"app.timeout": 60, "app.log.level": "debug"})
    expected = SETTINGS_YAML.replace("timeout: 120", "timeout: 60").replace("level: info", "level: debug")
    assert path.read_text(encoding="utf-8") == expected


def test_crlf_and_bom_preserved(tmp_path):
    path = write_settings(tmp_path / "ws_tool.yaml", newline="\r\n", bom=True)
    SettingsDocument.load(path).save({"app.timeout": 30})
    expected = SETTINGS_YAML.replace("timeout: 120", "timeout: 30").replace("\n", "\r\n")
    assert path.read_bytes() == b"\xef\xbb\xbf" + expected.encode("utf-8")


def test_quote_styles_and_trailing_comment(tmp_path):
    doc = load_text(tmp_path, "a:\n  d: \"x\"\n  s: 'x'\n  p: x\n  q: x\n  t: x  # 行尾\n")
    text = doc.render({"a.d": 'A "B"', "a.s": "it's", "a.p": "123", "a.q": "hello world", "a.t": "y"})
    assert text == (
        "a:\n"
        "  d: \"A \\\"B\\\"\"\n"
        "  s: 'it''s'\n"
        "  p: \"123\"\n"
        "  q: hello world\n"
        "  t: y  # 行尾\n"
    )


@pytest.mark.parametrize("value", ["true", "a: b", "x # y", " 前後空白 ", ""])
def test_plain_string_that_would_change_meaning_gets_quoted(tmp_path, value):
    doc = load_text(tmp_path, "a:\n  p: x\n")
    text = doc.render({"a.p": value})
    assert SettingsDocument.load(write_settings(tmp_path / "out.yaml", text)).values()["a.p"] == value
    assert text.startswith("a:\n  p: \"")


def test_bool_float_int_output(tmp_path):
    doc = load_text(tmp_path, "a:\n  enabled: true\n  ratio: 1.5\n  count: 3\n")
    assert doc.render({"a.enabled": False, "a.ratio": 2, "a.count": 4}) == (
        "a:\n  enabled: false\n  ratio: 2.0\n  count: 4\n"
    )


@pytest.mark.parametrize("values", [
    {"app.timeout": TIMEOUT_MAX + 1},
    {"app.timeout": TIMEOUT_MIN - 1},
    {"app.timeout": "60"},
    {"app.timeout": True},
    {"app.name": 1},
    {"app.log.level": "loud"},
    {"app.unknown": 1},
    {"app": "x"},
])
def test_invalid_values_raise(doc, values):
    with pytest.raises(SettingsError):
        doc.render(values)
    with pytest.raises(SettingsError):
        doc.changes(values)


def test_changes_are_classified_in_document_order(doc):
    changes = doc.changes({
        "app.connection.profile": "x.profile",
        "app.timeout": 60,
        "app.log.level": "debug",
        "app.name": "新名稱",
        "app.version": "v3.0.0",  # 與現值相同，不算變更
    })
    assert changes == SettingsChanges(hot=("app.name", "app.timeout"), restart=("app.log.level", "app.connection.profile"))
    assert HOT_RELOAD_KEYS == ("app.name", "app.version", "app.copyright", "app.img", "app.timeout")


@pytest.mark.parametrize("text", [
    "a:\n  - 1\n",
    "a: [1, 2]\n",
    "a: {b: 1}\n",
    "a: &x 1\nb: *x\n",
    "a: |\n  t\n",
    "- 1\n",
    "a:\n",
    "a: 1\n  b: 2\n",
    "a: \"未結束\n",
])
def test_unsupported_syntax_raises(tmp_path, text):
    with pytest.raises(SettingsError):
        load_text(tmp_path, text)


def test_missing_file_raises(tmp_path):
    with pytest.raises(SettingsError):
        SettingsDocument.load(tmp_path / "none.yaml")


def test_save_failure_keeps_original_and_cleans_temp(doc, path, tmp_path, monkeypatch):
    def boom(*_args):
        raise OSError("磁碟已滿")

    monkeypatch.setattr(app_settings.os, "replace", boom)
    with pytest.raises(SettingsError, match="磁碟已滿"):
        doc.save({"app.timeout": 60})
    assert path.read_text(encoding="utf-8") == SETTINGS_YAML
    assert [p.name for p in tmp_path.iterdir()] == ["ws_tool.yaml"]


def test_render_validation_failure_raises(doc, monkeypatch):
    monkeypatch.setattr(app_settings, "_format", lambda value, style: "999")
    with pytest.raises(SettingsError, match="驗證失敗"):
        doc.render({"app.name": "x"})


def test_save_returns_reloaded_document(doc):
    new_doc = doc.save({"app.name": "新名稱"})
    assert new_doc is not doc
    assert new_doc.values()["app.name"] == "新名稱"
    assert new_doc.changes({"app.name": "新名稱"}) == SettingsChanges(hot=(), restart=())
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_app_settings.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'src.config.app_settings'`）

- [ ] **Step 4: 實作 `src/config/app_settings.py`**

```python
# -*- coding: utf-8 -*-
"""
工具參數設定檔（ws_tool.yaml）：讀取欄位與註解標籤、保留註解寫回、變更分類

只支援巢狀 mapping + 純量值；寫回時只替換有變更那一行的值，其餘字元原樣保留。
"""
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

FieldKind = Literal["group", "str", "int", "float", "bool", "list"]
TIMEOUT_MIN = 5
TIMEOUT_MAX = 120
LOG_LEVELS = ("trace", "debug", "info", "success", "warning", "error", "critical")
HOT_RELOAD_KEYS = ("app.name", "app.version", "app.copyright", "app.img", "app.timeout")
_BOM = "\ufeff"
_KEY_LINE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z_][\w-]*):(?P<rest>(?:[ \t].*)?)$")
_DOUBLE = re.compile(r'"(?:[^"\\]|\\.)*"')
_SINGLE = re.compile(r"'(?:[^']|'')*'")
_PLAIN = re.compile(r"[^#]*?(?=\s+#|\s*$)")


class SettingsError(Exception):
    """設定檔無法讀取、格式不支援，或要寫入的值不合法"""


@dataclass(frozen=True)
class SettingField:
    key: str                     # 以點分隔的路徑，例如 "app.log.level"
    label: str                   # 正上方註解；無註解時為 key 的最後一段
    kind: FieldKind
    value: object = None         # group 為 None
    limits: tuple | None = None  # int：(最小, 最大)；list：選項


@dataclass(frozen=True)
class SettingsChanges:
    hot: tuple[str, ...]       # 需熱重載的 key（依文件順序）
    restart: tuple[str, ...]   # 需重新啟動的 key


@dataclass(frozen=True)
class AppSettings:
    """可熱重載的五個參數"""
    name: str
    version: str
    copyright: str
    img: str
    timeout: int


@dataclass(frozen=True)
class _ValueSpan:
    line: int     # 行號（0 起算）
    start: int    # 值在該行（不含換行符號）的起訖位置
    end: int
    style: str    # '"'、"'" 或 ''（無引號）


def _split_value(rest: str, offset: int) -> tuple[int, int, str] | None:
    """從 key 冒號後的字串找出值的位置與引號風格；沒有值（group）回傳 None"""
    stripped = rest.lstrip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped[0] in "&*!|>[{":
        raise SettingsError(f"不支援的值寫法：{stripped}")
    start = offset + len(rest) - len(stripped)
    for pattern, style in ((_DOUBLE, '"'), (_SINGLE, "'")):
        if stripped[0] == style:
            match = pattern.match(stripped)
            if match is None:
                raise SettingsError(f"引號未結束：{stripped}")
            return start, start + match.end(), style
    match = _PLAIN.match(stripped)
    return start, start + match.end(), ""


def _scan(lines: list[str]) -> list[tuple[str, str, _ValueSpan | None]]:
    """逐行掃描，回傳 (key 路徑, 標籤, 值位置) 清單，依文件順序"""
    result = []
    stack: list[tuple[int, str]] = []
    comments: list[str] = []
    for index, raw in enumerate(lines):
        body = raw.rstrip("\r\n")
        stripped = body.strip()
        if not stripped:
            comments = []
            continue
        if stripped.startswith("#"):
            comments.append(stripped.lstrip("#").strip())
            continue
        match = _KEY_LINE.match(body)
        if match is None:
            raise SettingsError(f"第 {index + 1} 行格式不支援：{stripped}")
        indent = len(match["indent"])
        while stack and stack[-1][0] >= indent:
            stack.pop()
        key = ".".join([name for _, name in stack] + [match["key"]])
        span = _split_value(match["rest"], match.start("rest"))
        label = "\n".join(comments) or match["key"]
        result.append((key, label, _ValueSpan(index, *span) if span else None))
        if span is None:
            stack.append((indent, match["key"]))
        comments = []
    return result


def _flatten(data, prefix: str = "") -> dict[str, object]:
    """把巢狀 dict 攤平成 {"a.b": 值}，group 本身也列入（值為 dict）"""
    flat = {}
    for name, value in data.items():
        key = f"{prefix}{name}"
        flat[key] = value
        if isinstance(value, dict):
            flat.update(_flatten(value, key + "."))
    return flat


def _field_for(key: str, label: str, value) -> SettingField:
    if isinstance(value, dict):
        return SettingField(key, label, "group")
    if key == "app.timeout" and isinstance(value, int) and not isinstance(value, bool):
        return SettingField(key, label, "int", value, (TIMEOUT_MIN, TIMEOUT_MAX))
    if key == "app.log.level" and str(value).lower() in LOG_LEVELS:
        return SettingField(key, label, "list", str(value).lower(), LOG_LEVELS)
    if isinstance(value, bool):
        return SettingField(key, label, "bool", value)
    if isinstance(value, int):
        return SettingField(key, label, "int", value)
    if isinstance(value, float):
        return SettingField(key, label, "float", value)
    if isinstance(value, str):
        return SettingField(key, label, "str", value)
    raise SettingsError(f"{key} 的值型別不支援：{type(value).__name__}")


def _coerce(field: SettingField, value):
    """檢查要寫入的值是否符合欄位型別與範圍"""
    kind = field.kind
    ok = {
        "bool": isinstance(value, bool),
        "int": isinstance(value, int) and not isinstance(value, bool),
        "float": isinstance(value, (int, float)) and not isinstance(value, bool),
        "str": isinstance(value, str),
        "list": value in (field.limits or ()),
    }.get(kind, False)
    if not ok:
        raise SettingsError(f"{field.key} 的值不合法：{value!r}")
    if kind == "int" and field.limits and not field.limits[0] <= value <= field.limits[1]:
        raise SettingsError(f"{field.key} 必須介於 {field.limits[0]}～{field.limits[1]}")
    return float(value) if kind == "float" else value


def _plain_ok(text: str, value) -> bool:
    """無引號輸出後，PyYAML 解析回來是否仍是同一個值"""
    if not text or text != text.strip() or " #" in text or ": " in text or text.endswith(":"):
        return False
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return False
    return type(parsed) is type(value) and parsed == value


def _format(value, style: str) -> str:
    text = ("true" if value else "false") if isinstance(value, bool) else str(value)
    if style == "'":
        return "'" + text.replace("'", "''") + "'"
    if style == '"' or (isinstance(value, str) and not _plain_ok(text, value)):
        return json.dumps(text, ensure_ascii=False)  # JSON 字串即合法的 YAML 雙引號字串
    return text


class SettingsDocument:
    def __init__(self, path: Path, text: str, bom: bool):
        self.path = path
        self._bom = bom
        self._lines = text.splitlines(keepends=True)
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise SettingsError(f"設定檔格式錯誤：{exc}") from exc
        if not isinstance(data, dict):
            raise SettingsError("設定檔最外層必須是 mapping")
        self._raw = _flatten(data)
        scanned = _scan(self._lines)
        if [key for key, _, _ in scanned] != list(self._raw):
            raise SettingsError("設定檔含有不支援的語法（僅支援巢狀 mapping 與純量值）")
        self._spans: dict[str, _ValueSpan] = {}
        self.fields: list[SettingField] = []
        for key, label, span in scanned:
            field = _field_for(key, label, self._raw[key])
            if (field.kind == "group") != (span is None):
                raise SettingsError(f"{key} 格式不支援")
            if span is not None:
                self._spans[key] = span
            self.fields.append(field)
        self._by_key = {field.key: field for field in self.fields if field.kind != "group"}

    @classmethod
    def load(cls, path) -> "SettingsDocument":
        path = Path(path)
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise SettingsError(f"無法讀取設定檔：{exc}") from exc
        return cls(path, text.removeprefix(_BOM), text.startswith(_BOM))

    def values(self) -> dict[str, object]:
        return {key: field.value for key, field in self._by_key.items()}

    def app_settings(self) -> AppSettings:
        values = self.values()
        return AppSettings(
            name=str(values["app.name"]),
            version=str(values["app.version"]),
            copyright=str(values["app.copyright"]),
            img=str(values["app.img"]),
            timeout=int(values["app.timeout"]),
        )

    def _changed(self, new_values: dict[str, object]) -> dict[str, object]:
        changed = {}
        for key, value in new_values.items():
            field = self._by_key.get(key)
            if field is None:
                raise SettingsError(f"未知的設定：{key}")
            value = _coerce(field, value)
            if value != field.value or type(value) is not type(field.value):
                changed[key] = value
        return changed

    def changes(self, new_values: dict[str, object]) -> SettingsChanges:
        changed = self._changed(new_values)
        ordered = [key for key in self._by_key if key in changed]
        return SettingsChanges(
            hot=tuple(key for key in ordered if key in HOT_RELOAD_KEYS),
            restart=tuple(key for key in ordered if key not in HOT_RELOAD_KEYS),
        )

    def render(self, new_values: dict[str, object]) -> str:
        changed = self._changed(new_values)
        lines = list(self._lines)
        for key, value in changed.items():
            span = self._spans[key]
            body = lines[span.line].rstrip("\r\n")
            eol = lines[span.line][len(body):]
            lines[span.line] = body[:span.start] + _format(value, span.style) + body[span.end:] + eol
        text = "".join(lines)
        expected = {key: value for key, value in self._raw.items() if not isinstance(value, dict)}
        expected.update(changed)
        try:
            actual = _flatten(yaml.safe_load(text))
        except (yaml.YAMLError, AttributeError) as exc:
            raise SettingsError(f"寫回內容驗證失敗：{exc}") from exc
        for key, value in expected.items():
            if actual.get(key) != value or type(actual.get(key)) is not type(value):
                raise SettingsError(f"寫回內容驗證失敗：{key}")
        return text

    def save(self, new_values: dict[str, object]) -> "SettingsDocument":
        text = (_BOM if self._bom else "") + self.render(new_values)
        try:
            fd, temp = tempfile.mkstemp(prefix=".ws_tool-", suffix=".tmp", dir=self.path.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(text.encode("utf-8"))
                os.replace(temp, self.path)
            except BaseException:
                Path(temp).unlink(missing_ok=True)
                raise
        except OSError as exc:
            raise SettingsError(f"無法寫入設定檔：{exc}") from exc
        return SettingsDocument.load(self.path)
```

- [ ] **Step 5: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_app_settings.py -q`
Expected: 全部 PASS

- [ ] **Step 6: 全部測試無回歸**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

訊息（Write 到暫存檔後 `git commit -F`）：

```
新增工具參數設定檔核心：註解標籤、保留註解寫回、變更分類

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

```bash
git add src/config/app_settings.py tests/test_app_settings.py tests/helpers.py
git commit -F <暫存檔>
```

---

### Task 2: 外掛 `SettingsTree` 與 dev 依賴

**Files:**
- Modify: `pyproject.toml`、`uv.lock`（以 `uv add --dev` 產生）
- Create: `plugins/settings_editor/settings_editor.py`
- Test: `tests/test_settings_editor_plugin.py`

**Interfaces:**
- Consumes: `SettingsDocument`、`SettingField`、`LOG_LEVELS`（Task 1，僅測試使用）；`tests.helpers.write_settings`
- Produces（外掛模組 `settings_editor`）：
  - `API_VERSION = 1`
  - `class SettingsTree(QWidget)`：Signal `valueChanged()`；屬性 `tree: ParameterTree`（objectName `SettingsTree`）；`load(fields: list[dict]) -> None`（dict 鍵：`key`、`label`、`kind`、`value`、`limits`，即 `dataclasses.asdict(SettingField)`）；`values() -> dict[str, object]`；`parameters() -> Parameter`（根參數）；`set_palette(colors: dict[str, str]) -> None`（需含 `bg`、`surface`、`surface_hover`、`border`、`text`、`text_muted`，多餘的鍵忽略）

- [ ] **Step 1: 加入 dev 依賴**

Run: `uv add --dev pyqtgraph==0.14.0 numpy==2.5.3`
Expected: `pyproject.toml` 的 `[dependency-groups] dev` 多出兩行，`uv.lock` 更新；`dependencies` 不變。
確認：`.venv/Scripts/python -c "import pyqtgraph, numpy; print(pyqtgraph.__version__, numpy.__version__)"` 輸出 `0.14.0 2.5.3`

- [ ] **Step 2: 寫失敗的測試 `tests/test_settings_editor_plugin.py`**

```python
# -*- coding: utf-8 -*-
import importlib.util
from dataclasses import asdict, fields
from pathlib import Path

import pytest

from src.config.app_settings import LOG_LEVELS, SettingsDocument
from src.ui.theme import DARK, LIGHT
from tests.helpers import write_settings

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_FILE = ROOT / "plugins" / "settings_editor" / "settings_editor.py"


@pytest.fixture(scope="module")
def plugin():
    spec = importlib.util.spec_from_file_location("settings_editor_under_test", PLUGIN_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def doc(tmp_path):
    return SettingsDocument.load(write_settings(tmp_path / "ws_tool.yaml"))


@pytest.fixture
def tree(qapp, plugin, doc):
    widget = plugin.SettingsTree()
    widget.load([asdict(f) for f in doc.fields])
    yield widget
    widget.deleteLater()


def colors(palette):
    return {f.name: getattr(palette, f.name) for f in fields(palette) if f.name not in ("name", "xml")}


def test_api_version(plugin):
    assert plugin.API_VERSION == 1


def test_plugin_does_not_import_src():
    source = PLUGIN_FILE.read_text(encoding="utf-8")
    assert "from src" not in source and "import src" not in source


def test_labels_shown_with_key_tooltips(tree):
    items = {item.text(0): item.toolTip(0) for item in tree.tree.listAllItems() if item.text(0)}
    assert items["Name of the application"] == "app.name"
    assert items["服務配置檔位置"] == "app.connection"
    assert items["retention"] == "app.log.retention"


def test_values_match_document(tree, doc):
    assert tree.values() == doc.values()


def test_user_change_emits_value_changed_but_load_does_not(tree, doc):
    hits = []
    tree.valueChanged.connect(lambda: hits.append(1))
    tree.load([asdict(f) for f in doc.fields])
    assert hits == []
    tree.parameters().child("app", "timeout").setValue(60)
    assert hits == [1]
    assert tree.values()["app.timeout"] == 60


def test_int_limits_and_list_options(tree):
    timeout = tree.parameters().child("app", "timeout")
    timeout.setValue(500)
    assert timeout.value() == 120
    assert tree.parameters().child("app", "log", "level").opts["limits"] == list(LOG_LEVELS)


def test_reload_replaces_previous_fields(tree, tmp_path):
    other = SettingsDocument.load(write_settings(tmp_path / "other.yaml", "a:\n  b: 1\n"))
    tree.load([asdict(f) for f in other.fields])
    assert tree.values() == {"a.b": 1}


def test_set_palette_styles_tree(tree):
    tree.set_palette(colors(LIGHT))
    assert LIGHT.surface in tree.tree.styleSheet()
    tree.set_palette(colors(DARK))
    assert DARK.surface in tree.tree.styleSheet()
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_settings_editor_plugin.py -q`
Expected: FAIL（`FileNotFoundError`／找不到 `settings_editor.py`）

- [ ] **Step 4: 實作 `plugins/settings_editor/settings_editor.py`**

```python
# -*- coding: utf-8 -*-
"""
設定編輯器外掛：以 pyqtgraph ParameterTree 顯示與編輯工具參數

本檔案另外打包在 plugins/settings_editor/，不可 import src.*；
與主程式之間只傳遞 dict、list、str 等基本型別。
"""
from pyqtgraph.parametertree import Parameter, ParameterTree
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

API_VERSION = 1

_TREE_QSS = """
QTreeWidget#SettingsTree {{
    background: {surface}; color: {text};
    border: 1px solid {border}; border-radius: 8px; outline: 0;
}}
QTreeWidget#SettingsTree::item:selected {{ background: {surface_hover}; color: {text}; }}
QTreeWidget#SettingsTree QHeaderView::section {{
    background: {bg}; color: {text_muted}; border: none; border-bottom: 1px solid {border}; padding: 4px 8px;
}}
"""


def _parameter_opts(field: dict) -> dict:
    name = field["key"].rsplit(".", 1)[-1]
    opts = {"name": name, "title": field["label"], "tip": field["key"], "type": field["kind"]}
    if field["kind"] != "group":
        opts["value"] = field["value"]
        opts["default"] = field["value"]
    if field.get("limits") is not None:
        opts["limits"] = list(field["limits"])
    return opts


class SettingsTree(QWidget):
    valueChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = Parameter.create(name="root", type="group")
        self._leaves: dict[str, Parameter] = {}
        self._loading = False
        self.tree = ParameterTree(showHeader=True)
        self.tree.setObjectName("SettingsTree")
        self.tree.setHeaderLabels(["參數", "值"])
        self.tree.setParameters(self._root, showTop=False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)
        self._root.sigTreeStateChanged.connect(self._on_tree_changed)

    def load(self, fields: list[dict]) -> None:
        """依 key 的父子關係建立參數樹；載入期間不發出 valueChanged"""
        self._loading = True
        try:
            self._root.clearChildren()
            self._leaves.clear()
            groups: dict[str, Parameter] = {"": self._root}
            for field in fields:
                parent_key = field["key"].rpartition(".")[0]
                param = Parameter.create(**_parameter_opts(field))
                groups[parent_key].addChild(param)
                if field["kind"] == "group":
                    groups[field["key"]] = param
                else:
                    self._leaves[field["key"]] = param
        finally:
            self._loading = False
        # pyqtgraph 只把 tip 設在值的編輯元件上；參數名稱欄另外補上 key 提示
        for item in self.tree.listAllItems():
            param = getattr(item, "param", None)
            if param is not None and param is not self._root:
                item.setToolTip(0, param.opts.get("tip", ""))

    def parameters(self) -> Parameter:
        """根參數（測試與進階操作用）"""
        return self._root

    def values(self) -> dict[str, object]:
        return {key: param.value() for key, param in self._leaves.items()}

    def set_palette(self, colors: dict[str, str]) -> None:
        self.tree.setStyleSheet(_TREE_QSS.format(**colors))

    def _on_tree_changed(self, _param, changes) -> None:
        if self._loading:
            return
        if any(change == "value" for _, change, _ in changes):
            self.valueChanged.emit()
```

- [ ] **Step 5: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_settings_editor_plugin.py -q`
Expected: 全部 PASS

- [ ] **Step 6: 全部測試無回歸**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```
新增設定編輯器外掛：pyqtgraph ParameterTree 包裝 SettingsTree

pyqtgraph、numpy 僅加入 dev 群組並固定版本，主程式依賴不變。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

```bash
git add pyproject.toml uv.lock plugins/settings_editor/settings_editor.py tests/test_settings_editor_plugin.py
git commit -F <暫存檔>
```

---

### Task 3: 外掛載入器 `plugin_loader.py`

**Files:**
- Create: `src/ui/plugin_loader.py`
- Test: `tests/test_plugin_loader.py`

**Interfaces:**
- Consumes: 外掛檔 `plugins/settings_editor/settings_editor.py`（Task 2）
- Produces:
  - `PLUGIN_NAME = "settings_editor"`、`PLUGIN_API_VERSION = 1`
  - `plugin_dir() -> Path`：打包後 `<exe 目錄>/plugins/settings_editor`，開發時 `<repo>/plugins/settings_editor`
  - `load_settings_plugin(directory: Path | None = None) -> ModuleType | None`：失敗回傳 `None`，結果依資料夾快取

- [ ] **Step 1: 寫失敗的測試 `tests/test_plugin_loader.py`**

```python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

from src.ui.plugin_loader import PLUGIN_NAME, load_settings_plugin, plugin_dir

ROOT = Path(__file__).resolve().parents[1]


def make_plugin(tmp_path, body):
    directory = tmp_path / PLUGIN_NAME
    directory.mkdir()
    (directory / f"{PLUGIN_NAME}.py").write_text(body, encoding="utf-8")
    return directory


def test_plugin_dir_in_development_is_repo_plugins():
    assert plugin_dir() == ROOT / "plugins" / "settings_editor"


def test_plugin_dir_when_frozen_is_next_to_exe(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "WebService-Tool.exe"))
    assert plugin_dir() == tmp_path / "plugins" / "settings_editor"


def test_loads_repo_plugin(qapp):
    module = load_settings_plugin(ROOT / "plugins" / "settings_editor")
    assert module is not None
    assert module.API_VERSION == 1
    assert hasattr(module, "SettingsTree")


def test_result_is_cached(tmp_path):
    directory = make_plugin(tmp_path, "API_VERSION = 1\n")
    assert load_settings_plugin(directory) is load_settings_plugin(directory)


def test_missing_directory_returns_none(tmp_path):
    assert load_settings_plugin(tmp_path / "nope") is None


def test_import_error_returns_none(tmp_path):
    assert load_settings_plugin(make_plugin(tmp_path, "raise ImportError('boom')\n")) is None


def test_api_version_mismatch_returns_none(tmp_path):
    assert load_settings_plugin(make_plugin(tmp_path, "API_VERSION = 2\n")) is None


def test_site_packages_put_first_on_sys_path(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))
    directory = make_plugin(tmp_path, "import fake_plugin_dep\nAPI_VERSION = fake_plugin_dep.VERSION\n")
    site = directory / "site-packages"
    site.mkdir()
    (site / "fake_plugin_dep.py").write_text("VERSION = 1\n", encoding="utf-8")
    try:
        assert load_settings_plugin(directory) is not None
        assert sys.path[0] == str(site.resolve())
    finally:
        sys.modules.pop("fake_plugin_dep", None)
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_plugin_loader.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'src.ui.plugin_loader'`）

- [ ] **Step 3: 實作 `src/ui/plugin_loader.py`**

```python
# -*- coding: utf-8 -*-
"""
外掛載入：執行期從外掛資料夾載入設定編輯器（pyqtgraph 不打包進主程式）

外掛資料夾結構：
    plugins/settings_editor/
    ├─ settings_editor.py
    └─ site-packages/      ← pyqtgraph、numpy（開發環境可省略，直接用 venv）
"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from loguru import logger

PLUGIN_NAME = "settings_editor"
PLUGIN_API_VERSION = 1
_cache: dict[Path, ModuleType | None] = {}


def plugin_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[2]
    return base / "plugins" / PLUGIN_NAME


def load_settings_plugin(directory: Path | None = None) -> ModuleType | None:
    """載入外掛；找不到、載入失敗或 API 版本不符都回傳 None，不丟例外"""
    directory = Path(directory or plugin_dir()).resolve()
    if directory not in _cache:
        _cache[directory] = _load(directory)
    return _cache[directory]


def _load(directory: Path) -> ModuleType | None:
    source = directory / f"{PLUGIN_NAME}.py"
    if not source.is_file():
        logger.info("找不到設定編輯器外掛：{}", directory)
        return None
    site = directory / "site-packages"
    if site.is_dir() and str(site) not in sys.path:
        sys.path.insert(0, str(site))
    try:
        # 以檔案路徑載入、不佔用 sys.modules 的名稱，避免不同外掛資料夾互相干擾
        spec = importlib.util.spec_from_file_location(f"_ws_plugin_{PLUGIN_NAME}", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        logger.exception("設定編輯器外掛載入失敗：{}", directory)
        return None
    if getattr(module, "API_VERSION", None) != PLUGIN_API_VERSION:
        logger.warning("設定編輯器外掛 API 版本不符：{}", getattr(module, "API_VERSION", None))
        return None
    return module
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_plugin_loader.py -q`
Expected: 全部 PASS

- [ ] **Step 5: 全部測試無回歸**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```
新增外掛載入器：從外掛資料夾載入設定編輯器，失敗時安全回傳

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

```bash
git add src/ui/plugin_loader.py tests/test_plugin_loader.py
git commit -F <暫存檔>
```

---

### Task 4: 設定頁 `settings_page.py`（含 `styled_button` 共用化）

**Files:**
- Modify: `src/ui/effects.py`（新增 `styled_button`）
- Modify: `src/ui/main_window.py:70-77`（刪除 `_button`，改用 `styled_button`）
- Modify: `src/ui/theme.py:99`（`QLabel#AppTitle` 下一行新增 QSS）
- Create: `src/ui/settings_page.py`
- Test: `tests/test_settings_page.py`

**Interfaces:**
- Consumes: `SettingsDocument`、`SettingsChanges`、`SettingsError`（Task 1）；`load_settings_plugin`、`plugin_dir`（Task 3）；外掛 `SettingsTree`（Task 2）
- Produces:
  - `src/ui/effects.py`：`styled_button(text: str, variant: str | None = None, tooltip: str = "") -> QPushButton`
  - `src/ui/settings_page.py`：常數 `PAGE_TITLE`、`MISSING_PLUGIN_TEXT = "設定編輯器外掛未安裝"`、`SAVED_TEXT = "設定已儲存並套用"`、`RESTART_TEXT = "已儲存，以下設定需重新啟動才會生效："`；`palette_colors(palette: ThemePalette) -> dict[str, str]`；`class SettingsPage(QWidget)`：Signal `saved(object, object)`（`SettingsDocument`, `SettingsChanges`）、Signal `backRequested()`；屬性 `editor`（`SettingsTree` 或 `None`）、`notification: NotificationBar`、`save_button`、`revert_button`、`back_button`、`placeholder`（僅外掛為 None 時存在）；方法 `open(path: Path) -> None`、`is_dirty() -> bool`、`save() -> bool`、`revert() -> None`、`notify(level: str, text: str) -> None`、`set_palette(palette: ThemePalette) -> None`

- [ ] **Step 1: 把按鈕輔助函式移到 `src/ui/effects.py`**

在 `src/ui/effects.py` 檔尾加入：

```python
def styled_button(text: str, variant: str | None = None, tooltip: str = "") -> QPushButton:
    """建立套用 variant 樣式（對應 theme.py 的 QSS selector）與懸浮效果的按鈕"""
    button = QPushButton(text)
    if variant:
        button.setProperty("variant", variant)
    if tooltip:
        button.setToolTip(tooltip)
    HoverLift(button)
    return button
```

在 `src/ui/main_window.py`：
1. 刪除 `def _button(...)` 整個函式（第 70-77 行）
2. `from src.ui.effects import HoverLift` 改為 `from src.ui.effects import styled_button`（已確認 `HoverLift` 在 main_window 只有 `_button` 使用）
3. 把所有 `_button(` 呼叫改為 `styled_button(`：`sed -i 's/\b_button(/styled_button(/g' src/ui/main_window.py`，再用 `grep -n "_button(" src/ui/main_window.py` 確認只剩 `self.xxx_button` 形式的屬性名稱

Run: `.venv/Scripts/python -m pytest tests/test_main_window.py -q`
Expected: 全部 PASS（純搬移，行為不變）

- [ ] **Step 2: 新增設定頁 QSS**

`src/ui/theme.py` 的 `_QSS` 中，`QLabel#AppTitle { ... }` 下一行加入：

```
QLabel#PageTitle { font-size: 13pt; font-weight: 600; }
QLabel#Placeholder { color: $text_muted; font-size: 11pt; }
```

- [ ] **Step 3: 寫失敗的測試 `tests/test_settings_page.py`**

```python
# -*- coding: utf-8 -*-
from pathlib import Path

import pytest

from src.config.app_settings import SettingsChanges, SettingsDocument, SettingsError
from src.ui.plugin_loader import load_settings_plugin
from src.ui.settings_page import (
    MISSING_PLUGIN_TEXT, RESTART_TEXT, SAVED_TEXT, SettingsPage, palette_colors,
)
from src.ui.theme import DARK, LIGHT
from tests.helpers import SETTINGS_YAML, write_settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def plugin(qapp):
    return load_settings_plugin(ROOT / "plugins" / "settings_editor")


@pytest.fixture
def path(tmp_path):
    return write_settings(tmp_path / "ws_tool.yaml")


@pytest.fixture
def page(plugin, path):
    widget = SettingsPage(plugin, LIGHT)
    widget.open(path)
    yield widget
    widget.deleteLater()


def set_value(page, *names, value):
    page.editor.parameters().child(*names).setValue(value)


def test_palette_colors_excludes_name_and_xml():
    colors = palette_colors(DARK)
    assert "name" not in colors and "xml" not in colors
    assert colors["surface"] == DARK.surface


def test_open_shows_values_and_buttons_disabled(page):
    assert page.editor.values()["app.timeout"] == 120
    assert not page.is_dirty()
    assert not page.save_button.isEnabled() and not page.revert_button.isEnabled()
    assert page.save_button.property("variant") == "green"


def test_edit_marks_dirty_and_enables_buttons(page):
    set_value(page, "app", "timeout", value=60)
    assert page.is_dirty()
    assert page.save_button.isEnabled() and page.revert_button.isEnabled()


def test_save_writes_file_emits_saved_and_shows_success(page, path):
    saved = []
    page.saved.connect(lambda doc, changes: saved.append((doc, changes)))
    set_value(page, "app", "timeout", value=60)
    assert page.save() is True
    assert path.read_text(encoding="utf-8") == SETTINGS_YAML.replace("timeout: 120", "timeout: 60")
    assert len(saved) == 1
    assert isinstance(saved[0][0], SettingsDocument)
    assert saved[0][1] == SettingsChanges(hot=("app.timeout",), restart=())
    assert (page.notification.level, page.notification.text) == ("success", SAVED_TEXT)
    assert not page.is_dirty() and not page.save_button.isEnabled()


def test_save_with_restart_keys_warns(page):
    set_value(page, "app", "log", "level", value="debug")
    assert page.save() is True
    assert page.notification.level == "warning"
    assert page.notification.text == RESTART_TEXT + "app.log.level"


def test_save_failure_shows_error_and_stays_dirty(page, path, monkeypatch):
    def boom(self, values):
        raise SettingsError("磁碟已滿")

    monkeypatch.setattr(SettingsDocument, "save", boom)
    set_value(page, "app", "timeout", value=60)
    assert page.save() is False
    assert page.notification.level == "error"
    assert "磁碟已滿" in page.notification.text
    assert page.is_dirty()
    assert path.read_text(encoding="utf-8") == SETTINGS_YAML


def test_save_without_changes_is_noop(page, path):
    saved = []
    page.saved.connect(lambda *args: saved.append(args))
    assert page.save() is True
    assert saved == []


def test_revert_restores_last_saved_values(page):
    set_value(page, "app", "timeout", value=60)
    page.revert()
    assert page.editor.values()["app.timeout"] == 120
    assert not page.is_dirty()


def test_open_reloads_from_disk(page, path):
    write_settings(path, SETTINGS_YAML.replace("timeout: 120", "timeout: 90"))
    page.open(path)
    assert page.editor.values()["app.timeout"] == 90


def test_open_failure_shows_error_and_disables_save(page, tmp_path):
    page.open(tmp_path / "missing.yaml")
    assert page.notification.level == "error"
    assert "無法讀取設定檔" in page.notification.text
    assert not page.is_dirty() and not page.save_button.isEnabled()


def test_missing_plugin_shows_placeholder(qapp, path):
    page = SettingsPage(None, LIGHT)
    page.open(path)
    assert page.editor is None
    assert MISSING_PLUGIN_TEXT in page.placeholder.text()
    assert not page.is_dirty()
    assert not page.save_button.isEnabled() and not page.revert_button.isEnabled()
    page.set_palette(DARK)  # 不應丟例外
    page.deleteLater()


def test_back_button_emits_back_requested(page):
    hits = []
    page.backRequested.connect(lambda: hits.append(1))
    page.back_button.click()
    assert hits == [1]


def test_set_palette_passes_theme_colors_to_editor(page):
    page.set_palette(DARK)
    assert DARK.surface in page.editor.tree.styleSheet()


def test_notify_uses_page_notification(page):
    page.notify("warning", "找不到圖示檔")
    assert (page.notification.level, page.notification.text) == ("warning", "找不到圖示檔")
```

- [ ] **Step 4: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_settings_page.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'src.ui.settings_page'`）

- [ ] **Step 5: 實作 `src/ui/settings_page.py`**

```python
# -*- coding: utf-8 -*-
"""
設定頁：以外掛提供的 ParameterTree 編輯 ws_tool.yaml，按「儲存」才寫回
"""
from dataclasses import asdict, fields
from pathlib import Path
from types import ModuleType

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.config.app_settings import SettingsChanges, SettingsDocument, SettingsError
from src.ui.effects import styled_button
from src.ui.notification_bar import NotificationBar
from src.ui.plugin_loader import plugin_dir
from src.ui.theme import ThemePalette

PAGE_TITLE = "工具參數設定"
MISSING_PLUGIN_TEXT = "設定編輯器外掛未安裝"
SAVED_TEXT = "設定已儲存並套用"
RESTART_TEXT = "已儲存，以下設定需重新啟動才會生效："
_NO_CHANGES = SettingsChanges(hot=(), restart=())


def palette_colors(palette: ThemePalette) -> dict[str, str]:
    """外掛用的色票：ThemePalette 除 name、xml 以外的欄位"""
    return {f.name: getattr(palette, f.name) for f in fields(palette) if f.name not in ("name", "xml")}


class SettingsPage(QWidget):
    saved = Signal(object, object)  # (SettingsDocument, SettingsChanges)
    backRequested = Signal()

    def __init__(self, plugin: ModuleType | None, palette: ThemePalette, parent=None):
        super().__init__(parent)
        self._doc: SettingsDocument | None = None
        self.editor = plugin.SettingsTree() if plugin is not None else None

        title = QLabel(PAGE_TITLE)
        title.setObjectName("PageTitle")
        self.save_button = styled_button("儲存", "green", "儲存並套用設定")
        self.revert_button = styled_button("還原", "orange", "還原為最後儲存的內容")
        self.back_button = styled_button("返回", tooltip="回到工作區 (F11 / Esc)")
        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch(1)
        for button in (self.save_button, self.revert_button, self.back_button):
            header.addWidget(button)

        self.notification = NotificationBar()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(self.notification)
        if self.editor is not None:
            self.editor.valueChanged.connect(self._update_buttons)
            layout.addWidget(self.editor, 1)
        else:
            self.placeholder = QLabel(f"{MISSING_PLUGIN_TEXT}\n\n請將外掛資料夾放在：\n{plugin_dir()}")
            self.placeholder.setObjectName("Placeholder")
            self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.placeholder.setWordWrap(True)
            layout.addWidget(self.placeholder, 1)

        self.save_button.clicked.connect(self.save)
        self.revert_button.clicked.connect(self.revert)
        self.back_button.clicked.connect(self.backRequested)
        self.set_palette(palette)
        self._update_buttons()

    def open(self, path: Path) -> None:
        """每次進入設定頁都重新讀檔，反映外部的修改"""
        self.notification.dismiss()
        if self.editor is None:
            return
        try:
            self._doc = SettingsDocument.load(path)
        except SettingsError as exc:
            self._doc = None
            self.editor.load([])
            self.notification.show_message("error", str(exc))
        else:
            self.editor.load([asdict(field) for field in self._doc.fields])
        self._update_buttons()

    def is_dirty(self) -> bool:
        if self._doc is None or self.editor is None:
            return False
        try:
            return self._doc.changes(self.editor.values()) != _NO_CHANGES
        except SettingsError:
            return True

    @Slot()
    def save(self) -> bool:
        """寫回設定檔；沒有修改時直接視為成功"""
        if not self.is_dirty():
            return True
        values = self.editor.values()
        try:
            changes = self._doc.changes(values)
            self._doc = self._doc.save(values)
        except SettingsError as exc:
            self.notification.show_message("error", f"儲存失敗：{exc}")
            return False
        if changes.restart:
            self.notification.show_message("warning", RESTART_TEXT + "、".join(changes.restart))
        else:
            self.notification.show_message("success", SAVED_TEXT)
        self._update_buttons()
        self.saved.emit(self._doc, changes)
        return True

    @Slot()
    def revert(self) -> None:
        if self._doc is not None and self.editor is not None:
            self.editor.load([asdict(field) for field in self._doc.fields])
        self.notification.dismiss()
        self._update_buttons()

    def notify(self, level: str, text: str) -> None:
        self.notification.show_message(level, text)

    def set_palette(self, palette: ThemePalette) -> None:
        if self.editor is not None:
            self.editor.set_palette(palette_colors(palette))

    @Slot()
    def _update_buttons(self) -> None:
        dirty = self.is_dirty()
        self.save_button.setEnabled(dirty)
        self.revert_button.setEnabled(dirty)
```

- [ ] **Step 6: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_settings_page.py tests/test_theme.py -q`
Expected: 全部 PASS

- [ ] **Step 7: 全部測試無回歸**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 8: Commit**

```
新增設定頁：儲存、還原、返回與外掛未安裝的佔位畫面

按鈕輔助函式移到 effects.styled_button 供主視窗與設定頁共用。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

```bash
git add src/ui/effects.py src/ui/main_window.py src/ui/theme.py src/ui/settings_page.py tests/test_settings_page.py
git commit -F <暫存檔>
```

---

### Task 5: 熱重載 `apply_app_settings` 與設定檔路徑

**Files:**
- Modify: `src/config/web_service_config.py`（新增 `config_path`）
- Modify: `src/ui/main_window.py`（`TIMEOUT_*` 改 import、`settings_path` 參數、`self.sidebar`／`self.app_title`、`apply_app_settings`）
- Modify: `src/ws_tool.py:93`（傳 `settings_path`）
- Test: `tests/test_main_window.py`、`tests/test_entry_point.py`

**Interfaces:**
- Consumes: `AppSettings`、`TIMEOUT_MIN`、`TIMEOUT_MAX`（Task 1）
- Produces:
  - `WebServiceConfig.config_path: Path`（實際讀取的 ws_tool.yaml 絕對路徑）
  - `MainWindow.__init__(store, service, theme, about, default_timeout: int, settings_path: Path, parent=None)`
  - `MainWindow` 屬性 `sidebar: QFrame`、`app_title: QLabel`、`_settings_path: Path`
  - `MainWindow.apply_app_settings(settings: AppSettings) -> None`

- [ ] **Step 1: 更新 `tests/test_main_window.py` 的 fixture 並寫失敗的測試**

import 區調整：

```python
from PySide6.QtGui import QGuiApplication, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QApplication, QMessageBox

from src.config.app_settings import TIMEOUT_MAX, AppSettings
from tests.helpers import wait_until, write_settings
```

`env` fixture 中建立設定檔，`make()` 傳入 `settings_path`，並預設「未存檔詢問」回答「不儲存」，避免測試卡在對話框：

```python
@pytest.fixture
def env(qapp, tmp_path):
    service = FakeService()
    theme = ThemeManager(qapp, QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    theme.apply()
    settings_path = write_settings(tmp_path / "ws_tool.yaml")
    ctx = SimpleNamespace(
        store=ConnectionStore(tmp_path / "connections.profile"), service=service, theme=theme,
        settings_path=settings_path,
    )
    windows = []

    def make(store=None):
        window = MainWindow(store or ctx.store, service, theme, ABOUT, default_timeout=30, settings_path=settings_path)
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
```

檔尾新增測試：

```python
@pytest.fixture
def app_calls(monkeypatch):
    """攔截 QApplication 的全域設定，避免測試互相影響"""
    calls = SimpleNamespace(icons=[], names=[])
    monkeypatch.setattr(QApplication, "setWindowIcon", lambda icon: calls.icons.append(icon))
    monkeypatch.setattr(QApplication, "setApplicationName", lambda name: calls.names.append(name))
    return calls


def test_apply_app_settings_updates_window(env, app_calls, tmp_path):
    icon_path = tmp_path / "icon.png"
    pixmap = QPixmap(16, 16)
    pixmap.fill()
    pixmap.save(str(icon_path))
    window = env.make()
    window.apply_app_settings(AppSettings("新名稱", "v9.9.9", "新版權", str(icon_path), 60))
    assert window.windowTitle() == "新名稱"
    assert window.app_title.text() == "新名稱"
    assert window._about == AboutInfo("新名稱", "v9.9.9", "新版權", ABOUT.website)
    assert app_calls.names == ["新名稱"]
    assert len(app_calls.icons) == 1
    assert window.timeout_spin.value() == 60


def test_apply_app_settings_clamps_timeout(env, app_calls):
    window = env.make()
    window.apply_app_settings(AppSettings("n", "v", "c", "assets/app_icon.ico", 500))
    assert window.timeout_spin.value() == TIMEOUT_MAX


def test_apply_app_settings_missing_icon_keeps_old_and_warns(env, app_calls):
    window = env.make()
    window.apply_app_settings(AppSettings("n", "v", "c", "not/exist.ico", 30))
    assert app_calls.icons == []
    assert window.notification.level == "warning"
    assert "找不到圖示檔" in window.notification.text
```

`tests/test_entry_point.py` 的 `test_resolve_app_dirs_uses_config_file_location_as_base` 在 `config = WebServiceConfig()` 之後加一行斷言：

```python
    assert config.config_path == app_data / "ws_tool.yaml"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_main_window.py tests/test_entry_point.py -q`
Expected: FAIL（`TypeError: ... unexpected keyword argument 'settings_path'`、`AttributeError: ... 'config_path'`）

- [ ] **Step 3: `WebServiceConfig` 新增 `config_path`**

`src/config/web_service_config.py`：

```python
from pathlib import Path

from src.utils import yaml_values, pathutil


class WebServiceConfig:

    def __init__(self):
        # 實際讀取的設定檔位置；設定頁也寫回同一個檔案
        self.config_path = Path(pathutil.resource_abspath('app_data\\ws_tool.yaml'))
        self.app_config = yaml_values.load_yaml_file(self.config_path)
```

（其餘欄位維持不變）

- [ ] **Step 4: 修改 `src/ui/main_window.py`**

1. import 調整：

```python
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QIcon, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    # …其餘不變
)

from src.config.app_settings import TIMEOUT_MAX, TIMEOUT_MIN, AppSettings
from src.utils import pathutil
```

2. 刪除模組常數 `TIMEOUT_MIN = 5`、`TIMEOUT_MAX = 120`（改由上方 import 提供，`main_window.TIMEOUT_MIN` 仍可存取）

3. 建構子新增參數並保存：

```python
    def __init__(self, store: ConnectionStore, service, theme: ThemeManager, about: AboutInfo,
                 default_timeout: int, settings_path: Path, parent=None):
        super().__init__(parent)
        self._store = store
        self._service = service
        self._theme = theme
        self._about = about
        self._settings_path = Path(settings_path)
        # …其餘不變
```

4. `_build_ui` 保存側欄參照：

```python
        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar)
        root.addWidget(self._build_workspace(default_timeout), 1)
```

5. `_build_sidebar` 中 `title = QLabel(self._about.name)` 改為 `self.app_title = QLabel(self._about.name)`，後續 `title.` 全部改為 `self.app_title.`，`layout.addWidget(title)` 改為 `layout.addWidget(self.app_title)`

6. 在 `_show_about` 之前新增：

```python
    def apply_app_settings(self, settings: AppSettings) -> None:
        """熱重載 ws_tool.yaml 的 name、version、copyright、img、timeout"""
        self._about = replace(self._about, name=settings.name, version=settings.version, copyright=settings.copyright)
        self.setWindowTitle(settings.name)
        self.app_title.setText(settings.name)
        QApplication.setApplicationName(settings.name)
        icon_path = Path(pathutil.resource_path(settings.img))
        if icon_path.is_file():
            QApplication.setWindowIcon(QIcon(str(icon_path)))
        else:
            logger.warning("找不到圖示檔：{}", icon_path)
            self._notify("warning", f"找不到圖示檔 {settings.img}，保留原圖示")
        self.timeout_spin.setValue(min(max(settings.timeout, TIMEOUT_MIN), TIMEOUT_MAX))
```

- [ ] **Step 5: `src/ws_tool.py` 傳入設定檔路徑**

```python
    window = MainWindow(
        store, SoapService(), theme, about,
        default_timeout=config.get_app_timeout(), settings_path=config.config_path,
    )
```

- [ ] **Step 6: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_main_window.py tests/test_entry_point.py -q`
Expected: 全部 PASS

- [ ] **Step 7: 全部測試無回歸**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 8: Commit**

```
主視窗支援熱重載工具參數：名稱、版本、版權、圖示與逾時

逾時上下限改由 app_settings 提供；WebServiceConfig 記錄實際讀取的設定檔路徑。

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

```bash
git add src/config/web_service_config.py src/ui/main_window.py src/ws_tool.py tests/test_main_window.py tests/test_entry_point.py
git commit -F <暫存檔>
```

---

### Task 6: F11 設定頁切換、未存檔保護

**Files:**
- Modify: `src/ui/main_window.py`（QStackedWidget、快捷鍵、`_notify`、主題、`closeEvent`）
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `SettingsPage`（Task 4）；`load_settings_plugin`（Task 3）；`apply_app_settings`、`_settings_path`、`sidebar`（Task 5）
- Produces:
  - `MainWindow` 屬性 `stack: QStackedWidget`、`workspace: QWidget`、`settings_page: SettingsPage | None`（首次按 F11 才建立）
  - `MainWindow._ask_unsaved() -> QMessageBox.StandardButton`（Save／Discard／Cancel；測試會覆寫）

- [ ] **Step 1: 寫失敗的測試（`tests/test_main_window.py` 檔尾）**

```python
from src.ui import main_window as main_window_module  # 放到檔案 import 區

WORKSPACE_KEYS = ("F1", "F2", "F3", "F5", "F6", "Ctrl+Shift+F")


def shortcut_enabled(window, key):
    return next(sc for sc in window.findChildren(QShortcut) if sc.key() == QKeySequence(key)).isEnabled()


def open_settings(window):
    press_shortcut(window, "F11")
    return window.settings_page


def test_f11_opens_settings_page_and_locks_workspace(env):
    window = env.make()
    page = open_settings(window)
    assert window.stack.currentWidget() is page
    assert page.editor.values()["app.timeout"] == 120
    assert not window.sidebar.isEnabled()
    assert not any(shortcut_enabled(window, key) for key in WORKSPACE_KEYS)
    assert shortcut_enabled(window, "F11") and shortcut_enabled(window, "Esc")


def test_f11_again_returns_to_workspace(env):
    window = env.make()
    open_settings(window)
    press_shortcut(window, "F11")
    assert window.stack.currentWidget() is window.workspace
    assert window.sidebar.isEnabled()
    assert all(shortcut_enabled(window, key) for key in WORKSPACE_KEYS)


def test_back_button_returns_to_workspace(env):
    window = env.make()
    open_settings(window).back_button.click()
    assert window.stack.currentWidget() is window.workspace


def test_escape_on_settings_page_goes_back_instead_of_closing(env):
    window = env.make()
    asked = []
    window._confirm = lambda title, text: asked.append(title) or False
    open_settings(window)
    press_shortcut(window, "Esc")
    assert window.stack.currentWidget() is window.workspace
    assert asked == []
    press_shortcut(window, "Esc")  # 回到工作區後 Esc 仍是離開程式
    assert asked == ["離開程式"]


def test_reopening_reloads_file_from_disk(env):
    window = env.make()
    open_settings(window)
    press_shortcut(window, "F11")
    env.settings_path.write_text(env.settings_path.read_text(encoding="utf-8").replace("timeout: 120", "timeout: 90"), encoding="utf-8")
    assert open_settings(window).editor.values()["app.timeout"] == 90


def test_unsaved_cancel_stays_on_settings_page(env):
    window = env.make()
    page = open_settings(window)
    page.editor.parameters().child("app", "timeout").setValue(60)
    window._ask_unsaved = lambda: QMessageBox.StandardButton.Cancel
    press_shortcut(window, "F11")
    assert window.stack.currentWidget() is page


def test_unsaved_discard_leaves_without_writing(env):
    window = env.make()
    page = open_settings(window)
    page.editor.parameters().child("app", "timeout").setValue(60)
    window._ask_unsaved = lambda: QMessageBox.StandardButton.Discard
    press_shortcut(window, "F11")
    assert window.stack.currentWidget() is window.workspace
    assert "timeout: 120" in env.settings_path.read_text(encoding="utf-8")


def test_unsaved_save_writes_hot_reloads_and_leaves(env, app_calls):
    window = env.make()
    page = open_settings(window)
    page.editor.parameters().child("app", "timeout").setValue(60)
    window._ask_unsaved = lambda: QMessageBox.StandardButton.Save
    press_shortcut(window, "F11")
    assert window.stack.currentWidget() is window.workspace
    assert "timeout: 60" in env.settings_path.read_text(encoding="utf-8")
    assert window.timeout_spin.value() == 60


def test_save_button_hot_reloads_and_stays(env, app_calls):
    window = env.make()
    page = open_settings(window)
    page.editor.parameters().child("app", "name").setValue("新名稱")
    page.save_button.click()
    assert window.windowTitle() == "新名稱"
    assert window.app_title.text() == "新名稱"
    assert window.stack.currentWidget() is page


def test_restart_only_change_does_not_hot_reload(env, app_calls):
    window = env.make()
    page = open_settings(window)
    page.editor.parameters().child("app", "log", "level").setValue("debug")
    page.save_button.click()
    assert app_calls.names == []
    assert page.notification.level == "warning"


def test_missing_icon_warning_shown_on_settings_page(env, app_calls):
    window = env.make()
    page = open_settings(window)
    page.editor.parameters().child("app", "img").setValue("not/exist.ico")
    page.save_button.click()
    assert page.notification.level == "warning"
    assert "找不到圖示檔" in page.notification.text


def test_close_with_unsaved_settings_asks_before_exit_confirm(env):
    window = env.make()
    asked = []
    window._confirm = lambda title, text: asked.append(title) or True
    page = open_settings(window)
    page.editor.parameters().child("app", "timeout").setValue(60)
    window._ask_unsaved = lambda: QMessageBox.StandardButton.Cancel
    assert window.close() is False
    assert asked == []


def test_missing_plugin_shows_placeholder(env, monkeypatch):
    monkeypatch.setattr(main_window_module, "load_settings_plugin", lambda: None)
    window = env.make()
    page = open_settings(window)
    assert page.editor is None
    assert window.stack.currentWidget() is page


def test_theme_change_updates_settings_page(env):
    window = env.make()
    page = open_settings(window)
    env.theme.set_mode(ThemeMode.DARK)
    assert DARK.surface in page.editor.tree.styleSheet()


def test_notify_routes_to_visible_page(env):
    window = env.make()
    page = open_settings(window)
    window._notify("info", "設定頁訊息")
    assert page.notification.text == "設定頁訊息"
    press_shortcut(window, "F11")
    window._notify("info", "工作區訊息")
    assert window.notification.text == "工作區訊息"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_main_window.py -q`
Expected: 新增的測試 FAIL（找不到 F11 快捷鍵、`stack` 屬性不存在）

- [ ] **Step 3: 修改 `src/ui/main_window.py`**

1. import：

```python
from PySide6.QtWidgets import (
    # …既有項目
    QStackedWidget,
)

from src.ui.plugin_loader import load_settings_plugin
from src.ui.settings_page import SettingsPage
```

2. `_build_ui` 右側改為 QStackedWidget：

```python
        self.sidebar = self._build_sidebar()
        self.workspace = self._build_workspace(default_timeout)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.workspace)
        self.settings_page: SettingsPage | None = None  # 首次按 F11 才載入外掛並建立
        root.addWidget(self.sidebar)
        root.addWidget(self.stack, 1)
```

3. `_build_shortcuts` 改為：

```python
    def _build_shortcuts(self) -> None:
        self._workspace_shortcuts: list[QShortcut] = []
        for key, handler in (
            ("F1", self._on_add_requested),
            ("F2", self.connection_list.request_delete_current),
            ("F3", self.load_button.click),
            ("F5", self.run_button.click),
            ("F6", self._on_clear),
            ("Ctrl+Shift+F", self._on_format),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)
            self._workspace_shortcuts.append(shortcut)
        for key, handler in (("F11", self._toggle_settings), ("Esc", self._on_escape)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)
```

4. 在 `_notify` 之前新增「設定頁」區段：

```python
    # ---------- 設定頁 ----------

    def _settings_active(self) -> bool:
        return self.settings_page is not None and self.stack.currentWidget() is self.settings_page

    @Slot()
    def _toggle_settings(self) -> None:
        if self._settings_active():
            self._leave_settings()
        else:
            self._enter_settings()

    @Slot()
    def _on_escape(self) -> None:
        if self._settings_active():
            self._leave_settings()
        else:
            self.close()

    def _enter_settings(self) -> None:
        if self.settings_page is None:
            self.settings_page = SettingsPage(load_settings_plugin(), self._theme.palette)
            self.settings_page.saved.connect(self._on_settings_saved)
            self.settings_page.backRequested.connect(self._leave_settings)
            self.stack.addWidget(self.settings_page)
        self.settings_page.open(self._settings_path)
        self.stack.setCurrentWidget(self.settings_page)
        self._set_settings_mode(True)

    @Slot()
    def _leave_settings(self) -> bool:
        """回到工作區；有未儲存修改且使用者取消（或儲存失敗）時回傳 False"""
        if not self._settings_active():
            return True
        if not self._resolve_unsaved():
            return False
        self.stack.setCurrentWidget(self.workspace)
        self._set_settings_mode(False)
        return True

    def _set_settings_mode(self, active: bool) -> None:
        """設定頁顯示期間停用左側清單與工作區快捷鍵，避免在看不到的地方送出請求"""
        self.sidebar.setEnabled(not active)
        for shortcut in self._workspace_shortcuts:
            shortcut.setEnabled(not active)

    def _resolve_unsaved(self) -> bool:
        """設定頁有未儲存修改時詢問；回傳 True 表示可以繼續離開"""
        page = self.settings_page
        if page is None or not page.is_dirty():
            return True
        answer = self._ask_unsaved()
        if answer == QMessageBox.StandardButton.Save:
            return page.save()
        return answer == QMessageBox.StandardButton.Discard

    def _ask_unsaved(self) -> QMessageBox.StandardButton:
        return QMessageBox.question(
            self, "未儲存的設定", "工具參數設定尚未儲存，要儲存嗎？",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

    @Slot(object, object)
    def _on_settings_saved(self, doc, changes) -> None:
        if changes.hot:
            self.apply_app_settings(doc.app_settings())
```

5. `_notify` 改為顯示在目前可見頁面：

```python
    def _notify(self, level: str, text: str) -> None:
        if self._settings_active():
            self.settings_page.notify(level, text)
        else:
            self.notification.show_message(level, text)
```

6. `_on_theme_changed` 末端加入：

```python
        if self.settings_page is not None:
            self.settings_page.set_palette(palette)
```

7. `closeEvent` 開頭加入：

```python
    def closeEvent(self, event) -> None:
        if self._settings_active() and not self._resolve_unsaved():
            event.ignore()
            return
        if not self._confirm("離開程式", "確定要離開嗎？"):
            # …其餘不變
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_main_window.py -q`
Expected: 全部 PASS

- [ ] **Step 5: 全部測試無回歸**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 6: 手動啟動確認（開發環境）**

Run: `uv run python src/ws_tool.py`
確認：按 F11 右側換成設定頁、左側清單變灰；改逾時為 60 按「儲存」後綠色通知、回到工作區逾時欄位為 60；改 log level 儲存後黃色通知；有修改時按 F11 跳出三選一；切換深色主題設定頁跟著變色。**確認後把 `src/app_data/ws_tool.yaml` 還原**（`git checkout src/app_data/ws_tool.yaml`）。

- [ ] **Step 7: Commit**

```
F11 切換工具參數設定頁：停用側欄與工作區快捷鍵、未存檔詢問、儲存後熱重載

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

```bash
git add src/ui/main_window.py tests/test_main_window.py
git commit -F <暫存檔>
```

---

### Task 7: 外掛打包、hiddenimports 清單與文件

**Files:**
- Create: `plugins/settings_editor/gen_host_imports.py`
- Create（產生）: `plugins/settings_editor/host_imports.txt`
- Create: `plugins/settings_editor/build_plugin.py`
- Modify: `build.bat`、`README.md`、`AGENTS.md`
- Test: `tests/test_plugin_build.py`

**Interfaces:**
- Consumes: 外掛 `SettingsTree`（Task 2）
- Produces:
  - `gen_host_imports.py`：`collect() -> list[str]`、`render(modules: list[str]) -> str`、`main(argv: list[str] | None = None) -> int`（`--check` 時檔案過期回傳 1）
  - `build_plugin.py`：`REQUIREMENTS: tuple[str, ...]`、`prune(site: Path) -> None`、`build(target: Path = TARGET) -> Path`

- [ ] **Step 1: 寫失敗的測試 `tests/test_plugin_build.py`**

```python
# -*- coding: utf-8 -*-
import importlib.util
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "settings_editor"


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", PLUGIN / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_host_imports_file_is_up_to_date():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, str(PLUGIN / "gen_host_imports.py"), "--check"],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_host_imports_cover_known_requirements():
    modules = (PLUGIN / "host_imports.txt").read_text(encoding="utf-8").splitlines()
    for name in ("platform", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSvg"):
        assert name in modules


def test_plugin_requirements_match_dev_dependencies():
    dev = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    for requirement in load("build_plugin").REQUIREMENTS:
        assert requirement in dev


def test_prune_removes_unneeded_files(tmp_path):
    site = tmp_path / "site-packages"
    for relative in ("pyqtgraph/examples/demo.py", "bin/f2py.exe", "numpy/__pycache__/x.pyc", "pyqtgraph/__init__.py"):
        target = site / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    load("build_plugin").prune(site)
    remaining = sorted(p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file())
    assert remaining == ["pyqtgraph/__init__.py"]
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_plugin_build.py -q`
Expected: FAIL（找不到 `gen_host_imports.py`、`host_imports.txt`、`build_plugin.py`）

- [ ] **Step 3: 實作 `plugins/settings_editor/gen_host_imports.py`**

```python
# -*- coding: utf-8 -*-
"""
產生 host_imports.txt：主程式打包時需額外包含、供外掛使用的模組

PyInstaller 只打包主程式靜態可見的模組；外掛（pyqtgraph、numpy）在執行期才載入，
它們用到的標準庫與 PySide6 子模組必須預先打包進主程式。
升級 pyqtgraph 或 numpy 後重新執行：uv run python plugins/settings_editor/gen_host_imports.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "host_imports.txt"
HEADER = "# 由 gen_host_imports.py 產生，請勿手動編輯；升級 pyqtgraph／numpy 後重新產生\n"
EXCLUDED_PACKAGES = ("encodings",)  # PyInstaller 一律完整打包；且依主控台編碼而異，排除以保持結果穩定
SAMPLE_FIELDS = [
    {"key": "app", "label": "app", "kind": "group", "value": None, "limits": None},
    {"key": "app.name", "label": "名稱", "kind": "str", "value": "x", "limits": None},
    {"key": "app.timeout", "label": "逾時", "kind": "int", "value": 30, "limits": (5, 120)},
    {"key": "app.ratio", "label": "比例", "kind": "float", "value": 1.5, "limits": None},
    {"key": "app.enabled", "label": "啟用", "kind": "bool", "value": True, "limits": None},
    {"key": "app.level", "label": "等級", "kind": "list", "value": "info", "limits": ("info", "debug")},
]
SAMPLE_COLORS = {
    "bg": "#000000", "surface": "#111111", "surface_hover": "#222222",
    "border": "#333333", "text": "#FFFFFF", "text_muted": "#AAAAAA",
}


def _wanted(name: str) -> bool:
    top = name.split(".")[0]
    if top in EXCLUDED_PACKAGES:
        return False
    return (top in sys.stdlib_module_names and not top.startswith("_")) or name.startswith("PySide6.")


def collect() -> list[str]:
    """實際建立並操作 SettingsTree，回傳過程中載入的標準庫與 PySide6 模組"""
    sys.path.insert(0, str(HERE))
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import settings_editor

    tree = settings_editor.SettingsTree()
    tree.load(SAMPLE_FIELDS)
    tree.set_palette(SAMPLE_COLORS)
    tree.show()
    app.processEvents()
    return sorted(name for name in sys.modules if _wanted(name))


def render(modules: list[str]) -> str:
    return HEADER + "".join(f"{name}\n" for name in modules)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    content = render(collect())
    if "--check" in argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print("host_imports.txt 已過期，請執行：uv run python plugins/settings_editor/gen_host_imports.py")
            return 1
        return 0
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"已寫入 {OUTPUT}（{content.count(chr(10)) - 1} 個模組）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 產生清單**

Run: `uv run python plugins/settings_editor/gen_host_imports.py`
Expected: `已寫入 ...host_imports.txt（約 130～160 個模組）`；檔案內含 `platform`、`PySide6.QtOpenGL`、`PySide6.QtOpenGLWidgets`、`PySide6.QtSvg`

再執行一次 `uv run python plugins/settings_editor/gen_host_imports.py --check`，Expected: 結束碼 0（確認結果穩定）

- [ ] **Step 5: 實作 `plugins/settings_editor/build_plugin.py`**

```python
# -*- coding: utf-8 -*-
"""
建置設定編輯器外掛：dist/plugins/settings_editor/（編輯器程式 + pyqtgraph + numpy）

必須以專案 .venv 的直譯器執行（uv run python ...），確保與主程式相同的 Python 版本與平台。
升級版本時同步修改 pyproject.toml 的 dev 群組，並重新產生 host_imports.txt。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TARGET = ROOT / "dist" / "plugins" / "settings_editor"
REQUIREMENTS = ("pyqtgraph==0.14.0", "numpy==2.5.3")
PRUNE_DIRS = ("pyqtgraph/examples", "bin")


def prune(site: Path) -> None:
    """刪除執行期用不到的內容，縮小外掛體積"""
    for relative in PRUNE_DIRS:
        shutil.rmtree(site / relative, ignore_errors=True)
    for cache in list(site.rglob("__pycache__")):
        shutil.rmtree(cache, ignore_errors=True)


def build(target: Path = TARGET) -> Path:
    if target.exists():
        shutil.rmtree(target)
    site = target / "site-packages"
    site.mkdir(parents=True)
    uv = os.environ.get("UV") or shutil.which("uv") or "uv"  # uv run 會設定 UV 環境變數
    subprocess.run(
        [uv, "pip", "install", "--quiet", "--target", str(site), "--python", sys.executable, *REQUIREMENTS],
        check=True,
    )
    shutil.copy2(HERE / "settings_editor.py", target / "settings_editor.py")
    prune(site)
    return target


if __name__ == "__main__":
    print(f"外掛已建置：{build()}")
```

- [ ] **Step 6: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_plugin_build.py -q`
Expected: 全部 PASS

- [ ] **Step 7: 修改 `build.bat`**

1. `cd /d "%~dp0"` 下一行加入 `setlocal EnableDelayedExpansion`
2. `echo Building WebService-Tool...` 之前加入：

```bat
echo Collecting hidden imports for the settings editor plugin...
set "HIDDEN="
for /f "usebackq eol=# delims=" %%m in ("plugins\settings_editor\host_imports.txt") do set "HIDDEN=!HIDDEN! --hidden-import=%%m"
```

3. pyinstaller 指令在 `-n WebService-Tool` 與 `src\ws_tool.py` 之間插入 `!HIDDEN!`：

```bat
"%UV%" run pyinstaller --clean --noconfirm --log-level=WARN --icon=assets/app_icon.ico --add-data "assets;assets" --version-file src\config\file_version_info.txt -F -w -n WebService-Tool !HIDDEN! src\ws_tool.py
```

4. 主程式建置成功後、`echo Build process finished` 之前加入：

```bat
echo.
echo Building settings editor plugin...
"%UV%" run python plugins\settings_editor\build_plugin.py
if errorlevel 1 (
    echo.
    echo [ERROR] Plugin build failed.
    pause
    exit /b 1
)
```

5. 結尾訊息改為 `echo Build process finished: dist\WebService-Tool.exe + dist\plugins\settings_editor`

- [ ] **Step 8: 更新文件**

`README.md`：
- 「介面」的快捷鍵清單加入 `F11 工具參數設定（再按一次或 Esc 返回）`
- 「介面」新增一條：`按 F11 以樹狀表單編輯 app_data/ws_tool.yaml；名稱、版本、版權、圖示、逾時儲存後立即生效，log 與連線設定需重新啟動`
- 「開發說明」第 5 點後補充：`build.bat 會一併產生 dist/plugins/settings_editor/（設定編輯器外掛，含 pyqtgraph、numpy）；散布時放在 exe 同層即可使用 F11 設定頁，不附上則 F11 顯示「未安裝」。升級 pyqtgraph／numpy 時同步修改 pyproject.toml 與 plugins/settings_editor/build_plugin.py 的版本，並執行 uv run python plugins/settings_editor/gen_host_imports.py 重新產生 host_imports.txt`

`AGENTS.md`「專案概覽」清單在 `src/ws_tool.py` 那行後加入：
- `` `plugins/settings_editor/` — 設定編輯器外掛（pyqtgraph ParameterTree），另外打包；不可 import `src.*`，主程式不可直接依賴 pyqtgraph ``

- [ ] **Step 9: 全部測試無回歸**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 全部 PASS

- [ ] **Step 10: 實機打包驗證**

Run（bash）：`cmd //c "build.bat" < /dev/null`（`< /dev/null` 讓結尾的 `pause` 直接結束）
Expected: `dist\WebService-Tool.exe` 與 `dist\plugins\settings_editor\`（含 `settings_editor.py`、`site-packages\pyqtgraph`、`site-packages\numpy`，且無 `pyqtgraph\examples`）

準備執行環境：`cp -r src/app_data dist/app_data`（README 規定 app_data 需與 exe 同層）

請使用者手動確認（回報結果）：
1. 啟動 `dist\WebService-Tool.exe`，按 F11 出現參數樹；改逾時為 60 → 儲存 → 綠色通知、返回後逾時欄位為 60；改名稱 → 視窗標題即時變更
2. 改 log level → 儲存 → 黃色「需重新啟動」通知
3. 關閉程式，把 `dist\plugins` 改名為 `dist\plugins_off`，重新啟動按 F11 → 顯示「設定編輯器外掛未安裝」與預期路徑；其他功能正常
4. 檢查 `dist\app_data\logs\run.log` 無外掛載入錯誤

驗證完成後刪除 `dist\app_data`（dist 已在 .gitignore，不會進版控）。

- [ ] **Step 11: Commit**

```
外掛打包：產生主程式 hiddenimports 清單、建置外掛資料夾，更新文件

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

```bash
git add plugins/settings_editor/gen_host_imports.py plugins/settings_editor/host_imports.txt plugins/settings_editor/build_plugin.py build.bat README.md AGENTS.md tests/test_plugin_build.py
git commit -F <暫存檔>
```
