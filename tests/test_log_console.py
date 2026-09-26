# -*- coding: utf-8 -*-
import threading
from datetime import datetime, timezone

import pytest
from loguru import logger
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtGui import QGuiApplication, QTextCursor

from src.core.log_buffer import LEVELS, LogBuffer, LogEntry
from src.ui.log_console import (
    DEFAULT_HEIGHT, DEFAULT_LEVELS, ConsolePanel, ConsoleSettings, LogBridge, format_entry,
)
from src.ui.theme import DARK, LIGHT
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


# ---------- ConsolePanel ----------

@pytest.fixture
def make_panel(qapp, buffer):
    panels = []

    def make(levels=DEFAULT_LEVELS, palette=LIGHT):
        panel = ConsolePanel(buffer, palette, levels)
        panels.append(panel)
        return panel

    yield make
    for panel in panels:
        panel.detach()
        panel.deleteLater()


def flush(panel, text):
    """等待 QueuedConnection 把記錄送到面板"""
    wait_until(lambda: text in panel.visible_text())


def lines(panel):
    return panel.visible_text().splitlines()


def test_format_entry_aligns_columns_and_indents_continuation():
    entry = LogEntry(1, datetime(2026, 9, 26, 14, 2, 11, 532000, tzinfo=timezone.utc), "INFO", "第一行\n第二行")
    time_text, level_text, message = format_entry(entry)
    assert time_text == "14:02:11.532  "
    assert level_text == "INFO     "
    assert message == "第一行\n" + " " * 23 + "第二行"


def test_panel_shows_entries_logged_before_creation(make_panel):
    logger.info("啟動時的訊息")
    panel = make_panel()
    assert lines(panel)[-1].endswith("INFO     啟動時的訊息")


def test_panel_receives_new_entries_including_background_threads(make_panel):
    panel = make_panel()
    logger.info("主執行緒訊息")
    worker = threading.Thread(target=lambda: logger.success("背景完成"))
    worker.start()
    worker.join()
    flush(panel, "背景完成")
    assert "主執行緒訊息" in panel.visible_text()


def test_panel_does_not_duplicate_snapshot_entries(make_panel, buffer):
    logger.info("只出現一次")
    panel = make_panel()
    flush(panel, "只出現一次")
    for _ in range(5):
        QCoreApplication.processEvents()  # 讓排隊中的即時通知也送達
    assert panel.visible_text().count("只出現一次") == 1


def test_panel_has_seven_level_buttons_in_order(make_panel):
    panel = make_panel()
    assert list(panel.level_buttons) == list(LEVELS)
    checked = {level for level, button in panel.level_buttons.items() if button.isChecked()}
    assert checked == {"DEBUG", "INFO", "SUCCESS"}


def test_default_filter_hides_other_levels_but_counts_them(make_panel):
    panel = make_panel()
    for level in LEVELS:
        logger.log(level, "{} 訊息", level.lower())
    flush(panel, "success 訊息")
    text = panel.visible_text()
    assert "debug 訊息" in text and "info 訊息" in text and "success 訊息" in text
    assert "trace 訊息" not in text and "error 訊息" not in text and "critical 訊息" not in text
    wait_until(lambda: panel.level_buttons["CRITICAL"].text() == "CRITICAL 1")
    assert panel.level_buttons["TRACE"].text() == "TRACE 1"


def test_each_level_toggles_independently(make_panel):
    panel = make_panel(levels={"SUCCESS"})
    logger.info("一般")
    logger.success("成功")
    logger.critical("嚴重")
    flush(panel, "成功")
    assert "一般" not in panel.visible_text()
    emitted = []
    panel.levelsChanged.connect(emitted.append)
    panel.level_buttons["CRITICAL"].click()
    assert "嚴重" in panel.visible_text() and "一般" not in panel.visible_text()
    assert emitted == [frozenset({"SUCCESS", "CRITICAL"})]
    assert panel.levels() == {"SUCCESS", "CRITICAL"}


def test_set_levels_updates_buttons_without_emitting(make_panel):
    panel = make_panel()
    emitted = []
    panel.levelsChanged.connect(emitted.append)
    panel.set_levels({"ERROR"})
    assert panel.level_buttons["ERROR"].isChecked() and not panel.level_buttons["INFO"].isChecked()
    assert emitted == []


