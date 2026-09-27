# -*- coding: utf-8 -*-
"""測試 tasks/build.py 的版本資訊產生流程（不執行實際的 PyInstaller 打包，太耗時）"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("build_under_test", ROOT / "tasks" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_write_version_info_reads_repo_ws_tool_yaml(tmp_path):
    """用 repo 內實際的 ws_tool.yaml，確認產生的內容是本專案的名稱／版本，不是借來的範本"""
    build = load()
    out_file = tmp_path / "file_version_info.txt"
    build._write_version_info(out_file)
    content = out_file.read_text(encoding="utf-8")
    assert "TIPTOP WebService Tool" in content
    assert "WWAHost" not in content
