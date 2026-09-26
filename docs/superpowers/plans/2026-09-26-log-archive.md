# 記錄分流、日期歸檔與請求紀錄查閱 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 依等級分流記錄檔、所有記錄檔依日期歸檔並自動清除過期檔，另外把每次請求的參數／回應（或 SOAP 信封）寫入 `ws_xml.log`，並提供 F10 查閱視窗。

**Architecture:** `src/core/daily_log.py` 提供可當 loguru sink 的 `DailyFileSink`（換日改名＋清除過期檔）；`src/core/xml_log.py` 定義 `CallRecord` 的文字格式、解析與 `XmlLogWriter`；`SoapService` 注入 recorder，在背景執行緒內不論成功或失敗都寫一筆。UI 端新增 `XmlLogViewer` 獨立視窗，透過 `resendRequested` 訊號請主視窗 `load_record()`。

**Tech Stack:** Python 3.14、PySide6、loguru、suds、pytest（`QT_QPA_PLATFORM=offscreen`）

**Spec:** `docs/superpowers/specs/2026-09-26-log-archive-design.md`

## Global Constraints

- 所有原始碼 UTF-8，檔案開頭 `# -*- coding: utf-8 -*-`，模組頂端一段繁體中文 docstring
- 註解、docstring、UI 文字、commit 訊息一律繁體中文；識別字用英文
- `src/core/*` 不可 import PySide6
- 背景讀檔一律用 `src/ui/workers.py` 的 `run_in_background`
- 顏色只能來自 `src/ui/theme.py` 的 palette／QSS
- `ws_tool.yaml` 舊欄位意義不變：`level` 只管 `run.log`；`retention` 接受 `"10 days"` 或純數字
- 新欄位預設值：`levels = "info, debug, error, other"`、`xml.enabled = true`、`xml.content = params`、`xml.retention = 30`
- 歸檔檔名：`<stem>_YYYYMMDD.log`；目前檔名：`<stem>.log`；stem 為 `run`、`ws_info`、`ws_debug`、`ws_error`、`ws_other`、`ws_xml`
- commit 訊息用 Write 工具寫入 `.git/COMMIT_MSG_TMP` 再 `git commit -F .git/COMMIT_MSG_TMP`，結尾加 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`；不要 push
- 測試指令：`.venv/Scripts/python -m pytest <path> -v -p no:xdist`（單檔）；全體：`.venv/Scripts/python -m pytest`

## 檔案結構

| 檔案 | 動作 | 職責 |
| --- | --- | --- |
| `src/core/daily_log.py` | 新增 | `DailyFileSink`、`purge_archives`、`archive_name`、`parse_retention_days`、`parse_levels` |
| `src/core/xml_log.py` | 新增 | `CallRecord`、`format_record`、`parse_records`、`XmlLogWriter`、`list_log_dates`、`read_records` |
| `src/config/web_service_config.py` | 修改 | 讀新欄位（有預設值） |
| `src/config/app_settings.py` | 修改 | `app.log.xml.content` 下拉、`app.log.xml.retention` 範圍 |
| `src/app_data/ws_tool.yaml` | 修改 | 新增 `levels`、`xml` 區段 |
| `src/ws_tool.py` | 修改 | `setup_logging` 分流、`create_recorder`、注入 `SoapService` 與 `xml_log_dir` |
| `src/core/soap_service.py` | 修改 | recorder、`connection` 參數、信封擷取 |
| `src/ui/xml_log_viewer.py` | 新增 | 查閱視窗 |
| `src/ui/icons.py`、`src/ui/theme.py` | 修改 | `record_icon()`、查閱視窗 QSS |
| `src/ui/main_window.py` | 修改 | 傳連線名稱、紀錄按鈕、F10、`load_record` |
| `README.md` | 修改 | 記錄檔說明 |

---

### Task 1: 日期歸檔 sink（`src/core/daily_log.py`）

**Files:**
- Create: `src/core/daily_log.py`
- Test: `tests/test_daily_log.py`

**Interfaces:**
- Produces:
  - `DEFAULT_RETENTION_DAYS: int = 10`、`SPLIT_LEVELS = ("info", "debug", "error", "other")`、`DEFAULT_SPLIT_LEVELS = "info, debug, error, other"`
  - `parse_retention_days(value, default: int = DEFAULT_RETENTION_DAYS) -> int`
  - `parse_levels(value) -> tuple[tuple[str, ...], tuple[str, ...]]`（有效, 無法辨識）
  - `archive_name(stem: str, day: date) -> str`
  - `purge_archives(log_dir: Path, stem: str, retention_days: int, today: date) -> list[Path]`
  - `DailyFileSink(log_dir, stem: str, retention_days: int, clock: Callable[[], datetime] = datetime.now)`，方法 `write(text)`、`flush()`、`stop()`、`close()`，屬性 `path`

- [ ] **Step 1: 寫失敗測試** — 建立 `tests/test_daily_log.py`

```python
# -*- coding: utf-8 -*-
import os
from datetime import date, datetime
from pathlib import Path

import pytest
from loguru import logger

from src.core.daily_log import DailyFileSink, archive_name, parse_levels, parse_retention_days, purge_archives

DAY1 = datetime(2026, 9, 25, 23, 59)
DAY2 = datetime(2026, 9, 26, 0, 1)


class Clock:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


@pytest.mark.parametrize("value, expected", [
    ("10 days", 10), ("1 day", 1), (" 3 Days ", 3), ("7", 7), (30, 30),
    ("abc", 10), ("", 10), (None, 10), (0, 10), ("0 days", 10), (True, 10),
])
def test_parse_retention_days(value, expected):
    assert parse_retention_days(value) == expected


def test_parse_retention_days_custom_default():
    assert parse_retention_days("x", default=30) == 30


def test_parse_levels():
    assert parse_levels("Error, info, INFO, other") == (("info", "error", "other"), ())
    assert parse_levels("info, warn, foo, warn") == (("info",), ("warn", "foo"))
    assert parse_levels("") == ((), ())
    assert parse_levels(None) == ((), ())
    assert parse_levels(["debug", "info"]) == (("info", "debug"), ())


def test_archive_name():
    assert archive_name("ws_xml", date(2026, 9, 5)) == "ws_xml_20260905.log"


def test_writes_to_stem_log_and_creates_dir(tmp_path):
    sink = DailyFileSink(tmp_path / "logs", "ws_info", 10, clock=Clock(DAY1))
    sink.write("第一行\n")
    sink.close()
    assert sink.path == tmp_path / "logs" / "ws_info.log"
    assert sink.path.read_text(encoding="utf-8") == "第一行\n"


def test_rolls_over_on_new_day(tmp_path):
    clock = Clock(DAY1)
    sink = DailyFileSink(tmp_path, "ws_info", 10, clock=clock)
    sink.write("a\n")
    clock.value = DAY2
    sink.write("b\n")
    sink.close()
    assert (tmp_path / "ws_info_20260925.log").read_text(encoding="utf-8") == "a\n"
    assert (tmp_path / "ws_info.log").read_text(encoding="utf-8") == "b\n"


def test_existing_old_file_archived_on_startup(tmp_path):
    old = tmp_path / "run.log"
    old.write_text("old\n", encoding="utf-8")
    stamp = datetime(2026, 9, 24, 12).timestamp()
    os.utime(old, (stamp, stamp))
    DailyFileSink(tmp_path, "run", 10, clock=Clock(DAY2)).close()
    assert (tmp_path / "run_20260924.log").read_text(encoding="utf-8") == "old\n"
    assert not old.exists()


def test_archive_appends_when_target_exists(tmp_path):
    (tmp_path / "run_20260925.log").write_text("earlier\n", encoding="utf-8")
    clock = Clock(DAY1)
    sink = DailyFileSink(tmp_path, "run", 10, clock=clock)
    sink.write("later\n")
    clock.value = DAY2
    sink.write("x\n")
    sink.close()
    assert (tmp_path / "run_20260925.log").read_text(encoding="utf-8") == "earlier\nlater\n"


def test_purge_archives_keeps_boundary_and_ignores_other_files(tmp_path):
    names = (
        "ws_xml_20260915.log", "ws_xml_20260916.log", "ws_xml_20260925.log",
        "ws_xml.log", "ws_xml_note.log", "ws_info_20200101.log",
    )
    for name in names:
        (tmp_path / name).write_text("", encoding="utf-8")
    removed = purge_archives(tmp_path, "ws_xml", 10, date(2026, 9, 26))
    assert [p.name for p in removed] == ["ws_xml_20260915.log"]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "ws_info_20200101.log", "ws_xml.log", "ws_xml_20260916.log", "ws_xml_20260925.log", "ws_xml_note.log",
    ]


def test_startup_and_rollover_purge_expired(tmp_path):
    (tmp_path / "run_20260901.log").write_text("", encoding="utf-8")
    clock = Clock(DAY1)
    sink = DailyFileSink(tmp_path, "run", 10, clock=clock)
    assert not (tmp_path / "run_20260901.log").exists()
    (tmp_path / "run_20260915.log").write_text("", encoding="utf-8")  # 9/25 時還在保留期內
    sink.write("a\n")
    assert (tmp_path / "run_20260915.log").exists()
    clock.value = DAY2
    sink.write("b\n")
    sink.close()
    assert not (tmp_path / "run_20260915.log").exists()


