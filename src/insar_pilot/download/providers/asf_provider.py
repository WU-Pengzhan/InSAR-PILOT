"""ASF provider for Sentinel-1 SLC search."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import asf_search as asf

from insar_pilot.download.geometry import polygon_from_kml, polygon_to_wkt
from insar_pilot.download.models import SceneRecord, SearchCriteria
from insar_pilot.download.network import NetworkConfig


class ASFProvider:
    """Provider boundary for ASF searches.

    GUI code should depend on :class:`SceneRecord`, not ASF product objects.
    """

    def search(self, criteria: SearchCriteria, network: NetworkConfig | None = None) -> list[SceneRecord]:
        """Search ASF for Sentinel-1 SLC scenes and map results to records."""

        network = network or NetworkConfig()
        intersects_with = self._intersects_with(criteria)
        session = self._asf_session(network)
        options = asf.ASFSearchOptions(session=session)
        search_kwargs = {
            "platform": self._platform(criteria.platform),
            "processingLevel": self._product_type(criteria.product_type),
            "beamMode": self._beam_mode(criteria.beam_mode),
            "intersectsWith": intersects_with,
            "start": self._date_start(criteria.start_date),
            "end": self._date_end(criteria.end_date),
            "flightDirection": self._orbit_direction(criteria.orbit_direction),
            "relativeOrbit": criteria.relative_orbit,
            "polarization": self._polarization(criteria.polarization),
            "opts": options,
        }
        if criteria.max_results is not None:
            search_kwargs["maxResults"] = max(1, int(criteria.max_results))
        results = asf.geo_search(**search_kwargs)
        return [self._scene_from_product(product) for product in results]

    @staticmethod
    def _asf_session(network: NetworkConfig) -> asf.ASFSession:
        """Create an ASF session that respects GUI network settings."""

        session = asf.ASFSession()
        mode = network.normalized_mode()
        if mode == "direct":
            session.trust_env = False
        elif mode == "environment":
            session.trust_env = True
        else:
            session.trust_env = False
            session.proxies.update(network.proxy_dict())
        return session

    @classmethod
    def _scene_from_product(cls, product: Any) -> SceneRecord:
        props = dict(getattr(product, "properties", {}) or {})
        scene_id = str(props.get("sceneName") or props.get("fileID") or props.get("fileName") or "")
        size_bytes = cls._safe_float(props.get("bytes"))
        file_name = str(props.get("fileName") or f"{scene_id}.zip")
        return SceneRecord(
            scene_id=scene_id,
            acquisition_time=str(props.get("startTime") or props.get("processingDate") or ""),
            platform=str(props.get("platform") or ""),
            orbit_direction=str(props.get("flightDirection") or ""),
            relative_orbit=cls._safe_int(props.get("pathNumber")),
            polarization=str(props.get("polarization") or ""),
            size_mb=size_bytes / (1024 * 1024) if size_bytes else 0.0,
            coverage_percent=0.0,
            status="available",
            local_path="",
            download_url=cls._download_url(product, props),
            file_name=file_name,
            footprint_geojson=cls._footprint_geojson(product, props),
        )

    @staticmethod
    def _download_url(product: Any, props: dict[str, Any]) -> str:
        """Extract the first product download URL exposed by ASF."""

        candidates = [
            props.get("url"),
            props.get("downloadUrl"),
            props.get("downloadURL"),
        ]
        for value in candidates:
            if value:
                return str(value)
        try:
            urls = product.get_urls()
        except Exception:
            return ""
        return str(urls[0]) if urls else ""

    @staticmethod
    def _footprint_geojson(product: Any, props: dict[str, Any]) -> dict[str, Any]:
        """Extract a GeoJSON geometry for footprint preview."""

        candidates = [
            getattr(product, "geojson", None),
            getattr(product, "geometry", None),
            props.get("geometry"),
            props.get("geojson"),
        ]
        for candidate in candidates:
            value = candidate() if callable(candidate) else candidate
            if not isinstance(value, dict):
                continue
            if value.get("type") == "Feature":
                geometry = value.get("geometry")
                return geometry if isinstance(geometry, dict) else {}
            if value.get("type") in {"Polygon", "MultiPolygon", "FeatureCollection"}:
                return value
        return {}

    @classmethod
    def _intersects_with(cls, criteria: SearchCriteria) -> str:
        mode = criteria.aoi_mode.strip().lower()
        if mode == "wkt":
            if not criteria.wkt.strip():
                raise ValueError("WKT AOI is required.")
            return criteria.wkt.strip()
        if mode == "kml":
            if not criteria.aoi_file.strip():
                raise ValueError("AOI KML file is required.")
            return cls._wkt_from_kml(Path(criteria.aoi_file).expanduser())
        if not criteria.bbox.strip():
            raise ValueError("BBOX AOI is required.")
        return cls._wkt_from_bbox(criteria.bbox)

    @staticmethod
    def _wkt_from_bbox(text: str) -> str:
        parts = text.replace(",", " ").split()
        if len(parts) != 4:
            raise ValueError("BBOX must contain minLon,minLat,maxLon,maxLat.")
        try:
            min_lon, min_lat, max_lon, max_lat = [float(part) for part in parts]
        except ValueError as exc:
            raise ValueError("BBOX values must be numeric.") from exc
        if min_lon >= max_lon or min_lat >= max_lat:
            raise ValueError("BBOX must satisfy minLon < maxLon and minLat < maxLat.")
        return (
            "POLYGON(("
            f"{min_lon:g} {min_lat:g},"
            f"{max_lon:g} {min_lat:g},"
            f"{max_lon:g} {max_lat:g},"
            f"{min_lon:g} {max_lat:g},"
            f"{min_lon:g} {min_lat:g}"
            "))"
        )

    @classmethod
    def _wkt_from_kml(cls, path: Path) -> str:
        try:
            return polygon_to_wkt(polygon_from_kml(path))
        except ET.ParseError as exc:
            raise ValueError(f"Failed to parse KML AOI: {path}") from exc

    @staticmethod
    def _date_start(text: str) -> str:
        value = text.strip()
        if len(value) == 8 and value.isdigit():
            value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
        return f"{value}T00:00:00Z" if "T" not in value else value

    @staticmethod
    def _date_end(text: str) -> str:
        value = text.strip()
        if len(value) == 8 and value.isdigit():
            value = f"{value[:4]}-{value[4:6]}-{value[6:]}"
        return f"{value}T23:59:59Z" if "T" not in value else value

    @staticmethod
    def _platform(value: str):
        normalized = value.strip().upper().replace("_", "-")
        if normalized in {"SENTINEL-1A", "S1A"}:
            return [asf.PLATFORM.SENTINEL1A]
        if normalized in {"SENTINEL-1B", "S1B"}:
            return [asf.PLATFORM.SENTINEL1B]
        if normalized in {"SENTINEL-1C", "S1C"} and hasattr(asf.PLATFORM, "SENTINEL1C"):
            return [asf.PLATFORM.SENTINEL1C]
        return [asf.PLATFORM.SENTINEL1]

    @staticmethod
    def _beam_mode(value: str):
        return getattr(asf.BEAMMODE, value.strip().upper() or "IW", value.strip().upper() or "IW")

    @staticmethod
    def _product_type(value: str):
        return getattr(asf.PRODUCT_TYPE, value.strip().upper() or "SLC", value.strip().upper() or "SLC")

    @staticmethod
    def _orbit_direction(value: str) -> str | None:
        value = value.strip().upper()
        return value if value in {"ASCENDING", "DESCENDING"} else None

    @staticmethod
    def _polarization(value: str) -> str | None:
        value = value.strip().upper()
        if value in {"", "ANY"}:
            return None
        if value == "VV+VH":
            return asf.POLARIZATION.VV_VH
        return getattr(asf.POLARIZATION, value, value)

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
