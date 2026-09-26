# -*- coding: utf-8 -*-
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from loguru import logger
from PySide6.QtWidgets import QMessageBox

ROOT = Path(__file__).resolve().parents[1]


def test_entry_point_imports_when_run_as_script():
    """用 --file 方式執行（PyQtInspect、IDE）時，src 套件必須能被匯入"""
    # 移除目前目錄，模擬 IDE / PyQtInspect 以腳本方式執行時 sys.path 不含專案根目錄的情況
    code = (
        "import os, runpy, sys; "
        "sys.path[:] = [p for p in sys.path if p not in ('', os.getcwd())]; "
        "ns = runpy.run_path('src/ws_tool.py', run_name='not_main'); "
        "print(callable(ns.get('main')))"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


def test_no_wx_imports_left():
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "src").rglob("*.py")
        if "import wx" in path.read_text(encoding="utf-8") or "from wx" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_resolve_app_dirs_uses_config_file_location_as_base(tmp_path, monkeypatch):
    """從 repo 根目錄啟動時，log 目錄與連線資料目錄必須共用同一個基準目錄（F1）：
    否則 log 目錄會先被建立在 <root>/app_data/logs，接著連線資料目錄又被找成
    <root>/app_data，導致使用者放在 src/app_data 底下的 connections.profile 被忽略。
    """
    from src.config.web_service_config import WebServiceConfig
    from src.utils import global_values
    from src.ws_tool import resolve_app_dirs

    app_data = tmp_path / "src" / "app_data"
    app_data.mkdir(parents=True)
    (app_data / "ws_tool.yaml").write_text(
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
        "  connection:\n"
        "    path: \"app_data\"\n"
        "    profile: \"connections.profile\"\n",
        encoding="utf-8",
    )
    (app_data / "connections.profile").write_text('{"connections": []}', encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(global_values, "EXE_PATH", "")

    config = WebServiceConfig()
    assert config.config_path == app_data / "ws_tool.yaml"
    log_dir, data_dir = resolve_app_dirs(config)

    assert data_dir == app_data
    assert not (tmp_path / "app_data").exists()
    assert not log_dir.exists()  # main() 才會 mkdir；resolve_app_dirs 本身不應有副作用


def test_worker_thread_exception_is_logged_without_dialog(qapp, monkeypatch):
    """背景執行緒的未預期例外只能記錄，不可呼叫 QMessageBox（非 GUI 執行緒）"""
    from src.ws_tool import _install_excepthook

    original_sys_hook = sys.excepthook
    original_thread_hook = threading.excepthook
    calls = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: calls.append(a))
    logged = []
    sink_id = logger.add(lambda msg: logged.append(str(msg)), level="ERROR")
    try:
        _install_excepthook()

        def boom():
            raise RuntimeError("worker-boom")

        thread = threading.Thread(target=boom)
        thread.start()
        thread.join(timeout=5)
    finally:
        logger.remove(sink_id)
        sys.excepthook = original_sys_hook
        threading.excepthook = original_thread_hook

    assert calls == []
    assert any("worker-boom" in line for line in logged)


def test_setup_logging_buffer_gets_all_levels_but_run_log_follows_config(tmp_path):
    from src.ws_tool import setup_logging

    config = SimpleNamespace(app_log_retention="1 day", app_log_level="info", app_log_levels="")
    buffer, handler_ids = setup_logging(tmp_path / "logs", config)
    try:
        logger.trace("追蹤訊息")
        logger.debug("除錯訊息")
        logger.info("一般訊息")
    finally:
        for handler_id in handler_ids:
            logger.remove(handler_id)
    assert [e.message for e in buffer.snapshot()][-3:] == ["追蹤訊息", "除錯訊息", "一般訊息"]
    text = (tmp_path / "logs" / "run.log").read_text(encoding="utf-8")
    assert "一般訊息" in text
    assert "除錯訊息" not in text and "追蹤訊息" not in text


def test_setup_logging_splits_by_levels(tmp_path):
    from src.ws_tool import setup_logging

    config = SimpleNamespace(app_log_retention="10 days", app_log_level="info", app_log_levels="info, other, bogus")
    _buffer, handler_ids = setup_logging(tmp_path, config)
    try:
        logger.debug("除錯訊息")
        logger.info("一般訊息")
        logger.warning("警告訊息")
        logger.error("錯誤訊息")
    finally:
        for handler_id in handler_ids:
            logger.remove(handler_id)
    run = (tmp_path / "run.log").read_text(encoding="utf-8")
    info = (tmp_path / "ws_info.log").read_text(encoding="utf-8")
    other = (tmp_path / "ws_other.log").read_text(encoding="utf-8")
    assert "一般訊息" in run and "錯誤訊息" in run and "除錯訊息" not in run
    assert "一般訊息" in info and "警告訊息" not in info and "錯誤訊息" not in info
    assert "警告訊息" in other and "bogus" in other and "一般訊息" not in other and "錯誤訊息" not in other
    assert not (tmp_path / "ws_debug.log").exists() and not (tmp_path / "ws_error.log").exists()
    assert "| INFO     |" in info  # 與舊版 run.log 相同的欄位格式


def test_setup_logging_split_ignores_run_level(tmp_path):
    from src.ws_tool import setup_logging

    config = SimpleNamespace(app_log_retention="10 days", app_log_level="error", app_log_levels="debug")
    _buffer, handler_ids = setup_logging(tmp_path, config)
    try:
        logger.debug("除錯訊息")
    finally:
        for handler_id in handler_ids:
            logger.remove(handler_id)
    assert "除錯訊息" in (tmp_path / "ws_debug.log").read_text(encoding="utf-8")
    assert "除錯訊息" not in (tmp_path / "run.log").read_text(encoding="utf-8")


def test_setup_logging_survives_unwritable_touch(tmp_path, monkeypatch):
    """啟動時的 touch() 若因目錄不可寫入而丟例外，不可讓 setup_logging 直接往外丟
    （此時 excepthook 尚未安裝，例外會讓打包後的 exe 直接閃退）"""
    from pathlib import Path

    from src.ws_tool import setup_logging

    def boom(self, *args, **kwargs):
        raise OSError("拒絕存取")

    monkeypatch.setattr(Path, "touch", boom)
    config = SimpleNamespace(app_log_retention="10 days", app_log_level="info", app_log_levels="info")
    buffer, handler_ids = setup_logging(tmp_path, config)
    for handler_id in handler_ids:
        logger.remove(handler_id)
    assert buffer is not None


def test_create_recorder_follows_config(tmp_path):
    from src.core.xml_log import XmlLogWriter
    from src.ws_tool import create_recorder

    off = SimpleNamespace(app_xml_enabled=False, app_xml_content="params", app_xml_retention=30)
    assert create_recorder(tmp_path, off) is None
    on = SimpleNamespace(app_xml_enabled=True, app_xml_content="BOTH", app_xml_retention="7 days")
    recorder = create_recorder(tmp_path, on)
    assert isinstance(recorder, XmlLogWriter) and recorder.content == "both"
    recorder.close()
