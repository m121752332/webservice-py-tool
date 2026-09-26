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


SETTINGS_YAML = (
    "app:\n"
    "  # Name of the application\n"
    "  name: \"TIPTOP WebService Tool\"\n"
    "  # Version of the application\n"
    "  version: \"v3.0.0\"\n"
    "  # Description of the application\n"
    "  copyright: \"Copyright 2026 GameStudio.\"\n"
    "  # APP icon location\n"
    "  img: \"assets/app_icon.ico\"\n"
    "  # APP loading timeout value (seconds)\n"
    "  timeout: 120\n"
    "\n"
    "  # Log path of the application\n"
    "  log:\n"
    "    path: \"app_data/logs\"\n"
    "    level: info\n"
    "    retention: \"10 days\"\n"
    "  # 服務配置檔位置\n"
    "  connection:\n"
    "    path: \"app_data\"\n"
    "    profile: \"connections.profile\"\n"
)


def write_settings(path, text=SETTINGS_YAML, newline="\n", bom=False):
    """寫出測試用 ws_tool.yaml；可指定換行符號與是否加 UTF-8 BOM"""
    data = text.replace("\n", newline).encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)
    return path
