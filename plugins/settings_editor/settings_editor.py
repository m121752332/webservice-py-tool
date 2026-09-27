# -*- coding: utf-8 -*-
"""
設定編輯器外掛：以 pyqtgraph ParameterTree 顯示與編輯工具參數

本檔案另外打包在 plugins/settings_editor/，不可導入來自 src 的模組；
與主程式之間只傳遞 dict、list、str 等基本型別。
"""
from pyqtgraph.parametertree import Parameter, ParameterTree
from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QAbstractSpinBox, QLineEdit, QVBoxLayout, QWidget

API_VERSION = 1
_SPINBOX_PADDING = 14  # 數值欄位固定高度：字型高度 + 上下留白，貼近其他欄位（QLineEdit 等）的實際高度

_TREE_QSS = """
QTreeWidget#SettingsTree {{
    background: {surface}; color: {text};
    border: 1px solid {border}; border-radius: 8px; outline: 0;
}}
QTreeWidget#SettingsTree::item:selected {{ background: {surface_hover}; color: {text}; }}
QTreeWidget#SettingsTree QHeaderView::section {{
    background: {bg}; color: {text_muted}; border: none; border-bottom: 1px solid {border}; padding: 4px 8px;
}}
"""


def _parameter_opts(field: dict) -> dict:
    name = field["key"].rsplit(".", 1)[-1]
    opts = {"name": name, "title": field["label"], "tip": field["key"], "type": field["kind"]}
    if field["kind"] != "group":
        opts["value"] = field["value"]
        opts["default"] = field["value"]
    if field.get("limits") is not None:
        opts["limits"] = list(field["limits"])
    return opts


