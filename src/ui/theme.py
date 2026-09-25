# -*- coding: utf-8 -*-
"""
主題：Light / Dark 色票、QSS 樣板與切換管理
"""
import tempfile
from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path
from string import Template

from PySide6.QtCore import QObject, QPointF, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPalette, QPolygonF
from PySide6.QtWidgets import QApplication, QWidget

SETTINGS_KEY = "ui/theme"
UI_FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Microsoft JhengHei UI"]
UI_FONT_SIZE = 10
ARROW_DIR = Path(tempfile.gettempdir()) / "webservice-tool-theme"
_ARROW_SCALE = 4  # 以 4 倍解析度繪製，縮小顯示時邊緣較平滑


class ThemeMode(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class XmlColors:
    tag: str
    attr_name: str
    attr_value: str
    comment: str
    declaration: str


@dataclass(frozen=True)
class ThemePalette:
    name: str
    bg: str
    surface: str
    surface_hover: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_text: str
    success: str
    warning: str
    danger: str
    xml: XmlColors


LIGHT = ThemePalette(
    name="light",
    bg="#F3F3F3",
    surface="#FFFFFF",
    surface_hover="#EAEAEA",
    border="#E0E0E0",
    text="#1B1B1B",
    text_muted="#616161",
    accent="#0067C0",
    accent_hover="#1975C5",
    accent_text="#FFFFFF",
    success="#0F7B0F",
    warning="#9D5D00",
    danger="#C42B1C",
    xml=XmlColors(tag="#800000", attr_name="#E50000", attr_value="#0000FF", comment="#008000", declaration="#808080"),
)

DARK = ThemePalette(
    name="dark",
    bg="#202020",
    surface="#2B2B2B",
    surface_hover="#383838",
    border="#3A3A3A",
    text="#FFFFFF",
    text_muted="#A0A0A0",
    accent="#4CC2FF",
    accent_hover="#47B1E8",
    accent_text="#000000",
    success="#6CCB5F",
    warning="#FCE100",
    danger="#FF99A4",
    xml=XmlColors(tag="#569CD6", attr_name="#9CDCFE", attr_value="#CE9178", comment="#6A9955", declaration="#808080"),
)

_QSS = Template("""
QWidget { color: $text; }
QMainWindow, QDialog { background: $bg; }
QFrame#Sidebar { background: $bg; border-right: 1px solid $border; }
QLabel#AppTitle { font-size: 13pt; font-weight: 600; padding: 0 4px 4px 4px; }
QLabel#SectionTitle { font-weight: 600; }
QLabel#Hint { color: $warning; }
QLabel#FieldLabel, QLabel#ItemSubtitle, QLabel#StatusDetail { color: $text_muted; }
QLabel#ItemTitle { font-weight: 600; }
QLabel#ItemSubtitle { font-size: 9pt; }
QFrame#Card { background: $surface; border: 1px solid $border; border-radius: 8px; }

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QPlainTextEdit { padding: 4px; }
QLineEdit#NameEdit { font-size: 12pt; font-weight: 600; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus { border: 1px solid $accent; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { color: $text_muted; background: $bg; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: url("$arrow_down"); width: 9px; height: 5px; }
QSpinBox { padding-right: 24px; }
QSpinBox::up-button, QSpinBox::down-button { subcontrol-origin: border; width: 20px; border: none; background: transparent; }
QSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 6px; }
QSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 6px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: $surface_hover; }
QSpinBox::up-arrow { image: url("$arrow_up"); width: 8px; height: 5px; }
QSpinBox::down-arrow { image: url("$arrow_down"); width: 8px; height: 5px; }
QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border;
    selection-background-color: $surface_hover;
    selection-color: $text;
    outline: 0;
}

QPushButton {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover { background: $surface_hover; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { color: $text_muted; }
QPushButton[variant="primary"] { background: $accent; color: $accent_text; border: 1px solid $accent; font-weight: 600; }
QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:disabled { background: $border; border-color: $border; color: $text_muted; }
QPushButton[variant="subtle"] { background: transparent; border: 1px solid transparent; padding: 4px 8px; }
QPushButton[variant="subtle"]:hover { background: $surface_hover; }
QPushButton::menu-indicator { width: 0; }

QTreeWidget#ConnectionList { background: transparent; border: none; outline: 0; show-decoration-selected: 0; }
QTreeWidget#ConnectionList::item { border-radius: 6px; margin: 1px 0; border-left: 3px solid transparent; }
QTreeWidget#ConnectionList QLineEdit {
    padding: 1px 6px; border: 1px solid $accent; border-radius: 4px;
    font-size: 11.5pt; font-weight: 600;  /* 清單內只有目錄可改名，與 connection_list.FOLDER_FONT_SIZE 一致 */
}
QTreeWidget#ConnectionList::item:hover { background: $surface_hover; }
QTreeWidget#ConnectionList::item:selected { background: $surface_hover; color: $text; border-left: 3px solid $accent; }

QFrame#NotificationBar { background: $surface; border: 1px solid $border; border-left: 4px solid $accent; border-radius: 8px; }
QFrame#NotificationBar[level="success"] { border-left-color: $success; }
QFrame#NotificationBar[level="warning"] { border-left-color: $warning; }
QFrame#NotificationBar[level="error"] { border-left-color: $danger; }

QStatusBar { background: $bg; border-top: 1px solid $border; }
QStatusBar::item { border: none; }
QLabel#StatusState[state="success"] { color: $success; font-weight: 600; }
QLabel#StatusState[state="error"] { color: $danger; font-weight: 600; }
QLabel#StatusState[state="busy"] { color: $accent; font-weight: 600; }

QSplitter::handle { background: transparent; }
QMenu { background: $surface; color: $text; border: 1px solid $border; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background: $surface_hover; }
QToolTip { background: $surface; color: $text; border: 1px solid $border; padding: 4px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 3px; min-height: 24px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 3px; min-width: 24px; }
QScrollBar::handle:hover { background: $text_muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
""")


def write_arrow_images(color: str, directory: Path) -> dict[str, str]:
    """QSS 自訂下拉與微調按鈕後 Qt 不再畫箭頭，依主題顏色產生 ▲▼ 圖檔供 QSS 引用

    檔名含顏色：Qt 會以路徑快取 QSS 圖片，切換主題時必須換新路徑才會重新載入
    """
    directory.mkdir(parents=True, exist_ok=True)
    width, height = 10 * _ARROW_SCALE, 6 * _ARROW_SCALE
    shapes = {
        "arrow_up": [QPointF(0, height), QPointF(width, height), QPointF(width / 2, 0)],
        "arrow_down": [QPointF(0, 0), QPointF(width, 0), QPointF(width / 2, height)],
    }
    paths = {}
    for name, points in shapes.items():
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF(points))
        painter.end()
        path = directory / f"{name}-{color.lstrip('#').lower()}.png"
        image.save(str(path))
        paths[name] = path.as_posix()
    return paths


