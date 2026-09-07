from __future__ import annotations

from datetime import datetime, timezone
from threading import get_ident
from time import monotonic

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from insar_pilot.application.search import SearchApplicationService
from insar_pilot.domain.search import (
    ProviderCapability,
    ProviderDescriptor,
    RemoteSARProduct,
    SearchCapability,
    SearchFilter,
    SearchFilterCapability,
    SearchPage,
    SearchPagination,
    SearchRequest,
    SupportReport,
)
from insar_pilot.providers.sar import ProviderRegistry
from insar_pilot.ui.features.search.inspector import ProductInspector
from insar_pilot.ui.features.search.presenter import SearchPresenter
from insar_pilot.ui.features.search.workspace import SearchViewState, SearchWorkspace
from insar_pilot.ui.workbench import WorkbenchWindow


def _qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


SENTINEL_CAPABILITY = SearchCapability(
    mission="SENTINEL-1",
    product_types=("SLC",),
    platforms=("SENTINEL-1A", "SENTINEL-1B", "SENTINEL-1C", "SENTINEL-1D"),
    filters=(
        SearchFilterCapability(
            SearchFilter.ORBIT_DIRECTION,
            choices=("ASCENDING", "DESCENDING"),
        ),
        SearchFilterCapability(SearchFilter.RELATIVE_ORBIT, minimum=1, maximum=175),
        SearchFilterCapability(
            SearchFilter.POLARIZATIONS,
            choices=("VV", "VH", "VV+VH"),
        ),
        SearchFilterCapability(SearchFilter.FREQUENCY_BANDS, choices=("C",)),
    ),
    pagination=SearchPagination(default_page_size=100, max_page_size=1000),
)


class _FakeRunner(QObject):
    succeeded = Signal(int, object)
    failed = Signal(int, str)
    cancelled = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[SearchRequest] = []
        self.current_id: int | None = None
        self.cancelled_ids: list[int] = []

    def submit(self, request: SearchRequest) -> int:
        self.requests.append(request)
        self.current_id = len(self.requests)
        return self.current_id

    def cancel_current(self) -> None:
        if self.current_id is not None:
            request_id = self.current_id
            self.current_id = None
            self.cancelled_ids.append(request_id)
            self.cancelled.emit(request_id)


class _CapabilityProvider:
    def __init__(
        self,
        provider_id: str,
        capability: SearchCapability,
        *,
        provider_capabilities: frozenset[ProviderCapability] | None = None,
    ) -> None:
        self.descriptor = ProviderDescriptor(
            provider_id=provider_id,
            display_name=provider_id,
            capabilities=provider_capabilities or frozenset({ProviderCapability.SEARCH}),
            search_capabilities=(capability,),
        )

    def supports(self, request: SearchRequest) -> SupportReport:
        return self.descriptor.search_capabilities[0].supports(request)

    def search(self, request: SearchRequest) -> SearchPage:
        return SearchPage((), self.descriptor.provider_id, request.page, request.page_size)


def _product(product_id: str, offset: float) -> RemoteSARProduct:
    return RemoteSARProduct(
        remote_product_id=product_id,
        provider_id="fake",
        mission="SENTINEL-1",
        platform="SENTINEL-1A",
        product_type="SLC",
        acquisition_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        footprint={
            "type": "Polygon",
            "coordinates": [
                [
                    [offset, 0],
                    [offset + 1, 0],
                    [offset + 1, 1],
                    [offset, 1],
                    [offset, 0],
                ]
            ],
        },
    )


def _presenter(
    *providers: _CapabilityProvider,
) -> tuple[SearchWorkspace, ProductInspector, _FakeRunner, SearchPresenter]:
    _qt_app()
    registry = ProviderRegistry()
    for provider in providers or (_CapabilityProvider("fake", SENTINEL_CAPABILITY),):
        registry.register(provider)
    service = SearchApplicationService(registry)
    workspace = SearchWorkspace()
    inspector = ProductInspector()
    runner = _FakeRunner()
    presenter = SearchPresenter(workspace, inspector, runner, service)  # type: ignore[arg-type]
    return workspace, inspector, runner, presenter


