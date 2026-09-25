# -*- coding: utf-8 -*-
import threading

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
