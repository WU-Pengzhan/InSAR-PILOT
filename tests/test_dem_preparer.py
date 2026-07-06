import json
import subprocess
from pathlib import Path

from insar_pilot.domain.project import APP_METADATA_DIR, EnvironmentConfig
from insar_pilot.services.dem_preparer import DemPreparationService


def _runner_with_payload(payload: dict, returncode: int = 0):
    def runner(argv, capture_output, text):
        return subprocess.CompletedProcess(argv, returncode, stdout=json.dumps(payload), stderr="")

    return runner


def test_prepare_passthrough_for_native_dem(tmp_path: Path):
    dem_path = tmp_path / "input.dem.wgs84"
    dem_path.write_text("x", encoding="utf-8")

    preparation = DemPreparationService().prepare(
        EnvironmentConfig(),
        dem_path,
        "",
        tmp_path / "work",
        tmp_path / "logs",
    )

    assert preparation.final_dem_path == str(dem_path)
    assert preparation.plans == []


def test_prepare_geotiff_requires_explicit_height_reference(tmp_path: Path):
    tif_path = tmp_path / "input.tif"
    tif_path.write_text("x", encoding="utf-8")
    payload = {"coordinateSystem": {"wkt": 'GEOGCRS["WGS 84"]'}}

    service = DemPreparationService(runner=_runner_with_payload(payload))

    try:
        service.prepare(EnvironmentConfig(), tif_path, "", tmp_path / "work", tmp_path / "logs")
    except ValueError as exc:
        assert "height reference" in str(exc)
    else:
        raise AssertionError("Expected GeoTIFF import to require an explicit height reference.")


def test_prepare_geotiff_builds_egm96_conversion_plans(tmp_path: Path):
    tif_path = tmp_path / "Copernicus DEM.tif"
    tif_path.write_text("x", encoding="utf-8")
    payload = {"coordinateSystem": {"wkt": 'GEOGCRS["WGS 84"]'}}

    preparation = DemPreparationService(runner=_runner_with_payload(payload)).prepare(
        EnvironmentConfig(),
        tif_path,
        "egm96",
        tmp_path / "work",
        tmp_path / "logs",
    )

    assert preparation.final_dem_path.endswith("Copernicus_DEM.dem.wgs84")
    assert len(preparation.plans) == 3
    assert "-overwrite" not in preparation.plans[0].command
    assert preparation.plans[-1].label == "Convert DEM heights from EGM96 to WGS84"


def test_prepare_geotiff_builds_egm2008_conversion_plans(tmp_path: Path):
    tif_path = tmp_path / "Copernicus DEM.tif"
    tif_path.write_text("x", encoding="utf-8")
    payload = {"coordinateSystem": {"wkt": 'GEOGCRS["WGS 84"]'}}

    preparation = DemPreparationService(runner=_runner_with_payload(payload)).prepare(
        EnvironmentConfig(),
        tif_path,
        "egm2008",
        tmp_path / "work",
        tmp_path / "logs",
    )

    assert preparation.final_dem_path.endswith("Copernicus_DEM.dem.wgs84")
    assert len(preparation.plans) == 2
    assert preparation.plans[0].label == "Convert DEM GeoTIFF from EGM2008 to WGS84 ellipsoid"
    assert "gdalwarp -overwrite -of ENVI" in preparation.plans[0].command
    assert "-s_srs EPSG:4326+3855 -t_srs EPSG:4979" in preparation.plans[0].command
    assert preparation.plans[1].label == "Create processing metadata for DEM"


def test_prepare_geotiff_builds_wgs84_import_plans(tmp_path: Path):
    tif_path = tmp_path / "ellipsoid.tif"
    tif_path.write_text("x", encoding="utf-8")
    payload = {"coordinateSystem": {"wkt": 'GEOGCRS["WGS 84"]'}}

    preparation = DemPreparationService(runner=_runner_with_payload(payload)).prepare(
        EnvironmentConfig(),
        tif_path,
        "wgs84",
        tmp_path / "work",
        tmp_path / "logs",
    )

    assert preparation.final_dem_path.endswith("ellipsoid.dem.wgs84")
    assert len(preparation.plans) == 2
    assert "-overwrite" not in preparation.plans[0].command
    assert all(plan.label != "Convert DEM heights from EGM96 to WGS84" for plan in preparation.plans)


def test_prepare_geotiff_rejects_projected_dem(tmp_path: Path):
    tif_path = tmp_path / "utm.tif"
    tif_path.write_text("x", encoding="utf-8")
    payload = {"coordinateSystem": {"wkt": 'PROJCRS["WGS 84 / UTM zone 50N"]'}}

    service = DemPreparationService(runner=_runner_with_payload(payload))

    try:
        service.prepare(EnvironmentConfig(), tif_path, "egm96", tmp_path / "work", tmp_path / "logs")
    except ValueError as exc:
        assert "geographic WGS84 grid" in str(exc)
    else:
        raise AssertionError("Expected projected GeoTIFF input to be rejected.")


def test_prepare_geotiff_cleans_stale_outputs(tmp_path: Path):
    tif_path = tmp_path / "stale.tif"
    tif_path.write_text("x", encoding="utf-8")
    payload = {"coordinateSystem": {"wkt": 'GEOGCRS["WGS 84"]'}}

    work_dir = tmp_path / "work"
    dem_dir = work_dir / APP_METADATA_DIR / "dem_import"
    dem_dir.mkdir(parents=True, exist_ok=True)
    stale_base = dem_dir / "stale.dem.wgs84"
    (stale_base).write_text("old", encoding="utf-8")
    (Path(f"{stale_base}.hdr")).write_text("old", encoding="utf-8")
    (Path(f"{stale_base}.xml")).write_text("old", encoding="utf-8")

    DemPreparationService(runner=_runner_with_payload(payload)).prepare(
        EnvironmentConfig(),
        tif_path,
        "wgs84",
        work_dir,
        tmp_path / "logs",
    )

    assert not stale_base.exists()
    assert not Path(f"{stale_base}.hdr").exists()
    assert not Path(f"{stale_base}.xml").exists()


def test_prepare_geotiff_requires_supported_height_reference_message(tmp_path: Path):
    tif_path = tmp_path / "input.tif"
    tif_path.write_text("x", encoding="utf-8")
    payload = {"coordinateSystem": {"wkt": 'GEOGCRS["WGS 84"]'}}

    service = DemPreparationService(runner=_runner_with_payload(payload))

    try:
        service.prepare(EnvironmentConfig(), tif_path, "bogus", tmp_path / "work", tmp_path / "logs")
    except ValueError as exc:
        assert "EGM2008 geoid" in str(exc)
    else:
        raise AssertionError("Expected unsupported height reference to be rejected.")
