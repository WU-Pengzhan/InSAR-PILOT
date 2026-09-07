"""Mission-neutral AOI helpers for remote SAR search and map previews."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from math import hypot, isfinite
from pathlib import Path
from typing import Any

import shapefile

Coord = tuple[float, float]


@dataclass(frozen=True)
class KmlGeometry:
    """A supported 2-D KML geometry with WGS84 lon/lat coordinates."""

    kind: str
    coordinates: list[Coord]


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
    return "POLYGON((" + ",".join(_format_wkt_coord(point) for point in coords) + "))"


def line_to_wkt(line: list[Coord]) -> str:
    """Return a LINESTRING WKT string without closing the input path."""

    if len(line) < 2:
        raise ValueError("LineString must contain at least two coordinates.")
    return "LINESTRING(" + ",".join(_format_wkt_coord(point) for point in line) + ")"


def aoi_geojson_from_inputs(aoi_mode: str, bbox: str = "", wkt: str = "", aoi_file: str = "") -> dict[str, Any]:
    """Return a drawable AOI GeoJSON geometry from BBOX, WKT, or KML controls."""

    mode = aoi_mode.strip().lower()
    if mode == "wkt" and wkt.strip():
        return polygon_to_geojson(_polygon_from_wkt(wkt))
    if mode == "kml" and aoi_file.strip():
        return geojson_from_kml(Path(aoi_file).expanduser())
    if bbox.strip():
        return polygon_to_geojson(bbox_to_polygon(bbox))
    return {}


def polygons_from_geojson(geometry: dict[str, Any]) -> list[list[Coord]]:
    """Extract drawable coordinate paths from common GeoJSON geometry types."""

    if not isinstance(geometry, dict):
        return []
    if geometry.get("type") == "Feature":
        return polygons_from_geojson(geometry.get("geometry") or {})
    if geometry.get("type") == "FeatureCollection":
        polygons: list[list[Coord]] = []
        for feature in geometry.get("features") or []:
            polygons.extend(polygons_from_geojson(feature))
        return polygons
    if geometry.get("type") == "GeometryCollection":
        paths: list[list[Coord]] = []
        for child in geometry.get("geometries") or []:
            paths.extend(polygons_from_geojson(child))
        return paths
    if geometry.get("type") == "Point":
        coordinates = geometry.get("coordinates") or []
        return [[_coord(coordinates)]] if len(coordinates) >= 2 else []
    if geometry.get("type") == "MultiPoint":
        return [[_coord(point)] for point in geometry.get("coordinates") or [] if len(point) >= 2]
    if geometry.get("type") == "LineString":
        line = [_coord(point) for point in geometry.get("coordinates") or [] if len(point) >= 2]
        return [line] if line else []
    if geometry.get("type") == "MultiLineString":
        return [
            [_coord(point) for point in line if len(point) >= 2]
            for line in geometry.get("coordinates") or []
            if line
        ]
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


def bounds_from_wkt(text: str) -> tuple[float, float, float, float]:
    """Return minLon,minLat,maxLon,maxLat for a supported polygon WKT."""

    points = _polygon_from_wkt(text)
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return min(lons), min(lats), max(lons), max(lats)


def _ring_to_polygon(ring: Any) -> list[Coord]:
    polygon = [_coord(point) for point in ring if len(point) >= 2]
    if polygon and polygon[0] != polygon[-1]:
        polygon.append(polygon[0])
    return polygon


def _coord(point: Any) -> Coord:
    return float(point[0]), float(point[1])


def _format_wkt_coord(point: Coord) -> str:
    return f"{point[0]:.12g} {point[1]:.12g}"


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
    """Return the largest Polygon exterior ring in a KML file."""

    polygons = [geometry.coordinates for geometry in geometries_from_kml(path) if geometry.kind == "Polygon"]
    if polygons:
        return max(polygons, key=_polygon_area)
    raise ValueError(f"No polygon coordinates found in KML AOI: {path}")


def wkt_from_kml(path: Path) -> str:
    """Return ASF-compatible WKT matching the KML's actual geometry type.

    ASF accepts one Polygon, LineString, or Point but not their multi-geometry
    variants. For multi-part inputs, the largest polygon or longest line is used
    as the representative search geometry instead of fabricating a closed line.
    """

    geometries = geometries_from_kml(path)
    polygons = [geometry.coordinates for geometry in geometries if geometry.kind == "Polygon"]
    if polygons:
        return polygon_to_wkt(max(polygons, key=_polygon_area))
    lines = [geometry.coordinates for geometry in geometries if geometry.kind == "LineString"]
    if lines:
        return line_to_wkt(max(lines, key=_line_length))
    points = [geometry.coordinates[0] for geometry in geometries if geometry.kind == "Point"]
    if points:
        return f"POINT({_format_wkt_coord(points[0])})"
    raise ValueError(f"No supported Point, LineString, or Polygon coordinates found in KML AOI: {path}")


def wkt_from_aoi_file(path: str | Path) -> str:
    """Return an ASF-compatible WGS84 WKT geometry from KML or Shapefile.

    ASF accepts a single search geometry. A Shapefile containing one polygon
    ring preserves that ring exactly. Multi-feature or multi-part inputs use
    their common WGS84 envelope so every requested feature remains covered;
    callers can inspect the returned WKT before starting a large download.
    """

    source = Path(path).expanduser()
    suffix = source.suffix.lower()
    if suffix == ".kml":
        return wkt_from_kml(source)
    if suffix == ".shp":
        return wkt_from_shapefile(source)
    raise ValueError(f"AOI file must be .kml or .shp: {source}")


def wkt_from_shapefile(path: Path) -> str:
    """Read a polygon Shapefile and return one ASF-compatible WGS84 polygon."""

    if not path.is_file():
        raise ValueError(f"AOI Shapefile was not found: {path}")
    _validate_shapefile_crs(path)
    try:
        with shapefile.Reader(str(path)) as reader:
            if reader.shapeType not in {
                shapefile.POLYGON,
                shapefile.POLYGONM,
                shapefile.POLYGONZ,
            }:
                raise ValueError(f"AOI Shapefile must contain polygons: {path}")
            rings = [ring for shape in reader.shapes() for ring in _shape_rings(shape)]
    except (OSError, shapefile.ShapefileException) as exc:
        raise ValueError(f"Failed to read AOI Shapefile: {path}") from exc
    if not rings:
        raise ValueError(f"AOI Shapefile contains no polygon coordinates: {path}")
    if len(rings) == 1:
        return polygon_to_wkt(rings[0])
    points = [point for ring in rings for point in ring]
    min_lon = min(point[0] for point in points)
    min_lat = min(point[1] for point in points)
    max_lon = max(point[0] for point in points)
    max_lat = max(point[1] for point in points)
    return polygon_to_wkt(bbox_to_polygon(f"{min_lon} {min_lat} {max_lon} {max_lat}"))


def _shape_rings(shape: Any) -> list[list[Coord]]:
    points = [_coord(point) for point in shape.points]
    _validate_lon_lat(points)
    boundaries = list(shape.parts) + [len(points)]
    rings: list[list[Coord]] = []
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        ring = points[start:end]
        if len(ring) < 3:
            continue
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        rings.append(ring)
    return rings


def _validate_lon_lat(points: list[Coord]) -> None:
    if any(not (-180 <= lon <= 180 and -90 <= lat <= 90) for lon, lat in points):
        raise ValueError("AOI coordinates must be WGS84 longitude/latitude values.")


def _validate_shapefile_crs(path: Path) -> None:
    projection_path = path.with_suffix(".prj")
    if not projection_path.exists():
        return
    try:
        projection = projection_path.read_text(encoding="utf-8", errors="ignore").upper()
    except OSError as exc:
        raise ValueError(f"Could not read Shapefile projection: {projection_path}") from exc
    geographic = any(token in projection for token in ("GEOGCS", "GEOGCRS", "GEODCRS"))
    wgs84 = "WGS_1984" in projection or "WGS 84" in projection or 'EPSG\",4326' in projection
    if projection.strip() and not (geographic and wgs84):
        raise ValueError("AOI Shapefile must use WGS84 geographic coordinates (EPSG:4326).")


def geojson_from_kml(path: Path) -> dict[str, Any]:
    """Return all supported KML geometries for previews and bounds calculation."""

    geometries = geometries_from_kml(path)
    payloads = [_kml_geometry_to_geojson(geometry) for geometry in geometries]
    if not payloads:
        raise ValueError(f"No supported Point, LineString, or Polygon coordinates found in KML AOI: {path}")
    if len(payloads) == 1:
        return payloads[0]
    return {"type": "GeometryCollection", "geometries": payloads}


def geometries_from_kml(path: Path) -> list[KmlGeometry]:
    """Parse Point, LineString, and Polygon exterior geometries from KML."""

    if not path.is_file():
        raise ValueError(f"AOI KML file was not found: {path}")
    root = ET.parse(path).getroot()
    geometries: list[KmlGeometry] = []

    for polygon in root.findall(".//{*}Polygon"):
        coordinates = polygon.find("./{*}outerBoundaryIs/{*}LinearRing/{*}coordinates")
        points = _coordinates_from_kml_node(coordinates)
        if len(points) >= 3:
            if points[0] != points[-1]:
                points.append(points[0])
            geometries.append(KmlGeometry("Polygon", points))

    for line in root.findall(".//{*}LineString"):
        points = _coordinates_from_kml_node(line.find("./{*}coordinates"))
        if len(points) >= 2:
            geometries.append(KmlGeometry("LineString", points))

    for point in root.findall(".//{*}Point"):
        points = _coordinates_from_kml_node(point.find("./{*}coordinates"))
        if points:
            geometries.append(KmlGeometry("Point", [points[0]]))

    return geometries


def _coordinates_from_kml_node(node: ET.Element | None) -> list[Coord]:
    coordinates: list[Coord] = []
    if node is None or not node.text:
        return coordinates
    for token in node.text.replace("\n", " ").split():
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon, lat = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        if isfinite(lon) and isfinite(lat):
            coordinates.append((lon, lat))
    return coordinates


def _line_length(line: list[Coord]) -> float:
    return sum(
        hypot(end[0] - start[0], end[1] - start[1])
        for start, end in zip(line, line[1:], strict=False)
    )


def _polygon_area(polygon: list[Coord]) -> float:
    return abs(
        sum(
            start[0] * end[1] - end[0] * start[1]
            for start, end in zip(polygon, polygon[1:], strict=False)
        )
        / 2
    )


def _kml_geometry_to_geojson(geometry: KmlGeometry) -> dict[str, Any]:
    coordinates = [[lon, lat] for lon, lat in geometry.coordinates]
    if geometry.kind == "Polygon":
        return {"type": "Polygon", "coordinates": [coordinates]}
    return {"type": geometry.kind, "coordinates": coordinates[0] if geometry.kind == "Point" else coordinates}