def build_stylesheet(palette: ThemePalette, arrows: dict[str, str]) -> str:
    values = {f.name: getattr(palette, f.name) for f in fields(palette) if isinstance(getattr(palette, f.name), str)}
    return _QSS.substitute(values | arrows)


def build_qpalette(palette: ThemePalette) -> QPalette:
    """QSS 管不到的地方（右鍵選單底色、捲軸等）由 QPalette 補上"""
    role = QPalette.ColorRole
    qpalette = QPalette()
    for color_role, color in {
        role.Window: palette.bg,
        role.WindowText: palette.text,
        role.Base: palette.surface,
        role.AlternateBase: palette.surface_hover,
        role.Text: palette.text,
        role.Button: palette.surface,
        role.ButtonText: palette.text,
        role.Highlight: palette.accent,
        role.HighlightedText: palette.accent_text,
        role.ToolTipBase: palette.surface,
        role.ToolTipText: palette.text,
        role.PlaceholderText: palette.text_muted,
        role.Link: palette.accent,
    }.items():
        qpalette.setColor(color_role, QColor(color))
    for color_role in (role.WindowText, role.Text, role.ButtonText):
        qpalette.setColor(QPalette.ColorGroup.Disabled, color_role, QColor(palette.text_muted))
    return qpalette


def repolish(widget: QWidget) -> None:
    """動態屬性改變後重新套用 QSS"""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class ThemeManager(QObject):
    themeChanged = Signal(object)

    def __init__(self, app: QApplication, settings: QSettings, arrow_dir: Path = ARROW_DIR):
        super().__init__(app)
        self._app = app
        self._settings = settings
        self._arrow_dir = arrow_dir
        try:
            self._mode = ThemeMode(str(settings.value(SETTINGS_KEY, ThemeMode.SYSTEM.value)))
        except ValueError:
            self._mode = ThemeMode.SYSTEM
        self._palette = LIGHT
        self._in_set_mode = False
        self._hints = QGuiApplication.styleHints()
        self._hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def palette(self) -> ThemePalette:
        return self._palette

    def apply(self) -> None:
        """啟動時呼叫一次：設定 Fusion 樣式、字型並套用目前模式"""
        self._app.setStyle("Fusion")
        font = QFont()
        font.setFamilies(UI_FONT_FAMILIES)
        font.setPointSize(UI_FONT_SIZE)
        self._app.setFont(font)
        self._apply_scheme_override()
        self._refresh()

    def set_mode(self, mode: ThemeMode) -> None:
        if mode is self._mode:
            return
        self._mode = mode
        self._settings.setValue(SETTINGS_KEY, mode.value)
        self._settings.sync()
        self._in_set_mode = True
        try:
            self._apply_scheme_override()
        finally:
            self._in_set_mode = False
        self._refresh()

    def _apply_scheme_override(self) -> None:
        # 手動模式時覆寫系統配色，讓 Windows 標題列也跟著變
        if self._mode is ThemeMode.LIGHT:
            self._hints.setColorScheme(Qt.ColorScheme.Light)
        elif self._mode is ThemeMode.DARK:
            self._hints.setColorScheme(Qt.ColorScheme.Dark)
        else:
            self._hints.unsetColorScheme()

    def _on_system_scheme_changed(self, _scheme) -> None:
        if self._in_set_mode:
            return  # set_mode 會自行呼叫 _refresh，避免 unsetColorScheme() 觸發的訊號重複刷新
        if self._mode is ThemeMode.SYSTEM:
            self._refresh()

    def _effective_palette(self) -> ThemePalette:
        if self._mode is ThemeMode.LIGHT:
            return LIGHT
        if self._mode is ThemeMode.DARK:
            return DARK
        return DARK if self._hints.colorScheme() == Qt.ColorScheme.Dark else LIGHT

    def _refresh(self) -> None:
        palette = self._effective_palette()
        self._palette = palette
        self._app.setPalette(build_qpalette(palette))
        arrows = write_arrow_images(palette.text_muted, self._arrow_dir)
        self._app.setStyleSheet(build_stylesheet(palette, arrows))
        self.themeChanged.emit(palette)
