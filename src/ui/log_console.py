# -*- coding: utf-8 -*-
"""
主控台：把 loguru 記錄即時顯示在主視窗下方的面板（等級篩選、搜尋、清除、複製）
"""
from collections import Counter
from collections.abc import Iterable

from PySide6.QtCore import QObject, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from src.core.log_buffer import DEFAULT_CAPACITY, LEVELS, LogBuffer, LogEntry
from src.ui.effects import styled_button
from src.ui.theme import ThemePalette

DEFAULT_LEVELS = frozenset({"DEBUG", "INFO", "SUCCESS"})
DEFAULT_HEIGHT = 220
HEIGHT_MIN, HEIGHT_MAX = 120, 2000
KEY_VISIBLE = "console/visible"
KEY_HEIGHT = "console/height"
KEY_LEVELS = "console/levels"
TRIM_THRESHOLD = int(DEFAULT_CAPACITY * 1.1)  # 超過才一次修剪回 DEFAULT_CAPACITY，避免每筆都重建
SEARCH_DELAY_MS = 200
LEVEL_WIDTH = 9  # 最長的 CRITICAL 8 字 + 1 空白
INDENT = " " * (len("HH:MM:SS.mmm  ") + LEVEL_WIDTH)  # 多行訊息後續行對齊訊息欄
MUTED_LEVELS = frozenset({"TRACE", "DEBUG"})
PLAIN_LEVELS = frozenset({"INFO"})


def parse_levels(value) -> frozenset[str]:
    """settings.ini 的等級設定轉成集合；手動編輯的逗號清單會被 QSettings 讀成 list，兩種都接受"""
    if isinstance(value, (list, tuple)):
        value = ",".join(map(str, value))
    names = (part.strip().upper() for part in str(value or "").split(","))
    return frozenset(name for name in names if name in LEVELS)


def format_levels(levels: Iterable[str]) -> str:
    """依嚴重度排序、小寫、逗號分隔，方便手動編輯"""
    chosen = set(levels)
    return ",".join(level.lower() for level in LEVELS if level in chosen)


def format_entry(entry: LogEntry) -> tuple[str, str, str]:
    """(時間欄、等級欄、訊息)；分成三段方便分別上色"""
    time_text = entry.time.strftime("%H:%M:%S.") + f"{entry.time.microsecond // 1000:03d}"
    return f"{time_text}  ", f"{entry.level:<{LEVEL_WIDTH}}", entry.message.replace("\n", "\n" + INDENT)


class ConsoleSettings:
    """settings.ini 的 console/* 設定；未提供 QSettings 時只存在記憶體（測試與舊呼叫端用）"""

    def __init__(self, settings: QSettings | None = None):
        self._settings = settings
        self._memory: dict[str, object] = {}

    def _value(self, key: str):
        if self._settings is None:
            return self._memory.get(key)
        return self._settings.value(key) if self._settings.contains(key) else None

    def _set(self, key: str, value) -> None:
        if self._settings is None:
            self._memory[key] = value
            return
        self._settings.setValue(key, value)
        self._settings.sync()

    def visible(self) -> bool:
        return str(self._value(KEY_VISIBLE)).lower() == "true"

    def set_visible(self, visible: bool) -> None:
        self._set(KEY_VISIBLE, bool(visible))

    def height(self) -> int:
        try:
            height = int(self._value(KEY_HEIGHT))
        except (TypeError, ValueError):
            return DEFAULT_HEIGHT
        return height if HEIGHT_MIN <= height <= HEIGHT_MAX else DEFAULT_HEIGHT

    def set_height(self, height: int) -> None:
        self._set(KEY_HEIGHT, int(height))

    def levels(self) -> frozenset[str]:
        """鍵不存在才用預設值；空字串代表使用者把全部等級都關掉"""
        value = self._value(KEY_LEVELS)
        return DEFAULT_LEVELS if value is None else parse_levels(value)

    def set_levels(self, levels: Iterable[str]) -> None:
        self._set(KEY_LEVELS, format_levels(levels))


