"""Qt bridge for cancellable, latest-request-wins SAR searches."""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import QObject, Signal, Slot

from insar_pilot.application.search import SearchApplicationService
from insar_pilot.domain.search import SearchPage, SearchRequest
from insar_pilot.ui.task_pool import BackgroundTaskPool, TaskHandle


class SearchTaskRunner(QObject):
    """Execute the synchronous application service outside the GUI thread."""

    started = Signal(int)
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int)

    def __init__(
        self,
        service: SearchApplicationService,
        parent: QObject | None = None,
        *,
        max_thread_count: int = 2,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._pool = BackgroundTaskPool(self, max_thread_count=max_thread_count)
        self._next_request_id = 0
        self._current_request_id: int | None = None
        self._current_handle: TaskHandle | None = None

    @property
    def current_request_id(self) -> int | None:
        return self._current_request_id

    def submit(self, request: SearchRequest, *, provider_id: str | None = None) -> int:
        """Start a search and invalidate any result from the preceding request."""

        self._cancel_current(notify=False)
        self._next_request_id += 1
        request_id = self._next_request_id
        self._current_request_id = request_id
        self.started.emit(request_id)

        def execute() -> SearchPage:
            return self._service.search(request, provider_id=provider_id)

        handle = self._pool.submit(
            execute,
            name=f"sar-search-{request_id}",
            on_success=partial(self._deliver_success, request_id),
            on_failure=partial(self._deliver_failure, request_id),
        )
        self._current_handle = handle
        return request_id

    def cancel_current(self) -> None:
        """Cancel or suppress delivery for the active request."""

        self._cancel_current(notify=True)

    def shutdown(self, wait_ms: int = 300) -> bool:
        """Cancel owned work and wait for only a bounded interval."""

        self._current_request_id = None
        self._current_handle = None
        return self._pool.shutdown(wait_ms)

    def _cancel_current(self, *, notify: bool) -> None:
        request_id = self._current_request_id
        handle = self._current_handle
        self._current_request_id = None
        self._current_handle = None
        if handle is not None:
            self._pool.cancel(handle)
        if notify and request_id is not None:
            self.cancelled.emit(request_id)

    @Slot(int, object)
    def _deliver_success(self, request_id: int, result: object) -> None:
        if request_id != self._current_request_id or not isinstance(result, SearchPage):
            return
        self._current_request_id = None
        self._current_handle = None
        self.succeeded.emit(request_id, result)

    @Slot(int, str)
    def _deliver_failure(self, request_id: int, message: str) -> None:
        if request_id != self._current_request_id:
            return
        self._current_request_id = None
        self._current_handle = None
        self.failed.emit(request_id, message)
