# -*- coding: utf-8 -*-
"""
建置設定編輯器外掛：dist/plugins/settings_editor/（編輯器程式 + pyqtgraph + numpy）

必須以專案 .venv 的直譯器執行（uv run python ...），確保與主程式相同的 Python 版本與平台。
升級版本時同步修改 pyproject.toml 的 dev 群組，並重新產生 host_imports.txt。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TARGET = ROOT / "dist" / "plugins" / "settings_editor"
REQUIREMENTS = ("pyqtgraph==0.14.0", "numpy==2.5.3")
PRUNE_DIRS = ("pyqtgraph/examples", "bin")


def prune(site: Path) -> None:
    """刪除執行期用不到的內容，縮小外掛體積"""
    for relative in PRUNE_DIRS:
        shutil.rmtree(site / relative, ignore_errors=True)
    for cache in list(site.rglob("__pycache__")):
        shutil.rmtree(cache, ignore_errors=True)


def build(target: Path = TARGET) -> Path:
    if target.exists():
        shutil.rmtree(target)
    site = target / "site-packages"
    site.mkdir(parents=True)
    uv = os.environ.get("UV") or shutil.which("uv") or "uv"  # uv run 會設定 UV 環境變數
    subprocess.run(
        [uv, "pip", "install", "--quiet", "--target", str(site), "--python", sys.executable, *REQUIREMENTS],
        check=True,
    )
    shutil.copy2(HERE / "settings_editor.py", target / "settings_editor.py")
    prune(site)
    return target


if __name__ == "__main__":
    print(f"外掛已建置：{build()}")
