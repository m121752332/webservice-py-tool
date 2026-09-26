# -*- coding: utf-8 -*-
"""先清除再封裝（uv run clean-package）：清除 dist 後執行完整的 build + package 流程"""
from tasks import clean as clean_task
from tasks import package as package_task


def main() -> int:
    exit_code = clean_task.main()
    if exit_code != 0:
        return exit_code
    return package_task.main()


if __name__ == "__main__":
    raise SystemExit(main())
