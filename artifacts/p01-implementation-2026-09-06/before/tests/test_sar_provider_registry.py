from __future__ import annotations

from datetime import datetime, timezone

import pytest

from insar_pilot.domain.search import (
    ProviderCapability,
    ProviderDescriptor,
    SearchCapability,
    SearchPage,
    SearchRequest,
    SupportReport,
)
from insar_pilot.providers.sar import (
    ProviderRegistrationError,
    ProviderRegistry,
    SARSearchProvider,
    build_default_sar_provider_registry,
)


class _FakeProvider:
    def __init__(self, descriptor: ProviderDescriptor, *, supported: bool = True) -> None:
        self.descriptor = descriptor
        self._supported = supported

    def supports(self, request: SearchRequest) -> SupportReport:
        if self._supported and any(
            capability.supports(request).supported
            for capability in self.descriptor.search_capabilities
        ):
            return SupportReport.supported_request()
        return SupportReport.unsupported_request("unsupported_mission", "Mission is not supported.")

    def search(self, request: SearchRequest) -> SearchPage:
        return SearchPage((), self.descriptor.provider_id, request.page, request.page_size)


def _request(mission: str = "ALOS", product_type: str = "SLC") -> SearchRequest:
    return SearchRequest(
        mission=mission,
        product_type=product_type,
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        aoi_wkt="POLYGON((0 0,1 0,1 1,0 0))",
    )


def test_registry_accepts_search_only_alos_provider():
    capability = SearchCapability(
        mission="ALOS",
        product_types=("SLC",),
        platforms=("ALOS-2",),
    )
    descriptor = ProviderDescriptor(
        provider_id="fake-alos",
        display_name="Fake ALOS",
        capabilities=frozenset({ProviderCapability.SEARCH}),
        search_capabilities=(capability,),
    )
    provider = _FakeProvider(descriptor)
    registry = ProviderRegistry()

    registry.register(provider)

    assert isinstance(provider, SARSearchProvider)
    assert registry.get("FAKE-ALOS") is provider
    assert registry.supporting(_request()) == (provider,)
    assert registry.descriptors() == (descriptor,)
    assert registry.descriptors_supporting(_request()) == (descriptor,)
    assert ProviderCapability.PROCESSING not in descriptor.capabilities


def test_registry_rejects_processing_capability_and_duplicate_ids():
    capability = SearchCapability(mission="ALOS", product_types=("SLC",))
    processing_descriptor = ProviderDescriptor(
        provider_id="bad-alos",
        display_name="Bad ALOS",
        capabilities=frozenset({ProviderCapability.SEARCH, ProviderCapability.PROCESSING}),
        search_capabilities=(capability,),
    )
    registry = ProviderRegistry()

    with pytest.raises(ProviderRegistrationError, match="Processing capability"):
        registry.register(_FakeProvider(processing_descriptor))

    search_descriptor = ProviderDescriptor(
        provider_id="fake-alos",
        display_name="Fake ALOS",
        capabilities=frozenset({ProviderCapability.SEARCH}),
        search_capabilities=(capability,),
    )
    registry.register(_FakeProvider(search_descriptor))
    with pytest.raises(ProviderRegistrationError, match="already registered"):
        registry.register(_FakeProvider(search_descriptor))


def test_default_registry_registers_production_asf_sentinel_and_nisar_adapters():
    registry = build_default_sar_provider_registry()

    assert tuple(descriptor.provider_id for descriptor in registry.descriptors()) == (
        "asf-sentinel-1",
        "asf-nisar",
    )
    descriptor = registry.descriptors()[0]
    assert descriptor.missions == ("SENTINEL-1",)
    assert descriptor.capabilities == frozenset(
        {ProviderCapability.SEARCH, ProviderCapability.DOWNLOAD}
    )
    assert ProviderCapability.PROCESSING not in descriptor.capabilities
    assert descriptor.search_capabilities[0].product_types == ("SLC",)
    assert descriptor.search_capabilities[0].platforms == (
        "SENTINEL-1A",
        "SENTINEL-1B",
        "SENTINEL-1C",
        "SENTINEL-1D",
    )


def test_registry_rejects_search_provider_without_a_schema():
    descriptor = ProviderDescriptor(
        provider_id="schema-less",
        display_name="Schema-less",
        capabilities=frozenset({ProviderCapability.SEARCH}),
        search_capabilities=(),
    )

    with pytest.raises(ProviderRegistrationError, match="Search schema"):
        ProviderRegistry().register(_FakeProvider(descriptor))


def test_registry_rejects_duplicate_search_schema_scope():
    capability = SearchCapability("ALOS", ("SLC",), ("ALOS-2",))
    descriptor = ProviderDescriptor(
        provider_id="conflicting",
        display_name="Conflicting",
        capabilities=frozenset({ProviderCapability.SEARCH}),
        search_capabilities=(capability, capability),
    )

    with pytest.raises(ProviderRegistrationError, match="Conflicting search schema"):
        ProviderRegistry().register(_FakeProvider(descriptor))
