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
