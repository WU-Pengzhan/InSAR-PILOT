from __future__ import annotations

from datetime import datetime, timezone
from threading import Event
from time import monotonic

from PySide6.QtWidgets import QApplication

from insar_pilot.application.search import SearchApplicationService
from insar_pilot.domain.search import (
    ProviderCapability,
    ProviderDescriptor,
    RemoteSARProduct,
    SearchCapability,
    SearchPage,
    SearchRequest,
    SupportReport,
)
from insar_pilot.providers.sar import ProviderRegistry
from insar_pilot.ui.features.search.task_runner import SearchTaskRunner


def _qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _request(name: str) -> SearchRequest:
    instant = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return SearchRequest(
        mission="SENTINEL-1",
        product_type="SLC",
        start_time=instant,
        end_time=instant,
        aoi_wkt=f"POLYGON(({name} 0,1 0,1 1,{name} 0))",
    )


def _product(product_id: str) -> RemoteSARProduct:
    return RemoteSARProduct(
        remote_product_id=product_id,
        provider_id="blocking-fake",
        mission="SENTINEL-1",
        platform="SENTINEL-1A",
        product_type="SLC",
        acquisition_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class _BlockingProvider:
    descriptor = ProviderDescriptor(
        provider_id="blocking-fake",
        display_name="Blocking fake",
        capabilities=frozenset({ProviderCapability.SEARCH}),
        search_capabilities=(SearchCapability("SENTINEL-1", ("SLC",)),),
    )

    def __init__(self) -> None:
        self.old_started = Event()
        self.release_old = Event()
        self.cancel_started = Event()
        self.release_cancel = Event()

    def supports(self, _request: SearchRequest) -> SupportReport:
        return SupportReport.supported_request()

    def search(self, request: SearchRequest) -> SearchPage:
        if "OLD" in request.aoi_wkt:
            self.old_started.set()
            self.release_old.wait(2)
            product_id = "OLD"
        elif "CANCEL" in request.aoi_wkt:
            self.cancel_started.set()
            self.release_cancel.wait(2)
            product_id = "CANCEL"
        else:
            product_id = "NEW"
        return SearchPage(
            items=(_product(product_id),),
            provider_id=self.descriptor.provider_id,
            page=1,
            page_size=100,
        )


def _runner(provider: _BlockingProvider) -> SearchTaskRunner:
    registry = ProviderRegistry()
    registry.register(provider)
    return SearchTaskRunner(SearchApplicationService(registry), max_thread_count=2)


def _wait_until(predicate, timeout: float = 2.0) -> bool:
    app = _qt_app()
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
    return False


def test_late_older_result_cannot_replace_a_newer_search():
    provider = _BlockingProvider()
    runner = _runner(provider)
    delivered: list[str] = []
    runner.succeeded.connect(lambda _request_id, page: delivered.append(page.items[0].remote_product_id))

    runner.submit(_request("OLD"))
    assert provider.old_started.wait(1)
    runner.submit(_request("NEW"))
    assert _wait_until(lambda: delivered == ["NEW"])

    provider.release_old.set()
    assert _wait_until(lambda: runner._pool.active_task_count == 0)  # noqa: SLF001
    assert delivered == ["NEW"]
    assert runner.shutdown()


def test_cancel_suppresses_a_running_provider_result():
    provider = _BlockingProvider()
    runner = _runner(provider)
    delivered: list[str] = []
    cancelled: list[int] = []
    runner.succeeded.connect(lambda _request_id, page: delivered.append(page.items[0].remote_product_id))
    runner.cancelled.connect(cancelled.append)

    request_id = runner.submit(_request("CANCEL"))
    assert provider.cancel_started.wait(1)
    runner.cancel_current()
    provider.release_cancel.set()

    assert _wait_until(lambda: runner._pool.active_task_count == 0)  # noqa: SLF001
    assert cancelled == [request_id]
    assert delivered == []
    assert runner.shutdown()
