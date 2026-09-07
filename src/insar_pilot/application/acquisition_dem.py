"""Full Sentinel scene coverage for acquisition, independent of processing AOI."""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from shapely.geometry import box, mapping, shape

from insar_pilot.download.cop30_service import Cop30AwsDemService
from insar_pilot.download.models import DemCoveragePlan


def expanded_bounds(bounds: tuple[float, float, float, float], buffer_m: float) -> list[float]:
    """Conservative WGS84 geodetic envelope, using minimum ellipsoid curvature radius."""
    west, south, east, north = bounds
    if not all(math.isfinite(v) for v in bounds) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid full-scene geographic bounds.")
    if east - west > 180:
        raise ValueError("Antimeridian coverage must be split into separate acquisition batches.")
    if not 20000 <= buffer_m <= 200000:
        raise ValueError("DEM safety margin must be between 20 and 200 km.")
    angle = buffer_m / 6335439.0
    lat_margin = math.degrees(angle)
    extreme = max(abs(south), abs(north))
    if extreme + lat_margin >= 89:
        raise ValueError("Polar DEM planning is not supported by this acquisition profile.")
    lon_margin = math.degrees(math.asin(min(1, math.sin(angle) / math.cos(math.radians(extreme)))))
    result = [west - lon_margin, south - lat_margin, east + lon_margin, north + lat_margin]
    result = [math.floor(v * 3600) / 3600 if i < 2 else math.ceil(v * 3600) / 3600 for i, v in enumerate(result)]
    if result[0] < -180 or result[2] > 180:
        raise ValueError("Buffered DEM crosses the antimeridian; split the batch.")
    return result


def scene_bounds(path: Path) -> tuple[float, float, float, float]:
    """Read all IW geolocation metadata, never only AOI-selected bursts."""
    xmls: list[tuple[str, bytes]] = []
    if path.is_dir():
        for p in sorted((path / "annotation").glob("s1*-iw*-slc-*.xml")):
            if p.stat().st_size > 16 * 1024**2:
                raise ValueError("SLC annotation is too large.")
            xmls.append((p.name, p.read_bytes()))
    else:
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                if re.search(r"/annotation/s1[abcd]-iw[123]-slc-.*\.xml$", item.filename, re.I):
                    if item.file_size > 16 * 1024**2:
                        raise ValueError("SLC annotation is too large.")
                    xmls.append((item.filename, archive.read(item)))
    found: set[str] = set()
    points: list[tuple[float, float]] = []
    for name, raw in xmls:
        match = re.search(r"-iw([123])-", name, re.I)
        if not match:
            continue
        nodes = ET.fromstring(raw).findall(".//geolocationGridPoint")
        if not nodes:
            raise ValueError("SLC annotation has no geolocation grid.")
        found.add(match[1])
        for node in nodes:
            points.append((float(node.findtext("longitude", "nan")), float(node.findtext("latitude", "nan"))))
    if found != {"1", "2", "3"} or not points:
        raise ValueError("Complete IW1/IW2/IW3 geolocation is required; AOI fallback is not allowed.")
    xs, ys = zip(*points, strict=True)
    if not all(math.isfinite(v) for v in (*xs, *ys)):
        raise ValueError("Invalid geolocation coordinate.")
    return min(xs), min(ys), max(xs), max(ys)


def coverage(
    products: list[dict[str, Any]], buffer_m: float = 20000, local_paths: dict[str, str] | None = None
) -> dict[str, Any]:
    if not products or any(p["mission"] != "SENTINEL-1" for p in products):
        raise ValueError("Full-scene DEM acquisition currently requires a Sentinel-1-only selection.")
    bounds = []
    for product in products:
        if local_paths is not None:
            source = local_paths.get(product["remote_product_id"])
            if not source:
                raise ValueError("DEM is waiting for complete SLC geometry.")
            bounds.append(scene_bounds(Path(source)))
        else:
            geometry = shape(product.get("footprint") or {})
            if geometry.is_empty or not geometry.is_valid:
                raise ValueError("Full-scene footprint is unavailable; DEM extent cannot be estimated.")
            bounds.append(geometry.bounds)
    joint = (min(b[0] for b in bounds), min(b[1] for b in bounds), max(b[2] for b in bounds), max(b[3] for b in bounds))
    west, south, east, north = expanded_bounds(joint, buffer_m)
    tiles = Cop30AwsDemService.tiles_for_bbox((south, north, west, east))
    return {
        "source_id": "COP30",
        "height_reference": "egm2008",
        "buffer_m": buffer_m,
        "planning_mode": "full_scene_union",
        "verified_geometry": local_paths is not None,
        "source_bounds": list(joint),
        "bounds": [west, south, east, north],
        "bbox_snwe": [south, north, west, east],
        "geometry": mapping(box(west, south, east, north)),
        "tiles": [t.tile_id for t in tiles],
        "tile_count": len(tiles),
        "selected_scene_ids": [p["remote_product_id"] for p in products],
    }


def legacy_plan(plan: dict[str, Any]) -> DemCoveragePlan:
    return DemCoveragePlan(
        source_id="COP30",
        selected_scene_ids=plan["selected_scene_ids"],
        planned_bbox_snwe=tuple(plan["bbox_snwe"]),
        planning_mode="full_scene_union",
        dem_height_reference="egm2008",
        notes=[f"Full scene union; safety margin {plan['buffer_m']} m."],
    )
