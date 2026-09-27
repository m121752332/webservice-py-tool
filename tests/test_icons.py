# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from src.ui.icons import swatch_icon, tinted_icon


def two_tone(left: str | None, right: str) -> QIcon:
    """20x20 圖示：左半 left（None 為透明）、右半 right"""
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    if left:
        painter.fillRect(0, 0, 10, 20, QColor(left))
    painter.fillRect(10, 0, 10, 20, QColor(right))
    painter.end()
    return QIcon(pixmap)


def test_tinted_icon_keeps_transparency_and_takes_color(qapp):
    image = tinted_icon(two_tone(None, "#FFFFFF"), "#C81E1E").pixmap(20, 20).toImage()
    assert image.pixelColor(2, 10).alpha() == 0
    assert image.pixelColor(15, 10) == QColor("#C81E1E")  # 白色 × 指定色 = 指定色


def test_tinted_icon_keeps_shading(qapp):
    image = tinted_icon(two_tone("#808080", "#FFFFFF"), "#1D4ED8").pixmap(20, 20).toImage()
    darker, lighter = image.pixelColor(5, 10), image.pixelColor(15, 10)
    assert darker.value() < lighter.value()  # 原圖較暗的部分染色後仍較暗
    assert abs(darker.hueF() - lighter.hueF()) < 0.02  # 色相一致


def test_swatch_icon_is_filled_with_color(qapp):
    image = swatch_icon("#15703A").pixmap(12, 12).toImage()
    assert image.pixelColor(6, 6) == QColor("#15703A")


def test_tinted_icon_brightest_part_matches_color(qapp):
    """原圖偏暗（例如深色的系統資料夾）時，最亮處仍要等於指定色，才會和選單色塊一致"""
    image = tinted_icon(two_tone("#404040", "#808080"), "#6AADFB").pixmap(20, 20).toImage()
    brightest = image.pixelColor(15, 10)
    target = QColor("#6AADFB")
    assert max(abs(brightest.red() - target.red()), abs(brightest.green() - target.green()),
               abs(brightest.blue() - target.blue())) <= 2
    assert image.pixelColor(5, 10).value() < brightest.value()
