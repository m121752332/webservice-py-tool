# -*- coding: utf-8 -*-
import threading

import pytest
from loguru import logger
from PySide6.QtCore import QSettings

from src.core.log_buffer import LogBuffer
from src.ui.log_console import DEFAULT_HEIGHT, DEFAULT_LEVELS, ConsoleSettings, LogBridge
from tests.helpers import wait_until


@pytest.fixture
def ini(tmp_path):
    return tmp_path / "settings.ini"


@pytest.fixture
def buffer():
    buffer = LogBuffer()
    handler_id = buffer.attach()
    yield buffer
    logger.remove(handler_id)


def qsettings(path):
    return QSettings(str(path), QSettings.Format.IniFormat)


# ---------- ConsoleSettings ----------

def test_settings_defaults_when_keys_missing(ini):
    settings = ConsoleSettings(qsettings(ini))
    assert settings.visible() is False
    assert settings.height() == DEFAULT_HEIGHT
    assert settings.levels() == DEFAULT_LEVELS == {"DEBUG", "INFO", "SUCCESS"}


def test_settings_round_trip(ini):
    ConsoleSettings(qsettings(ini)).set_visible(True)
    ConsoleSettings(qsettings(ini)).set_height(300)
    ConsoleSettings(qsettings(ini)).set_levels({"CRITICAL", "DEBUG"})
    settings = ConsoleSettings(qsettings(ini))
    assert settings.visible() is True
    assert settings.height() == 300
    assert settings.levels() == {"DEBUG", "CRITICAL"}


def test_settings_levels_written_in_severity_order(ini):
    ConsoleSettings(qsettings(ini)).set_levels({"ERROR", "TRACE", "INFO"})
    assert qsettings(ini).value("console/levels") == "trace,info,error"


def test_settings_reads_hand_edited_levels(ini):
    # 手動編輯、未加引號的逗號清單，QSettings 會讀成 list
    ini.write_text("[console]\nlevels=debug,info,success,critical\n", encoding="utf-8")
    assert ConsoleSettings(qsettings(ini)).levels() == {"DEBUG", "INFO", "SUCCESS", "CRITICAL"}


def test_settings_single_hand_edited_level(ini):
    ini.write_text("[console]\nlevels=error\n", encoding="utf-8")
    assert ConsoleSettings(qsettings(ini)).levels() == {"ERROR"}


def test_settings_empty_levels_means_all_hidden(ini):
    ConsoleSettings(qsettings(ini)).set_levels(set())
    assert ConsoleSettings(qsettings(ini)).levels() == frozenset()


def test_settings_ignores_unknown_levels_and_spaces(ini):
    ini.write_text("[console]\nlevels=\" Debug , bogus,ERROR \"\n", encoding="utf-8")
    assert ConsoleSettings(qsettings(ini)).levels() == {"DEBUG", "ERROR"}


@pytest.mark.parametrize("raw", ["abc", "5", "99999"])
def test_settings_invalid_height_falls_back(ini, raw):
    ini.write_text(f"[console]\nheight={raw}\n", encoding="utf-8")
    assert ConsoleSettings(qsettings(ini)).height() == DEFAULT_HEIGHT


def test_settings_without_qsettings_keeps_values_in_memory():
    settings = ConsoleSettings()
    assert settings.levels() == DEFAULT_LEVELS
    settings.set_visible(True)
    settings.set_levels({"ERROR"})
    assert settings.visible() is True
    assert settings.levels() == {"ERROR"}


# ---------- LogBridge ----------

def test_bridge_emits_entries_from_any_thread(qapp, buffer):
    bridge = LogBridge(buffer)
    received = []
    bridge.entryAdded.connect(lambda entry: received.append(entry.message))
    logger.info("主執行緒")
    worker = threading.Thread(target=lambda: logger.warning("背景執行緒"))
    worker.start()
    worker.join()
    wait_until(lambda: "背景執行緒" in received)
    assert received == ["主執行緒", "背景執行緒"]


def test_bridge_detach_stops_emitting(qapp, buffer):
    bridge = LogBridge(buffer)
    received = []
    bridge.entryAdded.connect(lambda entry: received.append(entry.message))
    bridge.detach()
    logger.info("不應收到")
    assert received == []
