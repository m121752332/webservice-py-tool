# -*- coding: utf-8 -*-
from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QWidget

from src.ui.theme import DARK, LIGHT
from src.ui.theme_transition import CircularReveal, reveal_origin
from tests.helpers import wait_until

RECT = QRect(0, 0, 200, 100)


def solid(color: str) -> QPixmap:
    pixmap = QPixmap(RECT.size())
    pixmap.fill(QColor(color))
    return pixmap


def test_light_to_dark_spreads_from_bottom_left():
    assert reveal_origin(DARK, RECT) == QPointF(0, 100)


def test_dark_to_light_spreads_from_top_right():
    assert reveal_origin(LIGHT, RECT) == QPointF(200, 0)


def test_reveal_covers_window_and_passes_mouse_events(qapp):
    host = QWidget()
    host.resize(RECT.size())
    reveal = CircularReveal(host, solid("#FFFFFF"), solid("#000000"), QPointF(0, 100))
    assert reveal.geometry() == host.rect()
    assert reveal.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    host.deleteLater()


def test_reveal_paints_new_theme_inside_circle(qapp):
    host = QWidget()
    host.resize(RECT.size())
    reveal = CircularReveal(host, solid("#FFFFFF"), solid("#000000"), QPointF(0, 100))
    reveal.set_progress(0.5)
    image = reveal.grab().toImage()
    assert image.pixelColor(2, 98) == QColor("#000000")  # 左下起點已換成新主題
    assert image.pixelColor(198, 2) == QColor("#FFFFFF")  # 右上角仍是舊畫面
    host.deleteLater()


def test_reveal_deletes_itself_when_finished(qapp):
    host = QWidget()
    host.resize(RECT.size())
    reveal = CircularReveal(host, solid("#FFFFFF"), solid("#000000"), QPointF(0, 100), duration_ms=30)
    reveal.start()
    wait_until(lambda: host.findChild(CircularReveal) is None)
    host.deleteLater()
