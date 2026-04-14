"""Recommend Sentinel-1 IW swaths from AOI bbox overlap."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile


Coord = tuple[float, float]  # (lon, lat)


@dataclass
class IwFootprint:
    swath: str
    bbox_snwe: tuple[float, float, float, float]
    polygon: list[Coord]


@dataclass
class BurstFootprint:
    swath: str
    burst_id: int
    bbox_snwe: tuple[float, float, float, float]
    polygon: list[Coord]


@dataclass
class IwRecommendationResult:
    basis_entry_path: str
    pass_direction: str = ""
    recommended_swaths: str = "1 2 3"
    overlaps: dict[str, float] = field(default_factory=dict)
    footprints: dict[str, IwFootprint] = field(default_factory=dict)
    bursts: dict[str, list[BurstFootprint]] = field(default_factory=dict)
    auto_selected_bursts: dict[str, list[int]] = field(default_factory=dict)
    auto_selected_burst_bbox_snwe: tuple[float, float, float, float] | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class IwRecommendationService:
    """Compute coarse IW recommendation from annotation geolocation grids."""

    _ANNOTATION_REGEX = re.compile(r"/annotation/s1[ab]-iw([123])-slc-.*\.xml$", re.IGNORECASE)

    def recommend(self, entry_path: str, bbox_snwe: str) -> IwRecommendationResult:
        south, north, west, east = self._parse_bbox(bbox_snwe)
        result = IwRecommendationResult(
            basis_entry_path=str(Path(entry_path).expanduser()),
            notes=[f"Recommendation basis entry: {entry_path}"],
        )
        annotations = self._load_annotation_texts(Path(entry_path).expanduser())
        if not annotations:
            raise ValueError(f"No Sentinel-1 annotation XML files were found in: {entry_path}")

        for swath, xml_text in annotations.items():
            footprint, pass_direction, bursts = self._footprint_from_annotation(swath, xml_text)
            result.footprints[swath] = footprint
            result.bursts[swath] = bursts
            if pass_direction and not result.pass_direction:
                result.pass_direction = pass_direction
            area = self._intersection_area((south, north, west, east), footprint.bbox_snwe)
            result.overlaps[swath] = area

            selected = [
                item.burst_id
                for item in bursts
                if self._polygon_bbox_intersection_area(
                    item.polygon,
                    (south, north, west, east),
                )
                > 0.0
            ]
            result.auto_selected_bursts[swath] = selected

        recommended = [swath for swath, area in sorted(result.overlaps.items()) if area > 0.0]
        if not recommended:
            recommended = ["1", "2", "3"]
            result.warnings.append(
                "AOI bbox does not overlap parsed IW footprints. Falling back to IW1 IW2 IW3."
            )
        result.recommended_swaths = " ".join(recommended)
        if result.pass_direction:
            result.notes.append(f"Pass direction: {result.pass_direction}")
        result.notes.extend(
            f"IW{swath} overlap area (deg^2): {area:g}"
            for swath, area in sorted(result.overlaps.items())
        )
        burst_boxes: list[tuple[float, float, float, float]] = []
        for swath, burst_ids in sorted(result.auto_selected_bursts.items()):
            text = ", ".join(str(value) for value in burst_ids) if burst_ids else "-"
            result.notes.append(f"IW{swath} auto-selected bursts: {text}")
            burst_lookup = {item.burst_id: item.bbox_snwe for item in result.bursts.get(swath, [])}
            burst_boxes.extend(burst_lookup[item] for item in burst_ids if item in burst_lookup)
        result.auto_selected_burst_bbox_snwe = self._union_bbox(burst_boxes)
        result.notes.append(f"Recommended swaths: {result.recommended_swaths}")
        return result

    def _load_annotation_texts(self, entry_path: Path) -> dict[str, str]:
        if entry_path.is_dir():
            return self._load_annotation_texts_from_safe(entry_path)
        if entry_path.is_file() and entry_path.suffix.lower() == ".zip":
            return self._load_annotation_texts_from_zip(entry_path)
        raise ValueError(f"Unsupported Sentinel entry path: {entry_path}")

    def _load_annotation_texts_from_safe(self, safe_dir: Path) -> dict[str, str]:
        annotation_dir = safe_dir / "annotation"
        if not annotation_dir.is_dir():
            return {}
        result: dict[str, str] = {}
        for xml_path in sorted(annotation_dir.glob("s1*-iw*-slc-*.xml")):
            match = re.search(r"-iw([123])-", xml_path.name, flags=re.IGNORECASE)
            if not match:
                continue
            swath = match.group(1)
            result.setdefault(swath, xml_path.read_text(encoding="utf-8", errors="ignore"))
        return result

    def _load_annotation_texts_from_zip(self, zip_path: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        with zipfile.ZipFile(zip_path, "r") as archive:
            for name in sorted(archive.namelist()):
                match = self._ANNOTATION_REGEX.search(name)
                if not match:
                    continue
                swath = match.group(1)
                if swath in result:
                    continue
                result[swath] = archive.read(name).decode("utf-8", errors="ignore")
        return result

    def _footprint_from_annotation(
        self, swath: str, xml_text: str
    ) -> tuple[IwFootprint, str, list[BurstFootprint]]:
        root = ET.fromstring(xml_text)
        pass_direction = (root.findtext(".//pass") or "").strip().lower()

        points = self._extract_geolocation_points(root)
        if not points:
            raise ValueError(f"No geolocationGridPoint was found for IW{swath}.")

        lons = [item[2] for item in points]
        lats = [item[3] for item in points]
        bbox = (min(lats), max(lats), min(lons), max(lons))
        polygon = self._polygon_from_points(points, bbox)
        iw_footprint = IwFootprint(swath=swath, bbox_snwe=bbox, polygon=polygon)
        bursts = self._extract_burst_footprints(swath, root, points, iw_footprint)
        return iw_footprint, pass_direction, bursts

    @staticmethod
    def _extract_geolocation_points(root: ET.Element) -> list[tuple[int, int, float, float]]:
        points: list[tuple[int, int, float, float]] = []
        for node in root.findall(".//geolocationGridPoint"):
            line_text = node.findtext("line")
            pixel_text = node.findtext("pixel")
            lat_text = node.findtext("latitude")
            lon_text = node.findtext("longitude")
            if None in (line_text, pixel_text, lat_text, lon_text):
                continue
            try:
                line = int(float(line_text))
                pixel = int(float(pixel_text))
                lat = float(lat_text)
                lon = float(lon_text)
            except ValueError:
                continue
            points.append((line, pixel, lon, lat))
        return points

    @staticmethod
    def _polygon_from_points(
        points: list[tuple[int, int, float, float]],
        bbox: tuple[float, float, float, float],
    ) -> list[Coord]:
        by_line: dict[int, list[tuple[int, int, float, float]]] = {}
        for item in points:
            by_line.setdefault(item[0], []).append(item)
        lines = sorted(by_line)
        if len(lines) >= 2:
            top = sorted(by_line[lines[0]], key=lambda item: item[1])
            bottom = sorted(by_line[lines[-1]], key=lambda item: item[1], reverse=True)
            polygon = [(item[2], item[3]) for item in top + bottom]
            if polygon and polygon[0] != polygon[-1]:
                polygon.append(polygon[0])
        else:
            south, north, west, east = bbox
            polygon = [(west, south), (west, north), (east, north), (east, south), (west, south)]
        return polygon

    def _extract_burst_footprints(
        self,
        swath: str,
        root: ET.Element,
        points: list[tuple[int, int, float, float]],
        iw: IwFootprint,
    ) -> list[BurstFootprint]:
        lines_per_burst = self._safe_int(root.findtext(".//linesPerBurst"))
        burst_nodes = root.findall(".//burstList/burst")
        burst_count = len(burst_nodes)
        if burst_count <= 0:
            burst_list = root.find(".//burstList")
            burst_count = self._safe_int(burst_list.get("count")) if burst_list is not None else 0
        if burst_count <= 0:
            return []

        min_line = min(item[0] for item in points)
        max_line = max(item[0] for item in points)
        if lines_per_burst <= 0:
            lines_per_burst = max(1, int(round((max_line - min_line + 1) / max(1, burst_count))))

        result: list[BurstFootprint] = []
        for index in range(burst_count):
            burst_id = index + 1
            start_line = min_line + (index * lines_per_burst)
            end_line = start_line + lines_per_burst
            burst_points = [item for item in points if start_line <= item[0] <= end_line]
            if burst_points:
                lons = [item[2] for item in burst_points]
                lats = [item[3] for item in burst_points]
                bbox = (min(lats), max(lats), min(lons), max(lons))
                polygon = self._polygon_from_points(burst_points, bbox)
            else:
                south, north, west, east = iw.bbox_snwe
                lat_span = (north - south) / max(burst_count, 1)
                burst_north = north - (index * lat_span)
                burst_south = north - ((index + 1) * lat_span)
                bbox = (burst_south, burst_north, west, east)
                polygon = [
                    (west, burst_south),
                    (west, burst_north),
                    (east, burst_north),
                    (east, burst_south),
                    (west, burst_south),
                ]
            result.append(BurstFootprint(swath=swath, burst_id=burst_id, bbox_snwe=bbox, polygon=polygon))
        return result

    @staticmethod
    def _safe_int(text: str | None) -> int:
        if not text:
            return 0
        try:
            return int(float(text))
        except ValueError:
            return 0

    @staticmethod
    def _parse_bbox(text: str) -> tuple[float, float, float, float]:
        parts = text.strip().replace(",", " ").split()
        if len(parts) != 4:
            raise ValueError("SNWE bbox must contain 4 values: south north west east.")
        south, north, west, east = [float(value) for value in parts]
        if south >= north or west >= east:
            raise ValueError("SNWE bbox must satisfy south < north and west < east.")
        return south, north, west, east

    @staticmethod
    def _intersection_area(
        bbox_a: tuple[float, float, float, float],
        bbox_b: tuple[float, float, float, float],
    ) -> float:
        south = max(bbox_a[0], bbox_b[0])
        north = min(bbox_a[1], bbox_b[1])
        west = max(bbox_a[2], bbox_b[2])
        east = min(bbox_a[3], bbox_b[3])
        if south >= north or west >= east:
            return 0.0
        return (north - south) * (east - west)

    @classmethod
    def _polygon_bbox_intersection_area(
        cls,
        polygon: list[Coord],
        bbox: tuple[float, float, float, float],
    ) -> float:
        clipped = cls._clip_polygon_to_bbox(polygon, bbox)
        return cls._polygon_area(clipped)

    @staticmethod
    def _polygon_area(polygon: list[Coord]) -> float:
        if len(polygon) < 3:
            return 0.0
        ring = list(polygon)
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        if len(ring) < 4:
            return 0.0
        total = 0.0
        for idx in range(len(ring) - 1):
            x1, y1 = ring[idx]
            x2, y2 = ring[idx + 1]
            total += (x1 * y2) - (x2 * y1)
        return abs(total) * 0.5

    @classmethod
    def _clip_polygon_to_bbox(
        cls,
        polygon: list[Coord],
        bbox: tuple[float, float, float, float],
    ) -> list[Coord]:
        south, north, west, east = bbox
        if len(polygon) < 3 or south >= north or west >= east:
            return []

        ring = list(polygon)
        if ring[0] == ring[-1]:
            ring = ring[:-1]
        if len(ring) < 3:
            return []

        def inside(point: Coord, edge: str) -> bool:
            lon, lat = point
            if edge == "left":
                return lon >= west
            if edge == "right":
                return lon <= east
            if edge == "bottom":
                return lat >= south
            return lat <= north

        def intersect(prev: Coord, curr: Coord, edge: str) -> Coord | None:
            x1, y1 = prev
            x2, y2 = curr
            if edge in {"left", "right"}:
                x_edge = west if edge == "left" else east
                dx = x2 - x1
                if abs(dx) < 1e-12:
                    return None
                t = (x_edge - x1) / dx
                y = y1 + (t * (y2 - y1))
                return (x_edge, y)
            y_edge = south if edge == "bottom" else north
            dy = y2 - y1
            if abs(dy) < 1e-12:
                return None
            t = (y_edge - y1) / dy
            x = x1 + (t * (x2 - x1))
            return (x, y_edge)

        subject = ring
        for edge_name in ("left", "right", "bottom", "top"):
            if not subject:
                break
            clipped: list[Coord] = []
            prev = subject[-1]
            prev_inside = inside(prev, edge_name)
            for curr in subject:
                curr_inside = inside(curr, edge_name)
                if curr_inside:
                    if not prev_inside:
                        cross = intersect(prev, curr, edge_name)
                        if cross is not None:
                            clipped.append(cross)
                    clipped.append(curr)
                elif prev_inside:
                    cross = intersect(prev, curr, edge_name)
                    if cross is not None:
                        clipped.append(cross)
                prev = curr
                prev_inside = curr_inside
            subject = clipped

        if len(subject) < 3:
            return []
        if subject[0] != subject[-1]:
            subject.append(subject[0])
        return subject

    @staticmethod
    def _union_bbox(
        bboxes: list[tuple[float, float, float, float]],
    ) -> tuple[float, float, float, float] | None:
        if not bboxes:
            return None
        south = min(item[0] for item in bboxes)
        north = max(item[1] for item in bboxes)
        west = min(item[2] for item in bboxes)
        east = max(item[3] for item in bboxes)
        return south, north, west, east
