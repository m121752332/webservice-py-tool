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


def test_version_template_exe_exists_on_windows():
    """建置流程依賴這個系統內建 exe 當版本資源範本，路徑打錯會讓所有人建置失敗"""
    build = load()
    assert Path(build.VERSION_TEMPLATE_EXE).is_file()


def test_generate_version_info_writes_file_from_template(tmp_path):
    build = load()
    version_file = tmp_path / "file_version_info.txt"
    assert build._generate_version_info(build.VERSION_TEMPLATE_EXE, version_file) is True
    content = version_file.read_text(encoding="utf-8")
    assert "VSVersionInfo" in content and "StringFileInfo" in content


def test_generate_version_info_fails_gracefully_for_missing_template(tmp_path):
    build = load()
    version_file = tmp_path / "file_version_info.txt"
    assert build._generate_version_info(str(tmp_path / "no-such.exe"), version_file) is False
    assert not version_file.exists()
