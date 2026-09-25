# -*- coding: utf-8 -*-
"""
左側連線清單：目錄分組、搜尋、選取、新增、刪除、拖曳排序
"""
from dataclasses import dataclass

from PySide6.QtCore import QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.connection_store import Connection, Folder

UNNAMED = "未命名"
FOLDER_UNNAMED = "未命名目錄"
NO_URL = "尚未設定網址"
FOLDER_ROW_HEIGHT = 36
FOLDER_FONT_SIZE = 11.5  # 比連線名稱大一級，作為分組標題
FOLDER_ICON_SIZE = 18
ROOT_LABEL = "最外層"
_UUID_ROLE = Qt.ItemDataRole.UserRole
_KIND_ROLE = Qt.ItemDataRole.UserRole + 1

FOLDER = "folder"
CONNECTION = "connection"
ABOVE = "above"
BELOW = "below"
ON = "on"


@dataclass
class TreeLayout:
    """清單目前的結構：目錄順序，以及各群組（目錄 uuid，None 為最外層）內的連線順序"""
    folders: list[str]
    groups: dict[str | None, list[str]]

    def folder_of(self, conn_uuid: str) -> str | None:
        for folder, members in self.groups.items():
            if conn_uuid in members:
                return folder
        raise KeyError(conn_uuid)


@dataclass(frozen=True)
class Move:
    kind: str  # FOLDER 或 CONNECTION
    uuid: str
    folder: str | None  # 連線的目標目錄；目錄移動時為 None
    index: int  # 移除自己之後，在目標群組中的位置


def resolve_drop(layout: TreeLayout, kind: str, uuid: str, target_kind: str | None,
                 target_uuid: str | None, position: str) -> Move | None:
    """計算拖放結果；target 為 None 表示放在空白處，放到自己身上時回傳 None"""
    if kind == FOLDER:
        return _resolve_folder_drop(layout, uuid, target_kind, target_uuid, position)
    return _resolve_connection_drop(layout, uuid, target_kind, target_uuid, position)


def _resolve_connection_drop(layout, uuid, target_kind, target_uuid, position) -> Move | None:
    if target_uuid == uuid:
        return None
    if target_kind == CONNECTION:
        folder = layout.folder_of(target_uuid)
        members = [member for member in layout.groups[folder] if member != uuid]
        return Move(CONNECTION, uuid, folder, members.index(target_uuid) + (0 if position == ABOVE else 1))
    if target_kind == FOLDER and position != ON:
        return Move(CONNECTION, uuid, None, 0)  # 最外層固定目錄在前、連線在後
    folder = target_uuid if target_kind == FOLDER else None
    members = [member for member in layout.groups[folder] if member != uuid]
    return Move(CONNECTION, uuid, folder, len(members))


def _resolve_folder_drop(layout, uuid, target_kind, target_uuid, position) -> Move | None:
    others = [folder for folder in layout.folders if folder != uuid]
    if target_kind == CONNECTION:
        # 放到連線上：視為放在該連線所屬目錄之後；最外層連線則放到所有目錄最後面
        target_uuid = layout.folder_of(target_uuid)
        position = BELOW
    if target_uuid is None:
        return Move(FOLDER, uuid, None, len(others))
    if target_uuid == uuid:
        return None
    return Move(FOLDER, uuid, None, others.index(target_uuid) + (0 if position == ABOVE else 1))


def _uuid_of(item: QTreeWidgetItem | None) -> str | None:
    return item.data(0, _UUID_ROLE) if item is not None else None


def _kind_of(item: QTreeWidgetItem | None) -> str | None:
    return item.data(0, _KIND_ROLE) if item is not None else None


