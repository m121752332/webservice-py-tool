# -*- coding: utf-8 -*-
"""
背景工作：在獨立的 daemon 執行緒執行函式，結果以訊號送回主執行緒

不使用 QThreadPool.globalInstance()：Qt 在應用程式關閉時會等待全域執行緒池裡的
工作全部結束（可能長達逾時秒數），導致視窗關閉後行程仍留在背景。daemon 執行緒
不會阻擋行程結束，且逐一建立/結束，不會有全域執行緒池被卡滿的問題。
"""
import threading

from PySide6.QtCore import QObject, Signal


class TaskSignals(QObject):
    succeeded = Signal(object, object)  # tag, 回傳值
    failed = Signal(object, object)  # tag, 例外


class Task:
    def __init__(self, tag, fn, args, kwargs):
        self.signals = TaskSignals()
        self._tag = tag
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, daemon=True, name=f"ws-task-{self._tag!r}")
        self.thread.start()

    def join(self, timeout: float | None = None) -> None:
        """測試用：等待背景執行緒結束"""
        if self.thread is not None:
            self.thread.join(timeout)

    def _run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as err:  # 所有錯誤都交給 UI 顯示
            self._emit(self.signals.failed, self._tag, err)
            return
        self._emit(self.signals.succeeded, self._tag, result)

    @staticmethod
    def _emit(signal: Signal, tag, payload) -> None:
        try:
            signal.emit(tag, payload)
        except RuntimeError:
            # 應用程式關閉過程中，訊號來源（QObject）可能已被刪除，忽略即可
            pass


def run_in_background(tag, fn, *args, on_success, on_failure, **kwargs) -> Task:
    """呼叫端需保留回傳的 Task 參照，直到收到成功或失敗回呼"""
    task = Task(tag, fn, args, kwargs)
    task.signals.succeeded.connect(on_success)
    task.signals.failed.connect(on_failure)
    task.start()
    return task
