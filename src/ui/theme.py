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

from src.core.log_buffer import LEVELS

SETTINGS_KEY = "ui/theme"
UI_FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Microsoft JhengHei UI"]
UI_FONT_SIZE = 10
ARROW_DIR = Path(tempfile.gettempdir()) / "webservice-tool-theme"
_ARROW_SCALE = 4  # 以 4 倍解析度繪製，縮小顯示時邊緣較平滑
# 彩色按鈕在淺色與深色主題下共用：(底色, 懸浮, 按下)
BUTTON_COLORS = {
    "green": ("#16A34A", "#22C55E", "#15803D"),
    "orange": ("#EA580C", "#F97316", "#C2410C"),
    "blue": ("#2563EB", "#3B82F6", "#1D4ED8"),
}


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
class LevelColor:
    fg: str  # 文字色：未勾選按鈕文字、記錄行的等級欄位
    fill: str  # 勾選按鈕的實心底色（淺色主題與 fg 相同；深色主題用較深色階）
    hover: str  # 勾選按鈕懸浮時的底色
    on: str  # 勾選按鈕（實心底）上的文字色


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
    levels: tuple[LevelColor, ...]  # 順序同 log_buffer.LEVELS；用 tuple 讓 ThemePalette 維持可 hash
    level_alphas: tuple[float, float, float, float]  # 未勾選淡底、未勾選懸浮淡底、未勾選外框、勾選外框的不透明度

    def level(self, name: str) -> LevelColor:
        return self.levels[LEVELS.index(name)]


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
    levels=(
        LevelColor(fg="#0E7490", fill="#0E7490", hover="#155E75", on="#FFFFFF"),  # TRACE
        LevelColor(fg="#64748B", fill="#64748B", hover="#475569", on="#FFFFFF"),  # DEBUG
        LevelColor(fg="#2563EB", fill="#2563EB", hover="#1D4ED8", on="#FFFFFF"),  # INFO
        LevelColor(fg="#15803D", fill="#15803D", hover="#166534", on="#FFFFFF"),  # SUCCESS
        LevelColor(fg="#B45309", fill="#B45309", hover="#92400E", on="#FFFFFF"),  # WARNING（#D97706 白字對比不足）
        LevelColor(fg="#DC2626", fill="#DC2626", hover="#B91C1C", on="#FFFFFF"),  # ERROR
        LevelColor(fg="#A21CAF", fill="#A21CAF", hover="#86198F", on="#FFFFFF"),  # CRITICAL（洋紅，與 ERROR 區隔）
    ),
    level_alphas=(0.12, 0.24, 0.35, 1.0),
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
    # 文字用亮的 400 色階；勾選底用深的 700 色階配近白字（亮色實心底在深色介面太刺眼），懸浮 800 色階
    levels=(
        LevelColor(fg="#22D3EE", fill="#0E7490", hover="#155E75", on="#ECFEFF"),  # TRACE
        LevelColor(fg="#94A3B8", fill="#475569", hover="#334155", on="#F8FAFC"),  # DEBUG
        LevelColor(fg="#60A5FA", fill="#1D4ED8", hover="#1E40AF", on="#EFF6FF"),  # INFO
        LevelColor(fg="#4ADE80", fill="#15803D", hover="#166534", on="#F0FDF4"),  # SUCCESS
        LevelColor(fg="#FBBF24", fill="#B45309", hover="#92400E", on="#FFFBEB"),  # WARNING
        LevelColor(fg="#F87171", fill="#B91C1C", hover="#991B1B", on="#FEF2F2"),  # ERROR
        LevelColor(fg="#E879F9", fill="#A21CAF", hover="#86198F", on="#FDF4FF"),  # CRITICAL
    ),
    level_alphas=(0.10, 0.20, 0.35, 0.55),
)

