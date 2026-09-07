"""Application service for validated, provider-neutral SAR search."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from insar_pilot.application.search.errors import (
    InvalidSearchRequestError,
    ProviderContractError,
    SearchProviderNotFoundError,
    UnsupportedSearchError,
)
from insar_pilot.domain.search import ProviderDescriptor, RemoteSARProduct, SearchPage, SearchRequest, SupportReport
from insar_pilot.providers.sar.base import SARSearchProvider
from insar_pilot.providers.sar.registry import ProviderRegistry


class SearchApplicationService:
    """Validate requests, select a provider, and enforce normalized results."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self.registry = registry

    def provider_descriptors(self) -> tuple[ProviderDescriptor, ...]:
        """Return immutable provider metadata for capability-driven clients."""

        return self.registry.descriptors()

    def validate_request(self, request: SearchRequest, *, provider_id: str | None = None) -> None:
        """Validate common and declared capabilities without invoking providers."""

        self._validate_common_request(request)
        if request.mission == "NISAR" and request.product_type != "RSLC":
            reason = "nisar_gslc_unsupported" if request.product_type == "GSLC" else "nisar_product_unsupported"
            raise InvalidSearchRequestError(reason, "NISAR search supports RSLC only; GSLC is not supported.")

        descriptors = self.registry.descriptors()
        if provider_id:
            descriptor = next(
                (item for item in descriptors if item.provider_id == provider_id.strip().lower()),
                None,
            )
            if descriptor is None:
                raise SearchProviderNotFoundError(provider_id)
            descriptors = (descriptor,)
        if any(
            capability.supports(request).supported
            for descriptor in descriptors
            for capability in descriptor.search_capabilities
        ):
            return

        reports = [
            capability.supports(request)
            for descriptor in descriptors
            for capability in descriptor.search_capabilities
        ]
        detail = "; ".join(report.message for report in reports if report.message)
        mission_advertised = any(request.mission in descriptor.missions for descriptor in descriptors)
        reason_code = "unsupported_capability_combination" if mission_advertised else "no_supporting_provider"
        raise UnsupportedSearchError(
            provider_id or "",
            SupportReport.unsupported_request(
                reason_code,
                detail or "No registered provider advertises this search combination.",
            ),
        )

    def search(self, request: SearchRequest, *, provider_id: str | None = None) -> SearchPage:
        self.validate_request(request, provider_id=provider_id)
        provider = self._resolve_provider(request, provider_id)
        page = provider.search(request)
        self._validate_provider_result(provider, page)
        return page

    def _resolve_provider(self, request: SearchRequest, provider_id: str | None) -> SARSearchProvider:
        if provider_id:
            provider = self.registry.get(provider_id)
            if provider is None:
                raise SearchProviderNotFoundError(provider_id)
            report = provider.supports(request)
            if not report.supported:
                raise UnsupportedSearchError(provider.descriptor.provider_id, report)
            return provider

        reports: list[SupportReport] = []
        for provider in self.registry.providers():
            report = provider.supports(request)
            if report.supported:
                return provider
            reports.append(report)
        detail = "; ".join(report.message for report in reports if report.message)
        raise UnsupportedSearchError(
            "",
            SupportReport.unsupported_request(
                "no_supporting_provider",
                detail or "No registered provider supports this request.",
            ),
        )

    @staticmethod
    def _validate_common_request(request: SearchRequest) -> None:
        if not request.mission:
            raise InvalidSearchRequestError("mission_required", "Mission is required.")
        if not request.product_type:
            raise InvalidSearchRequestError("product_type_required", "Product type is required.")
        if not request.aoi_wkt:
            raise InvalidSearchRequestError("aoi_required", "AOI WKT is required.")
        if request.start_time > request.end_time:
            raise InvalidSearchRequestError("invalid_date_range", "Start time must not be after end time.")
        if request.page < 1:
            raise InvalidSearchRequestError("invalid_page", "Page must be at least 1.")
        if not 1 <= request.page_size <= 1000:
            raise InvalidSearchRequestError("invalid_page_size", "Page size must be between 1 and 1000.")

    @staticmethod
    def _validate_provider_result(provider: SARSearchProvider, page: object) -> None:
        provider_id = provider.descriptor.provider_id
        if not isinstance(page, SearchPage):
            raise ProviderContractError(f"Provider {provider_id} did not return SearchPage.")
        if page.provider_id != provider_id:
            raise ProviderContractError(
                f"Provider result ID mismatch: expected {provider_id}, got {page.provider_id or '<empty>'}."
            )
        if not all(isinstance(product, RemoteSARProduct) for product in page.items):
            raise ProviderContractError(f"Provider {provider_id} returned a non-RemoteSARProduct item.")
        if any(product.provider_id != provider_id for product in page.items):
            raise ProviderContractError(f"Provider {provider_id} returned a product with a mismatched provider ID.")
        for product in page.items:
            if not SearchApplicationService._is_domain_value(product.footprint):
                raise ProviderContractError(f"Provider {provider_id} returned a non-portable footprint value.")
            if not SearchApplicationService._is_domain_value(product.provider_metadata):
                raise ProviderContractError(
                    f"Provider {provider_id} exposed a non-portable provider metadata value."
                )

    @staticmethod
    def _is_domain_value(value: object) -> bool:
        if value is None or isinstance(value, (str, int, float, bool, datetime)):
            return True
        if isinstance(value, Mapping):
            return all(
                isinstance(key, str) and SearchApplicationService._is_domain_value(item)
                for key, item in value.items()
            )
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return all(SearchApplicationService._is_domain_value(item) for item in value)
        return False