def test_write_never_raises(tmp_path, monkeypatch):
    sink = DailyFileSink(tmp_path, "run", 10, clock=Clock(DAY1))

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "open", boom)
    sink.write("x\n")  # 不可丟出例外


def test_rename_failure_keeps_writing_current_file(tmp_path, monkeypatch):
    clock = Clock(DAY1)
    sink = DailyFileSink(tmp_path, "run", 10, clock=clock)
    sink.write("a\n")

    def locked(self, target):
        raise PermissionError("檔案被占用")

    monkeypatch.setattr(Path, "replace", locked)
    clock.value = DAY2
    sink.write("b\n")
    sink.close()
    assert (tmp_path / "run.log").read_text(encoding="utf-8") == "a\nb\n"


def test_loguru_remove_closes_file(tmp_path):
    sink = DailyFileSink(tmp_path, "run", 10, clock=Clock(DAY1))
    handler_id = logger.add(sink, format="{message}", level="INFO")
    logger.info("訊息")
    logger.remove(handler_id)
    assert sink._file is None
    assert (tmp_path / "run.log").read_text(encoding="utf-8") == "訊息\n"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_daily_log.py -v -p no:xdist`
Expected: FAIL（`ModuleNotFoundError: No module named 'src.core.daily_log'`）

- [ ] **Step 3: 實作** — 建立 `src/core/daily_log.py`

```python
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
```

注意：`test_rename_failure_keeps_writing_current_file` 裡 `_rollover` 改名失敗會 `return` 而不更新 `_day`，所以之後每次寫入都會重試改名；這是預期行為。

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_daily_log.py -v -p no:xdist`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息：`新增日期歸檔記錄檔 DailyFileSink：換日改名、清除過期歸檔`

```bash
git add src/core/daily_log.py tests/test_daily_log.py
git commit -F .git/COMMIT_MSG_TMP
```

---

### Task 2: 請求紀錄格式（`src/core/xml_log.py`）

**Files:**
- Create: `src/core/xml_log.py`
- Test: `tests/test_xml_log.py`

**Interfaces:**
- Consumes: `DailyFileSink`（Task 1）
- Produces:
  - `XML_LOG_STEM = "ws_xml"`、`CONTENT_MODES = ("params", "envelope", "both")`、`DEFAULT_CONTENT = "params"`、`DEFAULT_XML_RETENTION_DAYS = 30`
  - `SECTIONS = {"params": "參數", "response": "回應", "sent": "SOAP 請求", "received": "SOAP 回應"}`
  - `@dataclass(frozen=True) CallRecord(time, connection, url, method, status, elapsed, size, error="", params="", response="", sent="", received="")`
  - `normalize_content(value) -> str`、`format_record(record, content="params") -> str`、`parse_records(text) -> list[CallRecord]`
  - `XmlLogWriter(log_dir, content="params", retention_days=30, clock=datetime.now)`：`__call__(record)`、`close()`、屬性 `content`
  - `list_log_dates(log_dir) -> list[tuple[date, Path]]`、`read_records(path) -> list[CallRecord]`

- [ ] **Step 1: 寫失敗測試** — 建立 `tests/test_xml_log.py`

```python
# -*- coding: utf-8 -*-
import json
import os
from dataclasses import replace
from datetime import date, datetime

import pytest

from src.core.xml_log import (
    CallRecord, XmlLogWriter, format_record, list_log_dates, normalize_content, parse_records, read_records,
)

RECORD = CallRecord(
    time=datetime(2026, 9, 26, 14, 3, 22, 123000), connection="訂單服務", url="http://h/ws?wsdl",
    method="GetOrder", status="success", elapsed=0.5321, size=1234,
    params='<?xml version="1.0"?>\n<Req>\n  <中文>值</中文>\n</Req>', response="<ok/>",
    sent="<Envelope>s</Envelope>", received="<Envelope>r</Envelope>",
)


def test_format_params_mode():
    lines = format_record(RECORD, "params").splitlines()
    assert lines[0] == "===== 2026-09-26 14:03:22.123 ====="
    assert json.loads(lines[1]) == {
        "connection": "訂單服務", "url": "http://h/ws?wsdl", "method": "GetOrder",
        "status": "success", "elapsed": 0.532, "size": 1234, "error": "",
    }
    assert "----- 參數 -----" in lines and "----- 回應 -----" in lines
    assert "----- SOAP 請求 -----" not in lines


def test_format_envelope_and_both_modes():
    envelope = format_record(RECORD, "envelope").splitlines()
    assert "----- SOAP 請求 -----" in envelope and "----- SOAP 回應 -----" in envelope
    assert "----- 參數 -----" not in envelope
    both = format_record(RECORD, "both").splitlines()
    assert [line for line in both if line.startswith("----- ")] == [
        "----- 參數 -----", "----- 回應 -----", "----- SOAP 請求 -----", "----- SOAP 回應 -----",
    ]


@pytest.mark.parametrize("value, expected", [
    ("params", "params"), ("Both", "both"), (" envelope ", "envelope"), ("xml", "params"), (None, "params"),
])
def test_normalize_content(value, expected):
    assert normalize_content(value) == expected


def test_round_trip_multiple_records():
    failed = replace(RECORD, status="failed", error="TimeoutError: 逾時", response="", size=0)
    records = parse_records(format_record(RECORD, "both") + format_record(failed, "both"))
    assert records == [replace(RECORD, elapsed=0.532), replace(failed, elapsed=0.532)]


def test_params_mode_leaves_envelopes_empty():
    record = parse_records(format_record(RECORD, "params"))[0]
    assert record.params == RECORD.params and record.sent == "" and record.received == ""


def test_broken_blocks_are_skipped():
    text = (
        "開頭的雜訊\n"
        "===== 2026-09-26 14:00:00.000 =====\n不是 JSON\n"
        "===== 2026-13-40 99:00:00.000 =====\n{}\n"
        + format_record(RECORD, "params")
    )
    records = parse_records(text)
    assert len(records) == 1 and records[0].method == "GetOrder"


def test_writer_uses_content_mode(tmp_path):
    writer = XmlLogWriter(tmp_path, "envelope", 30, clock=lambda: datetime(2026, 9, 26, 9))
    writer(RECORD)
    writer.close()
    record = read_records(tmp_path / "ws_xml.log")[0]
    assert record.sent == RECORD.sent and record.params == ""
    assert writer.content == "envelope"


def test_read_records_missing_file(tmp_path):
    assert read_records(tmp_path / "ws_xml.log") == []


def test_list_log_dates_newest_first(tmp_path):
    current = tmp_path / "ws_xml.log"
    current.write_text("", encoding="utf-8")
    stamp = datetime(2026, 9, 26, 10).timestamp()
    os.utime(current, (stamp, stamp))
    for name in ("ws_xml_20260924.log", "ws_xml_20260925.log", "ws_xml_bad.log", "ws_info_20260925.log"):
        (tmp_path / name).write_text("", encoding="utf-8")
    assert list_log_dates(tmp_path) == [
        (date(2026, 9, 26), current),
        (date(2026, 9, 25), tmp_path / "ws_xml_20260925.log"),
        (date(2026, 9, 24), tmp_path / "ws_xml_20260924.log"),
    ]


def test_list_log_dates_missing_dir(tmp_path):
    assert list_log_dates(tmp_path / "nope") == []
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_xml_log.py -v -p no:xdist`
Expected: FAIL（`ModuleNotFoundError: No module named 'src.core.xml_log'`）

- [ ] **Step 3: 實作** — 建立 `src/core/xml_log.py`

