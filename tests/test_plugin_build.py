# -*- coding: utf-8 -*-
import importlib.util
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "settings_editor"


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", PLUGIN / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_host_imports_file_is_up_to_date():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, str(PLUGIN / "gen_host_imports.py"), "--check"],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_host_imports_cover_known_requirements():
    modules = (PLUGIN / "host_imports.txt").read_text(encoding="utf-8").splitlines()
    for name in ("platform", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSvg"):
        assert name in modules


def test_plugin_requirements_match_dev_dependencies():
    dev = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    for requirement in load("build_plugin").REQUIREMENTS:
        assert requirement in dev


def test_prune_removes_unneeded_files(tmp_path):
    site = tmp_path / "site-packages"
    for relative in ("pyqtgraph/examples/demo.py", "bin/f2py.exe", "numpy/__pycache__/x.pyc", "pyqtgraph/__init__.py"):
        target = site / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    load("build_plugin").prune(site)
    remaining = sorted(p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file())
    assert remaining == ["pyqtgraph/__init__.py"]
