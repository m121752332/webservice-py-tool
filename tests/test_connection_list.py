# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from src.core.connection_store import Connection
from src.ui.connection_list import NO_URL, UNNAMED, ConnectionList

CONNECTIONS = [
    Connection("u1", "正式區", "http://prod/ws?WSDL", []),
    Connection("u2", "測試區", "http://test/ws?WSDL", []),
    Connection("u3", "", "", []),
]


def make_list(select=None):
    widget = ConnectionList()
    received = []
    widget.selectionChanged.connect(received.append)
    widget.set_connections(CONNECTIONS, select_uuid=select)
    return widget, received


def test_selects_first_by_default(qapp):
    widget, received = make_list()
    assert widget.current_uuid() == "u1"
    assert received == ["u1"]


def test_selects_requested_connection(qapp):
    widget, received = make_list("u2")
    assert widget.current_uuid() == "u2"
    assert received == ["u2"]


def test_blank_connection_shows_placeholders(qapp):
    widget, _ = make_list()
    item = widget.item_widget("u3")
    assert item.title.text() == UNNAMED
    assert item.subtitle.text() == NO_URL
    assert not item.grab().isNull()  # 觸發 ElidedLabel.paintEvent


def test_filter_matches_name_or_url_case_insensitive(qapp):
    widget, _ = make_list()
    widget.search_edit.setText("PROD")
    assert widget.visible_uuids() == ["u1"]
    widget.search_edit.setText("測試")
    assert widget.visible_uuids() == ["u2"]
    widget.search_edit.setText("")
    assert widget.visible_uuids() == ["u1", "u2", "u3"]


def test_update_connection_refreshes_labels(qapp):
    widget, _ = make_list()
    widget.update_connection(Connection("u3", "新名稱", "http://x/ws?WSDL", []))
    assert widget.item_widget("u3").title.text() == "新名稱"
    assert widget.item_widget("u3").subtitle.text() == "http://x/ws?WSDL"


def test_select_emits_selection_changed(qapp):
    widget, received = make_list()
    widget.select("u3")
    assert received == ["u1", "u3"]


def test_delete_key_requests_delete_of_current(qapp):
    widget, _ = make_list("u2")
    requested = []
    widget.deleteRequested.connect(requested.append)
    QTest.keyClick(widget.list_view, Qt.Key.Key_Delete)
    assert requested == ["u2"]


def test_add_button_emits_add_requested(qapp):
    widget, _ = make_list()
    requested = []
    widget.addRequested.connect(lambda: requested.append(True))
    widget.add_button.click()
    assert requested == [True]


def test_set_busy_disables_interaction(qapp):
    widget, _ = make_list()
    widget.set_busy(True)
    assert not widget.list_view.isEnabled() and not widget.add_button.isEnabled()
    widget.set_busy(False)
    assert widget.list_view.isEnabled() and widget.add_button.isEnabled()


def test_set_connections_empty(qapp):
    widget, _ = make_list()
    widget.set_connections([])
    assert widget.current_uuid() is None
    assert widget.visible_uuids() == []