```python
# -*- coding: utf-8 -*-
"""
請求紀錄（ws_xml.log）：CallRecord 的寫入格式、解析、寫入器與歸檔檔案清單（不依賴 Qt）

一筆一塊：「===== 時間 =====」標頭行、一行 JSON 摘要，接著以「----- 段名 -----」分段放參數／回應／信封。
"""
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from src.core.daily_log import DailyFileSink

XML_LOG_STEM = "ws_xml"
CONTENT_MODES = ("params", "envelope", "both")
DEFAULT_CONTENT = "params"
DEFAULT_XML_RETENTION_DAYS = 30
SECTIONS = {"params": "參數", "response": "回應", "sent": "SOAP 請求", "received": "SOAP 回應"}
MODE_SECTIONS = {
    "params": ("params", "response"),
    "envelope": ("sent", "received"),
    "both": ("params", "response", "sent", "received"),
}
_META_FIELDS = ("connection", "url", "method", "status", "elapsed", "size", "error")
_FIELD_BY_TITLE = {title: name for name, title in SECTIONS.items()}
_HEADER = re.compile(r"^===== (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) =====$")
_SECTION = re.compile(r"^----- (.+) -----$")
_ARCHIVE = re.compile(rf"^{XML_LOG_STEM}_(\d{{8}})\.log$")
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


@dataclass(frozen=True)
class CallRecord:
    time: datetime
    connection: str  # 連線名稱（可為空）
    url: str
    method: str
    status: str  # "success" / "failed"
    elapsed: float
    size: int
    error: str = ""
    params: str = ""  # 使用者輸入的參數
    response: str = ""  # 排版後的回應文字（失敗時為空）
    sent: str = ""  # SOAP 請求信封
    received: str = ""  # SOAP 回應信封


def normalize_content(value) -> str:
    text = str(value or "").strip().lower()
    return text if text in CONTENT_MODES else DEFAULT_CONTENT


def _format_time(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S.") + f"{moment.microsecond // 1000:03d}"


def format_record(record: CallRecord, content: str = DEFAULT_CONTENT) -> str:
    meta = {name: getattr(record, name) for name in _META_FIELDS}
    meta["elapsed"] = round(record.elapsed, 3)
    lines = [f"===== {_format_time(record.time)} =====", json.dumps(meta, ensure_ascii=False)]
    for name in MODE_SECTIONS[normalize_content(content)]:
        lines.append(f"----- {SECTIONS[name]} -----")
        lines.append(getattr(record, name).rstrip("\n"))
    return "\n".join(lines) + "\n"


def parse_records(text: str) -> list[CallRecord]:
    """解析整個檔案內容；格式壞掉的區塊略過"""
    blocks: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        match = _HEADER.match(line)
        if match:
            blocks.append((match.group(1), []))
        elif blocks:
            blocks[-1][1].append(line)
    records = []
    for stamp, lines in blocks:
        record = _parse_block(stamp, lines)
        if record is not None:
            records.append(record)
    return records


def _parse_block(stamp: str, lines: list[str]) -> CallRecord | None:
    try:
        moment = datetime.strptime(stamp, _TIME_FORMAT)
        meta = json.loads(lines[0])
        sections: dict[str, list[str]] = {}
        current = None
        for line in lines[1:]:
            match = _SECTION.match(line)
            if match and match.group(1) in _FIELD_BY_TITLE:
                current = _FIELD_BY_TITLE[match.group(1)]
                sections[current] = []
            elif current is not None:
                sections[current].append(line)
        return CallRecord(
            time=moment,
            connection=str(meta.get("connection", "")),
            url=str(meta.get("url", "")),
            method=str(meta.get("method", "")),
            status=str(meta.get("status", "")),
            elapsed=float(meta.get("elapsed", 0)),
            size=int(meta.get("size", 0)),
            error=str(meta.get("error", "")),
            **{name: "\n".join(body).rstrip("\n") for name, body in sections.items()},
        )
    except (IndexError, ValueError, TypeError, AttributeError):
        return None


class XmlLogWriter:
    """SoapService 的 recorder：依 content 模式把 CallRecord 寫入 ws_xml.log（每日歸檔）"""

    def __init__(self, log_dir, content: str = DEFAULT_CONTENT,
                 retention_days: int = DEFAULT_XML_RETENTION_DAYS, clock: Callable[[], datetime] = datetime.now):
        self.content = normalize_content(content)
        self._sink = DailyFileSink(log_dir, XML_LOG_STEM, retention_days, clock=clock)

    def __call__(self, record: CallRecord) -> None:
        self._sink.write(format_record(record, self.content))

    def close(self) -> None:
        self._sink.close()


def list_log_dates(log_dir) -> list[tuple[date, Path]]:
    """目前的 ws_xml.log（以修改日期為準）與所有歸檔檔，新的在前；同一天時目前檔在前"""
    directory = Path(log_dir)
    entries: list[tuple[date, int, Path]] = []
    try:
        current = directory / f"{XML_LOG_STEM}.log"
        if current.is_file():
            entries.append((datetime.fromtimestamp(current.stat().st_mtime).date(), 0, current))
        for path in directory.iterdir():
            match = _ARCHIVE.match(path.name)
            if match is None:
                continue
            try:
                entries.append((datetime.strptime(match.group(1), "%Y%m%d").date(), 1, path))
            except ValueError:
                continue
    except OSError:
        pass
    entries.sort(key=lambda item: (-item[0].toordinal(), item[1]))
    return [(day, path) for day, _order, path in entries]


def read_records(path) -> list[CallRecord]:
    """讀檔並解析；檔案不存在時回傳空清單，其他 I/O 錯誤往外丟給呼叫端顯示"""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return []
    return parse_records(text)
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_xml_log.py -v -p no:xdist`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息：`新增請求紀錄格式 xml_log：CallRecord 寫入／解析、XmlLogWriter 與歸檔清單`

```bash
git add src/core/xml_log.py tests/test_xml_log.py
git commit -F .git/COMMIT_MSG_TMP
```

---

### Task 3: 設定檔新欄位

**Files:**
- Modify: `src/app_data/ws_tool.yaml`
- Modify: `src/config/web_service_config.py:25-28`
- Modify: `src/config/app_settings.py`（常數區與 `_field_for`）
- Create: `tests/test_web_service_config.py`
- Modify: `tests/test_app_settings.py`

**Interfaces:**
- Consumes: `DEFAULT_SPLIT_LEVELS`（Task 1）、`CONTENT_MODES`、`DEFAULT_CONTENT`、`DEFAULT_XML_RETENTION_DAYS`（Task 2）
- Produces: `WebServiceConfig.app_log_levels`、`app_xml_enabled: bool`、`app_xml_content`、`app_xml_retention`；`app_settings.XML_RETENTION_MIN = 1`、`XML_RETENTION_MAX = 3650`

- [ ] **Step 1: 寫失敗測試** — 建立 `tests/test_web_service_config.py`

```python
# -*- coding: utf-8 -*-
from src.config.web_service_config import WebServiceConfig
from src.utils import global_values

BASE = (
    "app:\n"
    "  name: \"Test Tool\"\n"
    "  version: \"v0\"\n"
    "  copyright: \"c\"\n"
    "  img: \"assets/app_icon.ico\"\n"
    "  timeout: 120\n"
    "  log:\n"
    "    path: \"app_data/logs\"\n"
    "    level: info\n"
    "    retention: \"10 days\"\n"
    "{extra}"
    "  connection:\n"
    "    path: \"app_data\"\n"
    "    profile: \"connections.profile\"\n"
)


def make_config(tmp_path, monkeypatch, extra=""):
    app_data = tmp_path / "src" / "app_data"
    app_data.mkdir(parents=True)
    (app_data / "ws_tool.yaml").write_text(BASE.format(extra=extra), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(global_values, "EXE_PATH", "")
    return WebServiceConfig()


def test_old_config_without_new_fields_uses_defaults(tmp_path, monkeypatch):
    config = make_config(tmp_path, monkeypatch)
    assert config.app_log_level == "info"
    assert config.app_log_levels == "info, debug, error, other"
    assert (config.app_xml_enabled, config.app_xml_content, config.app_xml_retention) == (True, "params", 30)


def test_new_fields_are_read(tmp_path, monkeypatch):
    extra = (
        "    levels: \"error\"\n"
        "    xml:\n"
        "      enabled: false\n"
        "      content: both\n"
        "      retention: 7\n"
    )
    config = make_config(tmp_path, monkeypatch, extra)
    assert config.app_log_levels == "error"
    assert (config.app_xml_enabled, config.app_xml_content, config.app_xml_retention) == (False, "both", 7)


def test_repo_config_has_new_fields():
    config = WebServiceConfig()
    assert config.app_log_levels == "info, debug, error, other"
    assert (config.app_xml_enabled, config.app_xml_content, config.app_xml_retention) == (True, "params", 30)
```

在 `tests/test_app_settings.py` 的 import 區加入 `XML_RETENTION_MAX, XML_RETENTION_MIN` 與 `from src.core.xml_log import CONTENT_MODES`，並在檔尾加入：

```python
XML_YAML = SETTINGS_YAML.replace(
    '    retention: "10 days"\n',
    '    retention: "10 days"\n'
    "    # 額外分流的等級\n"
    '    levels: "info, error"\n'
    "    # 請求紀錄\n"
    "    xml:\n"
    "      enabled: true\n"
    "      content: params\n"
    "      retention: 30\n",
)


def test_xml_log_fields(tmp_path):
    doc = load_text(tmp_path, XML_YAML)
    assert field(doc, "app.log.levels").kind == "str"
    assert field(doc, "app.log.xml").kind == "group"
    assert field(doc, "app.log.xml.enabled").kind == "bool"
    content = field(doc, "app.log.xml.content")
    assert (content.kind, content.value, content.limits) == ("list", "params", CONTENT_MODES)
    retention = field(doc, "app.log.xml.retention")
    assert (retention.kind, retention.value, retention.limits) == ("int", 30, (XML_RETENTION_MIN, XML_RETENTION_MAX))


@pytest.mark.parametrize("values", [
    {"app.log.xml.retention": XML_RETENTION_MIN - 1},
    {"app.log.xml.retention": XML_RETENTION_MAX + 1},
    {"app.log.xml.content": "xml"},
])
def test_xml_log_invalid_values_raise(tmp_path, values):
    doc = load_text(tmp_path, XML_YAML)
    with pytest.raises(SettingsError):
        doc.render(values)


def test_xml_log_changes_need_restart(tmp_path):
    doc = load_text(tmp_path, XML_YAML)
    changes = doc.changes({"app.log.xml.content": "both", "app.log.levels": "info"})
    assert changes == SettingsChanges(hot=(), restart=("app.log.levels", "app.log.xml.content"))
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_web_service_config.py tests/test_app_settings.py -v -p no:xdist`
Expected: FAIL（`AttributeError: 'WebServiceConfig' object has no attribute 'app_log_levels'`、`ImportError: cannot import name 'XML_RETENTION_MAX'`）

- [ ] **Step 3: 實作**

`src/app_data/ws_tool.yaml` 的 `log:` 區段改為（`connection:` 以下不變）：

