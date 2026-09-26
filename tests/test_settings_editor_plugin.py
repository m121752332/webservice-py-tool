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
