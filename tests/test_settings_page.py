# -*- coding: utf-8 -*-
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

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


# ---------- 輸入中尚未提交的值 ----------

def type_into(page, *names, text):
    """模擬使用者輸入但尚未按 Enter／移開焦點（pyqtgraph 尚未提交到參數）"""
    line = next(iter(page.editor.parameters().child(*names).items)).widget
    line.selectAll()
    QTest.keyClicks(line, text)


def test_typing_enables_buttons_before_commit(page):
    type_into(page, "app", "name", text="NEWNAME")
    assert page.editor.parameters().child("app", "name").value() == "TIPTOP WebService Tool"
    assert page.save_button.isEnabled() and page.revert_button.isEnabled()


def test_is_dirty_commits_pending_edit(page):
    type_into(page, "app", "name", text="NEWNAME")
    assert page.is_dirty()
    assert page.editor.values()["app.name"] == "NEWNAME"


def test_save_writes_pending_edit(page, path):
    type_into(page, "app", "name", text="NEWNAME")
    assert page.save() is True
    assert path.read_text(encoding="utf-8") == SETTINGS_YAML.replace("TIPTOP WebService Tool", "NEWNAME")
    assert not page.save_button.isEnabled()


def test_revert_discards_pending_edit(page):
    type_into(page, "app", "name", text="NEWNAME")
    page.revert()
    assert page.editor.values()["app.name"] == "TIPTOP WebService Tool"
    assert not page.is_dirty() and not page.save_button.isEnabled()


class _MinimalTree(QWidget):
    """只實作 API 版本 1 必要介面（沒有 commit、valueEditing）的外掛"""
    valueChanged = Signal()

    def load(self, fields):
        self._values = {f["key"]: f["value"] for f in fields if f["kind"] != "group"}

    def values(self):
        return dict(self._values)

    def set_palette(self, colors):
        pass


def test_plugin_without_optional_commit_still_works(qapp, path):
    page = SettingsPage(SimpleNamespace(SettingsTree=_MinimalTree), LIGHT)
    page.open(path)
    assert not page.is_dirty()
    page.editor._values["app.timeout"] = 60
    assert page.is_dirty()
    assert page.save() is True
    assert "timeout: 60" in path.read_text(encoding="utf-8")
    page.deleteLater()
