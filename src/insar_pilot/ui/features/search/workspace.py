"""Search workspace view for the next-generation Workbench."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from PySide6.QtCore import QDate, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from insar_pilot.domain.search import RemoteSARProduct, SearchFilter, SearchFilterCapability
from insar_pilot.i18n import tr
from insar_pilot.ui.features.search.map_view import SearchFootprintMap
from insar_pilot.ui.icons import IconProvider
from insar_pilot.ui.models.search_results import SearchResultsTableModel
from insar_pilot.ui.widgets.collapsible_section import CollapsibleSection


class SearchViewState(str, Enum):
    EMPTY = "empty"
    LOADING = "loading"
    RESULTS = "results"
    NO_RESULTS = "no_results"
    ERROR = "error"


@dataclass(frozen=True)
class SearchFormValues:
    mission: str
    product_type: str
    start_date: date
    end_date: date
    aoi: str
    platform: str
    orbit_direction: str
    relative_orbit: str
    polarizations: tuple[str, ...]
    frequency_bands: tuple[str, ...]


class SearchWorkspace(QWidget):
    """Thin view containing search controls, map, states, and result table."""

    searchRequested = Signal()
    cancelRequested = Signal()
    RESULT_COLUMN_WIDTHS = (220, 100, 120, 120, 180, 140, 120, 130, 110)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("workbenchSearchWorkspace")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)

        title = QLabel(tr("workbench.search.title"))
        title.setObjectName("pageTitle")
        root.addWidget(title)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setObjectName("workbenchMainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(8)
        root.addWidget(self.main_splitter, 1)

        self.filter_panel = self._build_filter_panel()
        self.main_splitter.addWidget(self.filter_panel)

        self.map_results_splitter = QSplitter(Qt.Orientation.Vertical)
        self.map_results_splitter.setObjectName("workbenchMapResultsSplitter")
        self.map_results_splitter.setChildrenCollapsible(False)
        self.map_results_splitter.setHandleWidth(8)
        self.main_splitter.addWidget(self.map_results_splitter)

        self.map_placeholder = self._build_map_panel()
        self.map_results_splitter.addWidget(self.map_placeholder)

        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(6)
        results_title = QLabel(tr("workbench.results.title"))
        results_title.setObjectName("sectionTitle")
        results_layout.addWidget(results_title)

        self.results_model = SearchResultsTableModel(parent=self)
        self.results_view = QTableView()
        self.results_view.setObjectName("workbenchSearchResults")
        self.results_view.setModel(self.results_model)
        self.results_view.setAlternatingRowColors(True)
        self.results_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_view.setWordWrap(False)
        self.results_view.verticalHeader().setDefaultSectionSize(30)
        header = self.results_view.horizontalHeader()
        header.setMinimumSectionSize(80)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        for column, width in enumerate(self.RESULT_COLUMN_WIDTHS):
            self.results_view.setColumnWidth(column, width)
        self.result_state_stack = QStackedWidget()
        status_panel = QWidget()
        status_layout = QVBoxLayout(status_panel)
        status_layout.addStretch(1)
        self.status_label = QLabel()
        self.status_label.setObjectName("workbenchSearchState")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        self.loading_indicator = QProgressBar()
        self.loading_indicator.setRange(0, 0)
        self.loading_indicator.setTextVisible(False)
        status_layout.addWidget(self.loading_indicator)
        status_layout.addStretch(1)
        self.result_state_stack.addWidget(status_panel)
        self.result_state_stack.addWidget(self.results_view)
        results_layout.addWidget(self.result_state_stack, 1)
        self.map_results_splitter.addWidget(results_panel)

        self._state = SearchViewState.EMPTY
        self.set_search_state(SearchViewState.EMPTY)

        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.map_results_splitter.setStretchFactor(0, 3)
        self.map_results_splitter.setStretchFactor(1, 2)

    def _build_filter_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("workbenchFilterPanel")
        panel.setMinimumWidth(280)
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.mission_combo = QComboBox()
        self.product_type_combo = QComboBox()

        today = QDate.currentDate()
        self.start_date_edit = QDateEdit(today.addMonths(-1))
        self.end_date_edit = QDateEdit(today)
        for date_edit in (self.start_date_edit, self.end_date_edit):
            date_edit.setCalendarPopup(True)
            date_edit.setDisplayFormat("yyyy-MM-dd")

        self.aoi_edit = QLineEdit()
        self.aoi_edit.setPlaceholderText(tr("workbench.search.aoi.placeholder"))

        form.addRow(tr("workbench.search.mission"), self.mission_combo)
        form.addRow(tr("workbench.search.product_type"), self.product_type_combo)
        form.addRow(tr("workbench.search.start_date"), self.start_date_edit)
        form.addRow(tr("workbench.search.end_date"), self.end_date_edit)
        form.addRow(tr("workbench.search.aoi"), self.aoi_edit)
        layout.addLayout(form)

        self.advanced_filters = CollapsibleSection(
            tr("workbench.search.advanced"),
            expanded=False,
        )
        advanced_form = QFormLayout()
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.setSpacing(8)
        self.platform_combo = QComboBox()
        self.orbit_direction_combo = QComboBox()
        self.relative_orbit_edit = QLineEdit()
        self.polarization_combo = QComboBox()
        self.frequency_band_combo = QComboBox()
        self._advanced_rows = {
            "platform": (QLabel(tr("workbench.search.platform")), self.platform_combo),
            SearchFilter.ORBIT_DIRECTION: (
                QLabel(tr("workbench.search.orbit_direction")),
                self.orbit_direction_combo,
            ),
            SearchFilter.RELATIVE_ORBIT: (
                QLabel(tr("workbench.search.relative_orbit")),
                self.relative_orbit_edit,
            ),
            SearchFilter.POLARIZATIONS: (
                QLabel(tr("workbench.search.polarizations")),
                self.polarization_combo,
            ),
            SearchFilter.FREQUENCY_BANDS: (
                QLabel(tr("workbench.search.frequency_bands")),
                self.frequency_band_combo,
            ),
        }
        for label, field in self._advanced_rows.values():
            advanced_form.addRow(label, field)
        self.advanced_filters.content_layout.addLayout(advanced_form)
        layout.addWidget(self.advanced_filters)
        layout.addStretch(1)

        actions = QHBoxLayout()
        self.search_button = QPushButton(tr("workbench.search.action"))
        self.search_button.setProperty("role", "primary")
        self.search_button.setMinimumHeight(36)
        IconProvider.apply(self.search_button, "search")
        self.search_button.clicked.connect(self.searchRequested.emit)
        self.search_button.setEnabled(False)
        actions.addWidget(self.search_button, 1)
        self.cancel_button = QPushButton(tr("workbench.search.cancel"))
        self.cancel_button.setMinimumHeight(36)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        self.cancel_button.hide()
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)
        return panel

    def _build_map_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("workbenchMapPanel")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(tr("workbench.map.title"))
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        self.map_view = SearchFootprintMap()
        layout.addWidget(self.map_view, 1)
        return frame

    @property
    def state(self) -> SearchViewState:
        return self._state

    def form_values(self) -> SearchFormValues:
        return SearchFormValues(
            mission=str(self.mission_combo.currentData() or ""),
            product_type=str(self.product_type_combo.currentData() or ""),
            start_date=self.start_date_edit.date().toPython(),
            end_date=self.end_date_edit.date().toPython(),
            aoi=self.aoi_edit.text().strip(),
            platform=str(self.platform_combo.currentData() or ""),
            orbit_direction=str(self.orbit_direction_combo.currentData() or ""),
            relative_orbit=self.relative_orbit_edit.text().strip(),
            polarizations=self._tuple_choice(self.polarization_combo),
            frequency_bands=self._tuple_choice(self.frequency_band_combo),
        )

    def set_mission_options(self, missions: tuple[str, ...]) -> None:
        self._replace_combo_options(
            self.mission_combo,
            tuple((self._display_identifier(value), value) for value in missions),
        )

    def set_product_type_options(self, product_types: tuple[str, ...]) -> None:
        self._replace_combo_options(
            self.product_type_combo,
            tuple((value, value) for value in product_types),
        )

    def set_capability_options(
        self,
        platforms: tuple[str, ...],
        filters: tuple[SearchFilterCapability, ...],
        *,
        selected_platform: str = "",
    ) -> None:
        platform_options = ((tr("workbench.search.platform.all"), ""),) + tuple(
            (self._display_identifier(value), value) for value in platforms
        )
        self._replace_combo_options(
            self.platform_combo,
            platform_options,
            selected_value=selected_platform,
        )
        filter_map = {item.filter: item for item in filters}
        self._set_choice_filter(
            self.orbit_direction_combo,
            filter_map.get(SearchFilter.ORBIT_DIRECTION),
            translate_orbit=True,
        )
        self._set_choice_filter(
            self.polarization_combo,
            filter_map.get(SearchFilter.POLARIZATIONS),
        )
        self._set_choice_filter(
            self.frequency_band_combo,
            filter_map.get(SearchFilter.FREQUENCY_BANDS),
        )
        relative_orbit = filter_map.get(SearchFilter.RELATIVE_ORBIT)
        self.relative_orbit_edit.clear()
        self.relative_orbit_edit.setValidator(
            QIntValidator(relative_orbit.minimum, relative_orbit.maximum, self.relative_orbit_edit)
            if relative_orbit is not None
            and relative_orbit.minimum is not None
            and relative_orbit.maximum is not None
            else None
        )

        row_visibility: dict[str | SearchFilter, bool] = {
            "platform": bool(platforms),
            SearchFilter.ORBIT_DIRECTION: SearchFilter.ORBIT_DIRECTION in filter_map,
            SearchFilter.RELATIVE_ORBIT: relative_orbit is not None,
            SearchFilter.POLARIZATIONS: SearchFilter.POLARIZATIONS in filter_map,
            SearchFilter.FREQUENCY_BANDS: SearchFilter.FREQUENCY_BANDS in filter_map,
        }
        for key, visible in row_visibility.items():
            label, field = self._advanced_rows[key]
            label.setVisible(visible)
            field.setVisible(visible)
        self.advanced_filters.setVisible(any(row_visibility.values()))

    def set_search_available(self, available: bool) -> None:
        self.search_button.setEnabled(available)

    @staticmethod
    def _replace_combo_options(
        combo: QComboBox,
        options: tuple[tuple[str, str], ...],
        *,
        selected_value: str = "",
    ) -> None:
        blocker = QSignalBlocker(combo)
        try:
            combo.clear()
            for label, value in options:
                combo.addItem(label, value)
            selected_index = combo.findData(selected_value)
            if selected_index >= 0:
                combo.setCurrentIndex(selected_index)
        finally:
            del blocker

    def _set_choice_filter(
        self,
        combo: QComboBox,
        capability: SearchFilterCapability | None,
        *,
        translate_orbit: bool = False,
    ) -> None:
        choices: tuple[tuple[str, str], ...] = ((tr("workbench.search.any"), ""),)
        if capability is not None:
            choices += tuple(
                (self._orbit_label(value) if translate_orbit else value, value)
                for value in capability.choices
            )
        self._replace_combo_options(combo, choices)

    @staticmethod
    def _tuple_choice(combo: QComboBox) -> tuple[str, ...]:
        value = str(combo.currentData() or "")
        return tuple(part for part in value.split("+") if part)

    @staticmethod
    def _display_identifier(value: str) -> str:
        if value.startswith("SENTINEL-"):
            return "Sentinel-" + value.removeprefix("SENTINEL-")
        return value

    @staticmethod
    def _orbit_label(value: str) -> str:
        labels = {
            "ASCENDING": tr("workbench.search.ascending"),
            "DESCENDING": tr("workbench.search.descending"),
        }
        return labels.get(value, value)

    def set_search_state(self, state: SearchViewState, message: str = "") -> None:
        self._state = state
        if state == SearchViewState.RESULTS:
            self.result_state_stack.setCurrentWidget(self.results_view)
        else:
            default_messages = {
                SearchViewState.EMPTY: tr("workbench.search.state.empty"),
                SearchViewState.LOADING: tr("workbench.search.state.loading"),
                SearchViewState.NO_RESULTS: tr("workbench.search.state.no_results"),
                SearchViewState.ERROR: tr("workbench.search.state.error"),
            }
            self.status_label.setText(message or default_messages.get(state, ""))
            self.status_label.setProperty("state", state.value)
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
            self.loading_indicator.setVisible(state == SearchViewState.LOADING)
            self.result_state_stack.setCurrentIndex(0)
        is_loading = state == SearchViewState.LOADING
        self.cancel_button.setVisible(is_loading)
        self.search_button.setText(
            tr("workbench.search.action_again") if is_loading else tr("workbench.search.action")
        )

    def set_products(self, products: tuple[RemoteSARProduct, ...]) -> None:
        """Batch-replace both model rows and map markers."""

        self.results_model.set_rows(products)
        self.map_view.set_products(products)

    def clear_selection(self) -> None:
        self.results_view.clearSelection()
        self.map_view.set_selected_product_id(None)
