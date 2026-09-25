# -*- coding: utf-8 -*-
import subprocess
import sys
from pathlib import Path

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
