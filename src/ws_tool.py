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
from src.core.daily_log import DailyFileSink, parse_levels, parse_retention_days  # noqa: E402
from src.core.log_buffer import LogBuffer  # noqa: E402
from src.core.soap_service import SoapService  # noqa: E402
from src.ui.main_window import AboutInfo, MainWindow  # noqa: E402
from src.ui.theme import ThemeManager  # noqa: E402
from src.utils import path_util  # noqa: E402

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

    兩者共用同一個基準目錄，避免各自呼叫 path_util.resource_abspath 在不同時機
    （例如 log 目錄尚未建立、連線資料目錄已存在）找到不一致的基準目錄，
    導致從 repo 根目錄啟動時讀到空的連線設定（見 F1）。
    """
    config_path = Path(path_util.resource_abspath(
        os.path.join(config.app_connection_path, "ws_tool.yaml")
    ))
    base = config_path.parent.parent
    log_dir = base / config.app_log_path
    data_dir = base / config.app_connection_path
    return log_dir, data_dir


LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
SPLIT_EXACT = {"info": "INFO", "debug": "DEBUG", "error": "ERROR"}


def _split_filter(split: str):
    """info／debug／error 只收同名等級；other 收其餘所有等級（含自訂等級）"""
    if split == "other":
        exact = set(SPLIT_EXACT.values())
        return lambda record: record["level"].name not in exact
    name = SPLIT_EXACT[split]
    return lambda record: record["level"].name == name


def setup_logging(log_dir: Path, config) -> tuple[LogBuffer, list[int]]:
    """run.log 依 level 門檻記錄；levels 列出的等級另外分流到 ws_<等級>.log（不受 level 影響）；
    檔案每日歸檔。主控台暫存一律收集 TRACE 以上。回傳暫存與新增的 handler id"""
    log_dir.mkdir(parents=True, exist_ok=True)
    retention = parse_retention_days(config.app_log_retention)
    handlers = [logger.add(
        DailyFileSink(log_dir, "run", retention), level=str(config.app_log_level).upper(),
        format=LOG_FORMAT, colorize=False,
    )]
    levels, unknown = parse_levels(config.app_log_levels)
    for split in levels:
        handlers.append(logger.add(
            DailyFileSink(log_dir, f"ws_{split}", retention), level=0, filter=_split_filter(split),
            format=LOG_FORMAT, colorize=False,
        ))
    buffer = LogBuffer()
    handlers.append(buffer.attach())
    # 確保所有檔案存在，即使沒有寫入任何訊息
    (log_dir / "run.log").touch(exist_ok=True)
    for split in levels:
        (log_dir / f"ws_{split}.log").touch(exist_ok=True)
    if unknown:
        logger.warning("log.levels 有無法辨識的名稱，已略過：{}", ", ".join(unknown))
    return buffer, handlers


def main() -> int:
    config = WebServiceConfig()
    log_dir, data_dir = resolve_app_dirs(config)
    log_buffer, _handlers = setup_logging(log_dir, config)
    logger.info("程式啟動 · {} {}", config.app_name, config.app_version)
    logger.debug("設定檔={} · 連線資料={} · 記錄={}", config.config_path, data_dir, log_dir)

    app = QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setWindowIcon(QIcon(path_util.resource_path(config.app_img_path)))
    _install_excepthook()

    settings = QSettings(os.path.join(data_dir, "settings.ini"), QSettings.Format.IniFormat)
    theme = ThemeManager(app, settings)
    theme.apply()

    store = ConnectionStore(os.path.join(data_dir, config.app_connection_profile))
    about = AboutInfo(
        name=config.app_name,
        version=config.app_version,
        copyright=config.app_copyright,
        website=GITHUB_URL,
    )
    window = MainWindow(
        store, SoapService(), theme, about,
        default_timeout=config.app_timeout, settings_path=config.config_path,
        settings=settings, log_buffer=log_buffer,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
