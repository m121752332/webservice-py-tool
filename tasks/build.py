# -*- coding: utf-8 -*-
"""建置 WebService-Tool.exe 與設定編輯器外掛（uv run build，取代 build.bat）"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE_NAME = "WebService-Tool.exe"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
HOST_IMPORTS = ROOT / "plugins" / "settings_editor" / "host_imports.txt"
PLUGIN_BUILD_SCRIPT = ROOT / "plugins" / "settings_editor" / "build_plugin.py"
WS_TOOL_YAML_SRC = ROOT / "src" / "app_data" / "ws_tool.yaml"
WS_TOOL_YAML_DEST = DIST_DIR / "app_data" / "ws_tool.yaml"


def _kill_running_exe() -> None:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)


def _hidden_imports() -> list[str]:
    """讀取 gen_host_imports.py 產生的清單，轉成 PyInstaller 的 --hidden-import 參數"""
    lines = HOST_IMPORTS.read_text(encoding="utf-8").splitlines()
    modules = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    return [f"--hidden-import={module}" for module in modules]


def main() -> int:
    _kill_running_exe()

    if BUILD_DIR.exists():
        print("移除舊的 build 目錄...")
        shutil.rmtree(BUILD_DIR)

    if not HOST_IMPORTS.exists():
        print(f"[ERROR] {HOST_IMPORTS} 不存在，請先執行 uv run python plugins/settings_editor/gen_host_imports.py")
        return 1

    print("建置 WebService-Tool...")
    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--clean", "--noconfirm", "--log-level=WARN",
            "--icon=assets/app_icon.ico",
            "--add-data", "assets;assets",
            "--version-file", "src/config/file_version_info.txt",
            "-F", "-w", "-n", "WebService-Tool",
            *_hidden_imports(),
            "src/ws_tool.py",
        ],
        cwd=ROOT,
    )
    if result.returncode != 0:
        print("[ERROR] 主程式建置失敗。")
        return result.returncode

    print("建置設定編輯器外掛...")
    result = subprocess.run([sys.executable, str(PLUGIN_BUILD_SCRIPT)], cwd=ROOT)
    if result.returncode != 0:
        print("[ERROR] 外掛建置失敗。")
        return result.returncode

    print("複製 app_data/ws_tool.yaml 到 dist（一律覆寫，與 repo 保持一致）...")
    WS_TOOL_YAML_DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WS_TOOL_YAML_SRC, WS_TOOL_YAML_DEST)

    print(f"建置完成：{DIST_DIR / EXE_NAME} + dist/plugins/settings_editor + {WS_TOOL_YAML_DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
