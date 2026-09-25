# -*- coding: utf-8 -*-
"""
pytest 共用設定：所有 Qt 測試都在 offscreen 平台執行
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
