# -*- coding: utf-8 -*-
"""
按鈕懸浮效果：滑鼠移入時陰影加深、往上浮起
"""
from PySide6.QtCore import QEvent, QObject, QPointF, QPropertyAnimation, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QPushButton

REST_BLUR, HOVER_BLUR = 4.0, 16.0
REST_OFFSET, HOVER_OFFSET = QPointF(0, 1), QPointF(0, 4)
REST_ALPHA, HOVER_ALPHA = 40, 90
DURATION_MS = 120


class HoverLift(QObject):
    """裝在按鈕上的事件過濾器；以陰影動畫模擬懸浮"""

    def __init__(self, button: QPushButton):
        super().__init__(button)
        self._button = button
        self._shadow = QGraphicsDropShadowEffect(button)
        self._shadow.setBlurRadius(REST_BLUR)
        self._shadow.setOffset(REST_OFFSET)
        self._shadow.setColor(QColor(0, 0, 0, REST_ALPHA))
        button.setGraphicsEffect(self._shadow)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._blur = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._offset = QPropertyAnimation(self._shadow, b"offset", self)
        for animation in (self._blur, self._offset):
            animation.setDuration(DURATION_MS)
        button.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.Enter and self._button.isEnabled():
            self._animate(HOVER_BLUR, HOVER_OFFSET, HOVER_ALPHA)
        elif event.type() in (QEvent.Type.Leave, QEvent.Type.EnabledChange):
            self._animate(REST_BLUR, REST_OFFSET, REST_ALPHA)
        return False

    def _animate(self, blur: float, offset: QPointF, alpha: int) -> None:
        self._shadow.setColor(QColor(0, 0, 0, alpha))
        for animation, end in ((self._blur, blur), (self._offset, offset)):
            animation.stop()
            animation.setEndValue(end)
            animation.start()


def styled_button(text: str, variant: str | None = None, tooltip: str = "") -> QPushButton:
    """建立套用 variant 樣式（對應 theme.py 的 QSS selector）與懸浮效果的按鈕"""
    button = QPushButton(text)
    if variant:
        button.setProperty("variant", variant)
    if tooltip:
        button.setToolTip(tooltip)
    HoverLift(button)
    return button
