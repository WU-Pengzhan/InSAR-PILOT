from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QAbstractTableModel, Qt

from insar_pilot.domain.search import RemoteSARProduct
from insar_pilot.i18n import set_shared_language
from insar_pilot.ui.models.search_results import SearchResultsTableModel


def test_search_results_model_uses_qt_model_view_rows():
    set_shared_language("en")
    row = RemoteSARProduct(
        remote_product_id="S1A_TEST",
        provider_id="asf-sentinel-1",
        mission="Sentinel-1",
        platform="Sentinel-1A",
        product_type="SLC",
        acquisition_time=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        orbit_direction="ASCENDING",
        relative_orbit=42,
        polarizations=("VV", "VH"),
    )
    model = SearchResultsTableModel([row])

    assert isinstance(model, QAbstractTableModel)
    assert model.rowCount() == 1
    assert model.columnCount() == 9
    assert model.data(model.index(0, 0)) == "S1A_TEST"
    assert model.data(model.index(0, 3)) == "SLC"
    assert model.data(model.index(0, 7)) == "VV+VH"
    assert model.data(model.index(0, 8)) == "asf-sentinel-1"
    assert model.data(model.index(0, 0), int(Qt.ItemDataRole.UserRole)) == row
    assert model.headerData(0, Qt.Orientation.Horizontal) == "Product ID"
    assert model.result_at(model.index(0, 0)) == row
    assert model.product_for_id("S1A_TEST") == row
    assert model.index_for_product_id("S1A_TEST").row() == 0
    assert model.product_for_id("missing") is None
    assert not model.index_for_product_id("missing").isValid()


def test_search_results_model_replaces_and_clears_rows():
    model = SearchResultsTableModel()
    rows = [
        RemoteSARProduct(
            remote_product_id="NISAR_RSLC_TEST",
            provider_id="fake-nisar",
            mission="NISAR",
            platform="NISAR",
            product_type="RSLC",
            acquisition_time=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )
    ]

    model.set_rows(rows)
    assert model.rowCount() == 1

    model.clear()
    assert model.rowCount() == 0
