# -*- coding: utf-8 -*-
import threading
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest
from loguru import logger
from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication, QKeySequence, QPixmap, QShortcut
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QApplication, QMessageBox

from src.config.app_settings import TIMEOUT_MAX, AppSettings
from src.core.connection_store import ConnectionStore
from src.core.log_buffer import LogBuffer
from src.core.soap_service import CallResult, ParamCountMismatch
from src.core.xml_log import CallRecord
from src.ui import main_window as main_window_module
from src.ui.log_console import ConsoleSettings
from src.ui.main_window import AboutInfo, CANCEL_LABEL, LOAD_LABEL, MainWindow, RUN_LABEL, format_size
from src.ui.theme import DARK, ThemeManager, ThemeMode
from tests.helpers import wait_until, write_settings

ABOUT = AboutInfo("WebService 測試工具", "v2.0.0", "Copyright", "https://example.com")


class FakeService:
    """取代 SoapService：可設定回傳值、錯誤，或用 gate 讓呼叫停住"""

    def __init__(self):
        self.methods = ["AddTwo", "GetPOData"]
        self.result = CallResult(text="<ok/>\n", elapsed=0.123, size=5)
        self.error = None
        self.gate = None
        self.calls = []
        self.connections = []

    def _block_or_fail(self):
        if self.gate is not None:
            self.gate.wait(5)
        if self.error is not None:
            raise self.error

    def load_methods(self, url, timeout):
        self.calls.append(("load", url, timeout))
        self._block_or_fail()
        return list(self.methods)

    def call(self, url, method, raw_params, timeout, connection=""):
        self.calls.append(("call", url, method, raw_params, timeout))
        self.connections.append(connection)
        self._block_or_fail()
        return self.result


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

    def make(store=None, xml_log_dir=None):
        window = MainWindow(
            store or ctx.store, service, theme, ABOUT, default_timeout=30, settings_path=settings_path,
            settings=qsettings, log_buffer=log_buffer, xml_log_dir=xml_log_dir,
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


def test_run_passes_connection_name(env):
    seed(env.store, name="訂單服務")
    window = env.make()
    window.run_button.click()
    wait_until(lambda: window.status_state.text() == "● 成功")
    assert env.service.connections == ["訂單服務"]


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


# ---------- F1：選取目錄時停用工作區 ----------

def test_selecting_folder_disables_workspace_fields(env):
    uuid = seed(env.store)
    folder = env.store.add_folder("TIPTOP").uuid
    window = env.make()
    window.connection_list.select(folder)
    assert not window.name_edit.isEnabled()
    assert not window.url_edit.isEnabled()
    assert not window.method_combo.isEnabled()
    assert not window.timeout_spin.isEnabled()
    assert not window.load_button.isEnabled()
    assert not window.run_button.isEnabled()
    assert not window.clear_button.isEnabled()
    window.connection_list.select(uuid)
    assert window.name_edit.isEnabled()
    assert window.url_edit.isEnabled()
    assert window.method_combo.isEnabled()
    assert window.timeout_spin.isEnabled()
    assert window.load_button.isEnabled()
    assert window.run_button.isEnabled()
    assert window.clear_button.isEnabled()


def test_methods_loaded_ignores_unknown_or_none_uuid(env):
    """對應 F1 的 KeyError(None) 問題：uuid 為 None（目錄選取中）或已不存在時不應丟例外或寫入"""
    uuid = seed(env.store, methods=())
    window = env.make()
    window._on_methods_loaded(None, ["X"])
    window._on_methods_loaded("does-not-exist", ["Y"])
    assert env.store.get(uuid).methods == []
    assert env.store.get("does-not-exist") is None


def test_load_and_run_are_noop_without_selected_connection(env):
    seed(env.store)
    folder = env.store.add_folder("TIPTOP").uuid
    window = env.make()
    window.connection_list.select(folder)
    window._on_load_clicked()
    window._on_run_clicked()
    assert env.service.calls == []
    assert window._pending is None


# ---------- F6：重建清單重新選回同一筆連線時保留方法下拉選取 ----------

def test_rebuild_keeps_current_connections_selected_method(env):
    uuid = seed(env.store, methods=("A", "B"))
    window = env.make()
    window.method_combo.setCurrentText("B")
    window.connection_list.connectionMoved.emit(uuid, None, 0)  # 觸發重建，該連線仍是目前選取
    assert window.method_combo.currentText() == "B"


# ---------- 熱重載工具參數 ----------

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


# ---------- F11：設定頁切換、未存檔保護 ----------

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
    assert not window.connection_list.isEnabled()
    assert not any(shortcut_enabled(window, key) for key in WORKSPACE_KEYS)
    assert shortcut_enabled(window, "F11") and shortcut_enabled(window, "Esc")


def test_f11_again_returns_to_workspace(env):
    window = env.make()
    open_settings(window)
    press_shortcut(window, "F11")
    assert window.stack.currentWidget() is window.workspace
    assert window.connection_list.isEnabled()
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


def type_setting(page, *names, text):
    """模擬在設定頁輸入但尚未按 Enter／移開焦點（值還沒提交到參數）"""
    line = next(iter(page.editor.parameters().child(*names).items)).widget
    line.selectAll()
    QTest.keyClicks(line, text)


def test_f11_with_pending_typing_asks_and_saves(env, app_calls):
    window = env.make()
    page = open_settings(window)
    type_setting(page, "app", "name", text="NEWNAME")
    assert page.save_button.isEnabled()
    asked = []
    window._ask_unsaved = lambda: asked.append(1) or QMessageBox.StandardButton.Save
    press_shortcut(window, "F11")
    assert asked == [1]
    assert window.stack.currentWidget() is window.workspace
    assert 'name: "NEWNAME"' in env.settings_path.read_text(encoding="utf-8")
    assert window.windowTitle() == "NEWNAME"


@pytest.mark.parametrize("leave", ["Esc", "back", "close"])
def test_leaving_with_pending_typing_asks(env, leave):
    window = env.make()
    page = open_settings(window)
    type_setting(page, "app", "name", text="NEWNAME")
    asked = []
    window._ask_unsaved = lambda: asked.append(1) or QMessageBox.StandardButton.Cancel
    if leave == "Esc":
        press_shortcut(window, "Esc")
    elif leave == "back":
        page.back_button.click()
    else:
        assert window.close() is False
    assert asked == [1]
    assert window.stack.currentWidget() is page


def test_unsaved_save_forwards_restart_warning_to_workspace(env, app_calls):
    window = env.make()
    page = open_settings(window)
    page.editor.parameters().child("app", "log", "level").setValue("debug")
    window._ask_unsaved = lambda: QMessageBox.StandardButton.Save
    press_shortcut(window, "F11")
    assert window.stack.currentWidget() is window.workspace
    assert window.notification.level == "warning"
    assert "app.log.level" in window.notification.text
    assert not window.notification.isHidden()


def test_unsaved_save_forwards_missing_icon_warning_to_workspace(env, app_calls):
    window = env.make()
    page = open_settings(window)
    page.editor.parameters().child("app", "img").setValue("not/exist.ico")
    window._ask_unsaved = lambda: QMessageBox.StandardButton.Save
    press_shortcut(window, "F11")
    assert window.notification.level == "warning"
    assert "找不到圖示檔" in window.notification.text


def test_leaving_after_success_does_not_forward(env, app_calls):
    window = env.make()
    page = open_settings(window)
    page.editor.parameters().child("app", "timeout").setValue(60)
    page.save_button.click()
    assert page.notification.level == "success"
    before = (window.notification.level, window.notification.text)
    press_shortcut(window, "F11")
    assert (window.notification.level, window.notification.text) == before


# ---------- 只熱重載有變更的欄位 ----------

def test_apply_app_settings_only_given_keys(env, app_calls):
    window = env.make()
    window.timeout_spin.setValue(40)
    window.apply_app_settings(AppSettings("新名稱", "v9.9.9", "新版權", "not/exist.ico", 60), keys=("app.version",))
    assert window._about == AboutInfo(ABOUT.name, "v9.9.9", ABOUT.copyright, ABOUT.website)
    assert window.windowTitle() != "新名稱" and app_calls.names == []
    assert app_calls.icons == [] and "找不到圖示檔" not in window.notification.text
    assert window.timeout_spin.value() == 40


def test_saving_name_only_keeps_session_timeout_and_icon(env, app_calls):
    window = env.make()
    window.timeout_spin.setValue(40)
    page = open_settings(window)
    page.editor.parameters().child("app", "name").setValue("新名稱")
    page.save_button.click()
    assert window.windowTitle() == "新名稱"
    assert window._about.name == "新名稱"
    assert window.timeout_spin.value() == 40
    assert app_calls.icons == []


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
    window.resize(1100, 900)  # 700 高時工作區最小高度會把面板壓到 300 以下
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


# ---------- 請求紀錄（F10） ----------

def make_record(**changes):
    base = CallRecord(
        time=datetime(2026, 9, 26, 9, 0), connection="正式區", url="http://prod/ws?WSDL", method="GetPOData",
        status="success", elapsed=0.1, size=5, params="<Request>old</Request>",
    )
    return replace(base, **changes)


def test_record_button_hidden_without_log_dir(env):
    window = env.make()
    assert window.record_button is None
    assert not any(sc.key() == QKeySequence("F10") for sc in window.findChildren(QShortcut))


def test_record_button_and_f10_open_viewer(env, tmp_path):
    window = env.make(xml_log_dir=tmp_path)
    assert footer_buttons(window)[-1] is window.record_button
    assert window.record_button.text() == "" and "F10" in window.record_button.toolTip()
    press_shortcut(window, "F10")
    viewer = window.xml_log_viewer
    assert viewer is not None and viewer.isVisible()
    window.record_button.click()
    assert window.xml_log_viewer is viewer  # 只建立一次


def test_footer_buttons_fit_sidebar_with_record_button(env, tmp_path):
    window = env.make(xml_log_dir=tmp_path)
    footer = window.sidebar.layout().itemAt(2).layout()
    buttons = footer_buttons(window)
    needed = sum(b.sizeHint().width() for b in buttons) + footer.spacing() * (len(buttons) - 1)
    margins = window.sidebar.layout().contentsMargins()
    assert needed <= window.sidebar.width() - margins.left() - margins.right()


def test_load_record_selects_connection_and_fills_fields(env, tmp_path):
    seed(env.store, name="測試區", url="http://test/ws?WSDL")
    target = seed(env.store, methods=("AddTwo", "GetPOData"))
    window = env.make(xml_log_dir=tmp_path)
    window.load_record(make_record())
    assert window.connection_list.current_uuid() == target
    assert window.method_combo.currentText() == "GetPOData"
    assert window.request_editor.toPlainText() == "<Request>old</Request>"
    assert window.notification.level == "info"


def test_load_record_falls_back_to_url_match(env, tmp_path):
    target = seed(env.store, name="改過名字")
    window = env.make(xml_log_dir=tmp_path)
    window.load_record(make_record(connection="舊名字", url="http://PROD/ws?WSDL"))
    assert window.connection_list.current_uuid() == target


def test_load_record_without_matching_connection_warns(env, tmp_path):
    seed(env.store)
    window = env.make(xml_log_dir=tmp_path)
    window.load_record(make_record(url="http://other/ws?WSDL"))
    assert window.notification.level == "warning"
    assert "找不到對應的連線" in window.notification.text


def test_load_record_while_busy_warns(env, tmp_path):
    seed(env.store)
    env.service.gate = threading.Event()
    window = env.make(xml_log_dir=tmp_path)
    window.run_button.click()
    window.load_record(make_record(params="<Request>new</Request>"))
    assert window.notification.level == "warning"
    assert window.request_editor.toPlainText() != "<Request>new</Request>"


def test_load_record_without_params_keeps_editor(env, tmp_path):
    seed(env.store)
    window = env.make(xml_log_dir=tmp_path)
    window.request_editor.setPlainText("<keep/>")
    window.load_record(make_record(params="", sent="<S/>"))
    assert window.request_editor.toPlainText() == "<keep/>"
    assert window.notification.level == "warning"


def test_viewer_resend_signal_calls_load_record(env, tmp_path):
    target = seed(env.store)
    window = env.make(xml_log_dir=tmp_path)
    window.open_xml_log_viewer()
    window.xml_log_viewer.resendRequested.emit(make_record())
    assert window.connection_list.current_uuid() == target


def test_theme_change_updates_viewer(env, tmp_path):
    window = env.make(xml_log_dir=tmp_path)
    window.open_xml_log_viewer()
    env.theme.set_mode(ThemeMode.DARK)
    assert window.xml_log_viewer.editors["params"].colors == DARK.xml
