# -*- coding: utf-8 -*-
"""
啟動
"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False) and __package__ in (None, ""):
    # 以腳本方式執行（IDE、PyQtInspect --file）時，讓 src 套件可以被匯入
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os  # noqa: E402
import threading  # noqa: E402

from loguru import logger  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from src.config.web_service_config import WebServiceConfig  # noqa: E402
from src.core.connection_store import ConnectionStore  # noqa: E402
from src.core.soap_service import SoapService  # noqa: E402
from src.ui.main_window import AboutInfo, MainWindow  # noqa: E402
from src.ui.theme import ThemeManager  # noqa: E402
from src.utils import pathutil  # noqa: E402

GITHUB_URL = "https://github.com/m121752332/webservice-py-tool"


def _install_excepthook() -> None:
    """未預期的例外寫入記錄檔並顯示對話框，避免打包後的 exe 直接閃退

    對話框只能在 GUI（主）執行緒顯示；背景執行緒的例外一律只記錄，
    避免從非 GUI 執行緒呼叫 QMessageBox 造成程式崩潰。
    """

    def hook(exc_type, exc, tb):
        logger.opt(exception=(exc_type, exc, tb)).error("未預期的錯誤")
        if QApplication.instance() is not None and threading.current_thread() is threading.main_thread():
            QMessageBox.critical(None, "發生錯誤", f"{exc_type.__name__}: {exc}\n\n詳細內容已寫入記錄檔。")

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).error(
            "背景執行緒（{}）發生未預期的錯誤", args.thread.name if args.thread else "?"
        )

    sys.excepthook = hook
    threading.excepthook = thread_hook


def resolve_app_dirs(config: WebServiceConfig) -> tuple[Path, Path]:
    """由設定檔（ws_tool.yaml）實際所在位置推導 log 目錄與連線資料目錄。

    兩者共用同一個基準目錄，避免各自呼叫 pathutil.resource_abspath 在不同時機
    （例如 log 目錄尚未建立、連線資料目錄已存在）找到不一致的基準目錄，
    導致從 repo 根目錄啟動時讀到空的連線設定（見 F1）。
    """
    config_path = Path(pathutil.resource_abspath(
        os.path.join(config.get_app_connection_path(), "ws_tool.yaml")
    ))
    base = config_path.parent.parent
    log_dir = base / config.get_app_log_path()
    data_dir = base / config.get_app_connection_path()
    return log_dir, data_dir


def main() -> int:
    config = WebServiceConfig()
    log_dir, data_dir = resolve_app_dirs(config)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        os.path.join(log_dir, "run.log"),
        retention=config.get_app_log_retention(),
        level=str(config.get_app_log_level()).upper(),
    )

    app = QApplication(sys.argv)
    app.setApplicationName(config.get_app_name())
    app.setWindowIcon(QIcon(pathutil.resource_path(config.get_app_img_path())))
    _install_excepthook()

    settings = QSettings(os.path.join(data_dir, "settings.ini"), QSettings.Format.IniFormat)
    theme = ThemeManager(app, settings)
    theme.apply()

    store = ConnectionStore(os.path.join(data_dir, config.get_app_connection_profile()))
    about = AboutInfo(
        name=config.get_app_name(),
        version=config.get_app_version(),
        copyright=config.get_app_copyright(),
        website=GITHUB_URL,
    )
    window = MainWindow(
        store, SoapService(), theme, about,
        default_timeout=config.get_app_timeout(), settings_path=config.config_path,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
