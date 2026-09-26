# -*- coding: utf-8 -*-
"""
記錄暫存：以 loguru sink 把記錄收進環狀暫存並通知 listener，供主控台面板顯示（不依賴 Qt）
"""
import itertools
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from loguru import logger

# loguru 7 個內建等級，依嚴重度排列；主控台篩選鈕一個等級一顆
LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
LEVEL_NO = {"TRACE": 5, "DEBUG": 10, "INFO": 20, "SUCCESS": 25, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
DEFAULT_CAPACITY = 5000
# format 只取訊息本身；有例外時 loguru 會自動把 traceback 接在後面。diagnose=False 避免印出變數值
SINK_OPTIONS = dict(level="TRACE", format="{message}", colorize=False, backtrace=False, diagnose=False)


@dataclass(frozen=True)
class LogEntry:
    seq: int  # 寫入順序（遞增），面板用來避免 snapshot 與即時通知重複
    time: datetime
    level: str  # LEVELS 其中之一
    message: str  # 含例外 traceback（多行）


def normalize_level(name: str, no: int) -> str:
    """內建等級原樣回傳；自訂等級歸到數值不超過它的最高內建等級（低於 TRACE 時為 TRACE）"""
    if name in LEVEL_NO:
        return name
    result = LEVELS[0]
    for level in LEVELS:
        if LEVEL_NO[level] <= no:
            result = level
    return result


class LogBuffer:
    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        self._entries: deque[LogEntry] = deque(maxlen=capacity)
        self._listeners: list[Callable[[LogEntry], None]] = []
        self._lock = threading.Lock()
        self._seq = itertools.count(1)

    def attach(self) -> int:
        """註冊為 loguru sink，回傳 handler id（移除時用 logger.remove）"""
        return logger.add(self.write, **SINK_OPTIONS)

    def write(self, message) -> None:
        """loguru sink：message 是已格式化的字串（結尾帶換行），record 帶原始欄位"""
        try:
            level = message.record["level"]
            with self._lock:
                entry = LogEntry(
                    next(self._seq), message.record["time"],
                    normalize_level(level.name, level.no), str(message).rstrip("\n"),
                )
                self._entries.append(entry)
                listeners = list(self._listeners)
        except Exception:
            return  # 記錄動作不可以把主流程弄壞
        for listener in listeners:
            try:
                listener(entry)
            except Exception:
                pass  # 單一 listener 失敗不影響其他 listener 與記錄本身

    def snapshot(self) -> list[LogEntry]:
        with self._lock:
            return list(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def add_listener(self, callback: Callable[[LogEntry], None]) -> None:
        with self._lock:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[LogEntry], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)
