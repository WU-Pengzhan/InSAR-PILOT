"""Import AOI files (KML/SHP) and convert to ISCE bbox inputs."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable
import xml.etree.ElementTree as ET

import shapefile


Coord = tuple[float, float]  # (lon, lat)


@dataclass
class AoiImportResult:
    source_path: str
    source_kind: str
    bbox_snwe: str
    geometries: list[list[Coord]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class AoiImportService:
    """Read AOI files and return WGS84 SNWE bbox + lightweight geometry."""

    def __init__(
        self,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        which: Callable[[str], str | None] | None = None,
    ) -> None:
        self._runner = runner or subprocess.run
        self._which = which or shutil.which

    def import_aoi(self, source_path: str) -> AoiImportResult:
        path = Path(source_path).expanduser()
        if not path.exists():
            raise ValueError(f"AOI file was not found: {path}")

        suffix = path.suffix.lower()
        if suffix == ".kml":
            geometries, notes = self._parse_kml(path)
            warnings: list[str] = []
            kind = "kml"
        elif suffix == ".shp":
            geometries, notes, warnings = self._parse_shp(path)
            kind = "shp"
        else:
            raise ValueError("AOI file must be a .kml or .shp file.")

        bbox = self._bbox_from_geometries(geometries)
        if bbox is None:
            raise ValueError(f"No valid coordinates were found in AOI file: {path}")

        south, north, west, east = bbox
        bbox_snwe = f"{south:g} {north:g} {west:g} {east:g}"
        notes = list(notes)
        notes.append(f"AOI bbox (SNWE): {bbox_snwe}")
        return AoiImportResult(
            source_path=str(path),
            source_kind=kind,
            bbox_snwe=bbox_snwe,
            geometries=geometries,
            notes=notes,
            warnings=warnings,
        )

    def _parse_kml(self, path: Path) -> tuple[list[list[Coord]], list[str]]:
        try:
            root = ET.fromstring(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"Failed to parse KML: {path}") from exc

        geometries: list[list[Coord]] = []
        for node in root.findall(".//{*}coordinates"):
            if not node.text:
                continue
            line = self._parse_coordinates_text(node.text)
            if line:
                geometries.append(line)

        notes = [
            f"Imported AOI file: {path}",
            f"KML geometries parsed: {len(geometries)}",
        ]
        return geometries, notes

    def _parse_shp(self, path: Path) -> tuple[list[list[Coord]], list[str], list[str]]:
        warnings: list[str] = []
        notes = [f"Imported AOI file: {path}"]
        prj_path = path.with_suffix(".prj")

        if not prj_path.exists():
            geometries = self._parse_shp_as_wgs84(path)
            warnings.append(
                "SHP .prj was not found. Coordinates were interpreted as WGS84 (EPSG:4326)."
            )
            notes.append(f"SHP parts parsed: {len(geometries)}")
            return geometries, notes, warnings

        if self._which("ogr2ogr") is None:
            raise RuntimeError(
                "SHP reprojection requires ogr2ogr, but it was not found in PATH."
            )

        with tempfile.TemporaryDirectory(prefix="iscegui_aoi_") as temp_dir:
            geojson_path = Path(temp_dir) / "aoi_wgs84.geojson"
            cmd = [
                "ogr2ogr",
                "-f",
                "GeoJSON",
                "-t_srs",
                "EPSG:4326",
                str(geojson_path),
                str(path),
            ]
            completed = self._runner(cmd, capture_output=True, text=True)
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "").strip()
                raise RuntimeError(f"ogr2ogr failed while reading SHP AOI: {detail}")

            payload = json.loads(geojson_path.read_text(encoding="utf-8"))
            geometries = self._extract_geojson_lines(payload)
            notes.append("SHP was reprojected to WGS84 with ogr2ogr.")
            notes.append(f"SHP parts parsed: {len(geometries)}")
            return geometries, notes, warnings

    def _parse_shp_as_wgs84(self, path: Path) -> list[list[Coord]]:
        reader = shapefile.Reader(str(path))
        geometries: list[list[Coord]] = []
        for shape in reader.shapes():
            points = [(float(x), float(y)) for x, y in shape.points]
            if not points:
                continue

            if not shape.parts:
                geometries.append(points)
                continue

            parts = list(shape.parts) + [len(points)]
            for index in range(len(parts) - 1):
                segment = points[parts[index] : parts[index + 1]]
                if segment:
                    geometries.append(segment)
        return geometries

    @staticmethod
    def _extract_geojson_lines(payload: dict) -> list[list[Coord]]:
        geometries: list[list[Coord]] = []
        for feature in payload.get("features", []):
            geometry = feature.get("geometry") or {}
            gtype = (geometry.get("type") or "").lower()
            coords = geometry.get("coordinates")
            if not coords:
                continue

            if gtype == "point":
                lon, lat = coords[:2]
                geometries.append([(float(lon), float(lat))])
            elif gtype == "multipoint":
                for point in coords:
                    lon, lat = point[:2]
                    geometries.append([(float(lon), float(lat))])
            elif gtype == "linestring":
                geometries.append([(float(lon), float(lat)) for lon, lat, *_ in coords])
            elif gtype == "multilinestring":
                for line in coords:
                    geometries.append([(float(lon), float(lat)) for lon, lat, *_ in line])
            elif gtype == "polygon":
                for ring in coords:
                    geometries.append([(float(lon), float(lat)) for lon, lat, *_ in ring])
            elif gtype == "multipolygon":
                for polygon in coords:
                    for ring in polygon:
                        geometries.append([(float(lon), float(lat)) for lon, lat, *_ in ring])
        return geometries

    @staticmethod
    def _parse_coordinates_text(raw_text: str) -> list[Coord]:
        result: list[Coord] = []
        for token in raw_text.replace("\n", " ").split():
            parts = token.split(",")
            if len(parts) < 2:
                continue
            try:
                lon = float(parts[0])
                lat = float(parts[1])
            except ValueError:
                continue
            result.append((lon, lat))
        return result

    @staticmethod
    def _bbox_from_geometries(
        geometries: list[list[Coord]],
    ) -> tuple[float, float, float, float] | None:
        points = [point for line in geometries for point in line]
        if not points:
            return None
        lons = [lon for lon, _ in points]
        lats = [lat for _, lat in points]
        return min(lats), max(lats), min(lons), max(lons)
