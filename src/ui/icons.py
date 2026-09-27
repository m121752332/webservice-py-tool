# -*- coding: utf-8 -*-
"""
介面圖示：以 QPainter 繪製的漸層向量圖（不依賴外部圖檔），以及資料夾染色、選單色塊
"""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

ICON_CANVAS = 64  # 繪製座標系統的邏輯尺寸，實際輸出改用 ICON_SIZES 直接繪製對應解析度
ICON_SIZES = (20, 40, 64)  # 對應按鈕實際顯示尺寸與常見 2x／3x 螢幕縮放；避免用單張大圖縮小造成邊緣模糊（淺色主題下尤其明顯）
THEME_GRADIENT = ("#8B5CF6", "#EC4899")
ABOUT_GRADIENT = ("#0EA5E9", "#2563EB")
CONSOLE_GRADIENT = ("#10B981", "#0D9488")
RECORD_GRADIENT = ("#F59E0B", "#EA580C")
PROJECT_GRADIENT = ("#818CF8", "#4F46E5")
PALETTE_DOTS = ("#FACC15", "#34D399", "#38BDF8", "#F87171")
SWATCH_SIZE = 12  # 右鍵選單色塊


def _canvas(size: int) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / ICON_CANVAS, size / ICON_CANVAS)  # 繪圖座標維持 0~64，這裡換算成實際像素
    painter.setPen(Qt.PenStyle.NoPen)
    return pixmap, painter


def _build_icon(draw) -> QIcon:
    """依 ICON_SIZES 各別在對應解析度直接繪製，讓 QIcon 依螢幕縮放挑選精確尺寸"""
    icon = QIcon()
    for size in ICON_SIZES:
        pixmap, painter = _canvas(size)
        draw(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def _gradient(colors: tuple[str, str]) -> QLinearGradient:
    gradient = QLinearGradient(0, 0, ICON_CANVAS, ICON_CANVAS)
    gradient.setColorAt(0, QColor(colors[0]))
    gradient.setColorAt(1, QColor(colors[1]))
    return gradient


def theme_icon() -> QIcon:
    """調色盤：漸層盤身、拇指孔與四色顏料點"""
    def draw(painter: QPainter) -> None:
        body = QPainterPath()
        body.addEllipse(QRectF(4, 6, 56, 52))
        hole = QPainterPath()
        hole.addEllipse(QRectF(36, 36, 13, 13))
        painter.setBrush(_gradient(THEME_GRADIENT))
        painter.drawPath(body.subtracted(hole))
        for color, (x, y) in zip(PALETTE_DOTS, ((20, 20), (34, 15), (46, 24), (17, 36))):
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(x, y), 5.5, 5.5)

    return _build_icon(draw)


def about_icon() -> QIcon:
    """資訊：漸層圓底與白色 i"""
    def draw(painter: QPainter) -> None:
        painter.setBrush(_gradient(ABOUT_GRADIENT))
        painter.drawEllipse(QRectF(4, 4, 56, 56))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QPointF(32, 19), 4.5, 4.5)
        painter.drawRoundedRect(QRectF(28, 27, 8, 22), 4, 4)

    return _build_icon(draw)


def console_icon() -> QIcon:
    """主控台：漸層圓角方塊與白色 >_ 提示字元"""
    def draw(painter: QPainter) -> None:
        painter.setBrush(_gradient(CONSOLE_GRADIENT))
        painter.drawRoundedRect(QRectF(4, 8, 56, 48), 10, 10)
        pen = QPen(QColor("#FFFFFF"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline([QPointF(16, 22), QPointF(26, 32), QPointF(16, 42)])
        painter.drawLine(QPointF(32, 43), QPointF(46, 43))

    return _build_icon(draw)


def rail_toggle_icon(collapsed: bool, color: str) -> QIcon:
    """摺疊/展開側欄：純線稿正方形外框；摺疊時左側一條短直條，展開時左側分隔線 + 兩條選單橫條。
    座標以 20 px 顯示時每 3.2 單位 = 1 px 對齊像素格，線寬 2 px 不糊；顏色跟隨主題文字色"""
    unit = ICON_CANVAS / 20  # 20 px 顯示時的 1 px

    def draw(painter: QPainter) -> None:
        pen = QPen(QColor(color), 2 * unit, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(2 * unit, 2 * unit, 16 * unit, 16 * unit), 2 * unit, 2 * unit)
        if collapsed:
            painter.drawLine(QPointF(5 * unit, 8 * unit), QPointF(5 * unit, 12 * unit))
            return
        painter.drawLine(QPointF(6 * unit, 2 * unit), QPointF(6 * unit, 18 * unit))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        for top in (4, 8):
            painter.drawRect(QRectF(2 * unit, top * unit, 4 * unit, 2 * unit))

    return _build_icon(draw)


def record_icon() -> QIcon:
    """請求紀錄：漸層文件與白色條列線"""
    def draw(painter: QPainter) -> None:
        painter.setBrush(_gradient(RECORD_GRADIENT))
        painter.drawRoundedRect(QRectF(10, 4, 44, 56), 8, 8)
        pen = QPen(QColor("#FFFFFF"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for y, end in ((18, 44), (30, 44), (42, 34)):
            painter.drawLine(QPointF(20, y), QPointF(end, y))

    return _build_icon(draw)


def project_icon() -> QIcon:
    """專案目錄：漸層資料夾（後片含頁籤）與半透明白色前片"""
    def draw(painter: QPainter) -> None:
        back = QPainterPath()
        back.addRoundedRect(QRectF(4, 10, 26, 14), 5, 5)
        back.addRoundedRect(QRectF(4, 16, 56, 40), 8, 8)
        painter.setBrush(_gradient(PROJECT_GRADIENT))
        painter.drawPath(back.simplified())
        painter.setBrush(QColor(255, 255, 255, 70))
        painter.drawRoundedRect(QRectF(4, 25, 56, 31), 8, 8)

    return _build_icon(draw)


def tinted_icon(icon: QIcon, color: str) -> QIcon:
    """保留原圖示的明暗層次與透明度，把色相換成 color（有顏色標記的資料夾用）

    作法：轉灰階後以 Multiply 疊上指定色，再用原圖 alpha 裁切輪廓
    """
    sizes = icon.availableSizes() or [QSize(ICON_SIZES[0], ICON_SIZES[0])]
    tinted = QIcon()
    for size in sizes:
        source = icon.pixmap(size).toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        image = source.convertToFormat(QImage.Format.Format_Grayscale8).convertToFormat(
            QImage.Format.Format_ARGB32_Premultiplied
        )
        painter = QPainter(image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        painter.fillRect(image.rect(), QColor(color))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, source)
        painter.end()
        tinted.addPixmap(QPixmap.fromImage(image))
    return tinted


def swatch_icon(color: str) -> QIcon:
    """右鍵選單「顏色」各項目前方的圓角方形色塊"""
    pixmap = QPixmap(SWATCH_SIZE, SWATCH_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRectF(0, 0, SWATCH_SIZE, SWATCH_SIZE), 3, 3)
    painter.end()
    return QIcon(pixmap)
