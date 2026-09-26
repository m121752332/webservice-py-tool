# -*- coding: utf-8 -*-
"""
主視窗：左側連線清單 + 右側工作區
"""
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QSettings, QSize, Qt, Slot
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QIcon, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.config.app_settings import HOT_RELOAD_KEYS, TIMEOUT_MAX, TIMEOUT_MIN, AppSettings
from src.core.connection_store import Connection, ConnectionStore
from src.core.log_buffer import LogBuffer
from src.core.soap_service import CallResult, ParamCountMismatch, format_xml
from src.core.xml_log import CallRecord
from src.ui.connection_list import FOLDER_UNNAMED, UNNAMED, ConnectionList
from src.ui.effects import styled_button
from src.ui.icons import about_icon, console_icon, record_icon, theme_icon
from src.ui.log_console import ConsolePanel, ConsoleSettings
from src.ui.notification_bar import NotificationBar
from src.ui.plugin_loader import load_settings_plugin
from src.ui.settings_page import SettingsPage
from src.ui.theme import ThemeManager, ThemeMode, ThemePalette, repolish
from src.ui.workers import run_in_background
from src.ui.xml_editor import XmlEditor
from src.ui.xml_log_viewer import XmlLogViewer
from src.utils import path_util

XML_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>'
LOG_TEXT_CAP = 2000
LOAD_LABEL = "讀取 WSDL"
RUN_LABEL = "▶ 執行"
CANCEL_LABEL = "取消"
NEW_FOLDER_NAME = "新目錄"
FOOTER_ICON_SIZE = 20
FOOTER_SPACING = 6  # 三顆 footer 按鈕要塞進 236 px
CONSOLE_SHORTCUT = "Ctrl+`"
RECORD_SHORTCUT = "F10"
CONSOLE_MIN_HEIGHT = 120
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


def _caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldCaption")
    return label


