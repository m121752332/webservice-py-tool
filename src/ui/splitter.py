"""可拖曳分隔器：仿 VS Code 的 sash，平時中央顯示三個點（可選擇疊在 1px 分隔線上），懸浮或拖曳時淡入一條強調色實線"""
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSplitter, QSplitterHandle

from src.ui.theme import ThemePalette

HOVER_DELAY_MS = 300  # 同 VS Code：停留一下才顯示，滑鼠只是路過不會閃線
FADE_MS = 150
LINE_WIDTH = 4  # 同 VS Code 預設的 sash 懸浮粗細
DOT_RADIUS = 1.5
DOT_SPACING = 5  # 相鄰兩點圓心距離
DIVIDER_WIDTH = 5  # divider=True 時的分隔線粗細；用奇數才能以中央像素為軸左右對稱


def _colors(palette: ThemePalette) -> tuple[str, str, str]:
    """(點, 懸浮線, 分隔線)"""
    return palette.text_muted, palette.accent, palette.border


class SashHandle(QSplitterHandle):
    def __init__(self, orientation: Qt.Orientation, parent: "SashSplitter"):
        super().__init__(orientation, parent)
        self._divider = parent.divider
        self.set_colors(*parent.palette_colors)
        self._opacity = 0.0
        self._hovered = False
        self._dragging = False
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.setInterval(parent.hover_delay_ms)
        self._delay.timeout.connect(lambda: self._fade_to(1.0))
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(parent.fade_ms)
        self._fade.valueChanged.connect(self.set_line_opacity)

    def line_opacity(self) -> float:
        return self._opacity

    def set_line_opacity(self, opacity: float) -> None:
        self._opacity = float(opacity)
        self.update()

    def set_colors(self, dot: str, line: str, divider: str) -> None:
        self._dot_color = QColor(dot)
        self._line_color = QColor(line)
        self._divider_color = QColor(divider)
        self.update()

    def _fade_to(self, target: float) -> None:
        self._fade.stop()
        if self._opacity == target:
            return
        self._fade.setStartValue(self._opacity)
        self._fade.setEndValue(target)
        self._fade.start()

    def enterEvent(self, event) -> None:
        self._hovered = True
        if not self._dragging:
            self._delay.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        if not self._dragging:
            self._delay.stop()
            self._fade_to(0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._delay.stop()
            self._fade_to(1.0)  # 開始拖曳立即顯示，不等懸浮延遲
            self.splitter().sashPressed.emit(self.splitter().indexOf(self))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = False
        self._hovered = self.rect().contains(event.position().toPoint())
        if not self._hovered:
            self._fade_to(0.0)

    def hideEvent(self, event) -> None:
        # 拖曳途中相鄰元件被隱藏（例如專案目錄拖到太窄自動收起）時收不到放開事件，這裡把狀態歸零
        self._hovered = False
        self._dragging = False
        self._delay.stop()
        self._fade.stop()
        self.set_line_opacity(0.0)
        super().hideEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        horizontal = self.orientation() == Qt.Orientation.Horizontal
        # 以正中央那一排像素為軸：分隔線以這排像素左右對稱、點的圓心落在像素中心，邊緣才不會糊
        axis = (self.width() if horizontal else self.height()) // 2
        if self._divider:
            start = axis - DIVIDER_WIDTH // 2
            if horizontal:
                divider = QRectF(start, 0, DIVIDER_WIDTH, self.height())
            else:
                divider = QRectF(0, start, self.width(), DIVIDER_WIDTH)
            painter.fillRect(divider, self._divider_color)
        center = QPointF(axis + 0.5, self.height() / 2) if horizontal else QPointF(self.width() / 2, axis + 0.5)
        if self._opacity < 1.0:
            # 三個點沿分隔器長邊排列（左右分割為「⋮」），線淡入時同步淡出
            painter.setOpacity(1.0 - self._opacity)
            painter.setBrush(self._dot_color)
            for step in (-1, 0, 1):
                offset = QPointF(0, step * DOT_SPACING) if horizontal else QPointF(step * DOT_SPACING, 0)
                painter.drawEllipse(center + offset, DOT_RADIUS, DOT_RADIUS)
        if self._opacity > 0.0:
            painter.setOpacity(self._opacity)
            if horizontal:
                line = QRectF((self.width() - LINE_WIDTH) // 2, 0, LINE_WIDTH, self.height())
            else:
                line = QRectF(0, (self.height() - LINE_WIDTH) // 2, self.width(), LINE_WIDTH)
            painter.fillRect(line, self._line_color)


class SashSplitter(QSplitter):
    """分隔器顏色取自主題：點用 text_muted、懸浮線用 accent、分隔線用 border；切換主題時呼叫 set_palette

    divider=True 時由分隔器在正中央畫 1px 分隔線（取代相鄰面板自己的邊框），三個點會疊在線上，同 VS Code
    """

    sashPressed = Signal(int)  # 開始拖曳某個分隔器，參數為該 handle 的索引

    def __init__(self, orientation: Qt.Orientation, palette: ThemePalette, parent=None, *,
                 hover_delay_ms: int = HOVER_DELAY_MS, fade_ms: int = FADE_MS, divider: bool = False):
        self.palette_colors = _colors(palette)
        self.divider = divider
        self.hover_delay_ms = hover_delay_ms
        self.fade_ms = fade_ms
        super().__init__(orientation, parent)

    def createHandle(self) -> QSplitterHandle:
        return SashHandle(self.orientation(), self)

    def set_palette(self, palette: ThemePalette) -> None:
        self.palette_colors = _colors(palette)
        for index in range(self.count()):
            handle = self.handle(index)
            if isinstance(handle, SashHandle):
                handle.set_colors(*self.palette_colors)
