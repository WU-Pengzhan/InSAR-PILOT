from pathlib import Path

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