class MainWindow(QMainWindow):
    def __init__(self, store: ConnectionStore, service, theme: ThemeManager, about: AboutInfo,
                 default_timeout: int, settings_path: Path, parent=None, *,
                 settings: QSettings | None = None, log_buffer: LogBuffer | None = None,
                 xml_log_dir: Path | None = None):
        super().__init__(parent)
        self._store = store
        self._service = service
        self._theme = theme
        self._about = about
        self._settings_path = Path(settings_path)
        self._current_uuid: str | None = None
        self._methods: list[str] = []
        self._pending = None  # 進行中工作的 tag：(kind, seq, uuid)
        self._seq = 0
        self._tasks = {}  # tag -> Task，保留參照直到收到回呼
        self._console_settings = ConsoleSettings(settings)
        self._log_buffer = log_buffer if log_buffer is not None else LogBuffer()
        self._xml_log_dir = Path(xml_log_dir) if xml_log_dir is not None else None
        self.xml_log_viewer: XmlLogViewer | None = None  # 首次按 F10 才建立

        self.setWindowTitle(about.name)
        self.resize(1100, 700)
        self.setMinimumSize(900, 560)
        self._build_ui(default_timeout)
        self._build_shortcuts()
        self._connect_signals()
        self._theme.themeChanged.connect(self._on_theme_changed)
        self._reset_status()
        self._load_initial_connections()
        self.set_console_visible(self._console_settings.visible())

    # ---------- 版面 ----------

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

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        self.app_title = QLabel(self._about.name)
        self.app_title.setObjectName("AppTitle")
        self.app_title.setWordWrap(True)
        self.connection_list = ConnectionList()

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
        self.record_button = None
        if self._xml_log_dir is not None:
            # 只顯示圖示：既有三顆文字按鈕已接近側欄 236 px 上限
            self.record_button = styled_button("", "footer-icon", f"請求紀錄 ({RECORD_SHORTCUT})")
            self.record_button.setIcon(record_icon())
            self.record_button.setIconSize(QSize(FOOTER_ICON_SIZE, FOOTER_ICON_SIZE))
            footer.addWidget(self.record_button)
        footer.addStretch(1)

        layout.addWidget(self.app_title)
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
        self.format_button = styled_button("格式化", "blue", "格式化請求 XML (Ctrl+Shift+F)")
        self.copy_button = styled_button("複製", "blue", "複製回應結果")
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
        self.load_button = styled_button(LOAD_LABEL, "green", "讀取 WSDL 的服務方法 (F3)")
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
        timeout_label.setObjectName("TimeoutLabel")
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setObjectName("TimeoutSpin")
        self.timeout_spin.setRange(TIMEOUT_MIN, TIMEOUT_MAX)
        self.timeout_spin.setSuffix(" 秒")
        self.timeout_spin.setValue(min(max(default_timeout, TIMEOUT_MIN), TIMEOUT_MAX))
        self.run_button = styled_button(RUN_LABEL, "primary", "執行請求 (F5)")
        self.clear_button = styled_button("清空", "orange", "清空請求與回應 (F6)")
        method_row = QHBoxLayout()
        method_row.addWidget(self.method_combo, 1)
        method_row.addWidget(timeout_label)
        method_row.addWidget(self.timeout_spin)
        method_row.addWidget(self.run_button)
        method_row.addWidget(self.clear_button)

        layout.addWidget(_caption("連線名稱"))
        layout.addWidget(self.name_edit)
        layout.addSpacing(4)
        layout.addWidget(_caption("服務連結"))
        layout.addLayout(url_row)
        layout.addWidget(self.url_hint)
        layout.addSpacing(4)
        layout.addWidget(_caption("服務項目"))
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
        for key, handler in (
            ("F11", self._toggle_settings), ("Esc", self._on_escape), (CONSOLE_SHORTCUT, self.toggle_console),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)
        if self._xml_log_dir is not None:
            shortcut = QShortcut(QKeySequence(RECORD_SHORTCUT), self)
            shortcut.activated.connect(self.open_xml_log_viewer)

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
        self.console_button.clicked.connect(self.toggle_console)
        if self.record_button is not None:
            self.record_button.clicked.connect(self.open_xml_log_viewer)
        self.console_panel.closeRequested.connect(lambda: self.set_console_visible(False))
        self.console_panel.levelsChanged.connect(self._console_settings.set_levels)

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
        logger.info("讀取 WSDL · URL={}", url)
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
        self._start(
            "run", self._service.call, url, method, params, self.timeout_spin.value(),
            connection=self.name_edit.text().strip(),
        )

    def _start(self, kind: str, fn, *args, **kwargs) -> None:
        self._seq += 1
        tag = (kind, self._seq, self._current_uuid)
        self._pending = tag
        self._set_busy(kind)
        self._set_status("busy", "讀取中…" if kind == "load" else "執行中…")
        self._tasks[tag] = run_in_background(
            tag, fn, *args, on_success=self._on_task_succeeded, on_failure=self._on_task_failed, **kwargs,
        )

    def _cancel(self) -> None:
        logger.info("已取消{}", "讀取" if self._pending[0] == "load" else "執行")
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
        logger.success("讀取完成 · {} 個方法", len(methods))
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
        logger.success(
            "請求完成 · URL={} · 方法={} · 耗時={:.2f}s · 大小={} · 回應={}",
            url, method, result.elapsed, result.size, _cap(result.text),
        )
        self.response_editor.setPlainText(result.text)
        self._set_status("success", "● 成功", f"{result.elapsed:.2f} s · {format_size(result.size)}")

    # ---------- 請求紀錄 ----------

    def open_xml_log_viewer(self) -> None:
        if self._xml_log_dir is None:
            return
        if self.xml_log_viewer is None:
            self.xml_log_viewer = XmlLogViewer(self._xml_log_dir, self._theme.palette, self)
            self.xml_log_viewer.resendRequested.connect(self.load_record)
        viewer = self.xml_log_viewer
        viewer.refresh()
        viewer.setWindowState(viewer.windowState() & ~Qt.WindowState.WindowMinimized)
        viewer.show()
        viewer.raise_()
        viewer.activateWindow()

    def _find_connection(self, name: str, url: str) -> Connection | None:
        """URL 相同（不分大小寫）的連線中優先取名稱也相同者"""
        key = url.strip().lower()
        same_url = [conn for conn in self._store.all() if conn.url.strip().lower() == key]
        return next((conn for conn in same_url if conn.name == name), same_url[0] if same_url else None)

    @Slot(object)
    def load_record(self, record: CallRecord) -> None:
        """查閱視窗「帶回工作區」：選取對應連線並填入方法與參數"""
        self.raise_()
        self.activateWindow()
        if self._settings_active() and not self._leave_settings():
            return
        if self._pending:
            self._notify("warning", "目前有工作進行中，請等待完成或取消後再帶回")
            return
        conn = self._find_connection(record.connection, record.url)
        if conn is None:
            self._notify("warning", f"找不到對應的連線：{record.connection or record.url}")
            return
        self.connection_list.select(conn.uuid)
        index = self.method_combo.findText(record.method)
        if index >= 0:
            self.method_combo.setCurrentIndex(index)
        else:
            self.method_combo.setEditText(record.method)
        if not record.params:
            self._notify("warning", "這筆紀錄沒有保存請求參數（log.xml.content 為 envelope），只帶回連線與方法")
            return
        self.request_editor.setPlainText(record.params)
        self.response_editor.clear()
        self._notify("info", f"已帶回 {record.method} 的請求參數，按 F5 重新執行")

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
            self._apply_console_height()
        self._console_settings.set_visible(visible)

    def _apply_console_height(self) -> None:
        height = self._console_settings.height()
        total = sum(self.right_splitter.sizes()) or self.right_splitter.height()
        self.right_splitter.setSizes([max(total - height, 1), height])

    def _remember_console_height(self) -> None:
        height = self.right_splitter.sizes()[1]
        if height > 0:
            self._console_settings.set_height(height)

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
        self._forward_settings_notice()
        return True

    def _forward_settings_notice(self) -> None:
        """設定頁上仍顯示的 warning／error（例如從離開詢問選「儲存」後的需重啟提示）轉到工作區，免得看不到"""
        bar = self.settings_page.notification
        if not bar.isHidden() and bar.level in ("warning", "error"):
            self.notification.show_message(bar.level, bar.text)

    def _set_settings_mode(self, active: bool) -> None:
        """設定頁顯示期間停用連線清單與工作區快捷鍵，避免在看不到的地方送出請求；footer 按鈕（含主控台）維持可用"""
        self.connection_list.setEnabled(not active)
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
            self.apply_app_settings(doc.app_settings(), changes.hot)

    # ---------- 狀態、通知、主題 ----------

    def _set_status(self, state: str, label: str, detail: str = "") -> None:
        self.status_state.setProperty("state", state)
        repolish(self.status_state)
        self.status_state.setText(label)
        self.status_detail.setText(detail)

    def _reset_status(self) -> None:
        self._set_status("", "就緒")

    def _notify(self, level: str, text: str) -> None:
        if self._settings_active():
            self.settings_page.notify(level, text)
        else:
            self.notification.show_message(level, text)

    @Slot(object)
    def _on_theme_changed(self, palette: ThemePalette) -> None:
        self.request_editor.set_colors(palette.xml)
        self.response_editor.set_colors(palette.xml)
        for mode, action in self.theme_actions.items():
            action.setChecked(mode is self._theme.mode)
        if self.settings_page is not None:
            self.settings_page.set_palette(palette)
        self.console_panel.set_palette(palette)
        if self.xml_log_viewer is not None:
            self.xml_log_viewer.set_palette(palette)

    def apply_app_settings(self, settings: AppSettings, keys: Iterable[str] = HOT_RELOAD_KEYS) -> None:
        """熱重載 ws_tool.yaml 的 name、version、copyright、img、timeout；只套用 keys 列出的欄位"""
        keys = set(keys)
        if "app.name" in keys:
            self._about = replace(self._about, name=settings.name)
            self.setWindowTitle(settings.name)
            self.app_title.setText(settings.name)
            QApplication.setApplicationName(settings.name)
        if "app.version" in keys:
            self._about = replace(self._about, version=settings.version)
        if "app.copyright" in keys:
            self._about = replace(self._about, copyright=settings.copyright)
        if "app.img" in keys:
            icon_path = Path(path_util.resource_path(settings.img))
            if icon_path.is_file():
                QApplication.setWindowIcon(QIcon(str(icon_path)))
            else:
                logger.warning("找不到圖示檔：{}", icon_path)
                self._notify("warning", f"找不到圖示檔 {settings.img}，保留原圖示")
        if "app.timeout" in keys:
            # 只有檔案中的 timeout 改了才覆寫，保留使用者本次手動調整的逾時
            self.timeout_spin.setValue(min(max(settings.timeout, TIMEOUT_MIN), TIMEOUT_MAX))

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
        if self._settings_active() and not self._resolve_unsaved():
            event.ignore()
            return
        if not self._confirm("離開程式", "確定要離開嗎？"):
            event.ignore()
            return
        logger.info("程式關閉")
        if not self.console_panel.isHidden():
            self._remember_console_height()
        self.console_panel.detach()
        self._commit_fields()
        self._pending = None
        event.accept()
