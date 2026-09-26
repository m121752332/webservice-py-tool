# -*- coding: utf-8 -*-
"""
請求紀錄查閱視窗：依日期、連線、方法、關鍵字篩選 ws_xml.log，並可把某一筆帶回工作區
"""
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.xml_log import SECTIONS, CallRecord, list_log_dates, read_records
from src.ui.effects import styled_button
from src.ui.notification_bar import NotificationBar
from src.ui.theme import ThemePalette
from src.ui.workers import run_in_background
from src.ui.xml_editor import XmlEditor

ALL = "全部"
COLUMNS = ("時間", "連線", "方法", "狀態", "耗時")
STATUS_COLUMN = 3
STATUS_LABELS = {"success": "成功", "failed": "失敗"}
TAB_FIELDS = ("params", "response", "sent", "received")
SEARCH_DELAY_MS = 200


def connection_label(record: CallRecord) -> str:
    """連線名稱為空時以 URL 代替"""
    return record.connection or record.url


def matches(record: CallRecord, connection: str | None, method: str | None, keyword: str) -> bool:
    if connection is not None and connection_label(record) != connection:
        return False
    if method is not None and record.method != method:
        return False
    if not keyword:
        return True
    needle = keyword.casefold()
    texts = (record.params, record.response, record.sent, record.received, record.error)
    return any(needle in text.casefold() for text in texts)


def _refill(combo: QComboBox, values: list[str]) -> None:
    """重填下拉選單（第一項為「全部」），盡量保留原本的選取；過程中不發出訊號"""
    previous = combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(ALL)
    combo.addItems(values)
    combo.setCurrentIndex(max(combo.findText(previous), 0))
    combo.blockSignals(False)


def _selected(combo: QComboBox) -> str | None:
    return None if combo.currentIndex() <= 0 else combo.currentText()


def _caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldCaption")
    return label


