# -*- coding: utf-8 -*-
"""
通知橫幅：顯示 info / success / warning / error 訊息
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from src.ui.theme import repolish

AUTO_HIDE_LEVELS = ("info", "success")


class NotificationBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NotificationBar")
        self.setProperty("level", "info")
        self.auto_hide_ms = 3000

        self._message = QLabel()
        self._message.setWordWrap(True)
        self.close_button = QPushButton("✕")
        self.close_button.setProperty("variant", "subtle")
        self.close_button.setToolTip("關閉")
        self.close_button.clicked.connect(self.dismiss)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 6, 6)
        layout.addWidget(self._message, 1)
        layout.addWidget(self.close_button)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self.hide()

    @property
    def level(self) -> str:
        return self.property("level")

    @property
    def text(self) -> str:
        return self._message.text()

    def show_message(self, level: str, text: str) -> None:
        self.setProperty("level", level)
        repolish(self)
        self._message.setText(text)
        self.show()
        if level in AUTO_HIDE_LEVELS:
            self._timer.start(self.auto_hide_ms)
        else:
            self._timer.stop()

    def dismiss(self) -> None:
        self._timer.stop()
        self.hide()