def test_search_builds_domain_request_and_moves_through_loading_and_results():
    workspace, _inspector, runner, presenter = _presenter()
    workspace.aoi_edit.setText("100,20,101,21")
    workspace.platform_combo.setCurrentIndex(1)
    workspace.polarization_combo.setCurrentText("VV+VH")
    workspace.frequency_band_combo.setCurrentText("C")

    workspace.search_button.click()

    request = runner.requests[0]
    assert request.aoi_wkt == "POLYGON((100 20,101 20,101 21,100 21,100 20))"
    assert request.platforms == ("SENTINEL-1A",)
    assert request.polarizations == ("VV", "VH")
    assert request.frequency_bands == ("C",)
    assert workspace.state == SearchViewState.LOADING
    assert workspace.cancel_button.isVisibleTo(workspace)

    products = (_product("P1", 100), _product("P2", 102))
    revision = workspace.map_view.batch_revision
    runner.succeeded.emit(presenter.active_request_id, SearchPage(products, "fake", 1, 100))

    assert workspace.state == SearchViewState.RESULTS
    assert workspace.results_model.rowCount() == 2
    assert workspace.map_view.product_ids == ("P1", "P2")
    assert workspace.map_view.batch_revision == revision + 1


def test_empty_error_and_cancel_states_are_explicit():
    workspace, _inspector, runner, presenter = _presenter()
    workspace.search_button.click()
    assert workspace.state == SearchViewState.ERROR

    workspace.aoi_edit.setText("0,0,1,1")
    workspace.search_button.click()
    runner.succeeded.emit(presenter.active_request_id, SearchPage((), "fake", 1, 100))
    assert workspace.state == SearchViewState.NO_RESULTS

    workspace.search_button.click()
    workspace.cancel_button.click()
    assert workspace.state == SearchViewState.EMPTY


def test_table_map_and_inspector_share_product_id_selection():
    workspace, inspector, runner, presenter = _presenter()
    workspace.aoi_edit.setText("0,0,1,1")
    workspace.search_button.click()
    products = (_product("P1", 0), _product("P2", 2))
    runner.succeeded.emit(presenter.active_request_id, SearchPage(products, "fake", 1, 100))

    workspace.results_view.selectRow(0)
    assert inspector.product_id == "P1"
    assert workspace.map_view.selected_product_id == "P1"

    workspace.map_view.productSelected.emit("P2")
    current = workspace.results_model.result_at(workspace.results_view.currentIndex())
    assert current is not None
    assert current.remote_product_id == "P2"
    assert inspector.product_id == "P2"
    assert workspace.map_view.selected_product_id == "P2"


def test_advanced_filters_and_inspector_view_start_collapsed():
    workspace, inspector, _runner, _presenter_instance = _presenter()

    assert workspace.advanced_filters.content.isHidden()
    assert inspector.stack.currentIndex() == 0


class _ImmediateProvider:
    descriptor = ProviderDescriptor(
        provider_id="fake",
        display_name="Fake",
        capabilities=frozenset({ProviderCapability.SEARCH}),
        search_capabilities=(SENTINEL_CAPABILITY,),
    )

    def __init__(self) -> None:
        self.worker_thread_id: int | None = None

    def supports(self, _request: SearchRequest) -> SupportReport:
        return SENTINEL_CAPABILITY.supports(_request)

    def search(self, _request: SearchRequest) -> SearchPage:
        self.worker_thread_id = get_ident()
        return SearchPage((_product("P1", 0),), "fake", 1, 100)


