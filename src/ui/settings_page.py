# -*- coding: utf-8 -*-
"""
設定頁：以外掛提供的 ParameterTree 編輯 ws_tool.yaml，按「儲存」才寫回
"""
from dataclasses import asdict, fields
from pathlib import Path
from types import ModuleType

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.config.app_settings import SettingsChanges, SettingsDocument, SettingsError
from src.ui.effects import styled_button
from src.ui.notification_bar import NotificationBar
from src.ui.plugin_loader import plugin_dir
from src.ui.theme import ThemePalette

PAGE_TITLE = "工具參數設定"
MISSING_PLUGIN_TEXT = "設定編輯器外掛未安裝"
SAVED_TEXT = "設定已儲存並套用"
RESTART_TEXT = "已儲存，以下設定需重新啟動才會生效："
_NO_CHANGES = SettingsChanges(hot=(), restart=())


def palette_colors(palette: ThemePalette) -> dict[str, str]:
    """外掛用的色票：ThemePalette 中 name 以外的顏色字串欄位（排除 xml、levels 等非字串欄位）"""
    return {
        f.name: getattr(palette, f.name) for f in fields(palette)
        if f.name != "name" and isinstance(getattr(palette, f.name), str)
    }


class SettingsPage(QWidget):
    saved = Signal(object, object)  # (SettingsDocument, SettingsChanges)
    backRequested = Signal()

    def __init__(self, plugin: ModuleType | None, palette: ThemePalette, parent=None):
        super().__init__(parent)
        self._doc: SettingsDocument | None = None
        self.editor = plugin.SettingsTree() if plugin is not None else None

        title = QLabel(PAGE_TITLE)
        title.setObjectName("PageTitle")
        self.save_button = styled_button("儲存", "green", "儲存並套用設定")
        self.revert_button = styled_button("還原", "orange", "還原為最後儲存的內容")
        self.back_button = styled_button("返回", tooltip="回到工作區 (F11 / Esc)")
        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch(1)
        for button in (self.save_button, self.revert_button, self.back_button):
            header.addWidget(button)

        self.notification = NotificationBar()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(12)
        layout.addLayout(header)
        layout.addWidget(self.notification)
        if self.editor is not None:
            self.editor.valueChanged.connect(self._update_buttons)
            editing = getattr(self.editor, "valueEditing", None)  # 選用：API 版本 1 的外掛可能沒有
            if editing is not None:
                editing.connect(self._on_editing)
            layout.addWidget(self.editor, 1)
        else:
            self.placeholder = QLabel(f"{MISSING_PLUGIN_TEXT}\n\n請將外掛資料夾放在：\n{plugin_dir()}")
            self.placeholder.setObjectName("Placeholder")
            self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.placeholder.setWordWrap(True)
            layout.addWidget(self.placeholder, 1)

        self.save_button.clicked.connect(self.save)
        self.revert_button.clicked.connect(self.revert)
        self.back_button.clicked.connect(self.backRequested)
        self.set_palette(palette)
        self._update_buttons()

    def open(self, path: Path) -> None:
        """每次進入設定頁都重新讀檔，反映外部的修改"""
        self.notification.dismiss()
        if self.editor is None:
            return
        try:
            self._doc = SettingsDocument.load(path)
        except SettingsError as exc:
            self._doc = None
            self.editor.load([])
            self.notification.show_message("error", str(exc))
        else:
            self.editor.load([asdict(field) for field in self._doc.fields])
        self._update_buttons()

    def is_dirty(self) -> bool:
        """先提交輸入中的值再判斷，避免離開時漏掉尚未按 Enter 的修改"""
        self._commit_editor()
        return self._has_changes()

    def _commit_editor(self) -> None:
        commit = getattr(self.editor, "commit", None)  # 選用：API 版本 1 的外掛可能沒有
        if commit is not None:
            commit()

    def _has_changes(self) -> bool:
        if self._doc is None or self.editor is None:
            return False
        try:
            return self._doc.changes(self.editor.values()) != _NO_CHANGES
        except SettingsError:
            return True

    @Slot()
    def save(self) -> bool:
        """寫回設定檔；沒有修改時直接視為成功"""
        if not self.is_dirty():
            return True
        values = self.editor.values()
        try:
            changes = self._doc.changes(values)
            self._doc = self._doc.save(values)
        except SettingsError as exc:
            self.notification.show_message("error", f"儲存失敗：{exc}")
            return False
        if changes.restart:
            self.notification.show_message("warning", RESTART_TEXT + "、".join(changes.restart))
        else:
            self.notification.show_message("success", SAVED_TEXT)
        self._update_buttons()
        self.saved.emit(self._doc, changes)
        return True

    @Slot()
    def revert(self) -> None:
        if self._doc is not None and self.editor is not None:
            self.editor.load([asdict(field) for field in self._doc.fields])
        self.notification.dismiss()
        self._update_buttons()

    def notify(self, level: str, text: str) -> None:
        self.notification.show_message(level, text)

    def set_palette(self, palette: ThemePalette) -> None:
        if self.editor is not None:
            self.editor.set_palette(palette_colors(palette))

    @Slot()
    def _update_buttons(self) -> None:
        # 不在這裡提交：輸入途中提交會讓數值欄位的文字被重新格式化
        self._set_buttons_enabled(self._has_changes())

    @Slot()
    def _on_editing(self) -> None:
        """使用者開始輸入就啟用按鈕；值提交後再由 _update_buttons 重新判斷"""
        if self._doc is not None:
            self._set_buttons_enabled(True)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self.save_button.setEnabled(enabled)
        self.revert_button.setEnabled(enabled)
