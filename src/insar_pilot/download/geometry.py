"""Geometry helpers for Sentinel-1 download search previews."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

Coord = tuple[float, float]


def bbox_to_polygon(text: str) -> list[Coord]:
    """Convert minLon,minLat,maxLon,maxLat text into a closed lon/lat polygon."""

    parts = text.replace(",", " ").split()
    if len(parts) != 4:
        raise ValueError("BBOX must contain minLon,minLat,maxLon,maxLat.")
    min_lon, min_lat, max_lon, max_lat = [float(part) for part in parts]
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError("BBOX must satisfy minLon < maxLon and minLat < maxLat.")
    return [
        (min_lon, min_lat),
        (max_lon, min_lat),
        (max_lon, max_lat),
        (min_lon, max_lat),
        (min_lon, min_lat),
    ]


def polygon_to_geojson(polygon: list[Coord]) -> dict[str, Any]:
    """Return a GeoJSON Polygon geometry."""

    return {"type": "Polygon", "coordinates": [[[lon, lat] for lon, lat in polygon]]}


def polygon_to_wkt(polygon: list[Coord]) -> str:
    """Return a POLYGON WKT string from a closed lon/lat polygon."""

    if len(polygon) < 4:
        raise ValueError("Polygon must contain at least three coordinates.")
    coords = polygon if polygon[0] == polygon[-1] else polygon + [polygon[0]]
    return "POLYGON((" + ",".join(f"{lon:g} {lat:g}" for lon, lat in coords) + "))"


def aoi_geojson_from_inputs(aoi_mode: str, bbox: str = "", wkt: str = "", aoi_file: str = "") -> dict[str, Any]:
    """Return a drawable AOI GeoJSON geometry from BBOX, WKT, or KML controls."""

    mode = aoi_mode.strip().lower()
    if mode == "wkt" and wkt.strip():
        return polygon_to_geojson(_polygon_from_wkt(wkt))
    if mode == "kml" and aoi_file.strip():
        return polygon_to_geojson(polygon_from_kml(Path(aoi_file).expanduser()))
    if bbox.strip():
        return polygon_to_geojson(bbox_to_polygon(bbox))
    return {}


def polygons_from_geojson(geometry: dict[str, Any]) -> list[list[Coord]]:
    """Extract exterior rings from GeoJSON Polygon/MultiPolygon/Feature payloads."""

    if not isinstance(geometry, dict):
        return []
    if geometry.get("type") == "Feature":
        return polygons_from_geojson(geometry.get("geometry") or {})
    if geometry.get("type") == "FeatureCollection":
        polygons: list[list[Coord]] = []
        for feature in geometry.get("features") or []:
            polygons.extend(polygons_from_geojson(feature))
        return polygons
    if geometry.get("type") == "Polygon":
        rings = geometry.get("coordinates") or []
        return [_ring_to_polygon(rings[0])] if rings else []
    if geometry.get("type") == "MultiPolygon":
        polygons = []
        for polygon in geometry.get("coordinates") or []:
            if polygon:
                polygons.append(_ring_to_polygon(polygon[0]))
        return polygons
    return []


def bounds_from_geojson(geometries: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    """Return bounds as minLon,minLat,maxLon,maxLat for a list of geometries."""

    points = [point for geometry in geometries for polygon in polygons_from_geojson(geometry) for point in polygon]
    if not points:
        return None
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return min(lons), min(lats), max(lons), max(lats)


def _ring_to_polygon(ring: Any) -> list[Coord]:
    polygon = [(float(point[0]), float(point[1])) for point in ring if len(point) >= 2]
    if polygon and polygon[0] != polygon[-1]:
        polygon.append(polygon[0])
    return polygon


def _polygon_from_wkt(text: str) -> list[Coord]:
    match = re.search(r"POLYGON\s*\(\((.*?)\)\)", text.strip(), re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Only POLYGON WKT is supported for preview.")
    coords: list[Coord] = []
    for pair in match.group(1).split(","):
        parts = pair.strip().split()
        if len(parts) >= 2:
            coords.append((float(parts[0]), float(parts[1])))
    if len(coords) < 3:
        raise ValueError("WKT polygon has too few coordinates.")
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def polygon_from_kml(path: Path) -> list[Coord]:
    if not path.is_file():
        raise ValueError(f"AOI KML file was not found: {path}")
    root = ET.parse(path).getroot()
    for node in root.iter():
        if node.tag.endswith("coordinates") and node.text:
            coords: list[Coord] = []
            for token in node.text.replace("\n", " ").split():
                parts = token.split(",")
                if len(parts) >= 2:
                    coords.append((float(parts[0]), float(parts[1])))
            if len(coords) >= 3:
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                return coords
    raise ValueError(f"No polygon coordinates found in KML AOI: {path}")
