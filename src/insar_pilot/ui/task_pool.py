"""Owned Qt thread pool for short, callable-based background tasks.

Long-running or progress-producing work belongs on a dedicated ``QThread`` or
``QProcess``.  This pool is intentionally limited to bounded operations such
as credential and API-key checks.
"""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot


class TaskHandle(QObject):
    """Signals and cancellation state for one pooled callable."""

    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, name: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self._cancelled = Event()
        self._done = Event()

    def cancel(self) -> None:
        """Suppress delivery of this task's result.

        Python network calls cannot be interrupted safely mid-request. Their
        configured request timeout remains the hard execution bound.
        """

        self._cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def is_done(self) -> bool:
        return self._done.is_set()

    def _mark_done(self) -> None:
        self._done.set()


class _CallableRunnable(QRunnable):
    def __init__(self, function: Callable[[], Any], handle: TaskHandle) -> None:
        super().__init__()
        # Keeping ownership in BackgroundTaskPool makes tryTake() safe and
        # avoids Qt deleting a runnable while Python still references it.
        self.setAutoDelete(False)
        self.function = function
        self.handle = handle

    @Slot()
    def run(self) -> None:
        try:
            if self.handle.is_cancelled:
                return
            result = self.function()
            if not self.handle.is_cancelled:
                self.handle.succeeded.emit(result)
        except Exception as exc:
            if not self.handle.is_cancelled:
                self.handle.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self._finish()

    def finish_without_running(self) -> None:
        """Complete a queued runnable removed before its first execution."""

        self._finish()

    def _finish(self) -> None:
        if self.handle.is_done:
            return
        self.handle._mark_done()
        self.handle.finished.emit()


class BackgroundTaskPool(QObject):
    """Application-owned pool with per-task cancellation and bounded shutdown."""

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        max_thread_count: int = 3,
    ) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max(1, int(max_thread_count)))
        self._tasks: dict[TaskHandle, _CallableRunnable] = {}

    @property
    def max_thread_count(self) -> int:
        return self._pool.maxThreadCount()

    @property
    def active_task_count(self) -> int:
        return sum(not handle.is_done for handle in self._tasks)

    def submit(
        self,
        function: Callable[[], Any],
        *,
        name: str,
        on_success: Callable[[object], None] | None = None,
        on_failure: Callable[[str], None] | None = None,
        on_finished: Callable[[], None] | None = None,
    ) -> TaskHandle:
        """Connect callbacks before scheduling and return an explicit handle."""

        handle = TaskHandle(name, self)
        runnable = _CallableRunnable(function, handle)
        self._tasks[handle] = runnable
        queued = Qt.ConnectionType.QueuedConnection
        if on_success is not None:
            handle.succeeded.connect(on_success, queued)
        if on_failure is not None:
            handle.failed.connect(on_failure, queued)
        if on_finished is not None:
            handle.finished.connect(on_finished, queued)
        handle.finished.connect(self._forget_finished_task, queued)
        self._pool.start(runnable)
        return handle

    def cancel(self, handle: TaskHandle) -> None:
        """Cancel one queued/running task and suppress any later result."""

        runnable = self._tasks.get(handle)
        if runnable is None or handle.is_done:
            return
        handle.cancel()
        if self._pool.tryTake(runnable):
            runnable.finish_without_running()

    def cancel_all(self) -> None:
        for handle in tuple(self._tasks):
            self.cancel(handle)

    def shutdown(self, wait_ms: int = 300) -> bool:
        """Cancel pending work and wait only for this pool, never Qt's global pool."""

        self.cancel_all()
        return self._pool.waitForDone(max(0, int(wait_ms)))

    @Slot()
    def _forget_finished_task(self) -> None:
        handle = self.sender()
        if isinstance(handle, TaskHandle):
            self._tasks.pop(handle, None)
