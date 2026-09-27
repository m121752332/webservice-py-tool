"""主題切換轉場：新主題以圓形從角落擴散，蓋過舊畫面（淺→深從左下、深→淺從右上）"""
import math

from PySide6.QtCore import QEasingCurve, QPointF, QRect, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget

from src.ui.theme import DARK, ThemePalette

REVEAL_DURATION_MS = 600


def reveal_origin(new_palette: ThemePalette, rect: QRect) -> QPointF:
    """圓心位置：切到深色從左下角擴散，切到淺色從右上角擴散"""
    if new_palette == DARK:
        return QPointF(rect.left(), rect.bottom() + 1)
    return QPointF(rect.right() + 1, rect.top())


def _cover_radius(origin: QPointF, rect: QRect) -> float:
    """能蓋住整個 rect 的半徑：圓心到最遠角落的距離"""
    corners = (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight())
    return max(math.hypot(corner.x() - origin.x(), corner.y() - origin.y()) for corner in corners) + 1


class CircularReveal(QWidget):
    """蓋在視窗上的轉場層：圓內畫新畫面、圓外畫舊畫面；滑鼠事件穿透，播完自行刪除"""

    def __init__(self, host: QWidget, old: QPixmap, new: QPixmap, origin: QPointF,
                 duration_ms: int = REVEAL_DURATION_MS):
        super().__init__(host)
        self._old = old
        self._new = new
        self._origin = origin
        self._max_radius = _cover_radius(origin, host.rect())
        self._radius = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setGeometry(host.rect())
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(duration_ms)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._animation.valueChanged.connect(self.set_progress)
        self._animation.finished.connect(self.deleteLater)

    def start(self) -> None:
        self.raise_()
        self.show()
        self._animation.start()

    def finish(self) -> None:
        """立即結束（例如動畫中又切換主題）"""
        self._animation.stop()
        self.hide()
        self.deleteLater()

    def set_progress(self, progress: float) -> None:
        self._radius = self._max_radius * progress
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(self.rect(), self._old)
        circle = QPainterPath()
        circle.addEllipse(QRectF(
            self._origin.x() - self._radius, self._origin.y() - self._radius, self._radius * 2, self._radius * 2,
        ))
        painter.setClipPath(circle)
        painter.drawPixmap(self.rect(), self._new)
