# -*- coding: utf-8 -*-
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from src.ui.splitter import DIVIDER_WIDTH, LINE_WIDTH, SashHandle, SashSplitter
from src.ui.theme import DARK, LIGHT
from tests.helpers import wait_until


def make_splitter(palette=LIGHT, **kwargs) -> SashSplitter:
    splitter = SashSplitter(Qt.Orientation.Horizontal, palette, **kwargs)
    splitter.setHandleWidth(12)
    splitter.addWidget(QWidget())
    splitter.addWidget(QWidget())
    splitter.resize(300, 200)
    splitter.show()
    return splitter


def test_splitter_uses_sash_handle(qapp):
    splitter = make_splitter()
    assert isinstance(splitter.handle(1), SashHandle)
    splitter.deleteLater()


def test_line_hidden_at_rest(qapp):
    splitter = make_splitter()
    assert splitter.handle(1).line_opacity() == 0.0
    splitter.deleteLater()


def test_hover_fades_line_in_after_delay_and_out_on_leave(qapp):
    splitter = make_splitter(hover_delay_ms=30, fade_ms=20)
    handle = splitter.handle(1)
    QApplication.sendEvent(handle, QEvent(QEvent.Type.Enter))
    assert handle.line_opacity() == 0.0  # 延遲期間還不顯示，避免滑鼠路過就閃線
    wait_until(lambda: handle.line_opacity() == 1.0)
    QApplication.sendEvent(handle, QEvent(QEvent.Type.Leave))
    wait_until(lambda: handle.line_opacity() == 0.0)
    splitter.deleteLater()


def test_leave_before_delay_never_shows_line(qapp):
    splitter = make_splitter(hover_delay_ms=200, fade_ms=20)
    handle = splitter.handle(1)
    QApplication.sendEvent(handle, QEvent(QEvent.Type.Enter))
    QApplication.sendEvent(handle, QEvent(QEvent.Type.Leave))
    QTest.qWait(260)
    assert handle.line_opacity() == 0.0
    splitter.deleteLater()


def test_press_shows_line_immediately_and_keeps_it_while_dragging(qapp):
    splitter = make_splitter(hover_delay_ms=500, fade_ms=20)
    handle = splitter.handle(1)
    center = handle.rect().center()
    QTest.mousePress(handle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    wait_until(lambda: handle.line_opacity() == 1.0)
    QApplication.sendEvent(handle, QEvent(QEvent.Type.Leave))  # 拖曳中游標跑出分隔器也維持顯示
    QTest.qWait(60)
    assert handle.line_opacity() == 1.0
    QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(-50, -50))
    wait_until(lambda: handle.line_opacity() == 0.0)  # 放開時游標已不在分隔器上
    splitter.deleteLater()


def test_paints_accent_line_when_visible(qapp):
    splitter = make_splitter()
    handle = splitter.handle(1)
    handle.set_line_opacity(1.0)
    image = handle.grab().toImage()
    x = (handle.width() - LINE_WIDTH) // 2
    assert image.pixelColor(x, 5) == QColor(LIGHT.accent)
    assert image.pixelColor(x + LINE_WIDTH - 1, handle.height() - 5) == QColor(LIGHT.accent)
    splitter.deleteLater()


def test_paints_dots_without_line_at_rest(qapp):
    splitter = make_splitter()
    handle = splitter.handle(1)
    image = handle.grab().toImage()
    x = (handle.width() - LINE_WIDTH) // 2
    assert image.pixelColor(x, 5) != QColor(LIGHT.accent)  # 平時看不到線
    center = handle.rect().center()
    dot = image.pixelColor(center.x(), center.y())
    background = image.pixelColor(1, 5)
    assert dot != background  # 中央有三個點
    splitter.deleteLater()


def test_set_palette_updates_line_color(qapp):
    splitter = make_splitter()
    handle = splitter.handle(1)
    splitter.set_palette(DARK)
    handle.set_line_opacity(1.0)
    image = handle.grab().toImage()
    assert image.pixelColor((handle.width() - LINE_WIDTH) // 2, 5) == QColor(DARK.accent)
    splitter.deleteLater()


def test_vertical_splitter_paints_horizontal_line(qapp):
    splitter = SashSplitter(Qt.Orientation.Vertical, LIGHT)
    splitter.setHandleWidth(8)
    splitter.addWidget(QWidget())
    splitter.addWidget(QWidget())
    splitter.resize(200, 300)
    splitter.show()
    handle = splitter.handle(1)
    handle.set_line_opacity(1.0)
    image = handle.grab().toImage()
    y = (handle.height() - LINE_WIDTH) // 2
    assert image.pixelColor(5, y) == QColor(LIGHT.accent)
    assert image.pixelColor(handle.width() - 5, y + LINE_WIDTH - 1) == QColor(LIGHT.accent)
    splitter.deleteLater()


def test_press_emits_sash_pressed_with_handle_index(qapp):
    splitter = make_splitter()
    pressed = []
    splitter.sashPressed.connect(pressed.append)
    handle = splitter.handle(1)
    QTest.mousePress(handle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, handle.rect().center())
    QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, handle.rect().center())
    assert pressed == [1]
    splitter.deleteLater()


def test_hiding_handle_mid_drag_resets_line(qapp):
    splitter = make_splitter(fade_ms=20)
    handle = splitter.handle(1)
    QTest.mousePress(handle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, handle.rect().center())
    wait_until(lambda: handle.line_opacity() == 1.0)
    splitter.widget(0).hide()  # 相鄰元件隱藏會連帶隱藏 handle（下一輪事件迴圈），之後收不到放開事件
    wait_until(handle.isHidden)
    assert handle.line_opacity() == 0.0
    splitter.widget(0).show()
    QTest.qWait(60)
    assert handle.line_opacity() == 0.0  # 再次顯示時不會殘留藍線
    splitter.deleteLater()


def test_divider_draws_centered_line_under_dots(qapp):
    splitter = make_splitter(divider=True)
    handle = splitter.handle(1)
    image = handle.grab().toImage()
    axis = handle.width() // 2
    half = DIVIDER_WIDTH // 2
    for x in range(axis - half, axis + half + 1):  # 分隔線以正中央那排像素為軸，左右對稱
        assert image.pixelColor(x, 5) == QColor(LIGHT.border)
    assert image.pixelColor(axis - half - 1, 5) != QColor(LIGHT.border)
    assert image.pixelColor(axis + half + 1, 5) != QColor(LIGHT.border)
    middle = handle.height() // 2
    assert image.pixelColor(axis, middle) != QColor(LIGHT.border)  # 三個點疊在線上
    splitter.deleteLater()


def test_no_divider_by_default(qapp):
    splitter = make_splitter()
    handle = splitter.handle(1)
    image = handle.grab().toImage()
    assert image.pixelColor(handle.width() // 2, 5) != QColor(LIGHT.border)
    splitter.deleteLater()


def test_dots_are_centered_on_axis_pixel(qapp):
    splitter = make_splitter()
    handle = splitter.handle(1)
    image = handle.grab().toImage()
    axis, middle = handle.width() // 2, handle.height() // 2
    left, right = image.pixelColor(axis - 1, middle), image.pixelColor(axis + 1, middle)
    assert left == right  # 點以中央像素為軸左右對稱
    splitter.deleteLater()
