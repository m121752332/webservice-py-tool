# -*- coding: utf-8 -*-
"""執行測試（uv run test）：轉呼叫 pytest，額外參數會原樣傳入，並產生可檢視的 HTML 報告"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "reports" / "test-report.html"


def main() -> int:
    args = sys.argv[1:]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    has_html_opt = any(arg == "--html" or arg.startswith("--html=") for arg in args)
    if not has_html_opt:
        args = [*args, f"--html={REPORT_PATH}", "--self-contained-html"]
    exit_code = pytest.main(args)
    if not has_html_opt:
        print(f"測試報告：{REPORT_PATH}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
