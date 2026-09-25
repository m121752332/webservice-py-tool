# -*- coding: utf-8 -*-
"""
背景工作：在執行緒池執行函式，結果以訊號送回主執行緒
"""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class TaskSignals(QObject):
    succeeded = Signal(object, object)  # tag, 回傳值
    failed = Signal(object, object)  # tag, 例外


class Task(QRunnable):
    def __init__(self, tag, fn, args, kwargs):
        super().__init__()
        self.signals = TaskSignals()
        self._tag = tag
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as err:  # 所有錯誤都交給 UI 顯示
            self.signals.failed.emit(self._tag, err)
            return
        self.signals.succeeded.emit(self._tag, result)


def run_in_background(tag, fn, *args, on_success, on_failure, **kwargs) -> Task:
    """呼叫端需保留回傳的 Task 參照，直到收到成功或失敗回呼"""
    task = Task(tag, fn, args, kwargs)
    task.signals.succeeded.connect(on_success)
    task.signals.failed.connect(on_failure)
    QThreadPool.globalInstance().start(task)
    return task
