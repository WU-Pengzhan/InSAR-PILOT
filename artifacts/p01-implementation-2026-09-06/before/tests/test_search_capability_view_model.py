from __future__ import annotations

from insar_pilot.domain.search import (
    ProviderCapability,
    ProviderDescriptor,
    SearchCapability,
    SearchFilter,
    SearchFilterCapability,
    SearchPagination,
)
from insar_pilot.ui.features.search.capability_view_model import SearchCapabilityViewModel


def _descriptor(provider_id: str, capability: SearchCapability) -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=provider_id,
        display_name=provider_id,
        capabilities=frozenset({ProviderCapability.SEARCH}),
        search_capabilities=(capability,),
    )


def test_view_model_preserves_registry_order_and_merges_provider_options():
    sentinel_a = SearchCapability(
        mission="SENTINEL-1",
        product_types=("SLC",),
        platforms=("SENTINEL-1A",),
        filters=(
            SearchFilterCapability(SearchFilter.POLARIZATIONS, choices=("VV", "VV+VH")),
        ),
        pagination=SearchPagination(default_page_size=50, max_page_size=100),
    )
    sentinel_b = SearchCapability(
        mission="SENTINEL-1",
        product_types=("SLC",),
        platforms=("SENTINEL-1B",),
        filters=(
            SearchFilterCapability(SearchFilter.POLARIZATIONS, choices=("HH",)),
        ),
        pagination=SearchPagination(default_page_size=25, max_page_size=100),
    )
    nisar = SearchCapability(mission="NISAR", product_types=("RSLC",), platforms=("NISAR",))
    view_model = SearchCapabilityViewModel(
        (
            _descriptor("sentinel-a", sentinel_a),
            _descriptor("sentinel-b", sentinel_b),
            _descriptor("nisar", nisar),
        )
    )

    assert view_model.missions() == ("SENTINEL-1", "NISAR")
    assert view_model.product_types("NISAR") == ("RSLC",)
    all_options = view_model.options("SENTINEL-1", "SLC")
    assert all_options.platforms == ("SENTINEL-1A", "SENTINEL-1B")
    assert all_options.page_size == 25
    assert all_options.filter_capability(SearchFilter.POLARIZATIONS).choices == (
        "VV",
        "VV+VH",
        "HH",
    )

    platform_options = view_model.options("SENTINEL-1", "SLC", "SENTINEL-1A")
    assert platform_options.filter_capability(SearchFilter.POLARIZATIONS).choices == (
        "VV",
        "VV+VH",
    )
    assert platform_options.page_size == 50


def test_view_model_handles_an_empty_registry():
    view_model = SearchCapabilityViewModel(())

    assert view_model.missions() == ()
    assert view_model.product_types("NISAR") == ()
    assert view_model.options("NISAR", "RSLC").filters == ()
