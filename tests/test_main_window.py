# -*- coding: utf-8 -*-
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView

from src.core.connection_store import ConnectionStore
from src.core.soap_service import CallResult, ParamCountMismatch
from src.ui.main_window import AboutInfo, CANCEL_LABEL, LOAD_LABEL, MainWindow, RUN_LABEL, format_size
from src.ui.theme import DARK, ThemeManager, ThemeMode
from tests.helpers import wait_until

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


def press_shortcut(window, key):
    shortcut = next(sc for sc in window.findChildren(QShortcut) if sc.key() == QKeySequence(key))
    shortcut.activated.emit()


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


def test_add_with_active_search_filter_selects_visible_row(env):
    seed(env.store, "正式區")
    window = env.make()
    window.connection_list.search_edit.setText("找不到的關鍵字")
    window.connection_list.add_button.click()
    new_uuid = window.connection_list.current_uuid()
    assert new_uuid is not None
    assert new_uuid in window.connection_list.visible_uuids()
    assert window.connection_list.search_edit.text() == ""


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


def test_load_success_saves_methods(env):
    uuid = seed(env.store, methods=())
    window = env.make()
    window.load_button.click()
    wait_until(lambda: env.store.get(uuid).methods)
    assert env.store.get(uuid).methods == ["AddTwo", "GetPOData"]
    assert combo_items(window.method_combo) == ["AddTwo", "GetPOData"]
    assert window.request_editor.toPlainText() == '<?xml version="1.0" encoding="utf-8"?>'
    assert (window.status_state.text(), window.status_detail.text()) == ("● 成功", "讀取完成 · 2 個方法")
    assert window.load_button.text() == LOAD_LABEL
    assert env.service.calls == [("load", "http://prod/ws?WSDL", 30)]


def test_load_keeps_existing_request(env):
    seed(env.store, methods=())
    window = env.make()
    window.request_editor.setPlainText("<Request/>")
    window.load_button.click()
    wait_until(lambda: window.status_state.text() == "● 成功")
    assert window.request_editor.toPlainText() == "<Request/>"


def test_load_uses_unsaved_url(env):
    uuid = seed(env.store)
    window = env.make()
    window.url_edit.setText("http://typed/ws?WSDL")  # 尚未觸發 editingFinished
    window.load_button.click()
    wait_until(lambda: window.status_state.text() == "● 成功")
    assert env.service.calls == [("load", "http://typed/ws?WSDL", 30)]
    assert env.store.get(uuid).url == "http://typed/ws?WSDL"


def test_load_without_url_warns(env):
    seed(env.store, url="")
    window = env.make()
    window.load_button.click()
    assert window.notification.level == "warning"
    assert window.notification.text == "請填寫 WSDL 網址"
    assert env.service.calls == []


def test_load_failure_shows_error(env):
    seed(env.store)
    env.service.error = ConnectionError("連不上")
    window = env.make()
    window.load_button.click()
    wait_until(lambda: window.status_state.text() == "● 失敗")
    assert window.notification.level == "error"
    assert window.notification.text == "讀取 WSDL 失敗：連不上"
    assert window.load_button.isEnabled() and window.run_button.isEnabled()


def test_run_success_shows_response_and_stats(env):
    seed(env.store)
    window = env.make()
    window.request_editor.setPlainText("<Request/>")
    window.timeout_spin.setValue(45)
    window.run_button.click()
    wait_until(lambda: window.status_state.text() == "● 成功")
    assert window.response_editor.toPlainText() == "<ok/>\n"
    assert window.status_detail.text() == "0.12 s · 5 B"
    assert window.run_button.text() == RUN_LABEL
    assert env.service.calls == [("call", "http://prod/ws?WSDL", "GetPOData", "<Request/>", 45)]


def test_run_requires_known_method(env):
    seed(env.store, methods=())
    window = env.make()
    window.run_button.click()
    assert window.notification.level == "warning"
    assert window.notification.text == "請選擇服務方法（可先按「讀取 WSDL」取得清單）"
    assert env.service.calls == []


def test_run_param_mismatch_shows_warning(env):
    seed(env.store)
    env.service.error = ParamCountMismatch(2, 1)
    window = env.make()
    window.run_button.click()
    wait_until(lambda: window.status_state.text() == "● 失敗")
    assert window.notification.level == "warning"
    assert window.notification.text == str(ParamCountMismatch(2, 1))
    assert window.status_detail.text() == "參數數量不符"


def test_run_failure_shows_error(env):
    seed(env.store)
    env.service.error = TimeoutError("timed out")
    window = env.make()
    window.run_button.click()
    wait_until(lambda: window.status_state.text() == "● 失敗")
    assert window.notification.level == "error"
    assert window.notification.text == "請求失敗：timed out"


def test_busy_state_disables_other_actions(env):
    seed(env.store)
    env.service.gate = threading.Event()
    window = env.make()
    window.run_button.click()
    assert window.run_button.text() == CANCEL_LABEL and window.run_button.isEnabled()
    assert not window.load_button.isEnabled()
    assert not window.clear_button.isEnabled()
    assert not window.url_edit.isEnabled()
    assert not window.connection_list.tree.isEnabled()
    assert not window.connection_list.add_folder_button.isEnabled()
    assert window.status_state.text() == "執行中…"
    env.service.gate.set()
    wait_until(lambda: window.status_state.text() == "● 成功")
    assert window.load_button.isEnabled() and window.connection_list.tree.isEnabled()


def test_cancel_ignores_late_result(env):
    seed(env.store)
    env.service.gate = threading.Event()
    window = env.make()
    window.run_button.click()
    window.run_button.click()  # 取消
    assert window.run_button.text() == RUN_LABEL
    assert window.load_button.isEnabled()
    assert window.status_state.text() == "已取消"
    task = next(iter(window._tasks.values()))
    env.service.gate.set()
    task.join(3)
    wait_until(lambda: not window._tasks)
    assert window.response_editor.toPlainText() == ""
    assert window.status_state.text() == "已取消"


def test_cancel_load(env):
    uuid = seed(env.store, methods=())
    env.service.gate = threading.Event()
    window = env.make()
    window.load_button.click()
    assert window.load_button.text() == CANCEL_LABEL
    task = next(iter(window._tasks.values()))
    window.load_button.click()
    env.service.gate.set()
    task.join(3)
    wait_until(lambda: not window._tasks)
    assert env.store.get(uuid).methods == []
    assert window.load_button.text() == LOAD_LABEL


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
