# -*- coding: utf-8 -*-
"""
外掛載入：執行期從外掛資料夾載入設定編輯器（pyqtgraph 不打包進主程式）

外掛資料夾結構：
    plugins/settings_editor/
    ├─ settings_editor.py
    └─ site-packages/      ← pyqtgraph、numpy（開發環境可省略，直接用 venv）
"""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from loguru import logger

PLUGIN_NAME = "settings_editor"
PLUGIN_API_VERSION = 1
_cache: dict[Path, ModuleType | None] = {}


def plugin_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parents[2]
    return base / "plugins" / PLUGIN_NAME


def load_settings_plugin(directory: Path | None = None) -> ModuleType | None:
    """載入外掛；找不到、載入失敗或 API 版本不符都回傳 None，不丟例外"""
    directory = Path(directory or plugin_dir()).resolve()
    if directory not in _cache:
        _cache[directory] = _load(directory)
    return _cache[directory]


def _load(directory: Path) -> ModuleType | None:
    source = directory / f"{PLUGIN_NAME}.py"
    if not source.is_file():
        logger.info("找不到設定編輯器外掛：{}", directory)
        return None
    site = directory / "site-packages"
    if site.is_dir() and str(site) not in sys.path:
        sys.path.insert(0, str(site))
    try:
        # 以檔案路徑載入、不佔用 sys.modules 的名稱，避免不同外掛資料夾互相干擾
        spec = importlib.util.spec_from_file_location(f"_ws_plugin_{PLUGIN_NAME}", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        logger.exception("設定編輯器外掛載入失敗：{}", directory)
        return None
    if getattr(module, "API_VERSION", None) != PLUGIN_API_VERSION:
        logger.warning("設定編輯器外掛 API 版本不符：{}", getattr(module, "API_VERSION", None))
        return None
    return module
