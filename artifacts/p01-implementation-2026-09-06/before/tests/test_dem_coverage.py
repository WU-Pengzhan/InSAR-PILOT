from pathlib import Path

from insar_pilot.services.dem_coverage import DemCoverageService


def _write_vrt(path: Path, west: float, north: float, pixel: float, x_size: int, y_size: int) -> None:
    vrt = f"""<VRTDataset rasterXSize="{x_size}" rasterYSize="{y_size}">
  <GeoTransform>{west}, {pixel}, 0, {north}, 0, {-pixel}</GeoTransform>
</VRTDataset>
"""
    path.write_text(vrt, encoding="utf-8")


def test_dem_coverage_full(tmp_path: Path):
    dem = tmp_path / "dem.dem.wgs84"
    _write_vrt(Path(f"{dem}.vrt"), west=-119.0, north=35.0, pixel=0.01, x_size=300, y_size=300)
    service = DemCoverageService()

    result = service.assess(str(dem), (33.0, 34.0, -118.5, -117.5))

    assert result.status == "full"
    assert result.coverage_ratio == 1.0
    assert not result.warnings


def test_dem_coverage_partial(tmp_path: Path):
    dem = tmp_path / "dem.dem.wgs84"
    _write_vrt(Path(f"{dem}.vrt"), west=-118.2, north=34.2, pixel=0.01, x_size=80, y_size=80)
    service = DemCoverageService()

    result = service.assess(str(dem), (33.0, 34.0, -118.5, -117.5))

    assert result.status == "partial"
    assert 0.0 < result.coverage_ratio < 1.0
    assert result.missing_edges


def test_dem_coverage_none(tmp_path: Path):
    dem = tmp_path / "dem.dem.wgs84"
    _write_vrt(Path(f"{dem}.vrt"), west=10.0, north=10.0, pixel=0.01, x_size=100, y_size=100)
    service = DemCoverageService()

    result = service.assess(str(dem), (33.0, 34.0, -118.5, -117.5))

    assert result.status == "none"
    assert result.coverage_ratio == 0.0
    assert result.warnings
