# -*- coding: utf-8 -*-
"""
產生 host_imports.txt：主程式打包時需額外包含、供外掛使用的模組

PyInstaller 只打包主程式靜態可見的模組；外掛（pyqtgraph、numpy）在執行期才載入，
它們用到的標準庫與 PySide6 子模組必須預先打包進主程式。
升級 pyqtgraph 或 numpy 後重新執行：uv run python plugins/settings_editor/gen_host_imports.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "host_imports.txt"
HEADER = "# 由 gen_host_imports.py 產生，請勿手動編輯；升級 pyqtgraph／numpy 後重新產生\n"
EXCLUDED_PACKAGES = ("encodings",)  # PyInstaller 一律完整打包；且依主控台編碼而異，排除以保持結果穩定
SAMPLE_FIELDS = [
    {"key": "app", "label": "app", "kind": "group", "value": None, "limits": None},
    {"key": "app.name", "label": "名稱", "kind": "str", "value": "x", "limits": None},
    {"key": "app.timeout", "label": "逾時", "kind": "int", "value": 30, "limits": (5, 120)},
    {"key": "app.ratio", "label": "比例", "kind": "float", "value": 1.5, "limits": None},
    {"key": "app.enabled", "label": "啟用", "kind": "bool", "value": True, "limits": None},
    {"key": "app.level", "label": "等級", "kind": "list", "value": "info", "limits": ("info", "debug")},
]
SAMPLE_COLORS = {
    "bg": "#000000", "surface": "#111111", "surface_hover": "#222222",
    "border": "#333333", "text": "#FFFFFF", "text_muted": "#AAAAAA",
}


def _wanted(name: str) -> bool:
    top = name.split(".")[0]
    if top in EXCLUDED_PACKAGES:
        return False
    return (top in sys.stdlib_module_names and not top.startswith("_")) or name.startswith("PySide6.")


def collect() -> list[str]:
    """實際建立並操作 SettingsTree，回傳過程中載入的標準庫與 PySide6 模組"""
    sys.path.insert(0, str(HERE))
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    import settings_editor

    tree = settings_editor.SettingsTree()
    tree.load(SAMPLE_FIELDS)
    tree.set_palette(SAMPLE_COLORS)
    tree.show()
    app.processEvents()
    return sorted(name for name in sys.modules if _wanted(name))


def render(modules: list[str]) -> str:
    return HEADER + "".join(f"{name}\n" for name in modules)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    content = render(collect())
    if "--check" in argv:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print("host_imports.txt 已過期，請執行：uv run python plugins/settings_editor/gen_host_imports.py")
            return 1
        return 0
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"已寫入 {OUTPUT}（{content.count(chr(10)) - 1} 個模組）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
