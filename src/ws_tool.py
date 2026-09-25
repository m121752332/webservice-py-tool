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
    """未預期的例外寫入記錄檔並顯示對話框，避免打包後的 exe 直接閃退"""

    def hook(exc_type, exc, tb):
        logger.opt(exception=(exc_type, exc, tb)).error("未預期的錯誤")
        if QApplication.instance() is not None:
            QMessageBox.critical(None, "發生錯誤", f"{exc_type.__name__}: {exc}\n\n詳細內容已寫入記錄檔。")

    sys.excepthook = hook


def main() -> int:
    config = WebServiceConfig()
    logger.add(
        os.path.join(pathutil.resource_abspath(config.get_app_log_path()), "run.log"),
        retention=config.get_app_log_retention(),
        level=str(config.get_app_log_level()).upper(),
    )

    app = QApplication(sys.argv)
    app.setApplicationName(config.get_app_name())
    app.setWindowIcon(QIcon(pathutil.resource_path(config.get_app_img_path())))
    _install_excepthook()

    data_dir = pathutil.resource_abspath(config.get_app_connection_path())
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
    window = MainWindow(store, SoapService(), theme, about, default_timeout=config.get_app_timeout())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