class XmlLogViewer(QWidget):
    resendRequested = Signal(object)  # CallRecord

    def __init__(self, log_dir: Path, palette: ThemePalette, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("XmlLogViewer")
        self.setWindowTitle("請求紀錄")
        self.resize(1100, 680)
        self._log_dir = Path(log_dir)
        self._palette = palette
        self._records: list[CallRecord] = []
        self._visible: list[CallRecord] = []
        self._pending = None
        self._seq = 0
        self._tasks = {}  # tag -> Task，保留參照直到收到回呼
        self._build_ui()
        self._connect_signals()
        self._show_record(None)

    # ---------- 版面 ----------

    def _build_ui(self) -> None:
        self.date_combo = QComboBox()
        self.connection_combo = QComboBox()
        self.method_combo = QComboBox()
        for combo in (self.connection_combo, self.method_combo):
            combo.setMinimumWidth(160)
            combo.addItem(ALL)
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("ConsoleSearch")
        self.search_edit.setPlaceholderText("搜尋參數、回應、信封或錯誤訊息…")
        self.search_edit.setClearButtonEnabled(True)
        self.refresh_button = styled_button("重新整理", "blue", "重新讀取紀錄檔 (F5)")
        toolbar = QHBoxLayout()
        for text, widget in (("日期", self.date_combo), ("連線", self.connection_combo), ("方法", self.method_combo)):
            toolbar.addWidget(_caption(text))
            toolbar.addWidget(widget)
        toolbar.addWidget(self.search_edit, 1)
        toolbar.addWidget(self.refresh_button)

        self.notification = NotificationBar()

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("XmlLogTable")
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setShowGrid(False)

        self.tabs = QTabWidget()
        self.editors = {name: XmlEditor(self._palette.xml, read_only=True) for name in TAB_FIELDS}
        for name in TAB_FIELDS:
            self.tabs.addTab(self.editors[name], SECTIONS[name])
        self.resend_button = styled_button("帶回工作區", "primary", "把這筆的連線、方法與參數帶回主視窗（雙擊列也可以）")
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(self.tabs, 1)
        resend_row = QHBoxLayout()
        resend_row.addStretch(1)
        resend_row.addWidget(self.resend_button)
        detail_layout.addLayout(resend_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        splitter.addWidget(self.table)
        splitter.addWidget(detail)
        splitter.setSizes([1, 1])

        self.count_label = QLabel()
        self.count_label.setObjectName("Hint")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)
        layout.addLayout(toolbar)
        layout.addWidget(self.notification)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.count_label)

    def _connect_signals(self) -> None:
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DELAY_MS)
        self._search_timer.timeout.connect(self._apply_filters)
        self.search_edit.textChanged.connect(lambda _text: self._search_timer.start())
        self.date_combo.currentIndexChanged.connect(lambda _index: self._load_selected_date())
        self.connection_combo.currentIndexChanged.connect(lambda _index: self._on_connection_changed())
        self.method_combo.currentIndexChanged.connect(lambda _index: self._apply_filters())
        self.table.itemSelectionChanged.connect(lambda: self._show_record(self.selected_record()))
        self.table.itemDoubleClicked.connect(lambda _item: self._resend())
        self.resend_button.clicked.connect(self._resend)
        self.refresh_button.clicked.connect(self.refresh)
        shortcut = QShortcut(QKeySequence("F5"), self)
        shortcut.activated.connect(self.refresh)

    # ---------- 讀檔 ----------

    def refresh(self) -> None:
        """重新列出日期（保留目前選取，沒有時選最新）並讀取該日期"""
        current = self.date_combo.currentData()
        today = date.today()
        self.date_combo.blockSignals(True)
        self.date_combo.clear()
        for day, path in list_log_dates(self._log_dir):
            label = f"{day:%Y-%m-%d}" + ("（今天）" if day == today else "")
            self.date_combo.addItem(label, str(path))
        self.date_combo.setCurrentIndex(max(self.date_combo.findData(current), 0) if current else 0)
        self.date_combo.blockSignals(False)
        self._load_selected_date()

    def _load_selected_date(self) -> None:
        path = self.date_combo.currentData()
        if not path:
            self._pending = None
            self._set_records([])
            self.count_label.setText("尚無請求紀錄")
            return
        self._seq += 1
        tag = ("xml-log", self._seq)
        self._pending = tag
        self.count_label.setText("讀取中…")
        self._tasks[tag] = run_in_background(
            tag, read_records, path, on_success=self._on_loaded, on_failure=self._on_load_failed,
        )

    @Slot(object, object)
    def _on_loaded(self, tag, records) -> None:
        self._tasks.pop(tag, None)
        if tag != self._pending:
            return  # 已切換到其他日期
        self._pending = None
        self.notification.dismiss()
        self._set_records(records)

    @Slot(object, object)
    def _on_load_failed(self, tag, error) -> None:
        self._tasks.pop(tag, None)
        if tag != self._pending:
            return
        self._pending = None
        self._set_records([])
        self.notification.show_message("error", f"讀取紀錄檔失敗：{error}")

    # ---------- 篩選與顯示 ----------

    def _set_records(self, records: list[CallRecord]) -> None:
        self._records = sorted(records, key=lambda record: record.time, reverse=True)
        _refill(self.connection_combo, sorted({connection_label(record) for record in self._records}))
        self._on_connection_changed()

    def _on_connection_changed(self) -> None:
        connection = _selected(self.connection_combo)
        methods = {r.method for r in self._records if connection is None or connection_label(r) == connection}
        _refill(self.method_combo, sorted(methods))
        self._apply_filters()

    def _apply_filters(self) -> None:
        connection, method = _selected(self.connection_combo), _selected(self.method_combo)
        keyword = self.search_edit.text().strip()
        self._visible = [r for r in self._records if matches(r, connection, method, keyword)]
        self.table.setRowCount(0)
        self.table.setRowCount(len(self._visible))
        for row, record in enumerate(self._visible):
            cells = (
                record.time.strftime("%H:%M:%S"), connection_label(record), record.method,
                STATUS_LABELS.get(record.status, record.status), f"{record.elapsed:.2f} s",
            )
            for column, text in enumerate(cells):
                self.table.setItem(row, column, QTableWidgetItem(text))
        self._color_status()
        if self._records:
            total = len(self._records)
            suffix = "" if len(self._visible) == total else f"（全部 {total} 筆）"
            self.count_label.setText(f"共 {len(self._visible)} 筆{suffix}")
        else:
            self.count_label.setText("尚無請求紀錄")
        if self._visible:
            self.table.selectRow(0)
        else:
            self._show_record(None)

    def _color_status(self) -> None:
        for row, record in enumerate(self._visible):
            if record.status == "failed":
                self.table.item(row, STATUS_COLUMN).setForeground(QColor(self._palette.danger))

    def selected_record(self) -> CallRecord | None:
        rows = self.table.selectionModel().selectedRows()
        return self._visible[rows[0].row()] if rows else None

    def _show_record(self, record: CallRecord | None) -> None:
        for name in TAB_FIELDS:
            text = getattr(record, name) if record else ""
            if record and name == "response" and record.status == "failed" and not text:
                text = record.error
            self.editors[name].setPlainText(text)
        visible = [bool(self.editors[name].toPlainText()) for name in TAB_FIELDS]
        if not any(visible):
            visible[0] = True
        for index, shown in enumerate(visible):
            self.tabs.setTabVisible(index, shown)
        if not visible[self.tabs.currentIndex()]:
            self.tabs.setCurrentIndex(visible.index(True))
        self.resend_button.setEnabled(record is not None)

    def _resend(self) -> None:
        record = self.selected_record()
        if record is not None:
            self.resendRequested.emit(record)

    def set_palette(self, palette: ThemePalette) -> None:
        self._palette = palette
        for editor in self.editors.values():
            editor.set_colors(palette.xml)
        self._color_status()
