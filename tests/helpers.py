# -*- coding: utf-8 -*-
"""
測試共用工具
"""
import time

from PySide6.QtCore import QCoreApplication


def wait_until(predicate, timeout=5.0):
    """持續處理 Qt 事件直到 predicate() 為真，逾時則測試失敗"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("等待條件逾時")