```yaml
  # Log path of the application
  log:
    # log path setting
    path: "app_data/logs"
    # log level（run.log 門檻）
    level: info
    # 額外分流的等級（info, debug, error, other，以逗號分隔；留空則不分流）
    levels: "info, debug, error, other"
    # log retention days（run.log 與 ws_*.log）
    retention: "10 days"
    # 請求紀錄（ws_xml.log）
    xml:
      # 是否記錄
      enabled: true
      # 內容：params（參數＋回應）/ envelope（SOAP 信封）/ both
      content: params
      # 保留天數
      retention: 30
```

`src/config/web_service_config.py`：import 區加

```python
from src.core.daily_log import DEFAULT_SPLIT_LEVELS
from src.core.xml_log import DEFAULT_CONTENT, DEFAULT_XML_RETENTION_DAYS
```

把「LOG 配置」四行換成：

```python
        # LOG 配置
        log_config = self.app_config['app']['log']
        self.app_log_path = log_config['path']
        self.app_log_level = log_config['level']
        self.app_log_retention = log_config['retention']
        # 分流與請求紀錄；舊設定檔沒有這些欄位時使用預設值
        self.app_log_levels = log_config.get('levels', DEFAULT_SPLIT_LEVELS)
        xml_config = log_config.get('xml') or {}
        self.app_xml_enabled = bool(xml_config.get('enabled', True))
        self.app_xml_content = xml_config.get('content', DEFAULT_CONTENT)
        self.app_xml_retention = xml_config.get('retention', DEFAULT_XML_RETENTION_DAYS)
```

`src/config/app_settings.py`：import 區加 `from src.core.xml_log import CONTENT_MODES`；常數區 `LOG_LEVELS` 下一行加

```python
XML_RETENTION_MIN = 1
XML_RETENTION_MAX = 3650
```

`_field_for` 在 `app.log.level` 判斷之後加入：

```python
    if key == "app.log.xml.content" and str(value).lower() in CONTENT_MODES:
        return SettingField(key, label, "list", str(value).lower(), CONTENT_MODES)
    if key == "app.log.xml.retention" and isinstance(value, int) and not isinstance(value, bool):
        return SettingField(key, label, "int", value, (XML_RETENTION_MIN, XML_RETENTION_MAX))
```

- [ ] **Step 4: 執行測試確認通過（含設定頁與外掛）**

Run: `.venv/Scripts/python -m pytest tests/test_web_service_config.py tests/test_app_settings.py tests/test_settings_page.py tests/test_settings_editor_plugin.py tests/test_entry_point.py -v -p no:xdist`
Expected: 全部 PASS。若 `test_settings_editor_plugin.py` 因三層巢狀 group 失敗，檢查 `plugins/settings_editor/settings_editor.py` 建立 group 的遞迴邏輯並修正（外掛不可 import `src.*`）。

- [ ] **Step 5: Commit**

訊息：`設定檔新增 log.levels 與 log.xml 區段，舊設定檔缺欄位時使用預設值`

```bash
git add src/app_data/ws_tool.yaml src/config/web_service_config.py src/config/app_settings.py tests/test_web_service_config.py tests/test_app_settings.py
git commit -F .git/COMMIT_MSG_TMP
```

---

### Task 4: 記錄分流與歸檔（`setup_logging`）

**Files:**
- Modify: `src/ws_tool.py:68-78`（`setup_logging`）與 import 區
- Modify: `tests/test_entry_point.py:106-121`

**Interfaces:**
- Consumes: `DailyFileSink`、`parse_levels`、`parse_retention_days`（Task 1）；`config.app_log_level`、`app_log_retention`、`app_log_levels`（Task 3）
- Produces: `setup_logging(log_dir: Path, config) -> tuple[LogBuffer, list[int]]`（簽章不變）；`LOG_FORMAT`

- [ ] **Step 1: 寫失敗測試** — `tests/test_entry_point.py` 既有的 `test_setup_logging_buffer_gets_all_levels_but_run_log_follows_config` 的 config 改為 `SimpleNamespace(app_log_retention="1 day", app_log_level="info", app_log_levels="")`，並在它後面加入：

```python
def test_setup_logging_splits_by_levels(tmp_path):
    from src.ws_tool import setup_logging

    config = SimpleNamespace(app_log_retention="10 days", app_log_level="info", app_log_levels="info, other, bogus")
    _buffer, handler_ids = setup_logging(tmp_path, config)
    try:
        logger.debug("除錯訊息")
        logger.info("一般訊息")
        logger.warning("警告訊息")
        logger.error("錯誤訊息")
    finally:
        for handler_id in handler_ids:
            logger.remove(handler_id)
    run = (tmp_path / "run.log").read_text(encoding="utf-8")
    info = (tmp_path / "ws_info.log").read_text(encoding="utf-8")
    other = (tmp_path / "ws_other.log").read_text(encoding="utf-8")
    assert "一般訊息" in run and "錯誤訊息" in run and "除錯訊息" not in run
    assert "一般訊息" in info and "警告訊息" not in info and "錯誤訊息" not in info
    assert "警告訊息" in other and "bogus" in other and "一般訊息" not in other and "錯誤訊息" not in other
    assert not (tmp_path / "ws_debug.log").exists() and not (tmp_path / "ws_error.log").exists()
    assert "| INFO     |" in info  # 與舊版 run.log 相同的欄位格式


def test_setup_logging_split_ignores_run_level(tmp_path):
    from src.ws_tool import setup_logging

    config = SimpleNamespace(app_log_retention="10 days", app_log_level="error", app_log_levels="debug")
    _buffer, handler_ids = setup_logging(tmp_path, config)
    try:
        logger.debug("除錯訊息")
    finally:
        for handler_id in handler_ids:
            logger.remove(handler_id)
    assert "除錯訊息" in (tmp_path / "ws_debug.log").read_text(encoding="utf-8")
    assert "除錯訊息" not in (tmp_path / "run.log").read_text(encoding="utf-8")
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_entry_point.py -v -p no:xdist`
Expected: 新增的兩個測試 FAIL（`ws_info.log` 不存在）

- [ ] **Step 3: 實作** — `src/ws_tool.py` import 區加 `from src.core.daily_log import DailyFileSink, parse_levels, parse_retention_days  # noqa: E402`，把 `setup_logging` 換成：

```python
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
    if unknown:
        logger.warning("log.levels 有無法辨識的名稱，已略過：{}", ", ".join(unknown))
    return buffer, handlers
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_entry_point.py -v -p no:xdist`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息：`記錄檔依 log.levels 分流到 ws_info／ws_debug／ws_error／ws_other，run.log 與分流檔每日歸檔`

```bash
git add src/ws_tool.py tests/test_entry_point.py
git commit -F .git/COMMIT_MSG_TMP
```

---

### Task 5: SoapService 寫入請求紀錄

**Files:**
- Modify: `src/core/soap_service.py`（import 區、`SoapService.__init__`、`call`，新增 `_record`、`_message_text`）
- Modify: `src/ws_tool.py`（新增 `create_recorder`，`main()` 注入）
- Modify: `src/ui/main_window.py:502-532`（`_on_run_clicked`、`_start`）
- Test: `tests/test_soap_service.py`、`tests/test_entry_point.py`、`tests/test_main_window.py`

**Interfaces:**
- Consumes: `CallRecord`、`XmlLogWriter`、`normalize_content`、`DEFAULT_XML_RETENTION_DAYS`（Task 2）；`parse_retention_days`（Task 1）
- Produces:
  - `SoapService(client_factory=..., recorder: Callable[[CallRecord], None] | None = None)`
  - `SoapService.call(url, method, raw_params, timeout, *, connection: str = "") -> CallResult`
  - `create_recorder(log_dir: Path, config) -> XmlLogWriter | None`
  - `MainWindow._start(kind, fn, *args, **kwargs)`

- [ ] **Step 1: 寫失敗測試**

`tests/test_soap_service.py` 檔尾加入：

```python
class BrokenTransport(HttpTransport):
    def send(self, request):
        raise ConnectionError("連線被拒")


def broken_factory(url, timeout):
    return Client(url, timeout=timeout, cache=None, transport=BrokenTransport())


def test_call_records_success_with_envelopes():
    records = []
    service = SoapService(FakeClientFactory(response_text="<r>好</r>"), recorder=records.append)
    result = service.call(WSDL_URL, "GetPOData", "<a/>", 5, connection="訂單")
    [record] = records
    assert (record.connection, record.url, record.method, record.status, record.error) == (
        "訂單", WSDL_URL, "GetPOData", "success", "",
    )
    assert (record.params, record.response, record.size) == ("<a/>", result.text, result.size)
    assert "Envelope" in record.sent and "GetPOData" in record.sent
    assert "GetPODataResponse" in record.received
    assert record.elapsed >= 0


def test_call_records_failure_and_reraises():
    records = []
    service = SoapService(broken_factory, recorder=records.append)
    with pytest.raises(Exception, match="連線被拒"):
        service.call(WSDL_URL, "GetPOData", "<a/>", 5)
    [record] = records
    assert record.status == "failed" and "連線被拒" in record.error and record.response == ""
    assert record.received == ""


def test_param_mismatch_is_not_recorded():
    records = []
    service = SoapService(FakeClientFactory(), recorder=records.append)
    with pytest.raises(ParamCountMismatch):
        service.call(WSDL_URL, "GetPOData", "<a/>#~#<b/>", 5)
    assert records == []


def test_recorder_error_does_not_break_call():
    def boom(_record):
        raise RuntimeError("寫檔失敗")

    service = SoapService(FakeClientFactory(), recorder=boom)
    assert service.call(WSDL_URL, "GetPOData", "<a/>", 5).text


def test_failed_call_does_not_reuse_previous_envelope():
    records = []
    factory = FakeClientFactory()
    service = SoapService(factory, recorder=records.append)
    service.call(WSDL_URL, "GetPOData", "<a/>", 5)
    factory.clients[0].set_options(transport=BrokenTransport())
    with pytest.raises(Exception):
        service.call(WSDL_URL, "GetPOData", "<a/>", 5)
    assert records[1].received == ""
```

