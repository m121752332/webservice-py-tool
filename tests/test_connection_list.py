# -*- coding: utf-8 -*-
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView

from src.core.connection_store import Connection, Folder
from src.ui.connection_list import (
    ABOVE, BELOW, CONNECTION, FOLDER, FOLDER_UNNAMED, NO_URL, ON, UNNAMED, ConnectionList, Move, TreeLayout,
    resolve_drop,
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
    widget.set_tree([], CONNECTIONS, select_uuid=select)
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
    QTest.keyClick(widget.tree, Qt.Key.Key_Delete)
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
    assert not widget.tree.isEnabled()
    assert not widget.add_button.isEnabled() and not widget.add_folder_button.isEnabled()
    widget.set_busy(False)
    assert widget.tree.isEnabled()
    assert widget.add_button.isEnabled() and widget.add_folder_button.isEnabled()


def test_clear_search_shows_all_rows(qapp):
    widget, _ = make_list()
    widget.search_edit.setText("PROD")
    assert widget.visible_uuids() == ["u1"]
    widget.clear_search()
    assert widget.search_edit.text() == ""
    assert widget.visible_uuids() == ["u1", "u2", "u3"]


def test_set_tree_empty(qapp):
    widget, _ = make_list()
    widget.set_tree([], [])
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


FOLDERS = [Folder("f1", "TIPTOP", True), Folder("f2", "", False)]
TREE = [
    Connection("u1", "正式區", "http://prod/ws?WSDL", [], "f1"),
    Connection("u2", "測試區", "http://test/ws?WSDL", []),
    Connection("u4", "報表", "http://report/ws?WSDL", [], "f2"),
    Connection("u5", "備援", "http://backup/ws?WSDL", [], "f1"),
]


def make_tree(select=None):
    widget = ConnectionList()
    received = []
    widget.selectionChanged.connect(received.append)
    widget.set_tree(FOLDERS, TREE, select_uuid=select)
    return widget, received


def top_level(widget):
    return [widget.tree.topLevelItem(i) for i in range(widget.tree.topLevelItemCount())]


def uuid_of(item):
    return item.data(0, Qt.ItemDataRole.UserRole)


def child_uuids(item):
    return [uuid_of(item.child(i)) for i in range(item.childCount())]


def folder_item(widget, folder_uuid):
    return next(item for item in top_level(widget) if uuid_of(item) == folder_uuid)


def record(signal):
    calls = []
    signal.connect(lambda *args: calls.append(args))
    return calls


def test_tree_places_folders_first_and_connections_inside(qapp):
    widget, received = make_tree()
    items = top_level(widget)
    assert [uuid_of(item) for item in items] == ["f1", "f2", "u2"]
    assert child_uuids(items[0]) == ["u1", "u5"]
    assert child_uuids(items[1]) == ["u4"]
    assert (items[0].text(0), items[1].text(0)) == ("TIPTOP", FOLDER_UNNAMED)
    assert items[0].isExpanded() and not items[1].isExpanded()
    assert widget.current_uuid() == "u1"
    assert received == ["u1"]


def test_selecting_folder_emits_blank_and_reports_current_folder(qapp):
    widget, received = make_tree()
    widget.select("f1")
    assert received[-1] == ""
    assert widget.current_uuid() is None
    assert widget.current_folder() == "f1"
    widget.select("u5")
    assert widget.current_folder() == "f1"
    widget.select("u2")
    assert widget.current_folder() is None


def test_selecting_connection_in_collapsed_folder_expands_it(qapp):
    widget, _ = make_tree()
    changes = record(widget.folderExpandedChanged)
    widget.select("u4")
    assert folder_item(widget, "f2").isExpanded()
    assert changes == [("f2", True)]


def test_set_tree_keeps_current_selection(qapp):
    widget, _ = make_tree("u2")
    widget.set_tree(FOLDERS, TREE)
    assert widget.current_uuid() == "u2"
    widget.select("f1")
    widget.set_tree(FOLDERS, TREE)
    assert widget.current_folder() == "f1" and widget.current_uuid() is None


def test_set_tree_default_selection_skips_collapsed_folder(qapp):
    """F2：第一筆連線位於已收合目錄時，預設選取改為畫面上第一筆可見連線，且不展開該目錄"""
    folders = [Folder("f1", "TIPTOP", False)]
    connections = [
        Connection("u1", "正式區", "http://prod/ws?WSDL", [], "f1"),
        Connection("u2", "測試區", "http://test/ws?WSDL", []),
    ]
    widget = ConnectionList()
    changes = record(widget.folderExpandedChanged)
    widget.set_tree(folders, connections)
    assert not folder_item(widget, "f1").isExpanded()
    assert changes == []
    assert widget.current_uuid() == "u2"


def test_set_tree_keeps_folder_collapsed_when_current_connection_inside_it(qapp):
    """F2：重建前選取的連線位於使用者剛收合的目錄中，重建後改選該目錄，目錄仍保持收合"""
    widget, _ = make_tree()
    assert widget.current_uuid() == "u1"  # 預設選到展開的 f1 內第一筆連線
    folder_item(widget, "f1").setExpanded(False)  # 使用者收合該目錄
    changes = record(widget.folderExpandedChanged)
    collapsed_folders = [Folder("f1", "TIPTOP", False), Folder("f2", "", False)]
    widget.set_tree(collapsed_folders, TREE)
    assert not folder_item(widget, "f1").isExpanded()
    assert changes == []
    assert widget.current_folder() == "f1"
    assert widget.current_uuid() is None


def test_clicking_folder_toggles_and_reports(qapp):
    widget, _ = make_tree()
    changes = record(widget.folderExpandedChanged)
    item = folder_item(widget, "f1")
    widget.tree.itemClicked.emit(item, 0)
    assert not item.isExpanded()
    widget.tree.itemClicked.emit(item, 0)
    assert item.isExpanded()
    assert changes == [("f1", False), ("f1", True)]


def test_rename_folder_emits_trimmed_name(qapp):
    widget, _ = make_tree()
    renamed = record(widget.folderRenamed)
    item = folder_item(widget, "f1")
    item.setText(0, "  ERP  ")
    assert item.text(0) == "ERP"
    assert renamed == [("f1", "ERP")]


def test_blank_rename_restores_previous_name(qapp):
    widget, _ = make_tree()
    renamed = record(widget.folderRenamed)
    folder_item(widget, "f1").setText(0, "   ")
    folder_item(widget, "f2").setText(0, "")
    assert folder_item(widget, "f1").text(0) == "TIPTOP"
    assert folder_item(widget, "f2").text(0) == FOLDER_UNNAMED
    assert renamed == []


def test_edit_folder_starts_inline_editing(qapp):
    widget, _ = make_tree()
    widget.edit_folder("f2")
    assert widget.current_folder() == "f2"
    assert widget.tree.state() == QAbstractItemView.State.EditingState


def test_request_delete_current_ignored_while_renaming_folder(qapp):
    """F4：正在重新命名目錄時按 F2／Delete 不應觸發刪除確認"""
    widget, _ = make_tree()
    widget.edit_folder("f1")
    folders, connections = [], []
    widget.deleteFolderRequested.connect(folders.append)
    widget.deleteRequested.connect(connections.append)
    widget.request_delete_current()
    assert folders == [] and connections == []


def test_filter_shows_matching_connection_under_its_folder(qapp):
    widget, _ = make_tree()
    changes = record(widget.folderExpandedChanged)
    widget.search_edit.setText("REPORT")
    assert widget.visible_uuids() == ["u4"]
    assert folder_item(widget, "f1").isHidden()
    assert not folder_item(widget, "f2").isHidden()
    assert folder_item(widget, "f2").isExpanded()
    widget.search_edit.setText("")
    assert widget.visible_uuids() == ["u1", "u5", "u4", "u2"]
    assert not folder_item(widget, "f2").isExpanded()
    assert changes == []


def test_filter_by_folder_name_shows_all_its_connections(qapp):
    widget, _ = make_tree()
    widget.search_edit.setText("tiptop")
    assert widget.visible_uuids() == ["u1", "u5"]


def test_search_disables_drag(qapp):
    widget, _ = make_tree()
    assert widget.tree.dragEnabled()
    widget.search_edit.setText("prod")
    assert not widget.tree.dragEnabled()
    widget.clear_search()
    assert widget.tree.dragEnabled()


def test_delete_key_on_folder_requests_folder_delete(qapp):
    widget, _ = make_tree()
    widget.select("f2")
    folders, connections = [], []
    widget.deleteFolderRequested.connect(folders.append)
    widget.deleteRequested.connect(connections.append)
    QTest.keyClick(widget.tree, Qt.Key.Key_Delete)
    assert folders == ["f2"] and connections == []


def test_add_folder_button_emits(qapp):
    widget, _ = make_tree()
    requested = []
    widget.addFolderRequested.connect(lambda: requested.append(True))
    widget.add_folder_button.click()
    assert requested == [True]


def test_drop_emits_move_signals(qapp):
    widget, _ = make_tree()
    moved_connections = record(widget.connectionMoved)
    moved_folders = record(widget.folderMoved)
    items = top_level(widget)
    widget.tree.itemDropped.emit(items[2], items[0], ON)  # u2 放到 TIPTOP 上
    widget.tree.itemDropped.emit(items[1], items[0], ABOVE)  # 未命名目錄移到 TIPTOP 前
    widget.tree.itemDropped.emit(items[2], items[2], ABOVE)  # 放回自己身上
    assert moved_connections == [("u2", "f1", 2)]
    assert moved_folders == [("f2", 0)]


def actions_by_text(menu):
    return {action.text(): action for action in menu.actions() if action.text()}


def test_connection_menu_moves_into_folder(qapp):
    widget, _ = make_tree()
    moved = record(widget.connectionMoved)
    actions = actions_by_text(widget._context_menu(top_level(widget)[2]))  # u2 在最外層
    assert list(actions) == ["移動到", "刪除"]
    targets = actions_by_text(actions["移動到"].menu())
    assert list(targets) == ["最外層", "TIPTOP", FOLDER_UNNAMED]
    assert not targets["最外層"].isEnabled()
    targets["TIPTOP"].trigger()
    assert moved == [("u2", "f1", 2)]


def test_connection_menu_moves_to_root_and_deletes(qapp):
    widget, _ = make_tree()
    moved = record(widget.connectionMoved)
    deleted = []
    widget.deleteRequested.connect(deleted.append)
    actions = actions_by_text(widget._context_menu(folder_item(widget, "f1").child(0)))  # u1
    targets = actions_by_text(actions["移動到"].menu())
    assert not targets["TIPTOP"].isEnabled()
    targets["最外層"].trigger()
    actions["刪除"].trigger()
    assert moved == [("u1", None, 1)]
    assert deleted == ["u1"]


def test_folder_menu_actions(qapp):
    widget, _ = make_tree("u2")
    added, deleted = [], []
    widget.addRequested.connect(lambda: added.append(widget.current_folder()))
    widget.deleteFolderRequested.connect(deleted.append)
    actions = actions_by_text(widget._context_menu(folder_item(widget, "f2")))
    assert list(actions) == ["新增連線到此目錄", "重新命名", "刪除目錄"]
    actions["新增連線到此目錄"].trigger()
    assert added == ["f2"]
    actions["重新命名"].trigger()
    assert widget.tree.state() == QAbstractItemView.State.EditingState
    actions["刪除目錄"].trigger()
    assert deleted == ["f2"]


def test_blank_area_menu_actions(qapp):
    widget, _ = make_tree("u1")
    added, folders = [], []
    widget.addRequested.connect(lambda: added.append((widget.current_uuid(), widget.current_folder())))
    widget.addFolderRequested.connect(lambda: folders.append(True))
    actions = actions_by_text(widget._context_menu(None))
    assert list(actions) == ["新增連線", "新增目錄"]
    actions["新增連線"].trigger()
    actions["新增目錄"].trigger()
    assert added == [(None, None)]
    assert folders == [True]
