# -*- coding: utf-8 -*-
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QPalette

from src.ui.theme import DARK, LIGHT, ThemeManager, ThemeMode, build_qpalette, build_stylesheet


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_stylesheet_substitutes_all_tokens(palette):
    qss = build_stylesheet(palette)
    assert "$" not in qss
    for color in (palette.bg, palette.surface, palette.accent, palette.accent_hover, palette.danger):
        assert color in qss


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
