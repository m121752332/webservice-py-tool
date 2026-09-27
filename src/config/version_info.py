# -*- coding: utf-8 -*-
"""
產生 PyInstaller 打包用的 file_version_info.txt：內容直接取自 ws_tool.yaml 的 app 設定，
不再借用系統其他執行檔（例如 WWAHost.exe）的版本資源當範本，避免打包出來的 exe
「檔案內容」分頁顯示的是別人的產品名稱與描述
"""
import re

from src.config.app_settings import AppSettings

EXE_NAME = "WebService-Tool.exe"
COMPANY_NAME = "GameStudio"
_LANG_ID = 0x0404  # 繁體中文（台灣）
_CODEPAGE = 0x04B0  # Unicode
_LANG_CODEPAGE = f"{_LANG_ID:04X}{_CODEPAGE:04X}"
_VERSION_PART = re.compile(r"\d+")


def numeric_version(version: str) -> tuple[int, int, int, int]:
    """"v2.0.5" -> (2, 0, 5, 0)；抓不到四段數字的部分補 0，抓不到任何數字則全部是 0"""
    parts = [int(part) for part in _VERSION_PART.findall(version)[:4]]
    parts += [0] * (4 - len(parts))
    return tuple(parts)


def build_version_info_text(settings: AppSettings) -> str:
    """組出 PyInstaller --version-file 用的文字內容（VSVersionInfo 的 Python 原始碼表示）"""
    from PyInstaller.utils.win32 import versioninfo as vi

    version = numeric_version(settings.version)
    info = vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(filevers=version, prodvers=version),
        kids=[
            vi.StringFileInfo([
                vi.StringTable(_LANG_CODEPAGE, [
                    vi.StringStruct("CompanyName", COMPANY_NAME),
                    vi.StringStruct("FileDescription", settings.name),
                    vi.StringStruct("FileVersion", settings.version),
                    vi.StringStruct("InternalName", EXE_NAME),
                    vi.StringStruct("LegalCopyright", settings.copyright),
                    vi.StringStruct("OriginalFilename", EXE_NAME),
                    vi.StringStruct("ProductName", settings.name),
                    vi.StringStruct("ProductVersion", settings.version),
                ]),
            ]),
            vi.VarFileInfo([vi.VarStruct("Translation", [_LANG_ID, _CODEPAGE])]),
        ],
    )
    return str(info)
