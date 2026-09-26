# -*- coding: utf-8 -*-
from src.config.web_service_config import WebServiceConfig
from src.utils import global_values

BASE = (
    "app:\n"
    "  name: \"Test Tool\"\n"
    "  version: \"v0\"\n"
    "  copyright: \"c\"\n"
    "  img: \"assets/app_icon.ico\"\n"
    "  timeout: 120\n"
    "  log:\n"
    "    path: \"app_data/logs\"\n"
    "    level: info\n"
    "    retention: \"10 days\"\n"
    "{extra}"
    "  connection:\n"
    "    path: \"app_data\"\n"
    "    profile: \"connections.profile\"\n"
)


def make_config(tmp_path, monkeypatch, extra=""):
    app_data = tmp_path / "src" / "app_data"
    app_data.mkdir(parents=True)
    (app_data / "ws_tool.yaml").write_text(BASE.format(extra=extra), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(global_values, "EXE_PATH", "")
    return WebServiceConfig()


def test_old_config_without_new_fields_uses_defaults(tmp_path, monkeypatch):
    config = make_config(tmp_path, monkeypatch)
    assert config.app_log_level == "info"
    assert config.app_log_levels == "info, debug, error, other"
    assert (config.app_xml_enabled, config.app_xml_content, config.app_xml_retention) == (True, "params", 30)


def test_new_fields_are_read(tmp_path, monkeypatch):
    extra = (
        "    levels: \"error\"\n"
        "    xml:\n"
        "      enabled: false\n"
        "      content: both\n"
        "      retention: 7\n"
    )
    config = make_config(tmp_path, monkeypatch, extra)
    assert config.app_log_levels == "error"
    assert (config.app_xml_enabled, config.app_xml_content, config.app_xml_retention) == (False, "both", 7)


def test_repo_config_has_new_fields():
    config = WebServiceConfig()
    assert config.app_log_levels == "info, debug, error, other"
    assert (config.app_xml_enabled, config.app_xml_content, config.app_xml_retention) == (True, "params", 30)
