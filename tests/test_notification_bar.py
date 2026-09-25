# -*- coding: utf-8 -*-
from PySide6.QtTest import QTest

from src.ui.notification_bar import NotificationBar
from tests.helpers import wait_until


def test_hidden_initially(qapp):
    assert NotificationBar().isHidden()


def test_warning_stays_until_closed(qapp):
    bar = NotificationBar()
    bar.auto_hide_ms = 10
    bar.show_message("warning", "注意")
    assert not bar.isHidden()
    assert (bar.level, bar.text) == ("warning", "注意")
    QTest.qWait(60)
    assert not bar.isHidden()
    bar.close_button.click()
    assert bar.isHidden()


def test_success_auto_hides(qapp):
    bar = NotificationBar()
    bar.auto_hide_ms = 10
    bar.show_message("success", "完成")
    assert not bar.isHidden()
    wait_until(bar.isHidden, timeout=2)


def test_error_replaces_success_and_stops_auto_hide(qapp):
    bar = NotificationBar()
    bar.auto_hide_ms = 30
    bar.show_message("success", "完成")
    bar.show_message("error", "失敗了")
    QTest.qWait(80)
    assert not bar.isHidden()
    assert (bar.level, bar.text) == ("error", "失敗了")
