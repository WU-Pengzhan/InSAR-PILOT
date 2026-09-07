"""Production ASF adapter for AOI-constrained NISAR RSLC discovery."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

import asf_search as asf

from insar_pilot.domain.search import (
    PaginationMode,
    ProviderCapability,
    ProviderDescriptor,
    RemoteSARProduct,
    SearchCapability,
    SearchFilter,
    SearchFilterCapability,
    SearchPage,
    SearchPagination,
    SearchRequest,
    SupportReport,
)
from insar_pilot.download.network import NetworkConfig

NISAR_SEARCH_CAPABILITY = SearchCapability(
    mission="NISAR",
    product_types=("RSLC",),
    platforms=("NISAR",),
    filters=(
        SearchFilterCapability(SearchFilter.ORBIT_DIRECTION, choices=("ASCENDING", "DESCENDING")),
        SearchFilterCapability(SearchFilter.RELATIVE_ORBIT, minimum=1, maximum=173),
        SearchFilterCapability(
            SearchFilter.POLARIZATIONS,
            choices=("HH", "HV", "VV", "VH", "HH+HV", "VV+VH"),
        ),
        SearchFilterCapability(SearchFilter.FREQUENCY_BANDS, choices=("A", "B", "A+B")),
    ),
    pagination=SearchPagination(PaginationMode.PAGE, default_page_size=100, max_page_size=1000),
)

_PRODUCTION_CONFIGURATIONS = {"PR", "UR"}
_DATA_MATURITY = {"BETA", "PROVISIONAL", "VALIDATED"}
_FRAME_COVERAGE = {"FULL", "PARTIAL"}


class ASFNisarSearchProvider:
    """Search ASF/CMR for complete RSLC granules intersecting one AOI."""

    descriptor = ProviderDescriptor(
        provider_id="asf-nisar",
        display_name="ASF DAAC — NISAR",
        capabilities=frozenset({ProviderCapability.SEARCH, ProviderCapability.DOWNLOAD}),
        search_capabilities=(NISAR_SEARCH_CAPABILITY,),
    )

    def __init__(self, *, network: NetworkConfig | None = None) -> None:
        self._network = network or NetworkConfig()

    def supports(self, request: SearchRequest) -> SupportReport:
        report = NISAR_SEARCH_CAPABILITY.supports(request)
        if not report.supported:
            return report
        options = request.provider_options.get(self.descriptor.provider_id, {})
        validators = (
            ("production_configuration", _PRODUCTION_CONFIGURATIONS),
            ("data_maturity", _DATA_MATURITY),
            ("frame_coverage", _FRAME_COVERAGE),
        )
        for name, allowed in validators:
            value = str(options.get(name, "")).strip().upper()
            if value and value not in allowed:
                return SupportReport.unsupported_request(
                    "unsupported_provider_option",
                    f"ASF NISAR option {name} does not support {value}.",
                )
        frame = options.get("frame")
        if frame is not None and (isinstance(frame, bool) or not isinstance(frame, int) or frame < 1):
            return SupportReport.unsupported_request(
                "unsupported_provider_option", "ASF NISAR frame must be a positive integer."
            )
        joint = options.get("joint_observation")
        if joint is not None and not isinstance(joint, bool):
            return SupportReport.unsupported_request(
                "unsupported_provider_option", "ASF NISAR joint_observation must be a boolean."
            )
        return SupportReport.supported_request()

    def search(self, request: SearchRequest) -> SearchPage:
        report = self.supports(request)
        if not report.supported:
            raise ValueError(report.message)
        end_index = request.page * request.page_size
        # NISAR's CMR main/side polarization fields match the complete mode
        # (for example ``HH+HV``), not "contains HH". Generic workflow
        # selections therefore use a small client-side availability filter.
        query_limit = min(max((end_index + 1) * 4, end_index + 1), 10_000)
        results = asf.geo_search(**self._search_kwargs(request, query_limit))
        products_by_id = {
            product.remote_product_id: product
            for product in (self._remote_product(item) for item in results)
            if product.remote_product_id and self._matches_request(product, request)
        }
        ordered = sorted(
            products_by_id.values(),
            key=lambda product: (
                product.acquisition_time.isoformat() if product.acquisition_time is not None else "",
                product.remote_product_id,
            ),
        )
        start_index = (request.page - 1) * request.page_size
        selected = ordered[start_index:end_index]
        has_next = len(ordered) > end_index
        return SearchPage(
            items=tuple(selected),
            provider_id=self.descriptor.provider_id,
            page=request.page,
            page_size=request.page_size,
            next_page=request.page + 1 if has_next else None,
            total_results=None if has_next else len(ordered),
        )

    def _search_kwargs(self, request: SearchRequest, max_results: int) -> dict[str, object]:
        options = request.provider_options.get(self.descriptor.provider_id, {})
        session = asf.ASFSession()
        mode = self._network.normalized_mode()
        if mode == "direct":
            session.trust_env = False
        elif mode == "environment":
            session.trust_env = True
        else:
            session.trust_env = False
            session.proxies.update(self._network.proxy_dict())
        kwargs: dict[str, object] = {
            "platform": getattr(asf.PLATFORM, "NISAR", "NISAR"),
            "processingLevel": getattr(asf.PRODUCT_TYPE, "RSLC", "RSLC"),
            "intersectsWith": request.aoi_wkt,
            "start": self._iso_time(request.start_time),
            "end": self._iso_time(request.end_time),
            "flightDirection": request.orbit_direction,
            "relativeOrbit": request.relative_orbit,
            "maxResults": max_results,
            "opts": asf.ASFSearchOptions(session=session),
        }
        option_map = {
            "frame": "frame",
            "data_maturity": "dataMaturity",
            "frame_coverage": "frameCoverage",
            "joint_observation": "jointObservation",
            "production_configuration": "productionConfiguration",
            "range_bandwidth": "rangeBandwidth",
            "main_band_polarization": "mainBandPolarization",
            "side_band_polarization": "sideBandPolarization",
        }
        for local_name, sdk_name in option_map.items():
            value = options.get(local_name)
            if value is not None and value != "":
                kwargs[sdk_name] = value

        return {key: value for key, value in kwargs.items() if value is not None}

    @staticmethod
    def _matches_request(product: RemoteSARProduct, request: SearchRequest) -> bool:
        return set(request.frequency_bands).issubset(product.frequency_bands) and set(
            request.polarizations
        ).issubset(product.polarizations)

    def _remote_product(self, product: Any) -> RemoteSARProduct:
        props = dict(getattr(product, "properties", {}) or {})
        product_id = str(props.get("sceneName") or props.get("fileID") or props.get("fileName") or "")
        main_polarizations = _text_tuple(props.get("mainBandPolarization"))
        side_polarizations = _text_tuple(props.get("sideBandPolarization"))
        frequency_bands = tuple(
            band for band, polarizations in (("A", main_polarizations), ("B", side_polarizations)) if polarizations
        )
        file_name = str(props.get("fileName") or f"{product_id}.h5")
        return RemoteSARProduct(
            remote_product_id=product_id,
            provider_id=self.descriptor.provider_id,
            mission="NISAR",
            platform="NISAR",
            product_type="RSLC",
            acquisition_time=_parse_time(props.get("startTime")),
            orbit_direction=str(props.get("flightDirection") or "") or None,
            relative_orbit=_safe_int(props.get("pathNumber")),
            polarizations=tuple(dict.fromkeys(main_polarizations + side_polarizations)),
            frequency_bands=frequency_bands,
            footprint=_footprint_geojson(product, props),
            size_bytes=_primary_size_bytes(props.get("bytes"), file_name),
            download_supported=bool(_download_url(product, props)),
            download_url=_download_url(product, props),
            provider_metadata={
                "file_name": file_name,
                "frame_number": _safe_int(props.get("frameNumber")),
                "absolute_orbit": _safe_int(props.get("orbit")),
                "stop_time": str(props.get("stopTime") or ""),
                "main_band_polarizations": main_polarizations,
                "side_band_polarizations": side_polarizations,
                "range_bandwidth": _text_tuple(props.get("rangeBandwidth")),
                "production_configuration": str(props.get("productionConfiguration") or ""),
                "data_maturity": str(props.get("dataMaturity") or ""),
                "frame_coverage": str(props.get("frameCoverage") or ""),
                "joint_observation": bool(props.get("jointObservation", False)),
                "collection_name": str(props.get("collectionName") or ""),
            },
        )

    @staticmethod
    def _iso_time(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")


def _text_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        values: Sequence[object] = value.replace(",", " ").split()
    elif isinstance(value, Sequence):
        values = value
    else:
        values = ()
    return tuple(str(item).strip().upper() for item in values if str(item).strip())


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _primary_size_bytes(value: object, file_name: str) -> int | None:
    if isinstance(value, Mapping):
        entry = value.get(file_name)
        if isinstance(entry, Mapping):
            return _safe_int(entry.get("bytes"))
    return _safe_int(value)


def _download_url(product: Any, props: Mapping[str, object]) -> str:
    for key in ("url", "downloadUrl", "downloadURL"):
        if props.get(key):
            return str(props[key])
    try:
        urls = product.get_urls()
    except Exception:
        return ""
    return str(urls[0]) if urls else ""


def _footprint_geojson(product: Any, props: Mapping[str, object]) -> dict[str, object]:
    candidates = (getattr(product, "geojson", None), getattr(product, "geometry", None), props.get("geometry"))
    for candidate in candidates:
        value = candidate() if callable(candidate) else candidate
        if not isinstance(value, Mapping):
            continue
        if value.get("type") == "Feature" and isinstance(value.get("geometry"), Mapping):
            return dict(value["geometry"])
        if value.get("type") in {"Polygon", "MultiPolygon"}:
            return dict(value)
    return {}


__all__ = ["ASFNisarSearchProvider", "NISAR_SEARCH_CAPABILITY"]