def test_workbench_connects_application_service_without_using_the_gui_thread():
    app = _qt_app()
    provider = _ImmediateProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    window = WorkbenchWindow(search_service=SearchApplicationService(registry))
    window.search_workspace.aoi_edit.setText("0,0,1,1")

    gui_thread_id = get_ident()
    window.search_workspace.search_button.click()
    deadline = monotonic() + 2
    while window.search_workspace.state == SearchViewState.LOADING and monotonic() < deadline:
        app.processEvents()

    assert window.search_workspace.state == SearchViewState.RESULTS
    assert provider.worker_thread_id is not None
    assert provider.worker_thread_id != gui_thread_id
    window.search_workspace.results_view.selectRow(0)
    assert window.inspector_dock.isHidden()
    window.close()


def test_fake_registry_drives_mission_product_platform_and_filter_controls():
    nisar = _CapabilityProvider(
        "fake-nisar",
        SearchCapability(
            mission="NISAR",
            product_types=("RSLC",),
            platforms=("NISAR",),
            filters=(
                SearchFilterCapability(SearchFilter.FREQUENCY_BANDS, choices=("L", "S")),
            ),
            pagination=SearchPagination(default_page_size=25, max_page_size=100),
        ),
    )
    alos = _CapabilityProvider(
        "fake-alos",
        SearchCapability(
            mission="ALOS",
            product_types=("SLC",),
            platforms=("ALOS-2",),
            pagination=SearchPagination(default_page_size=50, max_page_size=100),
        ),
    )
    workspace, _inspector, runner, _presenter_instance = _presenter(nisar, alos)

    assert [workspace.mission_combo.itemData(index) for index in range(2)] == ["NISAR", "ALOS"]
    assert workspace.product_type_combo.currentData() == "RSLC"
    assert workspace.product_type_combo.findData("GSLC") == -1
    assert workspace.platform_combo.itemData(1) == "NISAR"
    assert workspace.frequency_band_combo.findData("L") >= 0
    assert workspace.orbit_direction_combo.isHidden()

    workspace.mission_combo.setCurrentIndex(1)
    assert workspace.product_type_combo.currentData() == "SLC"
    assert workspace.platform_combo.itemData(1) == "ALOS-2"
    assert workspace.frequency_band_combo.isHidden()
    assert runner.requests == []


def test_empty_registry_disables_search_without_inventing_gui_options():
    _qt_app()
    service = SearchApplicationService(ProviderRegistry())
    empty_workspace = SearchWorkspace()
    empty_runner = _FakeRunner()
    presenter = SearchPresenter(
        empty_workspace,
        ProductInspector(),
        empty_runner,  # type: ignore[arg-type]
        service,
    )

    assert empty_workspace.mission_combo.count() == 0
    assert empty_workspace.product_type_combo.count() == 0
    assert not empty_workspace.search_button.isEnabled()
    assert "provider" in empty_workspace.status_label.text().lower()
    assert empty_runner.requests == []
    assert presenter.active_request_id is None


def test_capability_change_cancels_loading_and_stale_product_is_not_searchable():
    nisar = _CapabilityProvider("fake-nisar", SearchCapability("NISAR", ("RSLC",), ("NISAR",)))
    alos = _CapabilityProvider("fake-alos", SearchCapability("ALOS", ("SLC",), ("ALOS-2",)))
    workspace, _inspector, runner, _presenter_instance = _presenter(nisar, alos)
    workspace.aoi_edit.setText("0,0,1,1")
    workspace.search_button.click()
    assert workspace.state == SearchViewState.LOADING

    workspace.mission_combo.setCurrentIndex(1)

    assert runner.cancelled_ids == [1]
    assert workspace.state == SearchViewState.EMPTY
    assert workspace.results_model.rowCount() == 0
    workspace.product_type_combo.addItem("GSLC", "GSLC")
    workspace.product_type_combo.setCurrentIndex(workspace.product_type_combo.count() - 1)
    assert not workspace.search_button.isEnabled()
    workspace.search_button.click()
    assert len(runner.requests) == 1
