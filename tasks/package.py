# -*- coding: utf-8 -*-
"""封裝發行版本（uv run package）：先執行 build，再把 dist 壓縮成 zip"""
import zipfile
from pathlib import Path

import yaml

from tasks import build as build_task

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
WS_TOOL_YAML = ROOT / "src" / "app_data" / "ws_tool.yaml"


def _app_version() -> str:
    data = yaml.safe_load(WS_TOOL_YAML.read_text(encoding="utf-8"))
    return data["app"]["version"]


def _archive_path() -> Path:
    return ROOT / f"WebService-Tool-{_app_version()}.zip"


def main() -> int:
    exit_code = build_task.main()
    if exit_code != 0:
        return exit_code

    archive_path = _archive_path()
    if archive_path.exists():
        archive_path.unlink()

    print(f"壓縮 {DIST_DIR} -> {archive_path} ...")
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in DIST_DIR.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(DIST_DIR))

    print(f"封裝完成：{archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
