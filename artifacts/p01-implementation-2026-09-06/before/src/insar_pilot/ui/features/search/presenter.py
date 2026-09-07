"""Presentation logic connecting Workbench search views to the application service."""

from __future__ import annotations

from datetime import datetime, time, timezone

from PySide6.QtCore import QModelIndex, QObject, Slot
from PySide6.QtWidgets import QAbstractItemView

from insar_pilot.application.search import SearchApplicationError, SearchApplicationService
from insar_pilot.domain.search import RemoteSARProduct, SearchPage, SearchRequest
from insar_pilot.download.geometry import bbox_to_polygon, polygon_to_wkt
from insar_pilot.i18n import tr
from insar_pilot.ui.features.search.capability_view_model import SearchCapabilityViewModel
from insar_pilot.ui.features.search.inspector import ProductInspector
from insar_pilot.ui.features.search.task_runner import SearchTaskRunner
from insar_pilot.ui.features.search.workspace import SearchFormValues, SearchViewState, SearchWorkspace


class SearchPresenter(QObject):
    """Own request construction, state transitions, and product-ID selection."""

    def __init__(
        self,
        workspace: SearchWorkspace,
        inspector: ProductInspector,
        runner: SearchTaskRunner,
        service: SearchApplicationService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self.inspector = inspector
        self.runner = runner
        self.service = service
        self.capabilities = SearchCapabilityViewModel(service.provider_descriptors())
        self._active_request_id: int | None = None
        self._selecting = False

        workspace.searchRequested.connect(self.search)
        workspace.cancelRequested.connect(self.cancel)
        workspace.results_view.selectionModel().currentChanged.connect(self._table_selection_changed)
        workspace.map_view.productSelected.connect(self.select_product)
        workspace.mission_combo.currentIndexChanged.connect(self._mission_changed)
        workspace.product_type_combo.currentIndexChanged.connect(self._product_type_changed)
        workspace.platform_combo.currentIndexChanged.connect(self._platform_changed)
        runner.succeeded.connect(self._search_succeeded)
        runner.failed.connect(self._search_failed)
        runner.cancelled.connect(self._search_cancelled)
        self._initialize_capabilities()

    @property
    def active_request_id(self) -> int | None:
        return self._active_request_id

    @Slot()
    def search(self) -> None:
        try:
            values = self.workspace.form_values()
            options = self.capabilities.options(
                values.mission,
                values.product_type,
                values.platform,
            )
            request = self.build_request(values, page_size=options.page_size)
            self.service.validate_request(request)
        except (SearchApplicationError, ValueError) as exc:
            self._replace_products(())
            self.workspace.set_search_state(SearchViewState.ERROR, str(exc))
            return

        self._replace_products(())
        self.workspace.set_search_state(SearchViewState.LOADING)
        self._active_request_id = self.runner.submit(request)

    @Slot()
    def cancel(self) -> None:
        self.runner.cancel_current()

    @staticmethod
    def build_request(values: SearchFormValues, *, page_size: int = 100) -> SearchRequest:
        aoi = values.aoi.strip()
        if not aoi:
            raise ValueError(tr("workbench.search.validation.aoi_required"))
        if not aoi.upper().startswith("POLYGON"):
            try:
                aoi = polygon_to_wkt(bbox_to_polygon(aoi))
            except ValueError as exc:
                raise ValueError(tr("workbench.search.validation.aoi_invalid")) from exc

        relative_orbit: int | None = None
        if values.relative_orbit:
            try:
                relative_orbit = int(values.relative_orbit)
            except ValueError as exc:
                raise ValueError(tr("workbench.search.validation.relative_orbit")) from exc
            if relative_orbit < 1:
                raise ValueError(tr("workbench.search.validation.relative_orbit"))

        platforms = (values.platform,) if values.platform else ()
        return SearchRequest(
            mission=values.mission,
            product_type=values.product_type,
            start_time=datetime.combine(values.start_date, time.min, tzinfo=timezone.utc),
            end_time=datetime.combine(values.end_date, time.max, tzinfo=timezone.utc),
            aoi_wkt=aoi,
            platforms=platforms,
            orbit_direction=values.orbit_direction or None,
            relative_orbit=relative_orbit,
            polarizations=values.polarizations,
            frequency_bands=values.frequency_bands,
            page_size=page_size,
        )

    @Slot(int)
    def _mission_changed(self, _index: int) -> None:
        self._invalidate_search_context()
        mission = str(self.workspace.mission_combo.currentData() or "")
        self.workspace.set_product_type_options(self.capabilities.product_types(mission))
        self._refresh_capability_options(reset_platform=True)

    @Slot(int)
    def _product_type_changed(self, _index: int) -> None:
        self._invalidate_search_context()
        self._refresh_capability_options(reset_platform=True)

    @Slot(int)
    def _platform_changed(self, _index: int) -> None:
        self._invalidate_search_context()
        self._refresh_capability_options(reset_platform=False)

    def _initialize_capabilities(self) -> None:
        missions = self.capabilities.missions()
        self.workspace.set_mission_options(missions)
        if not missions:
            self.workspace.set_product_type_options(())
            self.workspace.set_capability_options((), ())
            self.workspace.set_search_available(False)
            self.workspace.set_search_state(
                SearchViewState.EMPTY,
                tr("workbench.search.state.no_providers"),
            )
            return
        mission = str(self.workspace.mission_combo.currentData() or "")
        self.workspace.set_product_type_options(self.capabilities.product_types(mission))
        self._refresh_capability_options(reset_platform=True)

    def _refresh_capability_options(self, *, reset_platform: bool) -> None:
        mission = str(self.workspace.mission_combo.currentData() or "")
        product_type = str(self.workspace.product_type_combo.currentData() or "")
        selected_platform = "" if reset_platform else str(self.workspace.platform_combo.currentData() or "")
        options = self.capabilities.options(mission, product_type, selected_platform)
        self.workspace.set_capability_options(
            options.platforms,
            options.filters,
            selected_platform=selected_platform,
        )
        self.workspace.set_search_available(bool(mission and product_type and options.available))

    def _invalidate_search_context(self) -> None:
        if self._active_request_id is not None:
            self.runner.cancel_current()
        self._replace_products(())
        self.workspace.set_search_state(SearchViewState.EMPTY)

    @Slot(int, object)
    def _search_succeeded(self, request_id: int, result: object) -> None:
        if request_id != self._active_request_id or not isinstance(result, SearchPage):
            return
        self._active_request_id = None
        self._replace_products(result.items)
        state = SearchViewState.RESULTS if result.items else SearchViewState.NO_RESULTS
        self.workspace.set_search_state(state)

    @Slot(int, str)
    def _search_failed(self, request_id: int, message: str) -> None:
        if request_id != self._active_request_id:
            return
        self._active_request_id = None
        self._replace_products(())
        self.workspace.set_search_state(SearchViewState.ERROR, message)

    @Slot(int)
    def _search_cancelled(self, request_id: int) -> None:
        if request_id != self._active_request_id:
            return
        self._active_request_id = None
        self.workspace.set_search_state(
            SearchViewState.EMPTY,
            tr("workbench.search.state.cancelled"),
        )

    @Slot(QModelIndex, QModelIndex)
    def _table_selection_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if self._selecting:
            return
        product = self.workspace.results_model.result_at(current)
        self._apply_selection(product)

    @Slot(str)
    def select_product(self, product_id: str) -> None:
        product = self.workspace.results_model.product_for_id(product_id)
        if product is None:
            return
        self._selecting = True
        try:
            index = self.workspace.results_model.index_for_product_id(product_id)
            if index.isValid():
                self.workspace.results_view.setCurrentIndex(index)
                self.workspace.results_view.selectRow(index.row())
                self.workspace.results_view.scrollTo(
                    index,
                    QAbstractItemView.ScrollHint.EnsureVisible,
                )
            self._apply_selection(product)
        finally:
            self._selecting = False

    def _apply_selection(self, product: RemoteSARProduct | None) -> None:
        product_id = product.remote_product_id if product is not None else None
        self.workspace.map_view.set_selected_product_id(product_id)
        self.inspector.set_product(product)

    def _replace_products(self, products: tuple[RemoteSARProduct, ...]) -> None:
        self.workspace.clear_selection()
        self.inspector.set_product(None)
        self.workspace.set_products(products)
