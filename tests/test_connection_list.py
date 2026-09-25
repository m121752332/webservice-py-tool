# -*- coding: utf-8 -*-
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from src.core.connection_store import Connection
from src.ui.connection_list import (
    ABOVE, BELOW, CONNECTION, FOLDER, NO_URL, ON, UNNAMED, ConnectionList, Move, TreeLayout, resolve_drop,
)

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


def test_clear_search_shows_all_rows(qapp):
    widget, _ = make_list()
    widget.search_edit.setText("PROD")
    assert widget.visible_uuids() == ["u1"]
    widget.clear_search()
    assert widget.search_edit.text() == ""
    assert widget.visible_uuids() == ["u1", "u2", "u3"]


def test_set_connections_empty(qapp):
    widget, _ = make_list()
    widget.set_connections([])
    assert widget.current_uuid() is None
    assert widget.visible_uuids() == []


LAYOUT = TreeLayout(folders=["f1", "f2"], groups={"f1": ["a", "b"], "f2": [], None: ["c", "d"]})


@pytest.mark.parametrize("kind, uuid, target_kind, target_uuid, position, expected", [
    # 連線放到目錄上：放進該目錄最後面（以移除自己後的群組計算）
    (CONNECTION, "c", FOLDER, "f1", ON, Move(CONNECTION, "c", "f1", 2)),
    (CONNECTION, "c", FOLDER, "f2", ON, Move(CONNECTION, "c", "f2", 0)),
    (CONNECTION, "a", FOLDER, "f1", ON, Move(CONNECTION, "a", "f1", 1)),
    # 連線放在連線上方／下方：放到該連線所在群組
    (CONNECTION, "c", CONNECTION, "b", ABOVE, Move(CONNECTION, "c", "f1", 1)),
    (CONNECTION, "c", CONNECTION, "b", BELOW, Move(CONNECTION, "c", "f1", 2)),
    (CONNECTION, "a", CONNECTION, "b", BELOW, Move(CONNECTION, "a", "f1", 1)),
    (CONNECTION, "d", CONNECTION, "c", ABOVE, Move(CONNECTION, "d", None, 0)),
    (CONNECTION, "c", CONNECTION, "d", ON, Move(CONNECTION, "c", None, 1)),
    # 連線放在目錄上方／下方：最外層第一個（最外層固定目錄在前）
    (CONNECTION, "a", FOLDER, "f2", ABOVE, Move(CONNECTION, "a", None, 0)),
    (CONNECTION, "a", FOLDER, "f1", BELOW, Move(CONNECTION, "a", None, 0)),
    # 連線放在空白處：最外層最後面
    (CONNECTION, "a", None, None, ON, Move(CONNECTION, "a", None, 2)),
    (CONNECTION, "c", None, None, ON, Move(CONNECTION, "c", None, 1)),
    # 目錄只在目錄之間排序
    (FOLDER, "f2", FOLDER, "f1", ABOVE, Move(FOLDER, "f2", None, 0)),
    (FOLDER, "f1", FOLDER, "f2", BELOW, Move(FOLDER, "f1", None, 1)),
    (FOLDER, "f1", FOLDER, "f2", ON, Move(FOLDER, "f1", None, 1)),
    (FOLDER, "f2", CONNECTION, "a", BELOW, Move(FOLDER, "f2", None, 1)),
    (FOLDER, "f1", CONNECTION, "c", ABOVE, Move(FOLDER, "f1", None, 1)),
    (FOLDER, "f2", None, None, ON, Move(FOLDER, "f2", None, 1)),
])
def test_resolve_drop(kind, uuid, target_kind, target_uuid, position, expected):
    assert resolve_drop(LAYOUT, kind, uuid, target_kind, target_uuid, position) == expected


@pytest.mark.parametrize("kind, uuid, target_kind, target_uuid, position", [
    (CONNECTION, "a", CONNECTION, "a", ABOVE),  # 放在自己身上
    (FOLDER, "f1", FOLDER, "f1", ON),
    (FOLDER, "f1", CONNECTION, "a", ABOVE),  # 目錄放到自己的連線上
])
def test_resolve_drop_onto_itself_is_ignored(kind, uuid, target_kind, target_uuid, position):
    assert resolve_drop(LAYOUT, kind, uuid, target_kind, target_uuid, position) is None
