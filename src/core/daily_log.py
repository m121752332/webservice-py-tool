# -*- coding: utf-8 -*-
"""
日期歸檔記錄檔：固定寫入 <stem>.log，換日時把舊檔改名為 <stem>_YYYYMMDD.log 並清除過期歸檔（不依賴 Qt）
"""
import re
import shutil
import threading
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_RETENTION_DAYS = 10
SPLIT_LEVELS = ("info", "debug", "error", "other")
DEFAULT_SPLIT_LEVELS = ", ".join(SPLIT_LEVELS)
_RETENTION = re.compile(r"^\s*(\d+)\s*(?:days?)?\s*$", re.IGNORECASE)


def parse_retention_days(value, default: int = DEFAULT_RETENTION_DAYS) -> int:
    """「10 days」「1 day」「7」或 int 轉成天數；無法解析或小於 1 時回傳 default"""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value if value >= 1 else default
    match = _RETENTION.match(str(value or ""))
    days = int(match.group(1)) if match else 0
    return days if days >= 1 else default


def parse_levels(value) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """「info, debug」轉成 (有效等級, 無法辨識的名稱)；不分大小寫、去除重複，有效等級依 SPLIT_LEVELS 排序"""
    if isinstance(value, (list, tuple)):
        value = ",".join(map(str, value))
    names = [part.strip().lower() for part in str(value or "").split(",") if part.strip()]
    valid = tuple(level for level in SPLIT_LEVELS if level in names)
    unknown = tuple(dict.fromkeys(name for name in names if name not in SPLIT_LEVELS))
    return valid, unknown


def archive_name(stem: str, day: date) -> str:
    return f"{stem}_{day:%Y%m%d}.log"


def purge_archives(log_dir: Path, stem: str, retention_days: int, today: date) -> list[Path]:
    """刪除日期早於 today - retention_days 的歸檔檔，回傳成功刪除的檔案；刪不掉的留到下次"""
    pattern = re.compile(rf"^{re.escape(stem)}_(\d{{8}})\.log$")
    cutoff = today - timedelta(days=retention_days)
    removed = []
    try:
        candidates = sorted(Path(log_dir).iterdir())
    except OSError:
        return removed
    for path in candidates:
        match = pattern.match(path.name)
        if match is None:
            continue
        try:
            day = datetime.strptime(match.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        if day < cutoff:
            try:
                path.unlink()
                removed.append(path)
            except OSError:
                pass
    return removed


class DailyFileSink:
    """執行緒安全的記錄檔；物件本身可直接當 loguru sink（write／flush／stop）"""

    def __init__(self, log_dir, stem: str, retention_days: int, clock: Callable[[], datetime] = datetime.now):
        self._dir = Path(log_dir)
        self._stem = stem
        self._retention = retention_days
        self._clock = clock
        self._lock = threading.Lock()
        self._file = None
        try:
            today = clock().date()
            self._day = self._file_day(today)
            with self._lock:
                if self._day != today:
                    self._rollover(today)
                else:
                    purge_archives(self._dir, stem, retention_days, today)
        except Exception:
            self._day = None  # 下次寫入時再試

    @property
    def path(self) -> Path:
        return self._dir / f"{self._stem}.log"

    def write(self, text) -> None:
        try:
            with self._lock:
                today = self._clock().date()
                if today != self._day:
                    self._rollover(today)
                if self._file is None:
                    self._dir.mkdir(parents=True, exist_ok=True)
                    self._file = self.path.open("a", encoding="utf-8")
                self._file.write(str(text))
                self._file.flush()
        except Exception:
            pass  # 記錄動作不可以把主流程弄壞

    def flush(self) -> None:
        """write() 已逐筆 flush；保留給 loguru 呼叫"""

    def stop(self) -> None:
        """loguru logger.remove() 時呼叫"""
        self.close()

    def close(self) -> None:
        with self._lock:
            self._close()

    def _close(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            finally:
                self._file = None

    def _file_day(self, today: date) -> date:
        try:
            return datetime.fromtimestamp(self.path.stat().st_mtime).date()
        except OSError:
            return today

    def _rollover(self, today: date) -> None:
        """關檔、把舊檔歸檔、清除過期檔；改名失敗時保留 _day，下次寫入再試"""
        self._close()
        if self._day is not None and self.path.exists():
            try:
                self._archive(self._day)
            except OSError:
                return
        self._day = today
        purge_archives(self._dir, self._stem, self._retention, today)

    def _archive(self, day: date) -> None:
        target = self._dir / archive_name(self._stem, day)
        if target.exists():
            with self.path.open("rb") as source, target.open("ab") as dest:
                shutil.copyfileobj(source, dest)
            self.path.unlink()
        else:
            self.path.replace(target)
