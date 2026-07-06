"""Assess DEM coverage against AOI/burst geographic extents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import xml.etree.ElementTree as ET


Bbox = tuple[float, float, float, float]  # south, north, west, east


@dataclass
class DemCoverageResult:
    status: str
    coverage_ratio: float
    dem_bbox_snwe: Bbox
    target_bbox_snwe: Bbox
    intersection_bbox_snwe: Bbox | None
    missing_edges: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class DemCoverageService:
    """Compute DEM bbox and coverage status for verify diagnostics."""

    def assess(self, prepared_dem_path: str, target_bbox_snwe: Bbox) -> DemCoverageResult:
        dem_bbox = self.resolve_dem_bbox(prepared_dem_path)
        inter = self._intersection_bbox(dem_bbox, target_bbox_snwe)
        target_area = self._bbox_area(target_bbox_snwe)
        inter_area = self._bbox_area(inter) if inter else 0.0
        coverage_ratio = 0.0 if target_area <= 0.0 else max(0.0, min(1.0, inter_area / target_area))
        missing_edges = self._missing_edges(dem_bbox, target_bbox_snwe)

        if coverage_ratio <= 0.0:
            status = "none"
        elif coverage_ratio >= 0.9999 and not missing_edges:
            status = "full"
        else:
            status = "partial"

        notes = [
            f"DEM bbox (SNWE): {self._format_bbox(dem_bbox)}",
            f"Target bbox (SNWE): {self._format_bbox(target_bbox_snwe)}",
            f"DEM coverage ratio over target: {coverage_ratio * 100.0:.2f}%",
        ]
        warnings: list[str] = []
        if status == "partial":
            warnings.append("DEM only partially covers the auto-selected burst extent.")
        elif status == "none":
            warnings.append("DEM does not cover the auto-selected burst extent.")
        if missing_edges:
            notes.append(f"Potential DEM coverage gap edges: {', '.join(missing_edges)}")
        if inter is not None:
            notes.append(f"Intersection bbox (SNWE): {self._format_bbox(inter)}")

        return DemCoverageResult(
            status=status,
            coverage_ratio=coverage_ratio,
            dem_bbox_snwe=dem_bbox,
            target_bbox_snwe=target_bbox_snwe,
            intersection_bbox_snwe=inter,
            missing_edges=missing_edges,
            notes=notes,
            warnings=warnings,
        )

    def resolve_dem_bbox(self, prepared_dem_path: str) -> Bbox:
        base = Path(prepared_dem_path).expanduser()
        candidates = [base]
        if base.suffix.lower() != ".vrt":
            candidates.append(Path(f"{base}.vrt"))

        for candidate in candidates:
            if candidate.exists() and candidate.is_file() and candidate.suffix.lower() == ".vrt":
                return self._bbox_from_vrt(candidate)

        raise ValueError(
            f"Could not resolve DEM geographic metadata (.vrt) for prepared DEM: {prepared_dem_path}"
        )

    def _bbox_from_vrt(self, vrt_path: Path) -> Bbox:
        root = ET.fromstring(vrt_path.read_text(encoding="utf-8"))
        x_size = self._safe_int(root.attrib.get("rasterXSize"))
        y_size = self._safe_int(root.attrib.get("rasterYSize"))
        gt_text = (root.findtext("./GeoTransform") or "").strip()
        coeffs = [self._safe_float(item) for item in gt_text.split(",") if item.strip()]
        if x_size <= 0 or y_size <= 0 or len(coeffs) != 6:
            raise ValueError(f"Invalid VRT geotransform metadata: {vrt_path}")

        gt0, gt1, gt2, gt3, gt4, gt5 = coeffs
        corners = []
        for col, row in ((0, 0), (x_size, 0), (0, y_size), (x_size, y_size)):
            lon = gt0 + (gt1 * col) + (gt2 * row)
            lat = gt3 + (gt4 * col) + (gt5 * row)
            corners.append((lat, lon))

        lats = [item[0] for item in corners]
        lons = [item[1] for item in corners]
        return (min(lats), max(lats), min(lons), max(lons))

    @staticmethod
    def _safe_int(text: str | None) -> int:
        if not text:
            return 0
        try:
            return int(text)
        except ValueError:
            return 0

    @staticmethod
    def _safe_float(text: str | None) -> float:
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    @staticmethod
    def _intersection_bbox(a: Bbox, b: Bbox) -> Bbox | None:
        south = max(a[0], b[0])
        north = min(a[1], b[1])
        west = max(a[2], b[2])
        east = min(a[3], b[3])
        if south >= north or west >= east:
            return None
        return (south, north, west, east)

    @staticmethod
    def _bbox_area(bbox: Bbox | None) -> float:
        if bbox is None:
            return 0.0
        south, north, west, east = bbox
        if south >= north or west >= east:
            return 0.0
        return (north - south) * (east - west)

    @staticmethod
    def _format_bbox(bbox: Bbox) -> str:
        return " ".join(f"{value:g}" for value in bbox)

    @staticmethod
    def _missing_edges(dem: Bbox, target: Bbox, eps: float = 1e-9) -> list[str]:
        missing: list[str] = []
        if dem[0] > target[0] + eps:
            missing.append("south")
        if dem[1] < target[1] - eps:
            missing.append("north")
        if dem[2] > target[2] + eps:
            missing.append("west")
        if dem[3] < target[3] - eps:
            missing.append("east")
        return missing
