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
VERSION_FILE = BUILD_DIR / "file_version_info.txt"


def _kill_running_exe() -> None:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)


def _hidden_imports() -> list[str]:
    """讀取 gen_host_imports.py 產生的清單，轉成 PyInstaller 的 --hidden-import 參數"""
    lines = HOST_IMPORTS.read_text(encoding="utf-8").splitlines()
    modules = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    return [f"--hidden-import={module}" for module in modules]


def main() -> int:
    _kill_running_exe()

    # file_version_info.txt 放在 build/ 底下（不進版控），但下面會整個清空 build 目錄，
    # 所以先讀進記憶體，清空後再寫回去，避免每次建置前都要重新執行 grab_version.py
    old_version_info = VERSION_FILE.read_bytes() if VERSION_FILE.exists() else None

    if BUILD_DIR.exists():
        print("移除舊的 build 目錄...")
        shutil.rmtree(BUILD_DIR)

    if old_version_info is not None:
        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        VERSION_FILE.write_bytes(old_version_info)
    else:
        print(
            f"[ERROR] {VERSION_FILE} 不存在，請先執行 "
            f"uv run python src/config/grab_version.py <來源 exe 路徑> {VERSION_FILE}"
        )
        return 1

    if not HOST_IMPORTS.exists():
        print(f"[ERROR] {HOST_IMPORTS} 不存在，請先執行 uv run python plugins/settings_editor/gen_host_imports.py")
        return 1

    print("建置 WebService-Tool...")
    result = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--clean", "--noconfirm", "--log-level=WARN",
            f"--icon={ROOT / 'assets' / 'app_icon.ico'}",
            "--add-data", f"{ROOT / 'assets'};assets",
            "--version-file", str(VERSION_FILE),
            "--specpath", str(BUILD_DIR),
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
