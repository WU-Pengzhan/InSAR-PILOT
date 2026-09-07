from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from insar_pilot.domain.local_data import AssetRef, LocalSARProduct, SourceSnapshot, stable_product_id
from insar_pilot.services.product_compatibility import PairCompatibilityService


def _product(
    native_id: str,
    *,
    mission: str = "SENTINEL-1",
    product_type: str | None = None,
    day: int = 1,
    mode: str | None = None,
    layout: str | None = None,
    direction: str = "ASCENDING",
    relative_orbit: int | None = 12,
    track: int | None = None,
    frame: int | None = None,
    frequencies: tuple[str, ...] | None = None,
    polarizations: tuple[str, ...] = ("VV",),
    footprint: str | None = "POLYGON((0 0,2 0,2 2,0 2,0 0))",
    look_direction: str = "Left",
    metadata: dict[str, object] | None = None,
) -> LocalSARProduct:
    is_nisar = mission == "NISAR"
    actual_type = product_type or ("RSLC" if is_nisar else "SLC")
    start = datetime(2026, 1, day, tzinfo=timezone.utc)
    native_metadata = metadata or ({"identification": {"lookDirection": look_direction}} if is_nisar else {})
    return LocalSARProduct(
        product_id=stable_product_id(mission, actual_type, native_id),
        native_product_id=native_id,
        mission=mission,
        platform="NISAR" if is_nisar else "S1A",
        product_type=actual_type,
        acquisition_mode=mode or ("SCIENCE" if is_nisar else "IW"),
        acquisition_layout=layout or ("FREQUENCY_SWATHS" if is_nisar else "TOPS_SWATHS"),
        start_time=start,
        end_time=start + timedelta(minutes=1),
        orbit_direction=direction,
        orbit_identity=None,
        track=track if is_nisar else None,
        frame=frame if is_nisar else None,
        relative_orbit=None if is_nisar else relative_orbit,
        frequency_bands=frequencies or (("A",) if is_nisar else ("C",)),
        polarizations=polarizations,
        footprint_wkt=footprint,
        assets=(AssetRef(f"/readonly/{native_id}", "source_product"),),
        native_metadata=native_metadata,
        reader_id="nisar.rslc" if is_nisar else "sentinel1.safe",
        reader_schema_version=1,
        source_snapshot=SourceSnapshot("file", 1, day),
    )


def test_sentinel_pair_accepts_constellation_platforms_and_warns_for_deferred_bursts() -> None:
    left = _product("S1A_FIRST", day=1)
    right = _product("S1C_SECOND", day=13)

    report = PairCompatibilityService().check(left, right)

    assert report.compatible
    assert report.temporal_baseline_days == 12
    assert report.common_frequency_bands == ("C",)
    assert report.common_polarizations == ("VV",)
    assert report.warnings == ("swath_check_deferred", "burst_check_deferred")


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"relative_orbit": 13}, "relative_orbit_mismatch"),
        ({"direction": "DESCENDING"}, "orbit_direction_mismatch"),
        ({"polarizations": ("HH",)}, "polarization_mismatch"),
        ({"footprint": "POLYGON((10 10,11 10,11 11,10 10))"}, "spatial_coverage_mismatch"),
        ({"mode": "SM", "layout": "STRIPMAP"}, "acquisition_mode_mismatch"),
    ],
)
def test_sentinel_pair_explains_incompatibility(overrides: dict[str, object], reason: str) -> None:
    report = PairCompatibilityService().check(_product("LEFT", day=1), _product("RIGHT", day=2, **overrides))
    assert not report.compatible
    assert reason in report.reason_codes


def test_nisar_pair_checks_rslc_track_frame_look_frequency_and_coverage() -> None:
    left = _product("NISAR_LEFT", mission="NISAR", day=1, track=13, frame=71, polarizations=("HH", "HV"))
    right = _product("NISAR_RIGHT", mission="NISAR", day=5, track=13, frame=71, polarizations=("HH",))
    compatible = PairCompatibilityService().check(left, right)
    assert compatible.compatible
    assert compatible.common_frequency_bands == ("A",)
    assert compatible.common_polarizations == ("HH",)

    wrong = _product(
        "NISAR_WRONG",
        mission="NISAR",
        product_type="GSLC",
        day=6,
        track=99,
        frame=72,
        frequencies=("B",),
        polarizations=("VV",),
        look_direction="Right",
        footprint="POLYGON((10 10,11 10,11 11,10 10))",
    )
    report = PairCompatibilityService().check(left, wrong)
    assert not report.compatible
    assert {
        "nisar_requires_rslc",
        "track_mismatch",
        "frame_mismatch",
        "look_direction_mismatch",
        "frequency_mismatch",
        "polarization_mismatch",
        "spatial_coverage_mismatch",
    }.issubset(report.reason_codes)


def test_cross_mission_and_same_product_are_never_pairs() -> None:
    sentinel = _product("S1", day=1)
    nisar = _product("NISAR", mission="NISAR", day=2, track=1, frame=1)
    cross = PairCompatibilityService().check(sentinel, nisar)
    same = PairCompatibilityService().check(sentinel, sentinel)
    assert not cross.compatible and cross.reason_codes == ("cross_mission_pair",)
    assert not same.compatible and same.reason_codes == ("same_product",)


def test_nisar_three_ordinate_bounding_polygon_is_treated_as_lon_lat_height() -> None:
    left = _product(
        "NISAR_3D_LEFT",
        mission="NISAR",
        day=1,
        track=13,
        frame=71,
        footprint="POLYGON ((-118 36 1000,-117 36 900,-117 35 800,-118 36 1000))",
    )
    right = _product(
        "NISAR_3D_RIGHT",
        mission="NISAR",
        day=2,
        track=13,
        frame=71,
        footprint="POLYGON ((-117.5 35.5 1200,-116.5 35.5 900,-116.5 34.5 800,-117.5 35.5 1200))",
    )

    assert PairCompatibilityService().check(left, right).compatible
