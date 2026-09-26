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