`tests/test_entry_point.py` 檔尾加入：

```python
def test_create_recorder_follows_config(tmp_path):
    from src.core.xml_log import XmlLogWriter
    from src.ws_tool import create_recorder

    off = SimpleNamespace(app_xml_enabled=False, app_xml_content="params", app_xml_retention=30)
    assert create_recorder(tmp_path, off) is None
    on = SimpleNamespace(app_xml_enabled=True, app_xml_content="BOTH", app_xml_retention="7 days")
    recorder = create_recorder(tmp_path, on)
    assert isinstance(recorder, XmlLogWriter) and recorder.content == "both"
    recorder.close()
```

`tests/test_main_window.py`：`FakeService.__init__` 加 `self.connections = []`；`call` 改為

```python
    def call(self, url, method, raw_params, timeout, connection=""):
        self.calls.append(("call", url, method, raw_params, timeout))
        self.connections.append(connection)
        self._block_or_fail()
        return self.result
```

並在 `test_run_success_shows_response_and_stats` 後加入：

```python
def test_run_passes_connection_name(env):
    seed(env.store, name="訂單服務")
    window = env.make()
    window.run_button.click()
    wait_until(lambda: window.status_state.text() == "● 成功")
    assert env.service.connections == ["訂單服務"]
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_soap_service.py tests/test_entry_point.py tests/test_main_window.py -v -p no:xdist`
Expected: 新測試 FAIL（`TypeError: ... unexpected keyword argument 'recorder'`、`ImportError: cannot import name 'create_recorder'`、`connections == []`）

- [ ] **Step 3: 實作**

`src/core/soap_service.py`：import 區改為

```python
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from loguru import logger
from lxml import etree
from suds.client import Client

from src.core.xml_log import CallRecord
```

模組 docstring 改為 `WebService 呼叫：讀取 WSDL 方法、依參數呼叫方法（可交給 recorder 寫請求紀錄）、XML 排版`。在 `_param_names` 後新增：

```python
def _message_text(message) -> str:
    """suds last_sent／last_received 的 Document 轉成文字；沒有時回傳空字串"""
    if message is None:
        return ""
    if isinstance(message, bytes):
        return message.decode("utf-8", errors="replace")
    return str(message)
```

`SoapService.__init__` 與 `call` 換成：

```python
    def __init__(self, client_factory=_default_client_factory,
                 recorder: Callable[[CallRecord], None] | None = None):
        self._client_factory = client_factory
        self._recorder = recorder
        self._clients: dict[str, Client] = {}
        self._lock = threading.Lock()
```

```python
    def call(self, url: str, method: str, raw_params: str, timeout: int, *, connection: str = "") -> CallResult:
        """呼叫方法；參數數量正確時，不論成功或失敗都交給 recorder 記一筆"""
        client = self._client_for(url, timeout)
        names = _param_names(client, method)
        values = split_params(raw_params)
        if len(values) != len(names):
            raise ParamCountMismatch(expected=len(names), actual=len(values))
        client.messages.pop("tx", None)  # 避免失敗時取到上一次請求的信封
        client.messages.pop("rx", None)
        moment = datetime.now()
        started = time.perf_counter()
        try:
            result = getattr(client.service, method)(**dict(zip(names, values)))
        except Exception as err:
            self._record(client, CallRecord(
                time=moment, connection=connection, url=url, method=method, status="failed",
                elapsed=time.perf_counter() - started, size=0, error=f"{type(err).__name__}: {err}",
                params=raw_params,
            ))
            raise
        elapsed = time.perf_counter() - started
        raw = "" if result is None else str(result)
        try:
            text = format_xml(raw)
        except ValueError:
            text = raw
        call_result = CallResult(text=text, elapsed=elapsed, size=len(raw.encode("utf-8")))
        self._record(client, CallRecord(
            time=moment, connection=connection, url=url, method=method, status="success",
            elapsed=elapsed, size=call_result.size, params=raw_params, response=text,
        ))
        return call_result

    def _record(self, client: Client, record: CallRecord) -> None:
        """補上信封後交給 recorder；recorder 出錯只寫 warning，不影響呼叫結果"""
        if self._recorder is None:
            return
        try:
            self._recorder(replace(
                record, sent=_message_text(client.last_sent()), received=_message_text(client.last_received()),
            ))
        except Exception as err:
            logger.warning("寫入請求紀錄失敗：{}", err)
```

（`from dataclasses import dataclass, replace`。）

`src/ws_tool.py`：import 區加 `from src.core.xml_log import DEFAULT_XML_RETENTION_DAYS, XmlLogWriter, normalize_content  # noqa: E402`，並把 `parse_retention_days` 已在 Task 4 import。於 `setup_logging` 後新增：

```python
def create_recorder(log_dir: Path, config) -> XmlLogWriter | None:
    """依 log.xml 設定建立請求紀錄寫入器；停用時回傳 None"""
    if not config.app_xml_enabled:
        return None
    content = normalize_content(config.app_xml_content)
    if content != str(config.app_xml_content).strip().lower():
        logger.warning("log.xml.content 無法辨識（{}），改用 {}", config.app_xml_content, content)
    retention = parse_retention_days(config.app_xml_retention, DEFAULT_XML_RETENTION_DAYS)
    return XmlLogWriter(log_dir, content, retention)
```

`main()` 中 `SoapService()` 改為 `SoapService(recorder=create_recorder(log_dir, config))`。

`src/ui/main_window.py`：`_on_run_clicked` 最後一行改為

```python
        self._start(
            "run", self._service.call, url, method, params, self.timeout_spin.value(),
            connection=self.name_edit.text().strip(),
        )
```

`_start` 改為

```python
    def _start(self, kind: str, fn, *args, **kwargs) -> None:
        self._seq += 1
        tag = (kind, self._seq, self._current_uuid)
        self._pending = tag
        self._set_busy(kind)
        self._set_status("busy", "讀取中…" if kind == "load" else "執行中…")
        self._tasks[tag] = run_in_background(
            tag, fn, *args, on_success=self._on_task_succeeded, on_failure=self._on_task_failed, **kwargs,
        )
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_soap_service.py tests/test_entry_point.py tests/test_main_window.py -v -p no:xdist`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息：`執行請求時寫入 ws_xml.log：SoapService 注入 recorder，成功與失敗都記錄，依 log.xml.content 決定內容`

```bash
git add src/core/soap_service.py src/ws_tool.py src/ui/main_window.py tests/test_soap_service.py tests/test_entry_point.py tests/test_main_window.py
git commit -F .git/COMMIT_MSG_TMP
```

---

### Task 6: 查閱視窗（`src/ui/xml_log_viewer.py`）

**Files:**
- Create: `src/ui/xml_log_viewer.py`
- Modify: `src/ui/theme.py`（`_QSS` 內 `QWidget#ConsolePanel` 區塊之後）
- Test: `tests/test_xml_log_viewer.py`

**Interfaces:**
- Consumes: `CallRecord`、`XmlLogWriter`、`list_log_dates`、`read_records`（Task 2）；`run_in_background`；`XmlEditor`；`NotificationBar`；`styled_button`
- Produces:
  - `XmlLogViewer(log_dir: Path, palette: ThemePalette, parent=None)`：`resendRequested = Signal(object)`；`refresh()`、`set_palette(palette)`、`selected_record() -> CallRecord | None`
  - 公開元件：`date_combo`、`connection_combo`、`method_combo`、`search_edit`、`refresh_button`、`table`、`tabs`、`editors: dict[str, XmlEditor]`（key 為 `params/response/sent/received`）、`resend_button`、`count_label`、`notification`
  - 模組函式 `matches(record, connection: str | None, method: str | None, keyword: str) -> bool`、`connection_label(record) -> str`

- [ ] **Step 1: 寫失敗測試** — 建立 `tests/test_xml_log_viewer.py`

