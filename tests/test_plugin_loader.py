# -*- coding: utf-8 -*-
import sys
from pathlib import Path

from src.ui.plugin_loader import PLUGIN_NAME, load_settings_plugin, plugin_dir

ROOT = Path(__file__).resolve().parents[1]


def make_plugin(tmp_path, body):
    directory = tmp_path / PLUGIN_NAME
    directory.mkdir()
    (directory / f"{PLUGIN_NAME}.py").write_text(body, encoding="utf-8")
    return directory


def test_plugin_dir_in_development_is_repo_plugins():
    assert plugin_dir() == ROOT / "plugins" / "settings_editor"


def test_plugin_dir_when_frozen_is_next_to_exe(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "WebService-Tool.exe"))
    assert plugin_dir() == tmp_path / "plugins" / "settings_editor"


def test_loads_repo_plugin(qapp):
    module = load_settings_plugin(ROOT / "plugins" / "settings_editor")
    assert module is not None
    assert module.API_VERSION == 1
    assert hasattr(module, "SettingsTree")


def test_result_is_cached(tmp_path):
    directory = make_plugin(tmp_path, "API_VERSION = 1\n")
    assert load_settings_plugin(directory) is load_settings_plugin(directory)


def test_missing_directory_returns_none(tmp_path):
    assert load_settings_plugin(tmp_path / "nope") is None


def test_import_error_returns_none(tmp_path):
    assert load_settings_plugin(make_plugin(tmp_path, "raise ImportError('boom')\n")) is None


def test_api_version_mismatch_returns_none(tmp_path):
    assert load_settings_plugin(make_plugin(tmp_path, "API_VERSION = 2\n")) is None


def test_site_packages_put_first_on_sys_path(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))
    directory = make_plugin(tmp_path, "import fake_plugin_dep\nAPI_VERSION = fake_plugin_dep.VERSION\n")
    site = directory / "site-packages"
    site.mkdir()
    (site / "fake_plugin_dep.py").write_text("VERSION = 1\n", encoding="utf-8")
    try:
        assert load_settings_plugin(directory) is not None
        assert sys.path[0] == str(site.resolve())
    finally:
        sys.modules.pop("fake_plugin_dep", None)