class LogBridge(QObject):
    """LogBuffer 的 listener：把任何執行緒寫入的記錄轉成 Qt 訊號"""

    entryAdded = Signal(object)  # LogEntry

    def __init__(self, buffer: LogBuffer, parent=None):
        super().__init__(parent)
        self._buffer = buffer
        buffer.add_listener(self._on_entry)

    def detach(self) -> None:
        self._buffer.remove_listener(self._on_entry)

    def _on_entry(self, entry: LogEntry) -> None:
        try:
            self.entryAdded.emit(entry)
        except RuntimeError:
            pass  # 程式關閉過程中 QObject 可能已被刪除，比照 workers.py


class ConsolePanel(QWidget):
    """主控台面板：第一列標題、搜尋、清除／複製／關閉；第二列 7 顆等級鈕；下方記錄文字區"""

    closeRequested = Signal()
    levelsChanged = Signal(object)  # frozenset[str]

    def __init__(self, buffer: LogBuffer, palette: ThemePalette, levels: Iterable[str], parent=None):
        super().__init__(parent)
        self.setObjectName("ConsolePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._buffer = buffer
        self._palette = palette
        self._levels = frozenset(levels) & frozenset(LEVELS)
        self._search = ""
        self._entries: list[LogEntry] = []
        self._counts: Counter[str] = Counter()
        self._last_seq = 0
        self._visible_count = 0
        self._build_ui()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DELAY_MS)
        self._search_timer.timeout.connect(self._apply_search)
        self.search_edit.textChanged.connect(lambda _text: self._search_timer.start())  # start(int) 會誤收字串參數
        # 一律排入事件迴圈再更新：面板若在 loguru sink 呼叫中同步執行，裡面再寫記錄會觸發 loguru 的重入保護
        self._bridge = LogBridge(buffer, self)
        self._bridge.entryAdded.connect(self._on_entry_added, Qt.ConnectionType.QueuedConnection)
        for entry in buffer.snapshot():
            self._store(entry)
        self._rebuild()

    # ---------- 版面 ----------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(4)

        title = QLabel("主控台")
        title.setObjectName("ConsoleTitle")
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("ConsoleSearch")
        self.search_edit.setPlaceholderText("搜尋記錄…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(220)
        self.clear_button = styled_button("清除", "subtle", "清除主控台記錄")
        self.copy_button = styled_button("複製", "subtle", "複製目前顯示的記錄")
        self.close_button = styled_button("✕", "subtle", "關閉主控台 (Ctrl+`)")
        top = QHBoxLayout()
        top.addWidget(title)
        top.addStretch(1)
        for widget in (self.search_edit, self.clear_button, self.copy_button, self.close_button):
            top.addWidget(widget)

        chips = QHBoxLayout()
        chips.setSpacing(4)
        self.level_buttons: dict[str, QPushButton] = {}
        for level in LEVELS:
            button = QPushButton()
            button.setProperty("variant", "level")
            button.setProperty("level", level)
            button.setCheckable(True)
            button.setChecked(level in self._levels)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"顯示／隱藏 {level} 記錄")
            button.toggled.connect(lambda checked, lv=level: self._on_level_toggled(lv, checked))
            chips.addWidget(button)
            self.level_buttons[level] = button
        chips.addStretch(1)

        self.view = QPlainTextEdit()
        self.view.setObjectName("ConsoleView")
        self.view.setReadOnly(True)
        self.view.setUndoRedoEnabled(False)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        layout.addLayout(top)
        layout.addLayout(chips)
        layout.addWidget(self.view, 1)
        self.clear_button.clicked.connect(self.clear)
        self.copy_button.clicked.connect(self.copy_visible)
        self.close_button.clicked.connect(lambda: self.closeRequested.emit())

    # ---------- 公開介面 ----------

    def levels(self) -> frozenset[str]:
        return self._levels

    def set_levels(self, levels: Iterable[str]) -> None:
        """程式設定篩選（不發出 levelsChanged）"""
        self._levels = frozenset(levels) & frozenset(LEVELS)
        for level, button in self.level_buttons.items():
            button.blockSignals(True)
            button.setChecked(level in self._levels)
            button.blockSignals(False)
        self._rebuild()

    def set_search(self, text: str) -> None:
        """立即套用搜尋（不經延遲），測試與程式呼叫用"""
        self._search_timer.stop()
        self.search_edit.blockSignals(True)
        self.search_edit.setText(text)
        self.search_edit.blockSignals(False)
        self._apply_search()

    def visible_text(self) -> str:
        return self.view.toPlainText()

    def set_palette(self, palette: ThemePalette) -> None:
        self._palette = palette
        self._rebuild()

    def clear(self) -> None:
        """清空面板與 LogBuffer，關掉再開也不會跑回來"""
        self._buffer.clear()
        self._entries.clear()
        self._counts.clear()
        self._rebuild()

    def copy_visible(self) -> None:
        text = self.visible_text()
        if text:
            QGuiApplication.clipboard().setText(text)

    def detach(self) -> None:
        self._bridge.detach()

    # ---------- 記錄 ----------

    def _store(self, entry: LogEntry) -> bool:
        """加入記錄清單；超過上限時修剪並回傳 True（需要重建文字區）"""
        self._entries.append(entry)
        self._last_seq = entry.seq
        self._counts[entry.level] += 1
        if len(self._entries) <= TRIM_THRESHOLD:
            return False
        self._entries = self._entries[-DEFAULT_CAPACITY:]
        self._counts = Counter(e.level for e in self._entries)
        return True

    def _on_entry_added(self, entry: LogEntry) -> None:
        if entry.seq <= self._last_seq:
            return  # 已經從 snapshot 取得
        if self._store(entry):
            self._rebuild()
            return
        self._update_counts()
        if self._matches(entry):
            bar = self.view.verticalScrollBar()
            at_bottom = bar.value() >= bar.maximum()
            cursor = QTextCursor(self.view.document())
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._insert(cursor, entry)
            if at_bottom:
                bar.setValue(bar.maximum())

    def _matches(self, entry: LogEntry) -> bool:
        if entry.level not in self._levels:
            return False
        return not self._search or self._search in f"{entry.level} {entry.message}".lower()

    def _on_level_toggled(self, level: str, checked: bool) -> None:
        self._levels = self._levels | {level} if checked else self._levels - {level}
        self._rebuild()
        self.levelsChanged.emit(self._levels)

    def _apply_search(self) -> None:
        self._search = self.search_edit.text().strip().lower()
        self._rebuild()

    # ---------- 繪製 ----------

    def _update_counts(self) -> None:
        for level, button in self.level_buttons.items():
            button.setText(f"{level} {self._counts[level]}")

    def _rebuild(self) -> None:
        bar = self.view.verticalScrollBar()
        at_bottom = bar.value() >= bar.maximum()
        self.view.clear()
        self._visible_count = 0
        cursor = QTextCursor(self.view.document())
        cursor.beginEditBlock()
        for entry in self._entries:
            if self._matches(entry):
                self._insert(cursor, entry)
        cursor.endEditBlock()
        if at_bottom:
            bar.setValue(bar.maximum())
        self._update_counts()

    def _insert(self, cursor: QTextCursor, entry: LogEntry) -> None:
        time_text, level_text, message = format_entry(entry)
        color = self._palette.level(entry.level)
        if self._visible_count:
            cursor.insertText("\n", self._format(self._palette.text))
        cursor.insertText(time_text, self._format(self._palette.text_muted))
        cursor.insertText(level_text, self._format(color.fg, bold=True))
        cursor.insertText(message, self._format(self._message_color(entry.level)))
        self._visible_count += 1

    def _message_color(self, level: str) -> str:
        if level in MUTED_LEVELS:
            return self._palette.text_muted
        if level in PLAIN_LEVELS:
            return self._palette.text
        return self._palette.level(level).fg

    @staticmethod
    def _format(color: str, bold: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        return fmt
