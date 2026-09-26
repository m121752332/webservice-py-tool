# -*- coding: utf-8 -*-
"""清除打包產物（uv run clean）：保留 dist 目錄本身，清空底下所有檔案與子目錄"""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE_NAME = "WebService-Tool.exe"
DIST_DIR = ROOT / "dist"


def _kill_running_exe() -> None:
    # dist 底下的 exe 若還在執行中會鎖住檔案，刪除前先關閉
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)


def main() -> int:
    _kill_running_exe()
    if not DIST_DIR.exists():
        print("dist 目錄不存在，無需清除。")
        return 0

    print(f"清空 {DIST_DIR} 底下的檔案...")
    for entry in DIST_DIR.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
