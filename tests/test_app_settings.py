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