def test_search_is_case_insensitive_and_combines_with_levels(make_panel):
    panel = make_panel()
    logger.info("讀取 WSDL · URL=http://Prod/ws")
    logger.info("執行請求")
    logger.error("prod 連線失敗")
    flush(panel, "執行請求")
    panel.set_search("PROD")
    assert len(lines(panel)) == 1
    assert "http://Prod/ws" in panel.visible_text()
    panel.level_buttons["ERROR"].click()
    assert "prod 連線失敗" in panel.visible_text() and "執行請求" not in panel.visible_text()
    panel.set_search("")
    assert "執行請求" in panel.visible_text()


def test_search_matches_level_name(make_panel):
    panel = make_panel()
    logger.success("讀取完成")
    logger.info("一般")
    flush(panel, "一般")
    panel.set_search("success")
    assert "讀取完成" in panel.visible_text() and "一般" not in panel.visible_text()


def test_typing_in_search_applies_after_delay(make_panel):
    panel = make_panel()
    logger.info("甲")
    logger.info("乙")
    flush(panel, "乙")
    panel.search_edit.setText("甲")
    wait_until(lambda: "乙" not in panel.visible_text())


def test_clear_empties_panel_and_buffer(make_panel, buffer):
    panel = make_panel()
    logger.info("要被清掉")
    flush(panel, "要被清掉")
    panel.clear_button.click()
    assert panel.visible_text() == ""
    assert buffer.snapshot() == []
    assert panel.level_buttons["INFO"].text() == "INFO 0"


def test_copy_copies_only_visible_text(make_panel):
    panel = make_panel()
    logger.info("看得到")
    logger.error("看不到")
    flush(panel, "看得到")
    QGuiApplication.clipboard().setText("原本內容")
    panel.copy_button.click()
    copied = QGuiApplication.clipboard().text()
    assert "看得到" in copied and "看不到" not in copied


def test_copy_does_nothing_when_empty(make_panel):
    panel = make_panel()
    panel.set_levels(set())
    QGuiApplication.clipboard().setText("原本內容")
    panel.copy_button.click()
    assert QGuiApplication.clipboard().text() == "原本內容"


def test_close_button_emits_close_requested(make_panel):
    panel = make_panel()
    requested = []
    panel.closeRequested.connect(lambda: requested.append(True))
    panel.close_button.click()
    assert requested == [True]


def level_color(panel, line_no):
    """回傳第 line_no 行等級欄位的文字顏色（游標停在等級欄第一個字之後）"""
    block = panel.view.document().findBlockByNumber(line_no)
    cursor = QTextCursor(block)
    cursor.setPosition(block.position() + len("14:02:11.532  ") + 1)
    return cursor.charFormat().foreground().color().name().upper()


def test_level_column_uses_palette_color_and_follows_theme(make_panel):
    panel = make_panel(levels={"ERROR"})
    logger.error("失敗")
    flush(panel, "失敗")
    assert level_color(panel, 0) == LIGHT.level("ERROR").fg
    panel.set_palette(DARK)
    assert level_color(panel, 0) == DARK.level("ERROR").fg


def test_auto_scroll_only_when_at_bottom(make_panel):
    panel = make_panel()
    panel.resize(600, 150)
    panel.show()
    for i in range(80):
        logger.info("行 {}", i)
    flush(panel, "行 79")
    bar = panel.view.verticalScrollBar()
    assert bar.maximum() > 0 and bar.value() == bar.maximum()
    bar.setValue(0)
    logger.info("新的一行")
    flush(panel, "新的一行")
    assert bar.value() == 0


def test_panel_trims_to_capacity(make_panel, buffer, monkeypatch):
    import src.ui.log_console as module
    monkeypatch.setattr(module, "DEFAULT_CAPACITY", 10)
    monkeypatch.setattr(module, "TRIM_THRESHOLD", 11)
    panel = make_panel()
    for i in range(12):
        logger.info("第 {} 筆", i)
    flush(panel, "第 11 筆")
    assert len(lines(panel)) == 10
    assert "第 1 筆" not in panel.visible_text() and "第 2 筆" in panel.visible_text()
