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


def test_writer_round_trips_crlf_and_unicode_line_separators(tmp_path):
    """content 中若含 \\r\\n 或 U+2028 等特殊換行字元，寫入再讀回應保持原樣（不應變成雙換行或被截斷）"""
    record = replace(RECORD, params="a\r\nb", response="x y")
    writer = XmlLogWriter(tmp_path, "params", 30, clock=lambda: datetime(2026, 9, 26, 9))
    writer(record)
    writer.close()
    result = read_records(tmp_path / "ws_xml.log")[0]
    assert result.params == "a\nb"
    assert result.response == "x y"


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
