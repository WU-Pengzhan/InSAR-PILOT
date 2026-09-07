from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableView

from insar_pilot.ui.models.search_results import SearchResultsTableModel
from insar_pilot.ui.workbench import WorkbenchLayoutMode, WorkbenchWindow


def _qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_workbench_starts_with_only_the_primary_search_surface_visible():
    _qt_app()
    window = WorkbenchWindow()

    assert window.size().width() == 1440
    assert window.size().height() == 900
    assert window.layout_controller.mode == WorkbenchLayoutMode.NORMAL
    assert window.search_workspace.property("layoutMode") == "normal"
    assert window.search_workspace.advanced_filters.content.isHidden()
    assert window.inspector_dock.isHidden()
    assert window.activity_dock.isHidden()
    assert isinstance(window.search_workspace.results_view, QTableView)
    assert isinstance(window.search_workspace.results_view.model(), SearchResultsTableModel)
    assert window.search_workspace.results_view.columnWidth(0) >= 200
    assert window.search_workspace.results_view.columnWidth(4) >= 160
    assert window.search_workspace.mission_combo.currentData() == "SENTINEL-1"
    assert window.search_workspace.product_type_combo.currentData() == "SLC"
    window.close()


def test_layout_controller_owns_normal_and_maximized_splitter_strategies():
    app = _qt_app()
    window = WorkbenchWindow()
    window.resize(1366, 768)
    window.show()
    app.processEvents()
    workspace = window.search_workspace

    window.layout_controller.apply(WorkbenchLayoutMode.NORMAL)
    normal_main = workspace.main_splitter.sizes()
    normal_vertical = workspace.map_results_splitter.sizes()
    window.layout_controller.apply(WorkbenchLayoutMode.MAXIMIZED)
    maximized_main = workspace.main_splitter.sizes()
    maximized_vertical = workspace.map_results_splitter.sizes()

    assert workspace.main_splitter.orientation() == Qt.Orientation.Horizontal
    assert workspace.map_results_splitter.orientation() == Qt.Orientation.Vertical
    assert normal_main[0] >= 280
    assert maximized_main[0] >= 300
    assert maximized_main[1] > normal_main[1]
    assert maximized_vertical[0] / sum(maximized_vertical) > normal_vertical[0] / sum(normal_vertical)
    assert workspace.filter_panel.maximumWidth() > 1_000_000
    assert workspace.map_placeholder.maximumHeight() > 1_000_000
    assert window.inspector_dock.isHidden()
    assert window.activity_dock.isHidden()
    window.close()


def test_search_button_only_emits_a_view_intent():
    _qt_app()
    window = WorkbenchWindow()
    emissions: list[bool] = []
    window.search_workspace.searchRequested.connect(lambda: emissions.append(True))

    window.search_workspace.search_button.click()

    assert emissions == [True]
    assert window.search_workspace.results_model.rowCount() == 0
    window.close()
