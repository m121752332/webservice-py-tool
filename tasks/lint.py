# -*- coding: utf-8 -*-
"""語法／風格檢查（uv run lint）：對 src、tests、plugins 執行 ruff check"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ("src", "tests", "plugins")


def main() -> int:
    result = subprocess.run([sys.executable, "-m", "ruff", "check", *TARGETS], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
