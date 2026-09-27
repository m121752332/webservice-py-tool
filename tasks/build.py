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
GRAB_VERSION_SCRIPT = ROOT / "src" / "config" / "grab_version.py"
# 純粹借這個系統內建 exe 的 VERSIONINFO 資源結構當範本，跟本 App 的版本內容無關；
# Windows 10/11 都內建，不需要額外準備檔案
VERSION_TEMPLATE_EXE = r"C:\Windows\System32\WWAHost.exe"


def _kill_running_exe() -> None:
    subprocess.run(["taskkill", "/f", "/im", EXE_NAME], capture_output=True)


def _generate_version_info(template_exe: str, out_file: Path) -> bool:
    """執行 grab_version.py，把 template_exe 的版本資源寫成 PyInstaller 用的 out_file"""
    print(f"產生版本資訊 {out_file}...")
    result = subprocess.run(
        [sys.executable, str(GRAB_VERSION_SCRIPT), template_exe, str(out_file)],
        cwd=ROOT, capture_output=True,
    )
    if result.returncode != 0:
        # Windows API 的錯誤訊息會用系統的 locale 編碼（例如 cp950），不是固定 UTF-8，嚴格解碼會炸掉
        print((result.stderr or result.stdout).decode(errors="replace"))
    return result.returncode == 0


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
    BUILD_DIR.mkdir(parents=True)

    if not _generate_version_info(VERSION_TEMPLATE_EXE, VERSION_FILE):
        print(f"[ERROR] 版本資訊產生失敗，請確認 {VERSION_TEMPLATE_EXE} 存在。")
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
