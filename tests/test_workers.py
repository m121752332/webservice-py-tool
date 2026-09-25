# -*- coding: utf-8 -*-
import threading
import time

from PySide6.QtCore import QObject, Slot

from src.ui.workers import run_in_background
from tests.helpers import wait_until


class Receiver(QObject):
    def __init__(self):
        super().__init__()
        self.successes = []
        self.failures = []
        self.threads = []

    @Slot(object, object)
    def on_success(self, tag, value):
        self.successes.append((tag, value))
        self.threads.append(threading.get_ident())

    @Slot(object, object)
    def on_failure(self, tag, error):
        self.failures.append((tag, error))
        self.threads.append(threading.get_ident())


def test_success_is_delivered_on_main_thread(qapp):
    receiver = Receiver()
    task = run_in_background(("run", 1), lambda a, b: a + b, 2, 3,
                             on_success=receiver.on_success, on_failure=receiver.on_failure)
    wait_until(lambda: receiver.successes)
    assert receiver.successes == [(("run", 1), 5)]
    assert receiver.failures == []
    assert receiver.threads == [threading.get_ident()]
    assert task is not None


def test_function_runs_off_main_thread(qapp):
    receiver = Receiver()
    task = run_in_background("tag", threading.get_ident,
                             on_success=receiver.on_success, on_failure=receiver.on_failure)
    wait_until(lambda: receiver.successes)
    assert receiver.successes[0][1] != threading.get_ident()
    assert task is not None


def test_exception_is_delivered_as_failure(qapp):
    def boom():
        raise RuntimeError("壞了")

    receiver = Receiver()
    task = run_in_background(("load", 7), boom, on_success=receiver.on_success, on_failure=receiver.on_failure)
    wait_until(lambda: receiver.failures)
    tag, error = receiver.failures[0]
    assert tag == ("load", 7)
    assert isinstance(error, RuntimeError) and str(error) == "壞了"
    assert receiver.successes == []
    assert receiver.threads == [threading.get_ident()]
    assert task is not None


def test_keyword_arguments_are_forwarded(qapp):
    receiver = Receiver()
    task = run_in_background("kw", lambda *, x: x * 2, x=21,
                             on_success=receiver.on_success, on_failure=receiver.on_failure)
    wait_until(lambda: receiver.successes)
    assert receiver.successes == [("kw", 42)]
    assert task is not None


def test_blocked_task_does_not_prevent_new_task_from_running(qapp):
    """每個 Task 都在自己的執行緒上執行，不共用全域執行緒池，因此一個卡住的
    工作（例如被取消但仍在等逾時的請求）不會讓後續工作排隊等待（F2b）"""
    gate = threading.Event()
    receiver = Receiver()

    def blocker():
        gate.wait(5)
        return "blocked-done"

    blocked_task = run_in_background("blocked", blocker,
                                     on_success=receiver.on_success, on_failure=receiver.on_failure)
    try:
        start = time.monotonic()
        quick_task = run_in_background("quick", lambda: "quick-done",
                                       on_success=receiver.on_success, on_failure=receiver.on_failure)
        wait_until(lambda: any(tag == "quick" for tag, _ in receiver.successes), timeout=2.0)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0
        assert quick_task is not None
    finally:
        gate.set()
        wait_until(lambda: any(tag == "blocked" for tag, _ in receiver.successes))
    assert blocked_task is not None
