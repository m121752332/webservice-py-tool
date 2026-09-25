# -*- coding: utf-8 -*-
"""
主視窗：左側連線清單 + 右側工作區
"""
from dataclasses import dataclass

from loguru import logger
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.core.connection_store import Connection, ConnectionStore
from src.core.soap_service import CallResult, ParamCountMismatch, format_xml
from src.ui.connection_list import FOLDER_UNNAMED, UNNAMED, ConnectionList
from src.ui.notification_bar import NotificationBar
from src.ui.theme import ThemeManager, ThemeMode, ThemePalette, repolish
from src.ui.workers import run_in_background
from src.ui.xml_editor import XmlEditor

XML_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>'
TIMEOUT_MIN = 5
TIMEOUT_MAX = 120
LOG_TEXT_CAP = 2000
LOAD_LABEL = "讀取 WSDL"
RUN_LABEL = "▶ 執行"
CANCEL_LABEL = "取消"
NEW_FOLDER_NAME = "新目錄"
THEME_LABELS = {ThemeMode.SYSTEM: "跟隨系統", ThemeMode.LIGHT: "淺色", ThemeMode.DARK: "深色"}


@dataclass(frozen=True)
class AboutInfo:
    name: str
    version: str
    copyright: str
    website: str


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def _cap(text: str) -> str:
    """記錄檔用：避免超長內容把 run.log 灌爆"""
    if len(text) <= LOG_TEXT_CAP:
        return text
    return text[:LOG_TEXT_CAP] + f"…（已截斷，共 {len(text)} 字元）"


def _button(text: str, variant: str | None = None, tooltip: str = "") -> QPushButton:
    button = QPushButton(text)
    if variant:
        button.setProperty("variant", variant)
    if tooltip:
        button.setToolTip(tooltip)
    return button