_QSS = Template("""
QWidget { color: $text; }
QMainWindow, QDialog { background: $bg; }
QFrame#Sidebar { background: $bg; border-right: 1px solid $border; }
QLabel#AppTitle { font-size: 13pt; font-weight: 600; padding: 0 4px 4px 4px; }
QLabel#PageTitle { font-size: 13pt; font-weight: 600; }
QLabel#Placeholder { color: $text_muted; font-size: 11pt; }
QLabel#SectionTitle { font-weight: 600; }
QLabel#Hint { color: $warning; }
QLabel#FieldCaption { font-size: 8pt; font-weight: 600; padding-left: 2px; }
QLabel#TimeoutLabel { color: $text; font-size: 11pt; font-weight: 600; }
QSpinBox#TimeoutSpin { font-size: 11pt; font-weight: 600; }
QLabel#ItemSubtitle, QLabel#StatusDetail { color: $text_muted; }
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
QPushButton[variant="green"], QPushButton[variant="orange"], QPushButton[variant="blue"] {
    color: #FFFFFF; font-weight: 600; border-radius: 6px;
}
QPushButton[variant="green"] { background: $green; border: 1px solid $green; }
QPushButton[variant="green"]:hover { background: $green_hover; border-color: $green_hover; }
QPushButton[variant="green"]:pressed { background: $green_pressed; border-color: $green_pressed; }
QPushButton[variant="orange"] { background: $orange; border: 1px solid $orange; }
QPushButton[variant="orange"]:hover { background: $orange_hover; border-color: $orange_hover; }
QPushButton[variant="orange"]:pressed { background: $orange_pressed; border-color: $orange_pressed; }
QPushButton[variant="blue"] { background: $blue; border: 1px solid $blue; padding: 4px 14px; }
QPushButton[variant="blue"]:hover { background: $blue_hover; border-color: $blue_hover; }
QPushButton[variant="blue"]:pressed { background: $blue_pressed; border-color: $blue_pressed; }
QPushButton[variant="green"]:disabled, QPushButton[variant="orange"]:disabled, QPushButton[variant="blue"]:disabled {
    background: $border; border-color: $border; color: $text_muted;
}
QPushButton[variant="footer"] {
    background: $surface; border: 1px solid $border; border-radius: 8px;
    padding: 6px 7px; font-size: 10.5pt; font-weight: 600;  /* 三顆 footer 按鈕要塞進側欄 236 px */
}
QPushButton[variant="footer"]:hover { background: $surface_hover; border-color: $accent; }
QPushButton[variant="footer"]:checked { background: $surface_hover; border-color: $accent; }
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

QWidget#ConsolePanel { background: $surface; border-top: 1px solid $border; }
QLabel#ConsoleTitle { font-weight: 600; }
QLineEdit#ConsoleSearch { padding: 3px 8px; }
QPlainTextEdit#ConsoleView {
    background: $surface; border: none; padding: 2px;
    font-family: "Cascadia Mono", "Consolas"; font-size: 9.5pt;
}
QPushButton[variant="level"] { border-radius: 8px; padding: 1px 8px; font-size: 8.5pt; font-weight: 600; }

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

# 每個等級 4 條規則；border-radius 必須小於按鈕高度一半（8px），否則 Qt 會畫成直角
_LEVEL_QSS = Template("""
QPushButton[variant="level"][level="$level"] { color: $fg; background: $tint; border: 1px solid $edge; }
QPushButton[variant="level"][level="$level"]:hover { background: $tint_hover; border-color: $fg; }
QPushButton[variant="level"][level="$level"]:checked { background: $fill; color: $on; border-color: $edge_on; }
QPushButton[variant="level"][level="$level"]:checked:hover { background: $hover; border-color: $fg; }
""")


def _rgba(color: str, alpha: float) -> str:
    qcolor = QColor(color)
    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {alpha})"


def _level_stylesheet(palette: ThemePalette) -> str:
    """主控台等級鈕：勾選為實心 fill，未勾選為 fg 淡底（半透明色由 fg 換算，不另外寫死）"""
    tint, tint_hover, edge, edge_on = palette.level_alphas
    return "".join(
        _LEVEL_QSS.substitute(
            level=name, fg=color.fg, fill=color.fill, hover=color.hover, on=color.on,
            tint=_rgba(color.fg, tint), tint_hover=_rgba(color.fg, tint_hover),
            edge=_rgba(color.fg, edge), edge_on=_rgba(color.fg, edge_on),
        )
        for name, color in zip(LEVELS, palette.levels)
    )


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
    buttons = {}
    for name, (base, hover, pressed) in BUTTON_COLORS.items():
        buttons |= {name: base, f"{name}_hover": hover, f"{name}_pressed": pressed}
    return _QSS.substitute(values | buttons | arrows) + _level_stylesheet(palette)


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
