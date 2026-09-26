# -*- coding: utf-8 -*-
"""
主控台：把 loguru 記錄即時顯示在主視窗下方的面板（等級篩選、搜尋、清除、複製）
"""
from collections.abc import Iterable

from PySide6.QtCore import QObject, QSettings, Signal

from src.core.log_buffer import LEVELS, LogBuffer, LogEntry

DEFAULT_LEVELS = frozenset({"DEBUG", "INFO", "SUCCESS"})
DEFAULT_HEIGHT = 220
HEIGHT_MIN, HEIGHT_MAX = 120, 2000
KEY_VISIBLE = "console/visible"
KEY_HEIGHT = "console/height"
KEY_LEVELS = "console/levels"


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