class MainWindow(QMainWindow):
    def __init__(self, store: ConnectionStore, service, theme: ThemeManager, about: AboutInfo,
                 default_timeout: int, parent=None):
        super().__init__(parent)
        self._store = store
        self._service = service
        self._theme = theme
        self._about = about
        self._current_uuid: str | None = None
        self._methods: list[str] = []
        self._pending = None  # 進行中工作的 tag：(kind, seq, uuid)
        self._seq = 0
        self._tasks = {}  # tag -> Task，保留參照直到收到回呼

        self.setWindowTitle(about.name)
        self.resize(1100, 700)
        self.setMinimumSize(900, 560)
        self._build_ui(default_timeout)
        self._build_shortcuts()
        self._connect_signals()
        self._theme.themeChanged.connect(self._on_theme_changed)
        self._reset_status()
        self._load_initial_connections()

    # ---------- 版面 ----------

    def _build_ui(self, default_timeout: int) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_workspace(default_timeout), 1)
        self.setCentralWidget(central)

        self.status_state = QLabel()
        self.status_state.setObjectName("StatusState")
        self.status_detail = QLabel()
        self.status_detail.setObjectName("StatusDetail")
        self.statusBar().addWidget(self.status_state)
        self.statusBar().addWidget(self.status_detail, 1)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        title = QLabel(self._about.name)
        title.setObjectName("AppTitle")
        title.setWordWrap(True)
        self.connection_list = ConnectionList()

        self.theme_button = _button("◐ 主題", "subtle", "切換淺色 / 深色主題")
        self.theme_button.setMenu(self._build_theme_menu())
        self.about_button = _button("ⓘ 關於", "subtle")
        footer = QHBoxLayout()
        footer.setSpacing(4)
        footer.addWidget(self.theme_button)
        footer.addWidget(self.about_button)
        footer.addStretch(1)

        layout.addWidget(title)
        layout.addWidget(self.connection_list, 1)
        layout.addLayout(footer)
        return sidebar

    def _build_theme_menu(self) -> QMenu:
        menu = QMenu(self)
        group = QActionGroup(menu)
        group.setExclusive(True)
        self.theme_actions: dict[ThemeMode, QAction] = {}
        for mode, label in THEME_LABELS.items():
            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(mode is self._theme.mode)
            action.triggered.connect(lambda _checked=False, m=mode: self._theme.set_mode(m))
            group.addAction(action)
            menu.addAction(action)
            self.theme_actions[mode] = action
        return menu

    def _build_workspace(self, default_timeout: int) -> QWidget:
        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(12)

        layout.addWidget(self._build_request_card(default_timeout))
        self.notification = NotificationBar()
        layout.addWidget(self.notification)

        self.request_editor = XmlEditor(self._theme.palette.xml)
        self.response_editor = XmlEditor(self._theme.palette.xml, read_only=True)
        self.format_button = _button("格式化", "subtle", "格式化請求 XML (Ctrl+Shift+F)")
        self.copy_button = _button("複製", "subtle", "複製回應結果")
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        splitter.addWidget(self._editor_panel("請求參數（多個用 #~# 隔開）", self.format_button, self.request_editor))
        splitter.addWidget(self._editor_panel("回應結果", self.copy_button, self.response_editor))
        splitter.setSizes([1, 1])
        layout.addWidget(splitter, 1)
        return workspace

    def _build_request_card(self, default_timeout: int) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("NameEdit")
        self.name_edit.setPlaceholderText("請輸入配置名稱")
        self.name_edit.setMaxLength(100)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://host/path?WSDL")
        self.load_button = _button(LOAD_LABEL, tooltip="讀取 WSDL 的服務方法 (F3)")
        url_row = QHBoxLayout()
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.load_button)

        self.url_hint = QLabel("結尾請加上 ?WSDL")
        self.url_hint.setObjectName("Hint")
        self.url_hint.hide()

        self.method_combo = QComboBox()
        self.method_combo.setEditable(True)
        self.method_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.method_combo.lineEdit().setPlaceholderText("選擇或搜尋服務方法")
        completer = QCompleter(self.method_combo.model(), self.method_combo)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.method_combo.setCompleter(completer)

        timeout_label = QLabel("逾時")
        timeout_label.setObjectName("FieldLabel")
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(TIMEOUT_MIN, TIMEOUT_MAX)
        self.timeout_spin.setSuffix(" 秒")
        self.timeout_spin.setValue(min(max(default_timeout, TIMEOUT_MIN), TIMEOUT_MAX))
        self.run_button = _button(RUN_LABEL, "primary", "執行請求 (F5)")
        self.clear_button = _button("清空", tooltip="清空請求與回應 (F6)")
        method_row = QHBoxLayout()
        method_row.addWidget(self.method_combo, 1)
        method_row.addWidget(timeout_label)
        method_row.addWidget(self.timeout_spin)
        method_row.addWidget(self.run_button)
        method_row.addWidget(self.clear_button)

        layout.addWidget(self.name_edit)
        layout.addLayout(url_row)
        layout.addWidget(self.url_hint)
        layout.addLayout(method_row)
        return card

    @staticmethod
    def _editor_panel(title: str, button: QPushButton, editor: XmlEditor) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        header = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        header.addWidget(label)
        header.addStretch(1)
        header.addWidget(button)
        layout.addLayout(header)
        layout.addWidget(editor, 1)
        return panel

    def _build_shortcuts(self) -> None:
        for key, handler in (
            ("F1", self._on_add_requested),
            ("F2", self.connection_list.request_delete_current),
            ("F3", self.load_button.click),
            ("F5", self.run_button.click),
            ("F6", self._on_clear),
            ("Ctrl+Shift+F", self._on_format),
            ("Esc", self.close),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)

    def _connect_signals(self) -> None:
        self.connection_list.selectionChanged.connect(self._on_selection_changed)
        self.connection_list.addRequested.connect(self._on_add_requested)
        self.connection_list.deleteRequested.connect(self._on_delete_requested)
        self.connection_list.addFolderRequested.connect(self._on_add_folder_requested)
        self.connection_list.deleteFolderRequested.connect(self._on_delete_folder_requested)
        self.connection_list.folderRenamed.connect(self._on_folder_renamed)
        self.connection_list.folderExpandedChanged.connect(self._on_folder_expanded_changed)
        self.connection_list.connectionMoved.connect(self._on_connection_moved)
        self.connection_list.folderMoved.connect(self._on_folder_moved)
        self.name_edit.editingFinished.connect(self._commit_name)
        self.url_edit.editingFinished.connect(self._commit_url)
        self.url_edit.textChanged.connect(self._update_url_hint)
        self.load_button.clicked.connect(self._on_load_clicked)
        self.run_button.clicked.connect(self._on_run_clicked)
        self.clear_button.clicked.connect(self._on_clear)
        self.format_button.clicked.connect(self._on_format)
        self.copy_button.clicked.connect(self._on_copy)
        self.about_button.clicked.connect(self._show_about)

    # ---------- 連線資料 ----------

    def _refresh_tree(self, select_uuid: str | None = None) -> None:
        """store 結構變動後重建左側清單；未指定 select_uuid 時保留目前選取"""
        self.connection_list.set_tree(self._store.folders(), self._store.all(), select_uuid)

    def _load_initial_connections(self) -> None:
        if self._store.recovered_from_corruption:
            self._notify("warning", f"連線設定檔無法讀取，已備份為 {self._store.backup_path.name} 並重新建立")
        if not self._store.all():
            self._store.add()
            if not self._store.recovered_from_corruption:
                self._notify("info", "請輸入配置名稱與 WSDL 網址（結尾加上 ?WSDL），再按「讀取 WSDL」")
        self._refresh_tree()

    def _current_connection(self) -> Connection | None:
        return self._store.get(self._current_uuid) if self._current_uuid else None

    @Slot(str)
    def _on_selection_changed(self, uuid: str) -> None:
        if self._current_uuid and self._current_uuid != uuid:
            self._commit_fields()  # 切換前先保存上一筆尚未確認的編輯
        if uuid and uuid == self._current_uuid:
            return  # F6：重建清單重新選回同一筆連線，欄位內容已正確，不必重新載入
        self._current_uuid = uuid or None
        conn = self._current_connection()
        self.name_edit.setText(conn.name if conn else "")
        self.url_edit.setText(conn.url if conn else "")
        self._set_methods(conn.methods if conn else [])
        enabled = self._fields_enabled(busy=self._pending is not None)
        for widget in (
            self.name_edit, self.url_edit, self.method_combo, self.timeout_spin,
            self.load_button, self.run_button, self.clear_button,
        ):
            widget.setEnabled(enabled)

    def _commit_fields(self) -> None:
        self._commit_name()
        self._commit_url()

    def _commit_name(self) -> None:
        conn = self._current_connection()
        name = self.name_edit.text().strip()
        if conn is not None and name != conn.name:
            self._store.rename(conn.uuid, name)
            self.connection_list.update_connection(self._store.get(conn.uuid))

    def _commit_url(self) -> None:
        conn = self._current_connection()
        url = self.url_edit.text().strip()
        if conn is not None and url != conn.url:
            self._store.set_url(conn.uuid, url)
            self.connection_list.update_connection(self._store.get(conn.uuid))

    def _set_methods(self, methods: list[str]) -> None:
        self._methods = list(methods)
        self.method_combo.clear()
        self.method_combo.addItems(self._methods)
        if self._methods:
            self.method_combo.setCurrentIndex(0)

    def _update_url_hint(self, text: str) -> None:
        url = text.strip()
        self.url_hint.setVisible(bool(url) and not url.lower().endswith("?wsdl"))

    def _on_add_requested(self) -> None:
        if self._pending:
            return
        self._commit_fields()
        conn = self._store.add(self.connection_list.current_folder())
        self.connection_list.clear_search()  # 避免新連線被搜尋篩選隱藏卻又被選取
        self._refresh_tree(conn.uuid)
        self.name_edit.setFocus()

    @Slot(str)
    def _on_delete_requested(self, uuid: str) -> None:
        if self._pending:
            return
        conn = self._store.get(uuid)
        if conn is None or not self._confirm("刪除連線", f"確定要刪除「{conn.name or UNNAMED}」嗎？"):
            return
        if uuid != self._current_uuid:
            self._commit_fields()
        keep = self._current_uuid if self._current_uuid != uuid else None
        self._current_uuid = None  # 避免把欄位內容寫回即將刪除的連線
        self._store.remove(uuid)
        if not self._store.all():
            self._store.add()
        self._refresh_tree(keep)
        self._notify("success", "已刪除連線")

    # ---------- 目錄 ----------

    def _on_add_folder_requested(self) -> None:
        if self._pending:
            return
        self._commit_fields()
        self.connection_list.clear_search()  # 避免新目錄被搜尋篩選隱藏
        folder = self._store.add_folder(NEW_FOLDER_NAME)
        self._refresh_tree()
        self.connection_list.edit_folder(folder.uuid)

    @Slot(str, str)
    def _on_folder_renamed(self, uuid: str, name: str) -> None:
        self._store.rename_folder(uuid, name)

    @Slot(str, bool)
    def _on_folder_expanded_changed(self, uuid: str, expanded: bool) -> None:
        self._store.set_folder_expanded(uuid, expanded)

    @Slot(str)
    def _on_delete_folder_requested(self, uuid: str) -> None:
        if self._pending:
            return
        folder = self._store.get_folder(uuid)
        if folder is None:
            return
        count = sum(1 for conn in self._store.all() if conn.folder == uuid)
        text = f"確定要刪除目錄「{folder.name or FOLDER_UNNAMED}」嗎？"
        if count:
            text += f"裡面的 {count} 筆連線會移到最外層。"
        if not self._confirm("刪除目錄", text):
            return
        self._commit_fields()
        self._store.remove_folder(uuid)
        self._refresh_tree()
        self._notify("success", "已刪除目錄")

    @Slot(str, object, int)
    def _on_connection_moved(self, uuid: str, folder, index: int) -> None:
        if self._pending:
            return
        self._commit_fields()  # 重建清單會重新載入欄位，先保存尚未確認的編輯
        self._store.move_connection(uuid, folder, index)
        self._refresh_tree()

    @Slot(str, int)
    def _on_folder_moved(self, uuid: str, index: int) -> None:
        if self._pending:
            return
        self._commit_fields()
        self._store.move_folder(uuid, index)
        self._refresh_tree()

    # ---------- 背景讀取與執行 ----------

    def _on_load_clicked(self) -> None:
        if self._pending:
            if self._pending[0] == "load":
                self._cancel()
            return
        if self._current_connection() is None:
            return  # F1：目錄選取中（或快捷鍵繞過停用的按鈕）時沒有可載入的連線
        self._commit_fields()
        url = self.url_edit.text().strip()
        if not url:
            self._notify("warning", "請填寫 WSDL 網址")
            return
        self._start("load", self._service.load_methods, url, self.timeout_spin.value())

    def _on_run_clicked(self) -> None:
        if self._pending:
            if self._pending[0] == "run":
                self._cancel()
            return
        if self._current_connection() is None:
            return  # F1：目錄選取中（或快捷鍵繞過停用的按鈕）時沒有可執行的連線
        self._commit_fields()
        url = self.url_edit.text().strip()
        method = self.method_combo.currentText().strip()
        if not url:
            self._notify("warning", "請填寫 WSDL 網址")
            return
        if method not in self._methods:
            self._notify("warning", "請選擇服務方法（可先按「讀取 WSDL」取得清單）")
            return
        self.response_editor.clear()
        params = self.request_editor.toPlainText()
        logger.info("執行請求 · URL={} · 方法={} · 參數={}", url, method, _cap(params))
        self._run_context = (url, method)
        self._start("run", self._service.call, url, method, params, self.timeout_spin.value())

    def _start(self, kind: str, fn, *args) -> None:
        self._seq += 1
        tag = (kind, self._seq, self._current_uuid)
        self._pending = tag
        self._set_busy(kind)
        self._set_status("busy", "讀取中…" if kind == "load" else "執行中…")
        self._tasks[tag] = run_in_background(
            tag, fn, *args, on_success=self._on_task_succeeded, on_failure=self._on_task_failed
        )

    def _cancel(self) -> None:
        self._finish()
        self._set_status("", "已取消")
        self._notify("info", "已取消。背景請求會在逾時後自動結束")

    def _finish(self) -> None:
        self._pending = None
        self._set_busy(None)

    def _fields_enabled(self, busy: bool) -> bool:
        """工作區欄位可編輯的條件：沒有背景工作進行中，且目前有選取連線（F1）"""
        return not busy and self._current_uuid is not None

    def _set_busy(self, kind: str | None) -> None:
        busy = kind is not None
        self.load_button.setText(CANCEL_LABEL if kind == "load" else LOAD_LABEL)
        self.run_button.setText(CANCEL_LABEL if kind == "run" else RUN_LABEL)
        # 進行中的載入／執行按鈕本身要保持可點擊，作為取消鈕；其餘依 busy 與是否有選取連線決定
        self.load_button.setEnabled(kind == "load" or self._fields_enabled(busy))
        self.run_button.setEnabled(kind == "run" or self._fields_enabled(busy))
        for widget in (self.clear_button, self.name_edit, self.url_edit, self.method_combo, self.timeout_spin):
            widget.setEnabled(self._fields_enabled(busy))
        self.connection_list.set_busy(busy)

    @Slot(object, object)
    def _on_task_succeeded(self, tag, value) -> None:
        self._tasks.pop(tag, None)
        if tag != self._pending:
            return  # 已取消或被新的請求取代
        self._finish()
        kind, _seq, uuid = tag
        if kind == "load":
            self._on_methods_loaded(uuid, value)
        else:
            self._on_call_finished(value)

    @Slot(object, object)
    def _on_task_failed(self, tag, error) -> None:
        self._tasks.pop(tag, None)
        if tag != self._pending:
            return
        self._finish()
        if isinstance(error, ParamCountMismatch):
            self._notify("warning", str(error))
            self._set_status("error", "● 失敗", "參數數量不符")
            return
        action = "讀取 WSDL 失敗" if tag[0] == "load" else "請求失敗"
        logger.opt(exception=error).error(action)
        self._notify("error", f"{action}：{error}")
        self._set_status("error", "● 失敗", action)

    def _on_methods_loaded(self, uuid: str, methods: list[str]) -> None:
        if self._store.get(uuid) is None:
            return  # F1：連線在背景工作進行時被刪除，或 uuid 為 None（目錄選取中）
        self._store.set_methods(uuid, methods)
        self.connection_list.update_connection(self._store.get(uuid))
        if uuid == self._current_uuid:
            self._set_methods(methods)
        if not self.request_editor.toPlainText().strip():
            self.request_editor.setPlainText(XML_DECLARATION)
        self._set_status("success", "● 成功", f"讀取完成 · {len(methods)} 個方法")
        self._notify("success", f"已讀取 {len(methods)} 個服務方法")

    def _on_call_finished(self, result: CallResult) -> None:
        url, method = getattr(self, "_run_context", ("", ""))
        logger.info(
            "請求完成 · URL={} · 方法={} · 耗時={:.2f}s · 大小={} · 回應={}",
            url, method, result.elapsed, result.size, _cap(result.text),
        )
        self.response_editor.setPlainText(result.text)
        self._set_status("success", "● 成功", f"{result.elapsed:.2f} s · {format_size(result.size)}")

    # ---------- 編輯器工具 ----------

    def _on_clear(self) -> None:
        if self._pending:
            return
        self.request_editor.clear()
        self.response_editor.clear()
        self._reset_status()

    def _on_format(self) -> None:
        text = self.request_editor.toPlainText()
        if not text.strip():
            return
        try:
            formatted = format_xml(text)
        except ValueError:
            self._notify("warning", "請求內容不是合法的 XML，無法格式化")
            return
        cursor = self.request_editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(formatted)  # 用游標取代，保留復原紀錄

    def _on_copy(self) -> None:
        text = self.response_editor.toPlainText()
        if not text:
            self._notify("info", "沒有可複製的回應內容")
            return
        QGuiApplication.clipboard().setText(text)
        self._notify("success", "已複製回應結果")

    # ---------- 狀態、通知、主題 ----------

    def _set_status(self, state: str, label: str, detail: str = "") -> None:
        self.status_state.setProperty("state", state)
        repolish(self.status_state)
        self.status_state.setText(label)
        self.status_detail.setText(detail)

    def _reset_status(self) -> None:
        self._set_status("", "就緒")

    def _notify(self, level: str, text: str) -> None:
        self.notification.show_message(level, text)

    @Slot(object)
    def _on_theme_changed(self, palette: ThemePalette) -> None:
        self.request_editor.set_colors(palette.xml)
        self.response_editor.set_colors(palette.xml)
        for mode, action in self.theme_actions.items():
            action.setChecked(mode is self._theme.mode)

    def _show_about(self) -> None:
        about = self._about
        QMessageBox.about(
            self,
            f"關於 {about.name}",
            f"<h3>{about.name}</h3>"
            f"<p>版本 {about.version}</p>"
            "<p>這是一款針對 WebService 設計的開源工具，簡單好用、配置靈活。</p>"
            f"<p><a href='{about.website}'>{about.website}</a></p>"
            "<p>原創：Tiger Tseng</p>"
            f"<p>{about.copyright}</p>",
        )

    def _confirm(self, title: str, text: str) -> bool:
        answer = QMessageBox.question(
            self, title, text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:
        if not self._confirm("離開程式", "確定要離開嗎？"):
            event.ignore()
            return
        self._commit_fields()
        self._pending = None
        event.accept()
