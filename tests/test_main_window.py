# -*- coding: utf-8 -*-
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication

from src.core.connection_store import ConnectionStore
from src.core.soap_service import CallResult
from src.ui.main_window import AboutInfo, MainWindow, format_size
from src.ui.theme import DARK, ThemeManager, ThemeMode

ABOUT = AboutInfo("WebService 測試工具", "v2.0.0", "Copyright", "https://example.com")


class FakeService:
    """取代 SoapService：可設定回傳值、錯誤，或用 gate 讓呼叫停住"""

    def __init__(self):
        self.methods = ["AddTwo", "GetPOData"]
        self.result = CallResult(text="<ok/>\n", elapsed=0.123, size=5)
        self.error = None
        self.gate = None
        self.calls = []

    def _block_or_fail(self):
        if self.gate is not None:
            self.gate.wait(5)
        if self.error is not None:
            raise self.error

    def load_methods(self, url, timeout):
        self.calls.append(("load", url, timeout))
        self._block_or_fail()
        return list(self.methods)

    def call(self, url, method, raw_params, timeout):
        self.calls.append(("call", url, method, raw_params, timeout))
        self._block_or_fail()
        return self.result


@pytest.fixture
def env(qapp, tmp_path):
    service = FakeService()
    theme = ThemeManager(qapp, QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    theme.apply()
    ctx = SimpleNamespace(store=ConnectionStore(tmp_path / "connections.profile"), service=service, theme=theme)
    windows = []

    def make(store=None):
        window = MainWindow(store or ctx.store, service, theme, ABOUT, default_timeout=30)
        window._confirm = lambda title, text: True
        windows.append(window)
        return window

    ctx.make = make
    yield ctx
    if service.gate is not None:
        service.gate.set()
    for window in windows:
        window._confirm = lambda title, text: True
        window.close()
        window.deleteLater()


def seed(store, name="正式區", url="http://prod/ws?WSDL", methods=("GetPOData",)):
    uuid = store.add().uuid
    store.rename(uuid, name)
    store.set_url(uuid, url)
    store.set_methods(uuid, list(methods))
    return uuid


def combo_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def test_format_size():
    assert format_size(5) == "5 B"
    assert format_size(3174) == "3.1 KB"
    assert format_size(3 * 1024 * 1024) == "3.0 MB"


def test_empty_store_gets_blank_connection(env):
    window = env.make()
    connections = env.store.all()
    assert len(connections) == 1
    assert window.connection_list.current_uuid() == connections[0].uuid
    assert window.notification.level == "info"
    assert window.windowTitle() == "WebService 測試工具"


def test_corrupt_profile_shows_warning(env, tmp_path):
    path = tmp_path / "broken.profile"
    path.write_text("{ not json", encoding="utf-8")
    window = env.make(ConnectionStore(path))
    assert window.notification.level == "warning"
    assert "broken.profile.bak" in window.notification.text


def test_selecting_connection_fills_fields(env):
    seed(env.store)
    window = env.make()
    assert window.name_edit.text() == "正式區"
    assert window.url_edit.text() == "http://prod/ws?WSDL"
    assert combo_items(window.method_combo) == ["GetPOData"]
    assert window.method_combo.currentText() == "GetPOData"
    assert window.timeout_spin.value() == 30
    assert window.status_state.text() == "就緒"


def test_name_and_url_saved_on_editing_finished(env):
    uuid = seed(env.store)
    window = env.make()
    window.name_edit.setText("新名稱")
    window.name_edit.editingFinished.emit()
    window.url_edit.setText("http://new/ws?WSDL")
    window.url_edit.editingFinished.emit()
    reloaded = ConnectionStore(env.store.path).get(uuid)
    assert (reloaded.name, reloaded.url) == ("新名稱", "http://new/ws?WSDL")
    assert window.connection_list.item_widget(uuid).title.text() == "新名稱"


def test_switching_connection_commits_pending_edits(env):
    first = seed(env.store, "A")
    second = seed(env.store, "B")
    window = env.make()
    window.name_edit.setText("A2")  # 尚未觸發 editingFinished
    window.connection_list.select(second)
    assert env.store.get(first).name == "A2"
    assert window.name_edit.text() == "B"


def test_url_hint_when_missing_wsdl_suffix(env):
    seed(env.store)
    window = env.make()
    assert window.url_hint.isHidden()
    window.url_edit.setText("http://prod/ws")
    assert not window.url_hint.isHidden()
    window.url_edit.setText("http://prod/ws?wsdl")
    assert window.url_hint.isHidden()


def test_add_creates_and_selects(env):
    seed(env.store)
    window = env.make()
    window.connection_list.add_button.click()
    connections = env.store.all()
    assert len(connections) == 2
    assert window.connection_list.current_uuid() == connections[1].uuid
    assert window.name_edit.text() == ""


def test_delete_confirmed_removes_and_keeps_other_selected(env):
    first = seed(env.store, "A")
    second = seed(env.store, "B")
    window = env.make()
    window.connection_list.deleteRequested.emit(second)
    assert [conn.uuid for conn in env.store.all()] == [first]
    assert window.connection_list.current_uuid() == first
    assert window.notification.level == "success"


def test_delete_cancelled_keeps_connection(env):
    uuid = seed(env.store)
    window = env.make()
    window._confirm = lambda title, text: False
    window.connection_list.deleteRequested.emit(uuid)
    assert env.store.get(uuid) is not None


def test_deleting_last_connection_creates_blank(env):
    uuid = seed(env.store)
    window = env.make()
    window.connection_list.deleteRequested.emit(uuid)
    remaining = env.store.all()
    assert len(remaining) == 1
    assert remaining[0].uuid != uuid and remaining[0].name == ""
    assert window.name_edit.text() == ""


def test_clear_empties_editors_but_keeps_methods(env):
    seed(env.store)
    window = env.make()
    window.request_editor.setPlainText("<r/>")
    window.response_editor.setPlainText("<ok/>")
    window.clear_button.click()
    assert window.request_editor.toPlainText() == ""
    assert window.response_editor.toPlainText() == ""
    assert combo_items(window.method_combo) == ["GetPOData"]


def test_format_request(env):
    seed(env.store)
    window = env.make()
    window.request_editor.setPlainText("<a><b/></a>")
    window.format_button.click()
    assert window.request_editor.toPlainText() == "<a>\n  <b/>\n</a>\n"


def test_format_invalid_request_warns(env):
    seed(env.store)
    window = env.make()
    window.request_editor.setPlainText("<a>")
    window.format_button.click()
    assert window.request_editor.toPlainText() == "<a>"
    assert window.notification.level == "warning"
    assert window.notification.text == "請求內容不是合法的 XML，無法格式化"


def test_copy_response(env):
    seed(env.store)
    window = env.make()
    window.response_editor.setPlainText("<ok/>")
    window.copy_button.click()
    assert QGuiApplication.clipboard().text() == "<ok/>"
    assert window.notification.text == "已複製回應結果"


def test_copy_empty_response_informs(env):
    seed(env.store)
    window = env.make()
    window.copy_button.click()
    assert window.notification.text == "沒有可複製的回應內容"


def test_theme_change_recolors_editors_and_menu(env):
    window = env.make()
    env.theme.set_mode(ThemeMode.DARK)
    assert window.request_editor.colors == DARK.xml
    assert window.response_editor.colors == DARK.xml
    assert window.theme_actions[ThemeMode.DARK].isChecked()


def test_theme_menu_action_sets_mode(env):
    window = env.make()
    window.theme_actions[ThemeMode.LIGHT].trigger()
    assert env.theme.mode is ThemeMode.LIGHT
    assert window.theme_actions[ThemeMode.LIGHT].isChecked()


def test_close_requires_confirmation(env):
    uuid = seed(env.store)
    window = env.make()
    window.name_edit.setText("關閉前修改")
    window._confirm = lambda title, text: False
    assert window.close() is False
    window._confirm = lambda title, text: True
    assert window.close() is True
    assert env.store.get(uuid).name == "關閉前修改"