```python
# -*- coding: utf-8 -*-
from dataclasses import replace
from datetime import datetime

import pytest

from src.core.xml_log import CallRecord, format_record
from src.ui.theme import DARK, LIGHT
from src.ui.xml_log_viewer import TAB_FIELDS, XmlLogViewer, matches
from tests.helpers import wait_until

BASE = CallRecord(
    time=datetime(2026, 9, 26, 9, 0, 0), connection="訂單服務", url="http://h/order?wsdl", method="GetOrder",
    status="success", elapsed=0.5, size=10, params="<Req>A-001</Req>", response="<ok/>",
)
RECORDS = [
    BASE,
    replace(BASE, time=datetime(2026, 9, 26, 10, 0, 0), method="CancelOrder", params="<Req>A-002</Req>"),
    replace(BASE, time=datetime(2026, 9, 26, 11, 0, 0), connection="", url="http://h/stock?wsdl",
            method="GetStock", status="failed", error="TimeoutError: 逾時", response=""),
]


def write_log(path, records, content="params"):
    path.write_text("".join(format_record(r, content) for r in records), encoding="utf-8")


@pytest.fixture
def viewer(qapp, tmp_path):
    write_log(tmp_path / "ws_xml.log", RECORDS)
    write_log(tmp_path / "ws_xml_20260925.log", [replace(BASE, time=datetime(2026, 9, 25, 8, 0, 0))])
    window = XmlLogViewer(tmp_path, LIGHT)
    window.refresh()
    wait_until(lambda: window.table.rowCount() == 3)
    yield window
    window.close()
    window.deleteLater()


def column(viewer, index):
    return [viewer.table.item(row, index).text() for row in range(viewer.table.rowCount())]


def combo_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def test_matches_keyword_is_case_insensitive():
    assert matches(BASE, None, None, "a-001")
    assert not matches(BASE, None, None, "zzz")
    assert matches(RECORDS[2], None, None, "逾時")
    assert not matches(BASE, "http://h/stock?wsdl", None, "")


def test_lists_newest_first_with_dates(viewer):
    assert column(viewer, 0) == ["11:00:00", "10:00:00", "09:00:00"]
    assert column(viewer, 1) == ["http://h/stock?wsdl", "訂單服務", "訂單服務"]
    assert column(viewer, 3) == ["失敗", "成功", "成功"]
    assert viewer.date_combo.count() == 2
    assert viewer.count_label.text() == "共 3 筆"


def test_connection_and_method_filters(viewer):
    assert combo_items(viewer.connection_combo) == ["全部", "http://h/stock?wsdl", "訂單服務"]
    viewer.connection_combo.setCurrentText("訂單服務")
    assert combo_items(viewer.method_combo) == ["全部", "CancelOrder", "GetOrder"]
    assert column(viewer, 2) == ["CancelOrder", "GetOrder"]
    viewer.method_combo.setCurrentText("GetOrder")
    assert column(viewer, 2) == ["GetOrder"]
    assert viewer.count_label.text() == "共 1 筆（全部 3 筆）"


def test_keyword_filter(viewer):
    viewer.search_edit.setText("a-002")
    wait_until(lambda: viewer.table.rowCount() == 1)
    assert column(viewer, 2) == ["CancelOrder"]


def test_switch_date_loads_archive(viewer):
    viewer.date_combo.setCurrentIndex(1)
    wait_until(lambda: viewer.table.rowCount() == 1)
    assert column(viewer, 0) == ["08:00:00"]


def test_detail_tabs_follow_content(viewer):
    viewer.table.selectRow(2)  # 09:00 成功，params 模式
    assert viewer.editors["params"].toPlainText() == "<Req>A-001</Req>"
    visible = [viewer.tabs.isTabVisible(i) for i in range(len(TAB_FIELDS))]
    assert visible == [True, True, False, False]
    viewer.table.selectRow(0)  # 失敗：回應分頁顯示錯誤訊息
    assert viewer.editors["response"].toPlainText() == "TimeoutError: 逾時"


def test_envelope_only_record_shows_soap_tabs(qapp, tmp_path):
    write_log(tmp_path / "ws_xml.log", [replace(BASE, sent="<S/>", received="<R/>")], content="envelope")
    window = XmlLogViewer(tmp_path, LIGHT)
    window.refresh()
    wait_until(lambda: window.table.rowCount() == 1)
    assert [window.tabs.isTabVisible(i) for i in range(len(TAB_FIELDS))] == [False, False, True, True]
    assert window.tabs.currentIndex() == 2
    window.close()


def test_resend_emits_selected_record(viewer):
    emitted = []
    viewer.resendRequested.connect(emitted.append)
    viewer.table.selectRow(1)
    viewer.resend_button.click()
    assert emitted[0].method == "CancelOrder" and emitted[0].params == "<Req>A-002</Req>"


def test_empty_dir_shows_hint(qapp, tmp_path):
    window = XmlLogViewer(tmp_path, LIGHT)
    window.refresh()
    assert window.table.rowCount() == 0
    assert window.count_label.text() == "尚無請求紀錄"
    assert not window.resend_button.isEnabled()
    window.close()


def test_read_failure_shows_error(qapp, tmp_path, monkeypatch):
    write_log(tmp_path / "ws_xml.log", RECORDS)
    from src.ui import xml_log_viewer

    def boom(_path):
        raise PermissionError("拒絕存取")

    monkeypatch.setattr(xml_log_viewer, "read_records", boom)
    window = XmlLogViewer(tmp_path, LIGHT)
    window.refresh()
    wait_until(lambda: window.notification.level == "error")
    assert window.notification.level == "error" and "拒絕存取" in window.notification.text
    window.close()


def test_set_palette_updates_editors(viewer):
    viewer.set_palette(DARK)
    assert all(editor.colors == DARK.xml for editor in viewer.editors.values())
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_xml_log_viewer.py -v -p no:xdist`
Expected: FAIL（`ModuleNotFoundError: No module named 'src.ui.xml_log_viewer'`）

- [ ] **Step 3: 實作** — 建立 `src/ui/xml_log_viewer.py`

