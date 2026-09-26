# -*- coding: utf-8 -*-
import threading

import pytest
from loguru import logger

from src.core.log_buffer import LEVELS, LogBuffer, normalize_level


@pytest.fixture
def make_buffer():
    handler_ids = []

    def make(capacity=100):
        buffer = LogBuffer(capacity)
        handler_ids.append(buffer.attach())
        return buffer

    yield make
    for handler_id in handler_ids:
        logger.remove(handler_id)


def test_levels_are_loguru_builtin_levels_in_severity_order():
    assert LEVELS == ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")


@pytest.mark.parametrize("name,no", [
    ("TRACE", 5), ("DEBUG", 10), ("INFO", 20), ("SUCCESS", 25), ("WARNING", 30), ("ERROR", 40), ("CRITICAL", 50),
])
def test_builtin_levels_are_kept(name, no):
    assert normalize_level(name, no) == name


@pytest.mark.parametrize("no,expected", [(35, "WARNING"), (1, "TRACE"), (60, "CRITICAL"), (22, "INFO")])
def test_custom_levels_map_to_highest_builtin_not_above(no, expected):
    assert normalize_level("NOTICE", no) == expected


def test_captures_every_level_including_trace(make_buffer):
    buffer = make_buffer()
    logger.trace("t")
    logger.debug("d")
    logger.info("i")
    logger.success("s")
    logger.warning("w")
    logger.error("e")
    logger.critical("c")
    entries = buffer.snapshot()
    assert [e.level for e in entries] == list(LEVELS)
    assert [e.message for e in entries] == ["t", "d", "i", "s", "w", "e", "c"]
    assert [e.seq for e in entries] == sorted(e.seq for e in entries)
    assert all(e.time.tzinfo is not None for e in entries)


def test_message_is_formatted_with_arguments(make_buffer):
    buffer = make_buffer()
    logger.info("讀取 WSDL · URL={}", "http://x/ws?WSDL")
    assert buffer.snapshot()[-1].message == "讀取 WSDL · URL=http://x/ws?WSDL"


def test_exception_traceback_is_appended(make_buffer):
    buffer = make_buffer()
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("爆炸")
    message = buffer.snapshot()[-1].message
    assert message.startswith("爆炸\nTraceback")
    assert message.endswith("ZeroDivisionError: division by zero")


def test_oldest_entries_dropped_over_capacity(make_buffer):
    buffer = make_buffer(capacity=3)
    for i in range(5):
        logger.info("m{}", i)
    assert [e.message for e in buffer.snapshot()] == ["m2", "m3", "m4"]


def test_clear_empties_buffer(make_buffer):
    buffer = make_buffer()
    logger.info("x")
    buffer.clear()
    assert buffer.snapshot() == []


def test_listener_receives_entries_until_removed(make_buffer):
    buffer = make_buffer()
    received = []
    buffer.add_listener(received.append)
    logger.info("a")
    buffer.remove_listener(received.append)
    logger.info("b")
    assert [e.message for e in received] == ["a"]


def test_failing_listener_does_not_break_logging(make_buffer):
    buffer = make_buffer()
    received = []

    def broken(_entry):
        raise ValueError("listener 壞掉")

    buffer.add_listener(broken)
    buffer.add_listener(received.append)
    logger.info("仍然記錄")
    assert [e.message for e in buffer.snapshot()] == ["仍然記錄"]
    assert [e.message for e in received] == ["仍然記錄"]


def test_concurrent_writes_are_not_lost(make_buffer):
    buffer = make_buffer(capacity=10_000)

    def work(n):
        for i in range(250):
            logger.info("t{}-{}", n, i)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    entries = buffer.snapshot()
    assert len(entries) == 1000
    assert len({e.seq for e in entries}) == 1000
