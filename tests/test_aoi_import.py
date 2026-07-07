import json
import subprocess
from pathlib import Path

import pytest
import shapefile

from insar_pilot.services.aoi_import import AoiImportService


def test_import_kml_bbox(tmp_path: Path):
    kml_path = tmp_path / "aoi.kml"
    kml_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -118.15,33.95,0 -118.28,33.89,0 -118.20,33.80,0 -118.10,33.78,0 -118.04,33.87,0 -118.15,33.95,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
""",
        encoding="utf-8",
    )

    result = AoiImportService().import_aoi(str(kml_path))
    assert result.source_kind == "kml"
    assert result.bbox_snwe.startswith("33.78 ")
    assert result.bbox_snwe.endswith(" -118.04")
    assert result.geometries


def test_import_shp_without_prj_defaults_to_wgs84_with_warning(tmp_path: Path):
    shp_path = tmp_path / "aoi.shp"
    writer = shapefile.Writer(str(shp_path))
    writer.field("id", "N")
    writer.poly(
        [
            [
                [-118.28, 33.89],
                [-118.20, 33.80],
                [-118.10, 33.78],
                [-118.04, 33.87],
                [-118.28, 33.89],
            ]
        ]
    )
    writer.record(1)
    writer.close()

    result = AoiImportService().import_aoi(str(shp_path))
    assert result.source_kind == "shp"
    assert result.geometries
    assert result.warnings
    assert "WGS84" in result.warnings[0]


def test_import_rejects_missing_file(tmp_path: Path):
    with pytest.raises(ValueError, match="was not found"):
        AoiImportService().import_aoi(str(tmp_path / "absent.kml"))


def test_import_rejects_unsupported_suffix(tmp_path: Path):
    bad = tmp_path / "aoi.geojson"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a .kml or .shp"):
        AoiImportService().import_aoi(str(bad))


def test_import_kml_without_valid_coordinates_raises(tmp_path: Path):
    kml = tmp_path / "aoi.kml"
    kml.write_text(
        "<kml><Document><Placemark><Point><coordinates></coordinates>"
        "</Point></Placemark></Document></kml>",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="No valid coordinates"):
        AoiImportService().import_aoi(str(kml))


def test_import_shp_with_prj_uses_ogr2ogr_and_reprojects(tmp_path: Path):
    shp_path = tmp_path / "aoi.shp"
    writer = shapefile.Writer(str(shp_path))
    writer.field("id", "N")
    writer.poly([[[500000.0, 3700000.0], [500100.0, 3700000.0], [500100.0, 3700100.0], [500000.0, 3700000.0]]])
    writer.record(1)
    writer.close()
    (tmp_path / "aoi.prj").write_text('PROJCS["fake_utm"]', encoding="utf-8")

    calls: list[list[str]] = []

    def _fake_runner(cmd, capture_output=True, text=True):
        calls.append(cmd)
        # ogr2ogr's -f GeoJSON output path is the second-to-last argument.
        out_path = Path(cmd[-2])
        out_path.write_text(
            json.dumps(
                {
                    "features": [
                        {
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[120.0, 30.0], [121.0, 30.0], [121.0, 31.0], [120.0, 30.0]]],
                            }
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    service = AoiImportService(runner=_fake_runner, which=lambda name: "/usr/bin/ogr2ogr")
    result = service.import_aoi(str(shp_path))

    assert result.source_kind == "shp"
    # bbox reflects the reprojected WGS84 coordinates, not the source UTM values.
    assert result.bbox_snwe == "30 31 120 121"
    assert any(part == "-t_srs" for part in calls[0])
    assert any("reprojected to WGS84" in note for note in result.notes)


def test_import_shp_with_prj_but_no_ogr2ogr_raises(tmp_path: Path):
    shp_path = tmp_path / "aoi.shp"
    writer = shapefile.Writer(str(shp_path))
    writer.field("id", "N")
    writer.poly([[[120.0, 30.0], [121.0, 30.0], [121.0, 31.0], [120.0, 30.0]]])
    writer.record(1)
    writer.close()
    (tmp_path / "aoi.prj").write_text('PROJCS["fake_utm"]', encoding="utf-8")

    service = AoiImportService(which=lambda name: None)
    with pytest.raises(RuntimeError, match="requires ogr2ogr"):
        service.import_aoi(str(shp_path))


def test_import_shp_with_prj_reports_ogr2ogr_failure(tmp_path: Path):
    shp_path = tmp_path / "aoi.shp"
    writer = shapefile.Writer(str(shp_path))
    writer.field("id", "N")
    writer.poly([[[120.0, 30.0], [121.0, 30.0], [121.0, 31.0], [120.0, 30.0]]])
    writer.record(1)
    writer.close()
    (tmp_path / "aoi.prj").write_text('PROJCS["fake_utm"]', encoding="utf-8")

    def _failing_runner(cmd, capture_output=True, text=True):
        return subprocess.CompletedProcess(cmd, 1, "", "ogr2ogr: cannot open datasource")

    service = AoiImportService(runner=_failing_runner, which=lambda name: "/usr/bin/ogr2ogr")
    with pytest.raises(RuntimeError, match="ogr2ogr failed"):
        service.import_aoi(str(shp_path))


def test_extract_geojson_lines_handles_all_geometry_types():
    payload = {
        "features": [
            {"geometry": {"type": "Point", "coordinates": [1.0, 2.0]}},
            {"geometry": {"type": "MultiPoint", "coordinates": [[3.0, 4.0], [5.0, 6.0]]}},
            {"geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 1.0]]}},
            {"geometry": {"type": "MultiLineString", "coordinates": [[[0.0, 0.0], [1.0, 1.0]]]}},
            {"geometry": {"type": "Polygon", "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]]]}},
            {
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[2.0, 2.0], [3.0, 2.0], [3.0, 3.0], [2.0, 2.0]]]],
                }
            },
            {"geometry": {"type": "Polygon", "coordinates": None}},  # skipped: no coords
        ]
    }

    lines = AoiImportService._extract_geojson_lines(payload)

    assert list(lines[0][0]) == [1.0, 2.0]  # point
    assert len(lines[1]) == 1 and len(lines[2]) == 1  # two multipoints -> two 1-point lines
    assert lines[3] == [(0.0, 0.0), (1.0, 1.0)]  # linestring
    # 1 point + 2 multipoint + 1 line + 1 multiline + 1 polygon ring + 1 multipolygon ring = 7 lines
    assert len(lines) == 7
