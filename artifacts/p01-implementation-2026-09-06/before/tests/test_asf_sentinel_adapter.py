from __future__ import annotations

from datetime import datetime, timezone

import asf_search as asf
import pytest

from insar_pilot.domain.search import RemoteSARProduct, SearchRequest
from insar_pilot.download.models import SceneRecord, SearchCriteria
from insar_pilot.download.network import NetworkConfig
from insar_pilot.download.providers.asf_provider import ASFProvider
from insar_pilot.providers.sar import SENTINEL1_PLATFORMS, ASFSentinel1SearchProvider


class _FakeLegacyASFProvider(ASFProvider):
    def __init__(self, *, unavailable: tuple[str, ...] = ()) -> None:
        self.unavailable = unavailable
        self.calls: list[tuple[SearchCriteria, NetworkConfig | None]] = []

    def supports_platform(self, value: str) -> bool:  # type: ignore[override]
        return value not in self.unavailable

    def search(self, criteria: SearchCriteria, network: NetworkConfig | None = None) -> list[SceneRecord]:
        self.calls.append((criteria, network))
        platform = criteria.platform.title().replace("Sentinel", "Sentinel")
        return [
            SceneRecord(
                scene_id=f"{criteria.platform}_TEST",
                acquisition_time="2026-01-02T03:04:05Z",
                platform=platform,
                orbit_direction="ASCENDING",
                relative_orbit=42,
                polarization="VV+VH",
                size_mb=100.0,
                download_url=f"https://example.test/{criteria.platform}.zip",
                file_name=f"{criteria.platform}.zip",
                footprint_geojson={"type": "Polygon", "coordinates": []},
            )
        ]


def _request(
    *,
    platforms: tuple[str, ...] = (),
    polarizations: tuple[str, ...] = (),
) -> SearchRequest:
    return SearchRequest(
        mission="SENTINEL-1",
        platforms=platforms,
        product_type="SLC",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 31, tzinfo=timezone.utc),
        aoi_wkt="POLYGON((0 0,1 0,1 1,0 0))",
        polarizations=polarizations,
        page_size=10,
    )


def test_legacy_asf_provider_maps_all_sentinel_platforms_explicitly():
    expected = {
        "SENTINEL-1A": asf.PLATFORM.SENTINEL1A,
        "SENTINEL-1B": asf.PLATFORM.SENTINEL1B,
        "SENTINEL-1C": asf.PLATFORM.SENTINEL1C,
        "SENTINEL-1D": asf.PLATFORM.SENTINEL1D,
    }

    for platform, provider_value in expected.items():
        assert ASFProvider._platform(platform) == [provider_value]
        assert ASFProvider.supports_platform(platform)


def test_legacy_asf_provider_does_not_fallback_when_dependency_lacks_sentinel_1d(monkeypatch):
    class _PlatformWithoutD:
        SENTINEL1 = "SENTINEL1"
        SENTINEL1A = "SENTINEL1A"
        SENTINEL1B = "SENTINEL1B"
        SENTINEL1C = "SENTINEL1C"

    monkeypatch.setattr("insar_pilot.download.providers.asf_provider.asf.PLATFORM", _PlatformWithoutD)

    assert ASFProvider.supports_platform("SENTINEL-1D") is False
    with pytest.raises(ValueError, match="does not support platform SENTINEL-1D"):
        ASFProvider._platform("SENTINEL-1D")


def test_asf_adapter_expands_unconstrained_request_to_a_b_c_d():
    legacy = _FakeLegacyASFProvider()
    adapter = ASFSentinel1SearchProvider(legacy)

    page = adapter.search(_request())

    assert tuple(call[0].platform for call in legacy.calls) == SENTINEL1_PLATFORMS
    assert len(page.items) == 4
    assert all(isinstance(item, RemoteSARProduct) for item in page.items)
    assert all(item.provider_id == "asf-sentinel-1" for item in page.items)
    assert all(item.frequency_bands == ("C",) for item in page.items)
    assert all(call[0].max_results == 11 for call in legacy.calls)


def test_asf_adapter_reports_sentinel_1d_as_unsupported_without_fallback():
    legacy = _FakeLegacyASFProvider(unavailable=("SENTINEL-1D",))
    adapter = ASFSentinel1SearchProvider(legacy)

    report = adapter.supports(_request(platforms=("S1D",)))

    assert report.supported is False
    assert report.reason_code == "provider_platform_unsupported"
    assert "SENTINEL-1D" in report.message
    assert legacy.calls == []


def test_asf_adapter_converts_scene_records_without_sdk_objects():
    legacy = _FakeLegacyASFProvider()
    adapter = ASFSentinel1SearchProvider(legacy)

    product = adapter.search(_request(platforms=("S1A",))).items[0]

    assert product.remote_product_id == "SENTINEL-1A_TEST"
    assert product.product_type == "SLC"
    assert product.polarizations == ("VV", "VH")
    assert product.size_bytes == 100 * 1024 * 1024
    assert product.download_supported is True
    assert not hasattr(product, "properties")


def test_asf_adapter_passes_advertised_dual_polarization_to_legacy_provider():
    legacy = _FakeLegacyASFProvider()
    adapter = ASFSentinel1SearchProvider(legacy)

    adapter.search(_request(platforms=("S1A",), polarizations=("VV", "VH")))

    assert legacy.calls[0][0].polarization == "VV+VH"
