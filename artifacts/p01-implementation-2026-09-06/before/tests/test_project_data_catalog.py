from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from insar_pilot.domain.local_data import AssetRef, LocalSARProduct, SourceSnapshot, stable_product_id
from insar_pilot.services.project_data_catalog import (
    CatalogLoadError,
    CatalogMergeState,
    CatalogSourceState,
    CatalogWriteError,
    ProjectDataCatalog,
)


def _product(source: Path, *, fingerprint: str = "first") -> LocalSARProduct:
    stat = source.stat()
    native_id = "S1A_TEST_PRODUCT"
    return LocalSARProduct(
        product_id=stable_product_id("SENTINEL-1", "SLC", native_id),
        native_product_id=native_id,
        mission="SENTINEL-1",
        platform="S1A",
        product_type="SLC",
        acquisition_mode="IW",
        acquisition_layout="TOPS_SWATHS",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        orbit_direction="ASCENDING",
        orbit_identity="100",
        track=None,
        frame=None,
        relative_orbit=12,
        frequency_bands=("C",),
        polarizations=("VV",),
        footprint_wkt=None,
        assets=(AssetRef(str(source), "source_product", size_bytes=stat.st_size),),
        native_metadata={},
        reader_id="sentinel1.safe",
        reader_schema_version=1,
        source_snapshot=SourceSnapshot("file", stat.st_size, stat.st_mtime_ns, fingerprint=fingerprint),
    )


def test_catalog_round_trip_duplicate_and_explicit_changed_replace(tmp_path: Path) -> None:
    source = tmp_path / "S1.zip"
    source.write_bytes(b"one")
    product = _product(source)
    catalog = ProjectDataCatalog(tmp_path)

    first = catalog.merge(product)
    duplicate = catalog.merge(product)
    changed_product = _product(source, fingerprint="changed")
    changed = catalog.merge(changed_product)

    assert first.state is CatalogMergeState.NEW and first.persisted
    assert duplicate.state is CatalogMergeState.UNCHANGED and not duplicate.persisted
    assert changed.state is CatalogMergeState.CHANGED and not changed.persisted
    assert catalog.get(product.product_id).product.source_snapshot.fingerprint == "first"  # type: ignore[union-attr]

    replaced = catalog.merge(changed_product, replace_changed=True)
    reopened = ProjectDataCatalog(tmp_path).load()
    assert replaced.state is CatalogMergeState.CHANGED and replaced.persisted
    assert reopened.get(product.product_id) == replaced.entry
    assert len(tuple((tmp_path / ".insar_pilot/catalog/products").glob("*.sar.json"))) == 1


def test_catalog_source_state_and_defensive_load(tmp_path: Path) -> None:
    source = tmp_path / "S1.zip"
    source.write_bytes(b"one")
    product = _product(source)
    catalog = ProjectDataCatalog(tmp_path)
    catalog.merge(product)
    assert catalog.source_state(product.product_id) is CatalogSourceState.CURRENT

    source.write_bytes(b"changed-size")
    assert catalog.source_state(product.product_id) is CatalogSourceState.CHANGED
    source.unlink()
    assert catalog.source_state(product.product_id) is CatalogSourceState.MISSING

    sidecar = catalog.sidecar_path(product.product_id)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    payload["schema_version"] = 999
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CatalogLoadError, match="malformed"):
        ProjectDataCatalog(tmp_path).load()


def test_catalog_atomic_replace_failure_keeps_memory_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "S1.zip"
    source.write_bytes(b"one")
    catalog = ProjectDataCatalog(tmp_path)

    def fail_replace(source_path: str | bytes | os.PathLike[str], target_path: str | bytes | os.PathLike[str]) -> None:
        raise OSError(f"cannot replace {source_path} with {target_path}")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(CatalogWriteError):
        catalog.merge(_product(source))

    assert catalog.entries() == ()
    assert list(catalog.products_dir.glob("*.tmp")) == []
