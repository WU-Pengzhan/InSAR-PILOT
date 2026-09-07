"""Mission-neutral adapter around the existing Sentinel-1 ASF provider."""

from __future__ import annotations

from datetime import datetime

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
    normalize_platform,
)
from insar_pilot.download.models import SceneRecord, SearchCriteria
from insar_pilot.download.network import NetworkConfig
from insar_pilot.download.providers.asf_provider import ASFProvider

SENTINEL1_PLATFORMS = (
    "SENTINEL-1A",
    "SENTINEL-1B",
    "SENTINEL-1C",
    "SENTINEL-1D",
)

SENTINEL1_SEARCH_CAPABILITY = SearchCapability(
    mission="SENTINEL-1",
    product_types=("SLC",),
    platforms=SENTINEL1_PLATFORMS,
    filters=(
        SearchFilterCapability(
            SearchFilter.ORBIT_DIRECTION,
            choices=("ASCENDING", "DESCENDING"),
        ),
        SearchFilterCapability(
            SearchFilter.RELATIVE_ORBIT,
            minimum=1,
            maximum=175,
        ),
        SearchFilterCapability(
            SearchFilter.POLARIZATIONS,
            choices=("VV", "VH", "VV+VH"),
        ),
        SearchFilterCapability(
            SearchFilter.FREQUENCY_BANDS,
            choices=("C",),
        ),
    ),
    pagination=SearchPagination(
        mode=PaginationMode.PAGE,
        default_page_size=100,
        max_page_size=1000,
    ),
)


class ASFSentinel1SearchProvider:
    """Adapt legacy ASF search results without exposing ASF SDK objects."""

    descriptor = ProviderDescriptor(
        provider_id="asf-sentinel-1",
        display_name="ASF DAAC — Sentinel-1",
        capabilities=frozenset({ProviderCapability.SEARCH, ProviderCapability.DOWNLOAD}),
        search_capabilities=(SENTINEL1_SEARCH_CAPABILITY,),
    )

    def __init__(
        self,
        legacy_provider: ASFProvider | None = None,
        *,
        network: NetworkConfig | None = None,
    ) -> None:
        self._legacy_provider = legacy_provider or ASFProvider()
        self._network = network or NetworkConfig()

    def supports(self, request: SearchRequest) -> SupportReport:
        capability_report = SENTINEL1_SEARCH_CAPABILITY.supports(request)
        if not capability_report.supported:
            return capability_report
        platforms = self._requested_platforms(request)
        unavailable = [platform for platform in platforms if not self._legacy_provider.supports_platform(platform)]
        if unavailable:
            return SupportReport.unsupported_request(
                "provider_platform_unsupported",
                f"ASF provider does not support: {', '.join(unavailable)}.",
            )
        return SupportReport.supported_request()

    def search(self, request: SearchRequest) -> SearchPage:
        report = self.supports(request)
        if not report.supported:
            raise ValueError(report.message)

        end_index = request.page * request.page_size
        query_limit = end_index + 1
        scenes: list[SceneRecord] = []
        for platform in self._requested_platforms(request):
            scenes.extend(
                self._legacy_provider.search(
                    self._legacy_criteria(request, platform, query_limit),
                    network=self._network,
                )
            )

        scenes_by_id = {scene.scene_id: scene for scene in scenes}
        ordered = sorted(
            scenes_by_id.values(),
            key=lambda scene: (scene.acquisition_time, scene.scene_id),
            reverse=True,
        )
        start_index = (request.page - 1) * request.page_size
        selected = ordered[start_index:end_index]
        has_next = len(ordered) > end_index
        return SearchPage(
            items=tuple(self._remote_product(scene) for scene in selected),
            provider_id=self.descriptor.provider_id,
            page=request.page,
            page_size=request.page_size,
            next_page=request.page + 1 if has_next else None,
            total_results=None if has_next else len(ordered),
        )

    @staticmethod
    def _requested_platforms(request: SearchRequest) -> tuple[str, ...]:
        requested = request.platforms or SENTINEL1_PLATFORMS
        expanded: list[str] = []
        for value in requested:
            normalized = normalize_platform(value)
            candidates = SENTINEL1_PLATFORMS if normalized == "SENTINEL-1" else (normalized,)
            for candidate in candidates:
                if candidate not in expanded:
                    expanded.append(candidate)
        return tuple(expanded)

    def _legacy_criteria(self, request: SearchRequest, platform: str, max_results: int) -> SearchCriteria:
        provider_options = request.provider_options.get(self.descriptor.provider_id, {})
        beam_mode = str(provider_options.get("beam_mode", "IW"))
        return SearchCriteria(
            start_date=self._iso_time(request.start_time),
            end_date=self._iso_time(request.end_time),
            aoi_mode="wkt",
            wkt=request.aoi_wkt,
            platform=platform,
            beam_mode=beam_mode,
            product_type="SLC",
            orbit_direction=request.orbit_direction or "ANY",
            relative_orbit=request.relative_orbit,
            polarization="+".join(request.polarizations) if request.polarizations else "ANY",
            max_results=max_results,
        )

    def _remote_product(self, scene: SceneRecord) -> RemoteSARProduct:
        return RemoteSARProduct(
            remote_product_id=scene.scene_id,
            provider_id=self.descriptor.provider_id,
            mission="SENTINEL-1",
            platform=scene.platform,
            product_type="SLC",
            acquisition_time=self._parse_time(scene.acquisition_time),
            orbit_direction=scene.orbit_direction,
            relative_orbit=scene.relative_orbit or None,
            polarizations=self._parse_polarizations(scene.polarization),
            frequency_bands=("C",),
            footprint=scene.footprint_geojson,
            size_bytes=round(scene.size_mb * 1024 * 1024) if scene.size_mb > 0 else None,
            download_supported=bool(scene.download_url),
            download_url=scene.download_url,
            provider_metadata={
                "file_name": scene.file_name,
                "coverage_percent": scene.coverage_percent,
            },
        )

    @staticmethod
    def _iso_time(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse_time(value: str) -> datetime | None:
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _parse_polarizations(value: str) -> tuple[str, ...]:
        tokens = value.replace("+", " ").replace(",", " ").split()
        return tuple(token.upper() for token in tokens)
