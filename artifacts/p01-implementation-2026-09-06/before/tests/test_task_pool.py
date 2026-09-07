import time
from threading import Event, get_ident

from PySide6.QtCore import QRunnable, QThreadPool
from PySide6.QtWidgets import QApplication

from insar_pilot.ui.task_pool import BackgroundTaskPool


def _qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _wait_until(predicate, timeout: float = 2.0) -> bool:
    app = _qt_app()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    app.processEvents()
    return bool(predicate())


def test_task_pool_delivers_result_on_gui_thread():
    _qt_app()
    gui_thread_id = get_ident()
    callback_thread_ids: list[int] = []
    results: list[int] = []
    finished: list[bool] = []
    pool = BackgroundTaskPool(max_thread_count=2)

    pool.submit(
        lambda: 42,
        name="answer",
        on_success=lambda value: (results.append(value), callback_thread_ids.append(get_ident())),
        on_finished=lambda: finished.append(True),
    )

    assert _wait_until(lambda: bool(finished))
    assert results == [42]
    assert callback_thread_ids == [gui_thread_id]
    assert pool.active_task_count == 0
    assert pool.shutdown(100)


def test_task_pool_reports_exceptions_and_finishes():
    failures: list[str] = []
    finished: list[bool] = []
    pool = BackgroundTaskPool()

    def fail() -> None:
        raise RuntimeError("network exploded")

    pool.submit(
        fail,
        name="failing check",
        on_failure=failures.append,
        on_finished=lambda: finished.append(True),
    )

    assert _wait_until(lambda: bool(finished))
    assert failures == ["RuntimeError: network exploded"]
    assert pool.active_task_count == 0
    assert pool.shutdown(100)


def test_task_pool_can_cancel_a_queued_task_without_running_it():
    blocker_started = Event()
    release_blocker = Event()
    second_ran = Event()
    second_finished: list[bool] = []
    pool = BackgroundTaskPool(max_thread_count=1)

    def block_worker() -> str:
        blocker_started.set()
        release_blocker.wait(1.0)
        return "released"

    pool.submit(block_worker, name="blocker")
    assert blocker_started.wait(1.0)
    queued = pool.submit(
        lambda: second_ran.set(),
        name="queued",
        on_finished=lambda: second_finished.append(True),
    )

    pool.cancel(queued)
    release_blocker.set()

    assert _wait_until(lambda: bool(second_finished))
    assert queued.is_cancelled
    assert queued.is_done
    assert not second_ran.is_set()
    assert pool.shutdown(1000)


def test_task_pool_suppresses_a_running_task_result_after_cancel():
    started = Event()
    release = Event()
    results: list[str] = []
    finished: list[bool] = []
    pool = BackgroundTaskPool()

    def delayed_result() -> str:
        started.set()
        release.wait(1.0)
        return "stale"

    handle = pool.submit(
        delayed_result,
        name="stale check",
        on_success=results.append,
        on_finished=lambda: finished.append(True),
    )
    assert started.wait(1.0)

    pool.cancel(handle)
    release.set()

    assert _wait_until(lambda: bool(finished))
    assert results == []
    assert handle.is_cancelled
    assert pool.shutdown(100)


def test_owned_pool_shutdown_does_not_wait_for_qt_global_pool():
    global_started = Event()
    release_global = Event()

    class GlobalBlocker(QRunnable):
        def run(self) -> None:
            global_started.set()
            release_global.wait(1.0)

    global_pool = QThreadPool.globalInstance()
    global_pool.start(GlobalBlocker())
    assert global_started.wait(1.0)
    owned_pool = BackgroundTaskPool()

    started = time.monotonic()
    assert owned_pool.shutdown(20)
    elapsed = time.monotonic() - started

    release_global.set()
    assert global_pool.waitForDone(1000)
    assert elapsed < 0.25
