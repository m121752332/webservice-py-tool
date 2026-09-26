# -*- coding: utf-8 -*-
import subprocess
import sys
import threading
from pathlib import Path

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
    from src.utils import globalvalues
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
    monkeypatch.setattr(globalvalues, "EXE_PATH", "")

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