class SettingsTree(QWidget):
    """
    valueChanged：參數值已提交（編輯完成）
    valueEditing：使用者正在輸入、值尚未提交（pyqtgraph 要等 editingFinished 或延遲後才寫入參數）
    """
    valueChanged = Signal()
    valueEditing = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = Parameter.create(name="root", type="group")
        self._leaves: dict[str, Parameter] = {}
        self._loading = False
        self.tree = ParameterTree(showHeader=True)
        self.tree.setObjectName("SettingsTree")
        self.tree.setHeaderLabels(["參數", "值"])
        self.tree.setParameters(self._root, showTop=False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)
        self._root.sigTreeStateChanged.connect(self._on_tree_changed)

    def load(self, fields: list[dict]) -> None:
        """依 key 的父子關係建立參數樹；載入期間不發出 valueChanged"""
        self._loading = True
        try:
            self._root.clearChildren()
            self._leaves.clear()
            groups: dict[str, Parameter] = {"": self._root}
            for field in fields:
                parent_key = field["key"].rpartition(".")[0]
                param = Parameter.create(**_parameter_opts(field))
                groups[parent_key].addChild(param)
                if field["kind"] == "group":
                    groups[field["key"]] = param
                else:
                    self._leaves[field["key"]] = param
                    param.sigValueChanging.connect(self._on_value_changing)
        finally:
            self._loading = False
        # pyqtgraph 只把 tip 設在值的編輯元件上；參數名稱欄另外補上 key 提示
        for item in self.tree.listAllItems():
            param = getattr(item, "param", None)
            if param is not None and param is not self._root:
                item.setToolTip(0, param.opts.get("tip", ""))
        for _item, widget in self._pending_editors():
            if isinstance(widget, QAbstractSpinBox):
                # SpinBox 輸入文字時不會發出 sigValueChanging，另外監看使用者的輸入
                widget.lineEdit().textEdited.connect(self.valueEditing)
        self._fix_widget_row_heights()

    def parameters(self) -> Parameter:
        """根參數（測試與進階操作用）"""
        return self._root

    def values(self) -> dict[str, object]:
        return {key: param.value() for key, param in self._leaves.items()}

    def commit(self) -> None:
        """把輸入中尚未提交的值寫入參數；判斷是否有修改、儲存或離開前呼叫"""
        for item, widget in self._pending_editors():
            if isinstance(widget, QAbstractSpinBox):
                if widget.lineEdit().hasAcceptableInput():
                    widget.editingFinishedEvent()  # 解析輸入中的文字（無效文字比照失去焦點時捨棄）
                else:
                    widget.updateText()
            item.widgetValueChanged()  # 也涵蓋方向鍵／滾輪尚在延遲中的值

    def _fix_widget_row_heights(self) -> None:
        """pyqtgraph 為求緊湊，會把值欄的高度縮到編輯元件自然高度的 90%（見 basetypes.WidgetParameterItem），
        搭配本專案 QComboBox／SpinBox 的 QSS padding 常常放不下，元件會被裁切；改成至少留給元件自己要的高度。

        光把列（欄位）本身的 sizeHint 調高還不夠：元件所在的 layoutWidget 用 QHBoxLayout 排版，
        不會把元件垂直撐滿變高的列，元件會維持原本較矮的高度、上下留白，看起來像是被截掉一塊；
        下拉選單（ListParameterItem）又另外寫死 setMaximumHeight(20)，若只調高最小高度會跟這個
        上限打架，元件被選取顯示時反而會撐破列高、蓋到下一列。這裡統一把元件的最小／最大高度
        都定死在同一個值，等同 setFixedHeight，兩種問題一次處理
        """
        for item in self.tree.listAllItems():
            widget = getattr(item, "widget", None)
            if widget is None:
                continue
            needed = self._prepare_for_resize(widget)
            target, column = (item.subItem, 0) if getattr(item, "asSubItem", False) else (item, 1)
            current = target.sizeHint(column)
            # 列高最終可能由重設按鈕（defaultBtn）決定、比元件自己要的還高；
            # 元件的高度要跟著最終列高走，兩者對不齊就會留一截空白或蓋到下一列
            final_height = max(current.height(), needed)
            if current.height() != final_height:
                target.setSizeHint(column, QSize(current.width(), final_height))
            widget.setMinimumHeight(final_height)
            widget.setMaximumHeight(final_height)

    @staticmethod
    def _prepare_for_resize(widget: QWidget) -> int:
        """解除元件自己寫死、會跟後續調整衝突的高度限制，並回傳「元件自然想要多高」的參考值

        數值欄位（pyqtgraph 的 SpinBox）：sizeHint() 固定回傳高度 0，且預設開啟 compactHeight，
        每次繪製都會把自己壓回剛好文字高度、無視 QSS 留白，兩者都要先關閉／繞過

        下拉選單（ListParameterItem 的 QComboBox）：makeWidget() 寫死 setMaximumHeight(20)，
        先解除這個上限，才能讓下面統一設定的高度生效
        """
        if hasattr(widget, "opts") and "compactHeight" in widget.opts:
            widget.setOpts(compactHeight=False)
            return widget.fontMetrics().height() + _SPINBOX_PADDING
        widget.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        return widget.sizeHint().height()

    def _pending_editors(self):
        """(參數項目, 編輯元件)：只有文字與數值欄位會延遲提交"""
        leaves = set(map(id, self._leaves.values()))
        for item in self.tree.listAllItems():
            widget = getattr(item, "widget", None)
            if id(getattr(item, "param", None)) in leaves and isinstance(widget, (QLineEdit, QAbstractSpinBox)):
                yield item, widget

    def set_palette(self, colors: dict[str, str]) -> None:
        self.tree.setStyleSheet(_TREE_QSS.format(**colors))

    def _on_tree_changed(self, _param, changes) -> None:
        if self._loading:
            return
        if any(change == "value" for _, change, _ in changes):
            self.valueChanged.emit()

    def _on_value_changing(self, param, value) -> None:
        # 程式設定參數值時，編輯元件會在參數更新後才同步，此時兩者相同，不算輸入中
        if not self._loading and value != param.value():
            self.valueEditing.emit()
