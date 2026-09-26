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
_BOM = "﻿"
_KEY_LINE = re.compile(r"^(?P<indent> *)(?P<key>[A-Za-z_][\w-]*):(?P<rest>(?:[ \t].*)?)$")
_DOUBLE = re.compile(r'"(?:[^"\\]|\\.)*"')
_SINGLE = re.compile(r"'(?:[^']|'')*'")
_PLAIN = re.compile(r".*?(?=\s+#|\s*$)")  # 值不會以 # 開頭；「C#」、「/#top」等 # 前無空白者屬於值


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
