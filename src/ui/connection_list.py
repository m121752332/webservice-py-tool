# -*- coding: utf-8 -*-
"""
左側連線清單：搜尋、選取、新增、刪除
"""
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.connection_store import Connection

UNNAMED = "未命名"
NO_URL = "尚未設定網址"
_UUID_ROLE = Qt.ItemDataRole.UserRole

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
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(2)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        self.set_connection(conn)

    def set_connection(self, conn: Connection) -> None:
        self.title.setText(conn.name or UNNAMED)
        self.subtitle.setText(conn.url or NO_URL)
        self.setToolTip(conn.url)


class _ListView(QListWidget):
    deletePressed = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.deletePressed.emit()
            return
        super().keyPressEvent(event)


class ConnectionList(QWidget):
    selectionChanged = Signal(str)
    addRequested = Signal()
    deleteRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜尋連線")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)

        self.list_view = _ListView()
        self.list_view.setObjectName("ConnectionList")
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self._show_context_menu)
        self.list_view.currentItemChanged.connect(self._on_current_changed)
        self.list_view.deletePressed.connect(self._request_delete_current)

        self.add_button = QPushButton("+ 新增連線")
        self.add_button.setToolTip("新增連線 (F1)")
        self.add_button.clicked.connect(lambda: self.addRequested.emit())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.list_view, 1)
        layout.addWidget(self.add_button)

    def set_connections(self, connections: list[Connection], select_uuid: str | None = None) -> None:
        self.list_view.blockSignals(True)
        self.list_view.clear()
        for conn in connections:
            item = QListWidgetItem()
            item.setData(_UUID_ROLE, conn.uuid)
            widget = ConnectionItemWidget(conn)
            item.setSizeHint(QSize(0, widget.sizeHint().height()))
            self.list_view.addItem(item)
            self.list_view.setItemWidget(item, widget)
        self.list_view.blockSignals(False)
        self._apply_filter(self.search_edit.text())
        target = select_uuid or (connections[0].uuid if connections else None)
        if target:
            self.select(target)

    def update_connection(self, conn: Connection) -> None:
        item = self._item_for(conn.uuid)
        if item is None:
            return
        self.list_view.itemWidget(item).set_connection(conn)
        self._apply_filter(self.search_edit.text())

    def select(self, uuid: str) -> None:
        item = self._item_for(uuid)
        if item is not None:
            self.list_view.setCurrentItem(item)

    def current_uuid(self) -> str | None:
        item = self.list_view.currentItem()
        return item.data(_UUID_ROLE) if item is not None else None

    def item_widget(self, uuid: str) -> ConnectionItemWidget | None:
        item = self._item_for(uuid)
        return self.list_view.itemWidget(item) if item is not None else None

    def visible_uuids(self) -> list[str]:
        return [
            self.list_view.item(row).data(_UUID_ROLE)
            for row in range(self.list_view.count())
            if not self.list_view.item(row).isHidden()
        ]

    def clear_search(self) -> None:
        self.search_edit.clear()

    def set_busy(self, busy: bool) -> None:
        self.list_view.setEnabled(not busy)
        self.add_button.setEnabled(not busy)

    def _item_for(self, uuid: str) -> QListWidgetItem | None:
        for row in range(self.list_view.count()):
            item = self.list_view.item(row)
            if item.data(_UUID_ROLE) == uuid:
                return item
        return None

    def _apply_filter(self, text: str) -> None:
        keyword = text.strip().lower()
        for row in range(self.list_view.count()):
            item = self.list_view.item(row)
            widget = self.list_view.itemWidget(item)
            haystack = f"{widget.title.text()}\n{widget.subtitle.text()}".lower()
            item.setHidden(bool(keyword) and keyword not in haystack)

    def _on_current_changed(self, current, _previous) -> None:
        self.selectionChanged.emit(current.data(_UUID_ROLE) if current is not None else "")

    def _request_delete_current(self) -> None:
        uuid = self.current_uuid()
        if uuid:
            self.deleteRequested.emit(uuid)

    def _show_context_menu(self, pos) -> None:
        item = self.list_view.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("刪除")
        if menu.exec(self.list_view.viewport().mapToGlobal(pos)) is delete_action:
            self.deleteRequested.emit(item.data(_UUID_ROLE))