class ElidedLabel(QLabel):
    """單行標籤，文字過長時以 … 省略"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.contentsRect()
        elided = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, rect.width())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)


class ConnectionItemWidget(QWidget):
    def __init__(self, conn: Connection, parent=None):
        super().__init__(parent)
        self.title = ElidedLabel()
        self.title.setObjectName("ItemTitle")
        self.subtitle = ElidedLabel()
        self.subtitle.setObjectName("ItemSubtitle")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(0)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        self.set_connection(conn)

    def set_connection(self, conn: Connection) -> None:
        self.title.setText(conn.name or UNNAMED)
        self.subtitle.setText(conn.url or NO_URL)
        self.setToolTip(conn.url)


_DROP_POSITIONS = {
    QAbstractItemView.DropIndicatorPosition.AboveItem: ABOVE,
    QAbstractItemView.DropIndicatorPosition.BelowItem: BELOW,
    QAbstractItemView.DropIndicatorPosition.OnItem: ON,
}


class _TreeView(QTreeWidget):
    deletePressed = Signal()
    itemDropped = Signal(object, object, str)  # 拖曳的項目、放下處的項目（None 為空白處）、ABOVE/BELOW/ON

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.deletePressed.emit()
            return
        super().keyPressEvent(event)

    def dropEvent(self, event):
        indicator = self.dropIndicatorPosition()
        target = self.itemAt(event.position().toPoint()) if indicator in _DROP_POSITIONS else None
        # 不交給 Qt 搬移：忽略事件讓拖曳結果為 IgnoreAction，Qt 也就不會刪除來源項目；
        # 實際移動由主視窗更新 store 後重建整棵樹
        event.ignore()
        self.viewport().update()
        self.itemDropped.emit(self.currentItem(), target, _DROP_POSITIONS.get(indicator, ON))


class ConnectionList(QWidget):
    selectionChanged = Signal(str)
    addRequested = Signal()
    addFolderRequested = Signal()
    deleteRequested = Signal(str)
    deleteFolderRequested = Signal(str)
    folderRenamed = Signal(str, str)
    folderExpandedChanged = Signal(str, bool)
    connectionMoved = Signal(str, object, int)
    folderMoved = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder_names: dict[str, str] = {}
        self._folder_expanded: dict[str, bool] = {}

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜尋連線")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)

        self.tree = _TreeView()
        self.tree.setObjectName("ConnectionList")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setIconSize(QSize(FOLDER_ICON_SIZE, FOLDER_ICON_SIZE))
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.currentItemChanged.connect(self._on_current_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemExpanded.connect(lambda item: self._on_expansion_changed(item, True))
        self.tree.itemCollapsed.connect(lambda item: self._on_expansion_changed(item, False))
        self.tree.deletePressed.connect(self.request_delete_current)
        self.tree.itemDropped.connect(self._on_item_dropped)

        self.add_button = QPushButton("+ 新增連線")
        self.add_button.setToolTip("新增連線 (F1)")
        self.add_button.clicked.connect(lambda: self.addRequested.emit())
        self.add_folder_button = QPushButton("+ 新增目錄")
        self.add_folder_button.clicked.connect(lambda: self.addFolderRequested.emit())
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.add_folder_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.tree, 1)
        layout.addLayout(buttons)

    # ---------- 對外介面 ----------

    def set_tree(self, folders: list[Folder], connections: list[Connection], select_uuid: str | None = None) -> None:
        """依 store 資料重建整棵樹；選取 select_uuid，其次是重建前的目前項目，再其次是畫面上第一筆可見連線。

        除了明確指定 select_uuid，重建後一律不展開任何已收合的目錄（F2）：若重建前選取的連線
        現在位於已收合目錄中，改選該目錄；預設選取也只在已展開目錄的子項與最外層連線中挑選。
        """
        previous = _uuid_of(self.tree.currentItem())
        self._folder_names = {folder.uuid: folder.name for folder in folders}
        self._folder_expanded = {folder.uuid: folder.expanded for folder in folders}
        self.tree.blockSignals(True)
        self.tree.clear()
        parents = {folder.uuid: self._add_folder_item(folder) for folder in folders}
        for conn in connections:
            self._add_connection_item(parents.get(conn.folder, self.tree.invisibleRootItem()), conn)
        for folder in folders:
            parents[folder.uuid].setExpanded(folder.expanded)
        self.tree.blockSignals(False)
        self._apply_filter(self.search_edit.text())
        if select_uuid:
            self.select(select_uuid)
            return
        item = self._resolve_previous(previous) or self._default_item()
        if item is not None:
            self._select_item_without_expanding(item)

    def _resolve_previous(self, uuid: str | None) -> QTreeWidgetItem | None:
        """重建前的選取項目若仍存在就沿用；連線位於已收合目錄中則改選該目錄，不展開"""
        item = self._item_for(uuid) if uuid else None
        if item is None:
            return None
        if _kind_of(item) == CONNECTION:
            parent = item.parent()
            if parent is not None and not parent.isExpanded():
                return parent
        return item

    def _default_item(self) -> QTreeWidgetItem | None:
        """沒有可沿用的選取時：已展開目錄中第一筆連線（依目錄順序），其次最外層第一筆連線，
        再其次第一個最外層項目（一定是目錄）；樹是空的就回傳 None"""
        root = self.tree.invisibleRootItem()
        for row in range(root.childCount()):
            top = root.child(row)
            if _kind_of(top) != FOLDER:
                break  # 目錄一定排在最外層連線之前
            if top.isExpanded() and top.childCount():
                return top.child(0)
        for row in range(root.childCount()):
            top = root.child(row)
            if _kind_of(top) != FOLDER:
                return top
        return root.child(0) if root.childCount() else None

    def _select_item_without_expanding(self, item: QTreeWidgetItem) -> None:
        self.tree.setCurrentItem(item)

    def update_connection(self, conn: Connection) -> None:
        item = self._item_for(conn.uuid)
        if item is None:
            return
        self.tree.itemWidget(item, 0).set_connection(conn)
        self._apply_filter(self.search_edit.text())

    def select(self, uuid: str) -> None:
        item = self._item_for(uuid)
        if item is None:
            return
        parent = item.parent()
        if parent is not None and not parent.isExpanded():
            parent.setExpanded(True)
        self.tree.setCurrentItem(item)

    def current_uuid(self) -> str | None:
        item = self.tree.currentItem()
        return _uuid_of(item) if _kind_of(item) == CONNECTION else None

    def current_folder(self) -> str | None:
        """選到目錄時回傳該目錄；選到連線時回傳其所屬目錄（最外層為 None）"""
        item = self.tree.currentItem()
        if _kind_of(item) == FOLDER:
            return _uuid_of(item)
        return _uuid_of(item.parent()) if item is not None else None

    def edit_folder(self, uuid: str) -> None:
        item = self._item_for(uuid)
        if _kind_of(item) != FOLDER:
            return
        self.tree.setCurrentItem(item)
        self.tree.editItem(item, 0)

    def request_delete_current(self) -> None:
        if self.tree.state() == QAbstractItemView.State.EditingState:
            return  # F4：正在重新命名目錄時，F2／Delete 不應觸發刪除確認
        item = self.tree.currentItem()
        if _kind_of(item) == FOLDER:
            self.deleteFolderRequested.emit(_uuid_of(item))
        elif _kind_of(item) == CONNECTION:
            self.deleteRequested.emit(_uuid_of(item))

    def item_widget(self, uuid: str) -> ConnectionItemWidget | None:
        item = self._item_for(uuid)
        return self.tree.itemWidget(item, 0) if _kind_of(item) == CONNECTION else None

    def visible_uuids(self) -> list[str]:
        """未被搜尋篩選掉的連線（依畫面順序，不含目錄）"""
        return [
            _uuid_of(item)
            for item in self._iter_items()
            if _kind_of(item) == CONNECTION
            and not item.isHidden()
            and not (item.parent() is not None and item.parent().isHidden())
        ]

    def clear_search(self) -> None:
        self.search_edit.clear()

    def set_busy(self, busy: bool) -> None:
        for widget in (self.tree, self.add_button, self.add_folder_button):
            widget.setEnabled(not busy)

    # ---------- 建立項目 ----------

    def _add_folder_item(self, folder: Folder) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self.tree)
        item.setData(0, _UUID_ROLE, folder.uuid)
        item.setData(0, _KIND_ROLE, FOLDER)
        item.setText(0, folder.name or FOLDER_UNNAMED)
        item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        font = item.font(0)
        font.setWeight(QFont.Weight.DemiBold)
        font.setPointSizeF(FOLDER_FONT_SIZE)
        item.setFont(0, font)
        item.setSizeHint(0, QSize(0, FOLDER_ROW_HEIGHT))  # 固定高度，清單內改名的編輯框才放得下
        return item

    def _add_connection_item(self, parent: QTreeWidgetItem, conn: Connection) -> None:
        item = QTreeWidgetItem(parent)
        item.setData(0, _UUID_ROLE, conn.uuid)
        item.setData(0, _KIND_ROLE, CONNECTION)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)  # 連線不能當作放入目標
        widget = ConnectionItemWidget(conn)
        widget.ensurePolished()  # 先套用 QSS 字型，高度才會依較小的網址字型計算
        item.setSizeHint(0, QSize(0, widget.sizeHint().height()))
        self.tree.setItemWidget(item, 0, widget)

    # ---------- 查詢 ----------

    def _iter_items(self):
        root = self.tree.invisibleRootItem()
        for row in range(root.childCount()):
            top = root.child(row)
            yield top
            for child_row in range(top.childCount()):
                yield top.child(child_row)

    def _item_for(self, uuid: str) -> QTreeWidgetItem | None:
        return next((item for item in self._iter_items() if _uuid_of(item) == uuid), None)

    def _layout(self) -> TreeLayout:
        folders, groups = [], {None: []}
        root = self.tree.invisibleRootItem()
        for row in range(root.childCount()):
            item = root.child(row)
            if _kind_of(item) == FOLDER:
                folders.append(_uuid_of(item))
                groups[_uuid_of(item)] = [_uuid_of(item.child(i)) for i in range(item.childCount())]
            else:
                groups[None].append(_uuid_of(item))
        return TreeLayout(folders, groups)

    def _searching(self) -> bool:
        return bool(self.search_edit.text().strip())

    def _matches(self, item: QTreeWidgetItem, keyword: str) -> bool:
        widget = self.tree.itemWidget(item, 0)
        return keyword in f"{widget.title.text()}\n{widget.subtitle.text()}".lower()

    # ---------- 搜尋 ----------

    def _apply_filter(self, text: str) -> None:
        keyword = text.strip().lower()
        self.tree.setDragEnabled(not keyword)  # 篩選後的畫面位置與實際順序不對應
        self.tree.blockSignals(True)  # 搜尋造成的展開／收合不算使用者操作
        root = self.tree.invisibleRootItem()
        for row in range(root.childCount()):
            item = root.child(row)
            if _kind_of(item) == FOLDER:
                self._filter_folder(item, keyword)
            else:
                item.setHidden(bool(keyword) and not self._matches(item, keyword))
        self.tree.blockSignals(False)

    def _filter_folder(self, item: QTreeWidgetItem, keyword: str) -> None:
        if not keyword:
            item.setHidden(False)
            for row in range(item.childCount()):
                item.child(row).setHidden(False)
            item.setExpanded(self._folder_expanded.get(_uuid_of(item), True))
            return
        folder_hit = keyword in item.text(0).lower()
        any_visible = False
        for row in range(item.childCount()):
            child = item.child(row)
            visible = folder_hit or self._matches(child, keyword)
            child.setHidden(not visible)
            any_visible = any_visible or visible
        item.setHidden(not (folder_hit or any_visible))
        item.setExpanded(True)

    # ---------- 事件 ----------

    def _on_current_changed(self, current, _previous) -> None:
        self.selectionChanged.emit(_uuid_of(current) if _kind_of(current) == CONNECTION else "")

    def _on_item_clicked(self, item, _column) -> None:
        if _kind_of(item) == FOLDER:
            item.setExpanded(not item.isExpanded())

    def _on_expansion_changed(self, item, expanded: bool) -> None:
        uuid = _uuid_of(item)
        if _kind_of(item) != FOLDER or self._searching() or self._folder_expanded.get(uuid) == expanded:
            return
        self._folder_expanded[uuid] = expanded
        self.folderExpandedChanged.emit(uuid, expanded)

    def _on_item_changed(self, item, _column) -> None:
        """清單內改名完成：去除前後空白，空白名稱還原為原名"""
        if _kind_of(item) != FOLDER:
            return
        uuid = _uuid_of(item)
        display = self._folder_names.get(uuid) or FOLDER_UNNAMED
        name = item.text(0).strip()
        if not name or name == display:
            self._set_folder_text(item, display)
            return
        self._set_folder_text(item, name)
        self._folder_names[uuid] = name
        self.folderRenamed.emit(uuid, name)
        self._apply_filter(self.search_edit.text())

    def _set_folder_text(self, item: QTreeWidgetItem, text: str) -> None:
        if item.text(0) != text:
            self.tree.blockSignals(True)
            item.setText(0, text)
            self.tree.blockSignals(False)

    def _on_item_dropped(self, dragged, target, position: str) -> None:
        if dragged is None:
            return
        move = resolve_drop(
            self._layout(), _kind_of(dragged), _uuid_of(dragged), _kind_of(target), _uuid_of(target), position
        )
        if move is None:
            return
        if move.kind == FOLDER:
            self.folderMoved.emit(move.uuid, move.index)
        else:
            self.connectionMoved.emit(move.uuid, move.folder, move.index)

    def _show_context_menu(self, pos) -> None:
        menu = self._context_menu(self.tree.itemAt(pos))
        menu.exec(self.tree.viewport().mapToGlobal(pos))
        menu.deleteLater()

    def _context_menu(self, item: QTreeWidgetItem | None) -> QMenu:
        menu = QMenu(self)
        uuid = _uuid_of(item)
        if _kind_of(item) == CONNECTION:
            self._fill_connection_menu(menu, uuid, _uuid_of(item.parent()))
        elif _kind_of(item) == FOLDER:
            menu.addAction("新增連線到此目錄").triggered.connect(lambda: self._add_into(uuid))
            menu.addAction("重新命名").triggered.connect(lambda: self.edit_folder(uuid))
            menu.addSeparator()
            menu.addAction("刪除目錄").triggered.connect(lambda: self.deleteFolderRequested.emit(uuid))
        else:
            menu.addAction("新增連線").triggered.connect(lambda: self._add_into(None))
            menu.addAction("新增目錄").triggered.connect(lambda: self.addFolderRequested.emit())
        return menu

    def _fill_connection_menu(self, menu: QMenu, uuid: str, here: str | None) -> None:
        layout = self._layout()
        move_menu = menu.addMenu("移動到")
        targets = [(None, ROOT_LABEL)] + [
            (folder, self._folder_names.get(folder) or FOLDER_UNNAMED) for folder in layout.folders
        ]
        for folder, label in targets:
            action = move_menu.addAction(label)
            action.setEnabled(folder != here)
            action.triggered.connect(
                lambda _checked=False, target=folder: self.connectionMoved.emit(uuid, target, len(layout.groups[target]))
            )
        menu.addSeparator()
        menu.addAction("刪除").triggered.connect(lambda: self.deleteRequested.emit(uuid))

    def _add_into(self, folder: str | None) -> None:
        """先選取目標目錄（None 為取消選取，即最外層）再要求新增，主視窗依 current_folder() 決定位置"""
        if folder is None:
            self.tree.setCurrentIndex(QModelIndex())
        else:
            self.select(folder)
        self.addRequested.emit()
