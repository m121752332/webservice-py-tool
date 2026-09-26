# -*- coding: utf-8 -*-
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QImage, QPalette

from src.core.log_buffer import LEVELS
from src.ui.theme import (
    DARK, LIGHT, ThemeManager, ThemeMode, build_qpalette, build_stylesheet, write_arrow_images,
)


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_stylesheet_substitutes_all_tokens(palette, tmp_path):
    arrows = write_arrow_images(palette.text_muted, tmp_path)
    qss = build_stylesheet(palette, arrows)
    assert "$" not in qss
    for color in (palette.bg, palette.surface, palette.accent, palette.accent_hover, palette.danger):
        assert color in qss
    assert arrows["arrow_up"] in qss and arrows["arrow_down"] in qss


def test_arrow_images_are_drawn_in_palette_color(qapp, tmp_path):
    light = write_arrow_images(LIGHT.text_muted, tmp_path)
    dark = write_arrow_images(DARK.text_muted, tmp_path)
    assert set(light) == {"arrow_up", "arrow_down"}
    assert light["arrow_down"] != dark["arrow_down"]  # 檔名含顏色，避免 Qt 快取到舊主題的圖
    down = QImage(light["arrow_down"])
    up = QImage(dark["arrow_up"])
    assert down.pixelColor(down.width() // 2, 2).name().upper() == LIGHT.text_muted
    assert up.pixelColor(up.width() // 2, up.height() - 3).name().upper() == DARK.text_muted
    assert down.pixelColor(1, down.height() - 2).alpha() == 0  # 三角形以外透明


def test_manager_stylesheet_references_arrow_images(qapp, settings, tmp_path):
    manager = ThemeManager(qapp, settings, arrow_dir=tmp_path / "arrows")
    manager.apply()
    manager.set_mode(ThemeMode.DARK)
    expected = write_arrow_images(DARK.text_muted, tmp_path / "arrows")
    assert expected["arrow_down"] in qapp.styleSheet()
    assert expected["arrow_up"] in qapp.styleSheet()


def test_qpalette_uses_palette_colors():
    pal = build_qpalette(DARK)
    assert pal.color(QPalette.ColorRole.Window).name().upper() == DARK.bg
    assert pal.color(QPalette.ColorRole.Base).name().upper() == DARK.surface
    assert pal.color(QPalette.ColorRole.Highlight).name().upper() == DARK.accent
    assert pal.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text).name().upper() == DARK.text_muted


def test_defaults_to_system_mode(qapp, settings):
    assert ThemeManager(qapp, settings).mode is ThemeMode.SYSTEM


def test_system_mode_with_unknown_scheme_uses_light(qapp, settings, monkeypatch):
    # offscreen 平台回報 ColorScheme.Unknown，應視為淺色
    styles = []
    monkeypatch.setattr(qapp, "setStyle", styles.append)
    manager = ThemeManager(qapp, settings)
    manager.apply()
    assert manager.palette == LIGHT
    assert styles == ["Fusion"]


def test_set_mode_applies_persists_and_emits(qapp, settings):
    manager = ThemeManager(qapp, settings)
    manager.apply()
    received = []
    manager.themeChanged.connect(received.append)
    manager.set_mode(ThemeMode.DARK)
    assert manager.mode is ThemeMode.DARK
    assert manager.palette == DARK
    assert received == [DARK]
    assert DARK.bg in qapp.styleSheet()
    assert settings.value("ui/theme") == "dark"
    assert ThemeManager(qapp, settings).mode is ThemeMode.DARK


def test_set_same_mode_does_not_emit(qapp, settings):
    manager = ThemeManager(qapp, settings)
    manager.apply()
    received = []
    manager.themeChanged.connect(received.append)
    manager.set_mode(ThemeMode.SYSTEM)
    assert received == []


def test_switch_back_to_light(qapp, settings):
    manager = ThemeManager(qapp, settings)
    manager.apply()
    manager.set_mode(ThemeMode.DARK)
    manager.set_mode(ThemeMode.LIGHT)
    assert manager.palette == LIGHT
    assert LIGHT.bg in qapp.styleSheet()


def test_dark_to_system_emits_theme_changed_once(qapp, settings):
    # unsetColorScheme() 可能觸發 colorSchemeChanged，set_mode 應在切換期間抑制重複刷新
    manager = ThemeManager(qapp, settings)
    manager.apply()
    manager.set_mode(ThemeMode.DARK)
    received = []
    manager.themeChanged.connect(received.append)
    manager.set_mode(ThemeMode.SYSTEM)
    assert len(received) == 1


def test_invalid_stored_mode_falls_back_to_system(qapp, settings):
    settings.setValue("ui/theme", "purple")
    assert ThemeManager(qapp, settings).mode is ThemeMode.SYSTEM


def _luminance(color: str) -> float:
    channels = [int(color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_level_colors_cover_all_levels_and_are_distinct(palette):
    assert len(palette.levels) == len(LEVELS)
    assert len({color.fg for color in palette.levels}) == len(LEVELS)
    assert palette.level("ERROR") is palette.levels[LEVELS.index("ERROR")]


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_level_colors_meet_contrast(palette):
    for name, color in zip(LEVELS, palette.levels):
        assert _contrast(color.fg, palette.surface) >= 4.5, name
        assert _contrast(color.on, color.fill) >= 4.5, name
        assert _contrast(color.on, color.hover) >= 4.5, name


def test_light_fill_equals_text_color_dark_fill_is_deeper():
    assert all(color.fill == color.fg for color in LIGHT.levels)
    # 深色主題勾選底用深色階配淺字，避免亮色實心底刺眼
    assert all(_luminance(color.fill) < _luminance(color.fg) for color in DARK.levels)
    assert all(_luminance(color.on) > 0.8 for color in DARK.levels)


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_stylesheet_has_rules_for_every_level(palette, tmp_path):
    qss = build_stylesheet(palette, write_arrow_images(palette.text_muted, tmp_path))
    for name, color in zip(LEVELS, palette.levels):
        selector = f'QPushButton[variant="level"][level="{name}"]'
        assert f"{selector}:checked {{ background: {color.fill}; color: {color.on};" in qss
        assert f"{selector}:checked:hover {{ background: {color.hover};" in qss
        assert f"{selector} {{ color: {color.fg}; background: rgba(" in qss


def test_palettes_stay_hashable():
    hash(LIGHT)
    hash(DARK)
