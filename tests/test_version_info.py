# -*- coding: utf-8 -*-
from src.config.app_settings import AppSettings
from src.config.version_info import EXE_NAME, build_version_info_text, numeric_version

SETTINGS = AppSettings(
    name="TIPTOP WebService Tool", version="v2.0.5",
    copyright="Copyright 2026 GameStudio. All rights reserved.", img="assets/app_icon.ico", timeout=120,
)


def test_numeric_version_parses_leading_v_and_pads_to_four_parts():
    assert numeric_version("v2.0.5") == (2, 0, 5, 0)
    assert numeric_version("1.2.3.4") == (1, 2, 3, 4)


def test_numeric_version_falls_back_to_zero_for_unparsable_text():
    assert numeric_version("unknown") == (0, 0, 0, 0)


def test_version_info_text_uses_app_metadata_not_a_borrowed_exe():
    text = build_version_info_text(SETTINGS)
    assert "VSVersionInfo(" in text
    for expected in (
        "StringStruct('ProductName', 'TIPTOP WebService Tool')",
        "StringStruct('FileDescription', 'TIPTOP WebService Tool')",
        "StringStruct('FileVersion', 'v2.0.5')",
        "StringStruct('ProductVersion', 'v2.0.5')",
        "StringStruct('LegalCopyright', 'Copyright 2026 GameStudio. All rights reserved.')",
        f"StringStruct('OriginalFilename', '{EXE_NAME}')",
        f"StringStruct('InternalName', '{EXE_NAME}')",
    ):
        assert expected in text
    # 不該再出現和本專案無關的來源檔名／描述（曾經誤用系統元件當範本）
    assert "WWAHost" not in text
    assert "Microsoft WWA Host" not in text


def test_version_info_text_is_loadable_by_pyinstaller_and_round_trips(tmp_path):
    from PyInstaller.utils.win32 import versioninfo

    path = tmp_path / "file_version_info.txt"
    path.write_text(build_version_info_text(SETTINGS), encoding="utf-8")
    info = versioninfo.load_version_info_from_text_file(str(path))
    strings = {s.name: s.val for s in info.kids[0].kids[0].kids}
    assert strings["ProductName"] == SETTINGS.name
    assert strings["FileVersion"] == SETTINGS.version
    assert strings["CompanyName"]
    assert info.ffi.fileVersionMS == (2 << 16) | 0
    assert info.ffi.fileVersionLS == (5 << 16) | 0