```python
# -*- coding: utf-8 -*-
"""
請求紀錄查閱視窗：依日期、連線、方法、關鍵字篩選 ws_xml.log，並可把某一筆帶回工作區
"""
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.xml_log import SECTIONS, CallRecord, list_log_dates, read_records
from src.ui.effects import styled_button
from src.ui.notification_bar import NotificationBar
from src.ui.theme import ThemePalette
from src.ui.workers import run_in_background
from src.ui.xml_editor import XmlEditor

ALL = "全部"
COLUMNS = ("時間", "連線", "方法", "狀態", "耗時")
STATUS_COLUMN = 3
STATUS_LABELS = {"success": "成功", "failed": "失敗"}
TAB_FIELDS = ("params", "response", "sent", "received")
SEARCH_DELAY_MS = 200


def connection_label(record: CallRecord) -> str:
    """連線名稱為空時以 URL 代替"""
    return record.connection or record.url


def matches(record: CallRecord, connection: str | None, method: str | None, keyword: str) -> bool:
    if connection is not None and connection_label(record) != connection:
        return False
    if method is not None and record.method != method:
        return False
    if not keyword:
        return True
    needle = keyword.casefold()
    texts = (record.params, record.response, record.sent, record.received, record.error)
    return any(needle in text.casefold() for text in texts)


def _refill(combo: QComboBox, values: list[str]) -> None:
    """重填下拉選單（第一項為「全部」），盡量保留原本的選取；過程中不發出訊號"""
    previous = combo.currentText()
    combo.blockSignals(True)
    combo.clear()
    combo.addItem(ALL)
    combo.addItems(values)
    combo.setCurrentIndex(max(combo.findText(previous), 0))
    combo.blockSignals(False)


def _selected(combo: QComboBox) -> str | None:
    return None if combo.currentIndex() <= 0 else combo.currentText()


def _caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldCaption")
    return label


class XmlLogViewer(QWidget):
    resendRequested = Signal(object)  # CallRecord

    def __init__(self, log_dir: Path, palette: ThemePalette, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("XmlLogViewer")
        self.setWindowTitle("請求紀錄")
        self.resize(1100, 680)
        self._log_dir = Path(log_dir)
        self._palette = palette
        self._records: list[CallRecord] = []
        self._visible: list[CallRecord] = []
        self._pending = None
        self._seq = 0
        self._tasks = {}  # tag -> Task，保留參照直到收到回呼
        self._build_ui()
        self._connect_signals()
        self._show_record(None)

    # ---------- 版面 ----------

    def _build_ui(self) -> None:
        self.date_combo = QComboBox()
        self.connection_combo = QComboBox()
        self.method_combo = QComboBox()
        for combo in (self.connection_combo, self.method_combo):
            combo.setMinimumWidth(160)
            combo.addItem(ALL)
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("ConsoleSearch")
        self.search_edit.setPlaceholderText("搜尋參數、回應、信封或錯誤訊息…")
        self.search_edit.setClearButtonEnabled(True)
        self.refresh_button = styled_button("重新整理", "blue", "重新讀取紀錄檔 (F5)")
        toolbar = QHBoxLayout()
        for text, widget in (("日期", self.date_combo), ("連線", self.connection_combo), ("方法", self.method_combo)):
            toolbar.addWidget(_caption(text))
            toolbar.addWidget(widget)
        toolbar.addWidget(self.search_edit, 1)
        toolbar.addWidget(self.refresh_button)

        self.notification = NotificationBar()

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("XmlLogTable")
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setShowGrid(False)

        self.tabs = QTabWidget()
        self.editors = {name: XmlEditor(self._palette.xml, read_only=True) for name in TAB_FIELDS}
        for name in TAB_FIELDS:
            self.tabs.addTab(self.editors[name], SECTIONS[name])
        self.resend_button = styled_button("帶回工作區", "primary", "把這筆的連線、方法與參數帶回主視窗（雙擊列也可以）")
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(self.tabs, 1)
        resend_row = QHBoxLayout()
        resend_row.addStretch(1)
        resend_row.addWidget(self.resend_button)
        detail_layout.addLayout(resend_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        splitter.addWidget(self.table)
        splitter.addWidget(detail)
        splitter.setSizes([1, 1])

        self.count_label = QLabel()
        self.count_label.setObjectName("Hint")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)
        layout.addLayout(toolbar)
        layout.addWidget(self.notification)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.count_label)

    def _connect_signals(self) -> None:
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DELAY_MS)
        self._search_timer.timeout.connect(self._apply_filters)
        self.search_edit.textChanged.connect(lambda _text: self._search_timer.start())
        self.date_combo.currentIndexChanged.connect(lambda _index: self._load_selected_date())
        self.connection_combo.currentIndexChanged.connect(lambda _index: self._on_connection_changed())
        self.method_combo.currentIndexChanged.connect(lambda _index: self._apply_filters())
        self.table.itemSelectionChanged.connect(lambda: self._show_record(self.selected_record()))
        self.table.itemDoubleClicked.connect(lambda _item: self._resend())
        self.resend_button.clicked.connect(self._resend)
        self.refresh_button.clicked.connect(self.refresh)
        shortcut = QShortcut(QKeySequence("F5"), self)
        shortcut.activated.connect(self.refresh)

    # ---------- 讀檔 ----------

    def refresh(self) -> None:
        """重新列出日期（保留目前選取，沒有時選最新）並讀取該日期"""
        current = self.date_combo.currentData()
        today = date.today()
        self.date_combo.blockSignals(True)
        self.date_combo.clear()
        for day, path in list_log_dates(self._log_dir):
            label = f"{day:%Y-%m-%d}" + ("（今天）" if day == today else "")
            self.date_combo.addItem(label, str(path))
        self.date_combo.setCurrentIndex(max(self.date_combo.findData(current), 0) if current else 0)
        self.date_combo.blockSignals(False)
        self._load_selected_date()

    def _load_selected_date(self) -> None:
        path = self.date_combo.currentData()
        if not path:
            self._pending = None
            self._set_records([])
            self.count_label.setText("尚無請求紀錄")
            return
        self._seq += 1
        tag = ("xml-log", self._seq)
        self._pending = tag
        self.count_label.setText("讀取中…")
        self._tasks[tag] = run_in_background(
            tag, read_records, path, on_success=self._on_loaded, on_failure=self._on_load_failed,
        )

    @Slot(object, object)
    def _on_loaded(self, tag, records) -> None:
        self._tasks.pop(tag, None)
        if tag != self._pending:
            return  # 已切換到其他日期
        self._pending = None
        self.notification.dismiss()
        self._set_records(records)

    @Slot(object, object)
    def _on_load_failed(self, tag, error) -> None:
        self._tasks.pop(tag, None)
        if tag != self._pending:
            return
        self._pending = None
        self._set_records([])
        self.notification.show_message("error", f"讀取紀錄檔失敗：{error}")

    # ---------- 篩選與顯示 ----------

    def _set_records(self, records: list[CallRecord]) -> None:
        self._records = sorted(records, key=lambda record: record.time, reverse=True)
        _refill(self.connection_combo, sorted({connection_label(record) for record in self._records}))
        self._on_connection_changed()

    def _on_connection_changed(self) -> None:
        connection = _selected(self.connection_combo)
        methods = {r.method for r in self._records if connection is None or connection_label(r) == connection}
        _refill(self.method_combo, sorted(methods))
        self._apply_filters()

    def _apply_filters(self) -> None:
        connection, method = _selected(self.connection_combo), _selected(self.method_combo)
        keyword = self.search_edit.text().strip()
        self._visible = [r for r in self._records if matches(r, connection, method, keyword)]
        self.table.setRowCount(0)
        self.table.setRowCount(len(self._visible))
        for row, record in enumerate(self._visible):
            cells = (
                record.time.strftime("%H:%M:%S"), connection_label(record), record.method,
                STATUS_LABELS.get(record.status, record.status), f"{record.elapsed:.2f} s",
            )
            for column, text in enumerate(cells):
                self.table.setItem(row, column, QTableWidgetItem(text))
        self._color_status()
        if self._records:
            total = len(self._records)
            suffix = "" if len(self._visible) == total else f"（全部 {total} 筆）"
            self.count_label.setText(f"共 {len(self._visible)} 筆{suffix}")
        if self._visible:
            self.table.selectRow(0)
        else:
            self._show_record(None)

    def _color_status(self) -> None:
        for row, record in enumerate(self._visible):
            if record.status == "failed":
                self.table.item(row, STATUS_COLUMN).setForeground(QColor(self._palette.danger))

    def selected_record(self) -> CallRecord | None:
        rows = self.table.selectionModel().selectedRows()
        return self._visible[rows[0].row()] if rows else None

    def _show_record(self, record: CallRecord | None) -> None:
        for name in TAB_FIELDS:
            text = getattr(record, name) if record else ""
            if record and name == "response" and record.status == "failed" and not text:
                text = record.error
            self.editors[name].setPlainText(text)
        visible = [bool(self.editors[name].toPlainText()) for name in TAB_FIELDS]
        if not any(visible):
            visible[0] = True
        for index, shown in enumerate(visible):
            self.tabs.setTabVisible(index, shown)
        if not visible[self.tabs.currentIndex()]:
            self.tabs.setCurrentIndex(visible.index(True))
        self.resend_button.setEnabled(record is not None)

    def _resend(self) -> None:
        record = self.selected_record()
        if record is not None:
            self.resendRequested.emit(record)

    def set_palette(self, palette: ThemePalette) -> None:
        self._palette = palette
        for editor in self.editors.values():
            editor.set_colors(palette.xml)
        self._color_status()
```

`src/ui/theme.py` 的 `_QSS` 在 `QPushButton[variant="level"] …` 這行之後加入：

```
QWidget#XmlLogViewer { background: $bg; }
QTableWidget#XmlLogTable {
    background: $surface; border: 1px solid $border; border-radius: 8px; outline: 0;
    selection-background-color: $surface_hover; selection-color: $text;
}
QHeaderView::section {
    background: $surface; color: $text_muted; border: none; border-bottom: 1px solid $border;
    padding: 4px 8px; font-weight: 600;
}
QTabWidget::pane { border: 1px solid $border; border-radius: 8px; background: $surface; top: -1px; }
QTabBar::tab { padding: 5px 14px; color: $text_muted; background: transparent; border: none; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: $text; border-bottom-color: $accent; }
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv/Scripts/python -m pytest tests/test_xml_log_viewer.py tests/test_theme.py -v -p no:xdist`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

訊息：`新增請求紀錄查閱視窗：依日期／連線／方法／關鍵字篩選，分頁顯示參數、回應與信封`

```bash
git add src/ui/xml_log_viewer.py src/ui/theme.py tests/test_xml_log_viewer.py
git commit -F .git/COMMIT_MSG_TMP
```

---

### Task 7: 主視窗整合（紀錄按鈕、F10、帶回工作區）與 README

**Files:**
- Modify: `src/ui/icons.py`（新增 `RECORD_GRADIENT`、`record_icon()`）
- Modify: `src/ui/main_window.py`（常數、`__init__`、`_build_sidebar`、`_build_shortcuts`、`_on_theme_changed`，新增 `open_xml_log_viewer`、`load_record`、`_find_connection`）
- Modify: `src/ws_tool.py`（`MainWindow(..., xml_log_dir=log_dir)`）
- Modify: `README.md`（記錄檔說明）
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `XmlLogViewer`（Task 6）、`CallRecord`（Task 2）
- Produces: `MainWindow(..., xml_log_dir: Path | None = None)`；屬性 `record_button`、`xml_log_viewer: XmlLogViewer | None`；方法 `open_xml_log_viewer()`、`load_record(record)`；常數 `RECORD_SHORTCUT = "F10"`

- [ ] **Step 1: 寫失敗測試** — `tests/test_main_window.py`

import 區加 `from datetime import datetime`、`from src.core.xml_log import CallRecord`。`env` fixture 的 `make` 改為接受 `xml_log_dir=None` 並傳給 `MainWindow(..., xml_log_dir=xml_log_dir)`：

```python
    def make(store=None, xml_log_dir=None):
        window = MainWindow(
            store or ctx.store, service, theme, ABOUT, default_timeout=30, settings_path=settings_path,
            settings=qsettings, log_buffer=log_buffer, xml_log_dir=xml_log_dir,
        )
```

檔尾加入：

