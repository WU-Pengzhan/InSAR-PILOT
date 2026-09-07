from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import shapefile

from insar_pilot.application.nisar_acquisition import NisarAcquisitionManifest, NisarAcquisitionService
from insar_pilot.domain.search import RemoteSARProduct
from insar_pilot.download.geometry import wkt_from_aoi_file


def _product() -> RemoteSARProduct:
    return RemoteSARProduct(
        remote_product_id="NISAR_L1_PR_RSLC_TEST",
        provider_id="asf-nisar",
        mission="NISAR",
        platform="NISAR",
        product_type="RSLC",
        acquisition_time=datetime(2026, 7, 1, tzinfo=timezone.utc),
        relative_orbit=13,
        polarizations=("HH",),
        frequency_bands=("A",),
        footprint={"type": "Polygon", "coordinates": []},
        size_bytes=123,
        download_supported=True,
        download_url="https://example.test/test.h5",
        provider_metadata={"file_name": "NISAR_L1_PR_RSLC_TEST.h5", "frame_number": 71},
    )


def test_shapefile_aoi_is_read_as_wgs84_polygon(tmp_path: Path) -> None:
    path = tmp_path / "aoi.shp"
    with shapefile.Writer(str(path), shapeType=shapefile.POLYGON) as writer:
        writer.field("name", "C")
        writer.poly([[[-117.8, 34.5], [-117.6, 34.5], [-117.6, 34.7], [-117.8, 34.5]]])
        writer.record("test")
    path.with_suffix(".prj").write_text(
        'GEOGCS["WGS 84",DATUM["WGS_1984"],UNIT["degree",0.0174532925199433]]',
        encoding="utf-8",
    )

    wkt = wkt_from_aoi_file(path)

    assert wkt.startswith("POLYGON((")
    assert "-117.8 34.5" in wkt


def test_shapefile_aoi_rejects_projected_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "aoi.shp"
    with shapefile.Writer(str(path), shapeType=shapefile.POLYGON) as writer:
        writer.field("name", "C")
        writer.poly([[[500000, 3800000], [501000, 3800000], [501000, 3801000], [500000, 3800000]]])
        writer.record("test")
    path.with_suffix(".prj").write_text('PROJCS["WGS 84 / UTM zone 11N"]', encoding="utf-8")

    try:
        wkt_from_aoi_file(path)
    except ValueError as exc:
        assert "EPSG:4326" in str(exc)
    else:
        raise AssertionError("Projected AOI should be rejected")


def test_manifest_round_trip_and_rslc_task_path(tmp_path: Path) -> None:
    product = _product()
    manifest = NisarAcquisitionManifest(
        aoi_file="/readonly/aoi.kml",
        aoi_wkt="POLYGON((0 0,1 0,1 1,0 0))",
        start_time=datetime(2026, 6, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 1, tzinfo=timezone.utc),
        products=(product,),
    )
    path = NisarAcquisitionService.save_manifest(manifest, tmp_path / "manifest.json")

    loaded = NisarAcquisitionService.load_manifest(path)
    tasks = NisarAcquisitionService().create_download_tasks(loaded, tmp_path / "downloads")

    assert loaded.products[0].remote_product_id == product.remote_product_id
    assert tasks[0].product_type == "RSLC"
    assert Path(tasks[0].local_path).name == "NISAR_L1_PR_RSLC_TEST.h5"
    assert Path(tasks[0].local_path).parent.name == "RSLC"

