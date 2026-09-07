from __future__ import annotations

from datetime import datetime, timezone

import pytest

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


def test_search_request_normalizes_cross_mission_fields_and_provider_options():
    request = SearchRequest(
        mission="s1",
        platforms=("s1a", "sentinel_1d"),
        product_type="slc",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        aoi_wkt="  POLYGON((0 0,1 0,1 1,0 0))  ",
        orbit_direction="ascending",
        polarizations=("vv", "vh"),
        frequency_bands=("c",),
        provider_options={"asf-sentinel-1": {"beam_mode": "IW"}},
    )

    assert request.mission == "SENTINEL-1"
    assert request.platforms == ("SENTINEL-1A", "SENTINEL-1D")
    assert request.product_type == "SLC"
    assert request.orbit_direction == "ASCENDING"
    assert request.polarizations == ("VV", "VH")
    assert request.frequency_bands == ("C",)
    assert request.aoi_wkt.startswith("POLYGON")
    with pytest.raises(TypeError):
        request.provider_options["asf-sentinel-1"]["beam_mode"] = "EW"  # type: ignore[index]


def test_remote_product_is_a_remote_reference_not_a_catalog_product():
    product = RemoteSARProduct(
        remote_product_id="NISAR_TEST",
        provider_id="fake-nisar",
        mission="nisar",
        platform="nisar",
        product_type="rslc",
        acquisition_time=None,
        provider_metadata={"native_id": "sdk-independent"},
    )
    page = SearchPage(
        items=(product,),
        provider_id="fake-nisar",
        page=1,
        page_size=25,
    )

    assert product.mission == "NISAR"
    assert product.product_type == "RSLC"
    assert not hasattr(product, "local_path")
    assert not hasattr(product, "processing_capability")
    assert page.items == (product,)


def test_provider_descriptor_and_support_report_are_explicit():
    capability = SearchCapability(
        mission="alos",
        product_types=("slc",),
        platforms=("alos-2",),
        filters=(
            SearchFilterCapability(SearchFilter.FREQUENCY_BANDS, choices=("l",)),
        ),
        pagination=SearchPagination(PaginationMode.PAGE, 25, 100),
    )
    descriptor = ProviderDescriptor(
        provider_id="fake-alos",
        display_name="Fake ALOS",
        capabilities=frozenset({ProviderCapability.SEARCH}),
        search_capabilities=(capability,),
    )
    report = SupportReport.unsupported_request("unsupported_product_type", "Search-only product mismatch.")

    assert descriptor.missions == ("ALOS",)
    assert descriptor.has_capability(ProviderCapability.SEARCH)
    assert not descriptor.has_capability(ProviderCapability.PROCESSING)
    assert report.supported is False
    assert report.reason_code == "unsupported_product_type"
    assert capability.product_types == ("SLC",)
    assert capability.platforms == ("ALOS-2",)
    assert capability.supported_filters == frozenset({SearchFilter.FREQUENCY_BANDS})


def test_search_capability_validates_filters_and_pagination_without_provider_objects():
    capability = SearchCapability(
        mission="NISAR",
        product_types=("RSLC",),
        platforms=("NISAR",),
        filters=(
            SearchFilterCapability(SearchFilter.RELATIVE_ORBIT, minimum=1, maximum=173),
            SearchFilterCapability(SearchFilter.POLARIZATIONS, choices=("HH", "HH+HV")),
        ),
        pagination=SearchPagination(default_page_size=25, max_page_size=50),
    )
    request = SearchRequest(
        mission="NISAR",
        product_type="RSLC",
        platforms=("NISAR",),
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        aoi_wkt="POLYGON((0 0,1 0,1 1,0 0))",
        relative_orbit=12,
        polarizations=("HH", "HV"),
        page_size=25,
    )

    assert capability.supports(request).supported
    assert not capability.supports(
        SearchRequest(
            mission="NISAR",
            product_type="GSLC",
            start_time=request.start_time,
            end_time=request.end_time,
            aoi_wkt=request.aoi_wkt,
            page_size=25,
        )
    ).supported


def test_search_filter_and_pagination_capabilities_reject_invalid_definitions():
    with pytest.raises(ValueError, match="integer range"):
        SearchFilterCapability(SearchFilter.RELATIVE_ORBIT, choices=("1",))
    with pytest.raises(ValueError, match="requires at least one choice"):
        SearchFilterCapability(SearchFilter.POLARIZATIONS)
    with pytest.raises(ValueError, match="Maximum page size"):
        SearchPagination(default_page_size=100, max_page_size=25)
