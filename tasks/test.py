# -*- coding: utf-8 -*-
"""執行測試（uv run test）：轉呼叫 pytest，額外參數會原樣傳入"""
import sys

import pytest


def main() -> int:
    return pytest.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
