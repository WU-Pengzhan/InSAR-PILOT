from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from insar_pilot.domain.local_data import (
    AssetRef,
    LocalSARProduct,
    SourceSnapshot,
    stable_product_id,
)


def _sentinel_product(
    uri: str,
    *,
    source_kind: str = "file",
    native_metadata: dict[str, object] | None = None,
) -> LocalSARProduct:
    native_id = "S1A_IW_SLC__1SDV_20260801T000000_20260801T000027_000001_000001_0001"
    return LocalSARProduct(
        product_id=stable_product_id("SENTINEL-1", "SLC", native_id),
        native_product_id=native_id,
        mission="s1",
        platform="s1a",
        product_type="slc",
        acquisition_mode="iw",
        acquisition_layout="tops_swaths",
        start_time=datetime(2026, 8, 1, 8, tzinfo=timezone(timedelta(hours=8))),
        end_time=datetime(2026, 8, 1, 8, 0, 27, tzinfo=timezone(timedelta(hours=8))),
        orbit_direction="descending",
        orbit_identity="orbit-1",
        track=13,
        frame=None,
        relative_orbit=42,
        frequency_bands=("c",),
        polarizations=("vv", "vh", "vv"),
        footprint_wkt=" POLYGON((0 0,1 0,1 1,0 0)) ",
        assets=(AssetRef(uri, "source_product", media_type="application/zip"),),
        native_metadata=native_metadata or {"ipf": "003.90", "swaths": ["IW1", "IW2"]},
        reader_id="sentinel1.safe",
        reader_schema_version=1,
        source_snapshot=SourceSnapshot(source_kind, 100, 123, member_count=53),
    )


def test_asset_ref_expresses_plain_files_and_hdf5_subdatasets() -> None:
    sentinel = AssetRef("/readonly/S1.zip", "source_product", media_type="application/zip")
    nisar = AssetRef(
        "/readonly/NISAR_RSLC.h5",
        "complex_radar_image",
        subdataset="/science/LSAR/RSLC/swaths/frequencyA/HH",
        media_type="application/x-hdf5",
        size_bytes=29_032_972_288,
    )

    assert not sentinel.is_hdf5_subdataset
    assert nisar.is_hdf5_subdataset
    assert AssetRef.from_dict(nisar.to_dict()) == nisar
    with pytest.raises(ValueError, match="must be absolute"):
        AssetRef("/readonly/NISAR_RSLC.h5", "complex_radar_image", subdataset="science/LSAR")


def test_stable_product_id_is_mission_native_and_path_independent() -> None:
    zip_product = _sentinel_product("/readonly/one/S1.zip")
    safe_product = _sentinel_product("/readonly/moved/S1.SAFE", source_kind="directory")

    assert zip_product.product_id == safe_product.product_id
    assert zip_product.product_id.startswith("SENTINEL-1:SLC:S1A_IW_SLC")
    assert zip_product.assets != safe_product.assets
    with pytest.raises(ValueError, match="stable"):
        LocalSARProduct(**{**zip_product.__dict__, "product_id": "path-derived-id"})


def test_product_can_express_nisar_frequency_and_dataset_layout() -> None:
    native_id = "NISAR_L1_PR_RSLC_001_005_A_001_2000_SHNA_A_20260801T000000"
    uri = "/readonly/NISAR_RSLC.h5"
    product = LocalSARProduct(
        product_id=stable_product_id("NISAR", "RSLC", native_id),
        native_product_id=native_id,
        mission="NISAR",
        platform="NISAR",
        product_type="RSLC",
        acquisition_mode="science",
        acquisition_layout="frequency_swaths",
        start_time=datetime(2026, 8, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 1, 0, 1, tzinfo=timezone.utc),
        orbit_direction="descending",
        orbit_identity="4783",
        track=13,
        frame=71,
        relative_orbit=None,
        frequency_bands=("B", "A"),
        polarizations=("HV", "HH"),
        footprint_wkt=None,
        assets=(
            AssetRef(uri, "source_product", media_type="application/x-hdf5"),
            AssetRef(
                uri,
                "complex_radar_image",
                "/science/LSAR/RSLC/swaths/frequencyB/HV",
                "application/x-hdf5",
            ),
            AssetRef(
                uri,
                "complex_radar_image",
                "/science/LSAR/RSLC/swaths/frequencyA/HH",
                "application/x-hdf5",
            ),
        ),
        native_metadata={"identification": {"lookDirection": "Left", "productLevel": "L1"}},
        reader_id="nisar.rslc",
        reader_schema_version=1,
        source_snapshot=SourceSnapshot("file", 29_032_972_288, 123),
    )

    assert product.frequency_bands == ("A", "B")
    assert product.polarizations == ("HH", "HV")
    assert tuple(asset.subdataset for asset in product.assets if asset.is_hdf5_subdataset) == (
        "/science/LSAR/RSLC/swaths/frequencyA/HH",
        "/science/LSAR/RSLC/swaths/frequencyB/HV",
    )


def test_model_is_deeply_immutable_and_rejects_native_objects() -> None:
    metadata = {"nested": {"values": [1, True, None]}}
    product = _sentinel_product("/readonly/S1.zip", native_metadata=metadata)
    metadata["nested"] = {"values": [999]}

    with pytest.raises(FrozenInstanceError):
        product.product_id = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        product.native_metadata["new"] = "value"  # type: ignore[index]
    nested = product.native_metadata["nested"]
    assert isinstance(nested, dict) is False
    assert product.to_dict()["native_metadata"] == {"nested": {"values": [1, True, None]}}
    with pytest.raises(TypeError, match="not JSON-compatible"):
        _sentinel_product("/readonly/S1.zip", native_metadata={"provider_object": object()})
    with pytest.raises(TypeError, match="not JSON-compatible"):
        _sentinel_product("/readonly/S1.zip", native_metadata={"path": Path("/tmp/value")})


def test_serialization_is_canonical_deterministic_and_round_trips() -> None:
    first = _sentinel_product(
        "/readonly/S1.zip",
        native_metadata={"z": [3, 2, 1], "a": {"b": 2, "a": 1}},
    )
    second = _sentinel_product(
        "/readonly/S1.zip",
        native_metadata={"a": {"a": 1, "b": 2}, "z": [3, 2, 1]},
    )

    assert first.to_json() == second.to_json()
    assert LocalSARProduct.from_json(first.to_json()) == first
    assert '"start_time":"2026-08-01T00:00:00Z"' in first.to_json()


def test_product_rejects_naive_time_and_non_json_numbers() -> None:
    product = _sentinel_product("/readonly/S1.zip")

    with pytest.raises(ValueError, match="timezone"):
        LocalSARProduct(**{**product.__dict__, "start_time": datetime(2026, 8, 1)})
    with pytest.raises(ValueError, match="non-finite"):
        _sentinel_product("/readonly/S1.zip", native_metadata={"bad": float("nan")})