```python
# ---------- 請求紀錄（F10） ----------

def make_record(**changes):
    base = CallRecord(
        time=datetime(2026, 9, 26, 9, 0), connection="正式區", url="http://prod/ws?WSDL", method="GetPOData",
        status="success", elapsed=0.1, size=5, params="<Request>old</Request>",
    )
    return replace(base, **changes)


def test_record_button_hidden_without_log_dir(env):
    window = env.make()
    assert window.record_button is None
    assert not any(sc.key() == QKeySequence("F10") for sc in window.findChildren(QShortcut))


def test_record_button_and_f10_open_viewer(env, tmp_path):
    window = env.make(xml_log_dir=tmp_path)
    assert footer_buttons(window)[-1] is window.record_button
    assert window.record_button.text() == "" and "F10" in window.record_button.toolTip()
    press_shortcut(window, "F10")
    viewer = window.xml_log_viewer
    assert viewer is not None and viewer.isVisible()
    window.record_button.click()
    assert window.xml_log_viewer is viewer  # 只建立一次


def test_footer_buttons_fit_sidebar_with_record_button(env, tmp_path):
    window = env.make(xml_log_dir=tmp_path)
    footer = window.sidebar.layout().itemAt(2).layout()
    buttons = footer_buttons(window)
    needed = sum(b.sizeHint().width() for b in buttons) + footer.spacing() * (len(buttons) - 1)
    margins = window.sidebar.layout().contentsMargins()
    assert needed <= window.sidebar.width() - margins.left() - margins.right()


def test_load_record_selects_connection_and_fills_fields(env, tmp_path):
    seed(env.store, name="測試區", url="http://test/ws?WSDL")
    target = seed(env.store, methods=("AddTwo", "GetPOData"))
    window = env.make(xml_log_dir=tmp_path)
    window.load_record(make_record())
    assert window.connection_list.current_uuid() == target
    assert window.method_combo.currentText() == "GetPOData"
    assert window.request_editor.toPlainText() == "<Request>old</Request>"
    assert window.notification.level == "info"


def test_load_record_falls_back_to_url_match(env, tmp_path):
    target = seed(env.store, name="改過名字")
    window = env.make(xml_log_dir=tmp_path)
    window.load_record(make_record(connection="舊名字", url="http://PROD/ws?WSDL"))
    assert window.connection_list.current_uuid() == target


def test_load_record_without_matching_connection_warns(env, tmp_path):
    seed(env.store)
    window = env.make(xml_log_dir=tmp_path)
    window.load_record(make_record(url="http://other/ws?WSDL"))
    assert window.notification.level == "warning"
    assert "找不到對應的連線" in window.notification.text


def test_load_record_while_busy_warns(env, tmp_path):
    seed(env.store)
    env.service.gate = threading.Event()
    window = env.make(xml_log_dir=tmp_path)
    window.run_button.click()
    window.load_record(make_record(params="<Request>new</Request>"))
    assert window.notification.level == "warning"
    assert window.request_editor.toPlainText() != "<Request>new</Request>"


def test_load_record_without_params_keeps_editor(env, tmp_path):
    seed(env.store)
    window = env.make(xml_log_dir=tmp_path)
    window.request_editor.setPlainText("<keep/>")
    window.load_record(make_record(params="", sent="<S/>"))
    assert window.request_editor.toPlainText() == "<keep/>"
    assert window.notification.level == "warning"


def test_viewer_resend_signal_calls_load_record(env, tmp_path):
    target = seed(env.store)
    window = env.make(xml_log_dir=tmp_path)
    window.open_xml_log_viewer()
    window.xml_log_viewer.resendRequested.emit(make_record())
    assert window.connection_list.current_uuid() == target


def test_theme_change_updates_viewer(env, tmp_path):
    window = env.make(xml_log_dir=tmp_path)
    window.open_xml_log_viewer()
    env.theme.set_mode(ThemeMode.DARK)
    assert window.xml_log_viewer.editors["params"].colors == DARK.xml
```

import 區另外加 `from dataclasses import replace`（原檔沒有）。

- [ ] **Step 2: 執行測試確認失敗**

Run: `.venv/Scripts/python -m pytest tests/test_main_window.py -v -p no:xdist`
Expected: 新測試 FAIL（`TypeError: MainWindow.__init__() got an unexpected keyword argument 'xml_log_dir'`）

- [ ] **Step 3: 實作**

`src/ui/icons.py` 常數區加 `RECORD_GRADIENT = ("#F59E0B", "#EA580C")`，檔尾加：

```python
def record_icon() -> QIcon:
    """請求紀錄：漸層文件與白色條列線"""
    pixmap, painter = _canvas()
    painter.setBrush(_gradient(RECORD_GRADIENT))
    painter.drawRoundedRect(QRectF(10, 4, 44, 56), 8, 8)
    pen = QPen(QColor("#FFFFFF"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    for y, end in ((18, 44), (30, 44), (42, 34)):
        painter.drawLine(QPointF(20, y), QPointF(end, y))
    painter.end()
    return QIcon(pixmap)
```

`src/ui/main_window.py`：
- import：`from src.core.xml_log import CallRecord`、`from src.ui.icons import about_icon, console_icon, record_icon, theme_icon`、`from src.ui.xml_log_viewer import XmlLogViewer`
- 常數區加 `RECORD_SHORTCUT = "F10"`
- `__init__` 參數加 `xml_log_dir: Path | None = None`（在 `log_buffer` 之後），並在 `self._log_buffer = …` 後加

```python
        self._xml_log_dir = Path(xml_log_dir) if xml_log_dir is not None else None
        self.xml_log_viewer: XmlLogViewer | None = None  # 首次按 F10 才建立
```

- `_build_sidebar`：在 `footer.addWidget(self.console_button)` 之後、`footer.addStretch(1)` 之前加

```python
        self.record_button = None
        if self._xml_log_dir is not None:
            # 只顯示圖示：既有三顆文字按鈕已接近側欄 236 px 上限
            self.record_button = styled_button("", "footer", f"請求紀錄 ({RECORD_SHORTCUT})")
            self.record_button.setIcon(record_icon())
            self.record_button.setIconSize(QSize(FOOTER_ICON_SIZE, FOOTER_ICON_SIZE))
            footer.addWidget(self.record_button)
```

- `_build_shortcuts` 第二個 for 迴圈之後加

```python
        if self._xml_log_dir is not None:
            shortcut = QShortcut(QKeySequence(RECORD_SHORTCUT), self)
            shortcut.activated.connect(self.open_xml_log_viewer)
```

- `_connect_signals` 內加 `if self.record_button is not None: self.record_button.clicked.connect(self.open_xml_log_viewer)`（放在既有 `console_button` 連線附近）
- `_on_theme_changed` 最後加 `if self.xml_log_viewer is not None: self.xml_log_viewer.set_palette(palette)`
- 在 `# ---------- 編輯器工具 ----------` 之前新增：

```python
    # ---------- 請求紀錄 ----------

    def open_xml_log_viewer(self) -> None:
        if self._xml_log_dir is None:
            return
        if self.xml_log_viewer is None:
            self.xml_log_viewer = XmlLogViewer(self._xml_log_dir, self._theme.palette, self)
            self.xml_log_viewer.resendRequested.connect(self.load_record)
        viewer = self.xml_log_viewer
        viewer.refresh()
        viewer.setWindowState(viewer.windowState() & ~Qt.WindowState.WindowMinimized)
        viewer.show()
        viewer.raise_()
        viewer.activateWindow()

    def _find_connection(self, name: str, url: str) -> Connection | None:
        """URL 相同（不分大小寫）的連線中優先取名稱也相同者"""
        key = url.strip().lower()
        same_url = [conn for conn in self._store.all() if conn.url.strip().lower() == key]
        return next((conn for conn in same_url if conn.name == name), same_url[0] if same_url else None)

    @Slot(object)
    def load_record(self, record: CallRecord) -> None:
        """查閱視窗「帶回工作區」：選取對應連線並填入方法與參數"""
        self.raise_()
        self.activateWindow()
        if self._settings_active() and not self._leave_settings():
            return
        if self._pending:
            self._notify("warning", "目前有工作進行中，請等待完成或取消後再帶回")
            return
        conn = self._find_connection(record.connection, record.url)
        if conn is None:
            self._notify("warning", f"找不到對應的連線：{record.connection or record.url}")
            return
        self.connection_list.select(conn.uuid)
        index = self.method_combo.findText(record.method)
        if index >= 0:
            self.method_combo.setCurrentIndex(index)
        else:
            self.method_combo.setEditText(record.method)
        if not record.params:
            self._notify("warning", "這筆紀錄沒有保存請求參數（log.xml.content 為 envelope），只帶回連線與方法")
            return
        self.request_editor.setPlainText(record.params)
        self.response_editor.clear()
        self._notify("info", f"已帶回 {record.method} 的請求參數，按 F5 重新執行")
```

`src/ws_tool.py` 的 `MainWindow(...)` 加 `xml_log_dir=log_dir`。

`README.md`：在主控台說明段落之後加一節：

```markdown
### 記錄檔

所有記錄檔都放在 `ws_tool.yaml` 的 `app.log.path`（預設 `app_data/logs`），每天自動歸檔為 `名稱_YYYYMMDD.log`，超過保留天數的歸檔會自動刪除。

| 檔案 | 內容 | 相關設定 |
| --- | --- | --- |
| `run.log` | `app.log.level` 以上的所有記錄 | `level`、`retention` |
| `ws_info.log`／`ws_debug.log`／`ws_error.log` | 只收該等級 | `levels`、`retention` |
| `ws_other.log` | TRACE、SUCCESS、WARNING、CRITICAL | `levels`、`retention` |
| `ws_xml.log` | 每次執行請求的參數＋回應（或 SOAP 信封） | `xml.enabled`、`xml.content`、`xml.retention` |

按 **F10** 或側欄的紀錄按鈕開啟「請求紀錄」視窗，可依日期、連線、方法與關鍵字查詢，並把某一筆帶回工作區重新執行。
```

- [ ] **Step 4: 執行全部測試與 lint**

Run: `.venv/Scripts/python -m pytest` 然後 `.venv/Scripts/ruff check src tests plugins tasks`
Expected: 全部 PASS、ruff 無錯誤

- [ ] **Step 5: 實際啟動確認**

Run: `uv run python src/ws_tool.py`，執行一次請求後按 F10，確認紀錄出現、帶回工作區可用，且 `src/app_data/logs/` 下有 `run.log`、`ws_info.log`、`ws_debug.log`、`ws_xml.log`。

- [ ] **Step 6: Commit**

訊息：`主視窗加入請求紀錄按鈕與 F10 快捷鍵，查閱視窗可把紀錄帶回工作區；README 補上記錄檔說明`

```bash
git add src/ui/icons.py src/ui/main_window.py src/ws_tool.py README.md tests/test_main_window.py
git commit -F .git/COMMIT_MSG_TMP
```
