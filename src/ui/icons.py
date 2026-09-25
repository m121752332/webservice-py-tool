# -*- coding: utf-8 -*-
"""
側欄底部按鈕圖示：以 QPainter 繪製的漸層向量圖，不依賴外部圖檔
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap

ICON_CANVAS = 64  # 以大尺寸繪製，縮小顯示時邊緣平滑
THEME_GRADIENT = ("#8B5CF6", "#EC4899")
ABOUT_GRADIENT = ("#0EA5E9", "#2563EB")
PALETTE_DOTS = ("#FACC15", "#34D399", "#38BDF8", "#F87171")


def _canvas() -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(ICON_CANVAS, ICON_CANVAS)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    return pixmap, painter


def _gradient(colors: tuple[str, str]) -> QLinearGradient:
    gradient = QLinearGradient(0, 0, ICON_CANVAS, ICON_CANVAS)
    gradient.setColorAt(0, QColor(colors[0]))
    gradient.setColorAt(1, QColor(colors[1]))
    return gradient


def theme_icon() -> QIcon:
    """調色盤：漸層盤身、拇指孔與四色顏料點"""
    pixmap, painter = _canvas()
    body = QPainterPath()
    body.addEllipse(QRectF(4, 6, 56, 52))
    hole = QPainterPath()
    hole.addEllipse(QRectF(36, 36, 13, 13))
    painter.setBrush(_gradient(THEME_GRADIENT))
    painter.drawPath(body.subtracted(hole))
    for color, (x, y) in zip(PALETTE_DOTS, ((20, 20), (34, 15), (46, 24), (17, 36))):
        painter.setBrush(QColor(color))
        painter.drawEllipse(QPointF(x, y), 5.5, 5.5)
    painter.end()
    return QIcon(pixmap)


def about_icon() -> QIcon:
    """資訊：漸層圓底與白色 i"""
    pixmap, painter = _canvas()
    painter.setBrush(_gradient(ABOUT_GRADIENT))
    painter.drawEllipse(QRectF(4, 4, 56, 56))
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawEllipse(QPointF(32, 19), 4.5, 4.5)
    painter.drawRoundedRect(QRectF(28, 27, 8, 22), 4, 4)
    painter.end()
    return QIcon(pixmap)
