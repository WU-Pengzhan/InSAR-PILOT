from __future__ import annotations

from datetime import datetime, timezone

import pytest

from insar_pilot.application.search import (
    InvalidSearchRequestError,
    ProviderContractError,
    SearchApplicationService,
    UnsupportedSearchError,
)
from insar_pilot.domain.search import (
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
from insar_pilot.providers.sar import ProviderRegistry


class _FakeProvider:
    def __init__(self, provider_id: str, mission: str, product_type: str) -> None:
        self.descriptor = ProviderDescriptor(
            provider_id=provider_id,
            display_name=provider_id,
            capabilities=frozenset({ProviderCapability.SEARCH}),
            search_capabilities=(
                SearchCapability(
                    mission=mission,
                    product_types=(product_type,),
                    platforms=(mission,),
                    filters=(
                        SearchFilterCapability(
                            SearchFilter.POLARIZATIONS,
                            choices=("VV",),
                        ),
                    ),
                ),
            ),
        )
        self.product_type = product_type
        self.calls = 0
        self.return_value: object | None = None

    def supports(self, request: SearchRequest) -> SupportReport:
        if request.mission not in self.descriptor.missions or request.product_type != self.product_type:
            return SupportReport.unsupported_request("unsupported_request", "Fake provider rejected request.")
        return SupportReport.supported_request()

    def search(self, request: SearchRequest) -> SearchPage:
        self.calls += 1
        if self.return_value is not None:
            return self.return_value  # type: ignore[return-value]
        product = RemoteSARProduct(
            remote_product_id=f"{request.mission}_{request.product_type}_TEST",
            provider_id=self.descriptor.provider_id,
            mission=request.mission,
            platform=request.platforms[0] if request.platforms else request.mission,
            product_type=request.product_type,
            acquisition_time=request.start_time,
        )
        return SearchPage(
            items=(product,),
            provider_id=self.descriptor.provider_id,
            page=request.page,
            page_size=request.page_size,
        )


def _request(mission: str, product_type: str) -> SearchRequest:
    return SearchRequest(
        mission=mission,
        product_type=product_type,
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        aoi_wkt="POLYGON((0 0,1 0,1 1,0 0))",
        page_size=25,
    )


def test_application_service_selects_fake_nisar_rslc_provider():
    provider = _FakeProvider("fake-nisar", "NISAR", "RSLC")
    registry = ProviderRegistry()
    registry.register(provider)
    service = SearchApplicationService(registry)

    page = service.search(_request("NISAR", "RSLC"))

    assert service.provider_descriptors() == (provider.descriptor,)
    assert provider.calls == 1
    assert page.provider_id == "fake-nisar"
    assert page.items[0].product_type == "RSLC"


def test_application_service_rejects_nisar_gslc_before_provider_call():
    provider = _FakeProvider("fake-nisar", "NISAR", "GSLC")
    registry = ProviderRegistry()
    registry.register(provider)

    with pytest.raises(InvalidSearchRequestError) as exc_info:
        SearchApplicationService(registry).search(_request("NISAR", "GSLC"))

    assert exc_info.value.reason_code == "nisar_gslc_unsupported"
    assert "RSLC only" in str(exc_info.value)
    assert provider.calls == 0


def test_application_service_reports_no_supporting_provider():
    provider = _FakeProvider("fake-sentinel", "SENTINEL-1", "SLC")
    registry = ProviderRegistry()
    registry.register(provider)

    with pytest.raises(UnsupportedSearchError) as exc_info:
        SearchApplicationService(registry).search(_request("ALOS", "SLC"))

    assert exc_info.value.report.reason_code == "no_supporting_provider"
    assert provider.calls == 0


def test_application_service_rejects_unadvertised_filter_before_provider_call():
    provider = _FakeProvider("fake-sentinel", "SENTINEL-1", "SLC")
    registry = ProviderRegistry()
    registry.register(provider)
    request = _request("SENTINEL-1", "SLC")
    request = SearchRequest(
        mission=request.mission,
        product_type=request.product_type,
        start_time=request.start_time,
        end_time=request.end_time,
        aoi_wkt=request.aoi_wkt,
        polarizations=("HH",),
        page_size=request.page_size,
    )

    with pytest.raises(UnsupportedSearchError) as exc_info:
        SearchApplicationService(registry).validate_request(request)

    assert exc_info.value.report.reason_code == "unsupported_capability_combination"
    assert provider.calls == 0


def test_application_service_rejects_page_size_above_provider_schema_limit():
    provider = _FakeProvider("fake-sentinel", "SENTINEL-1", "SLC")
    provider.descriptor = ProviderDescriptor(
        provider_id="fake-sentinel",
        display_name="fake-sentinel",
        capabilities=frozenset({ProviderCapability.SEARCH}),
        search_capabilities=(
            SearchCapability(
                mission="SENTINEL-1",
                product_types=("SLC",),
                pagination=SearchPagination(default_page_size=25, max_page_size=50),
            ),
        ),
    )
    registry = ProviderRegistry()
    registry.register(provider)
    request = _request("SENTINEL-1", "SLC")
    request = SearchRequest(
        mission=request.mission,
        product_type=request.product_type,
        start_time=request.start_time,
        end_time=request.end_time,
        aoi_wkt=request.aoi_wkt,
        page_size=100,
    )

    with pytest.raises(UnsupportedSearchError) as exc_info:
        SearchApplicationService(registry).validate_request(request)

    assert exc_info.value.report.reason_code == "unsupported_capability_combination"
    assert provider.calls == 0


def test_application_service_rejects_provider_sdk_objects():
    provider = _FakeProvider("fake-nisar", "NISAR", "RSLC")
    provider.return_value = object()
    registry = ProviderRegistry()
    registry.register(provider)

    with pytest.raises(ProviderContractError, match="did not return SearchPage"):
        SearchApplicationService(registry).search(_request("NISAR", "RSLC"))


def test_application_service_rejects_sdk_objects_nested_in_provider_metadata():
    provider = _FakeProvider("fake-nisar", "NISAR", "RSLC")
    product = RemoteSARProduct(
        remote_product_id="NISAR_RSLC_TEST",
        provider_id="fake-nisar",
        mission="NISAR",
        platform="NISAR",
        product_type="RSLC",
        acquisition_time=None,
        provider_metadata={"native_sdk_product": object()},
    )
    provider.return_value = SearchPage((product,), "fake-nisar", 1, 25)
    registry = ProviderRegistry()
    registry.register(provider)

    with pytest.raises(ProviderContractError, match="non-portable provider metadata"):
        SearchApplicationService(registry).search(_request("NISAR", "RSLC"))
