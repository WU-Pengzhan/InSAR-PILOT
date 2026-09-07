"""Registry for mission-neutral SAR search providers."""

from __future__ import annotations

from insar_pilot.domain.search import ProviderCapability, ProviderDescriptor, SearchRequest
from insar_pilot.providers.sar.base import SARSearchProvider


class ProviderRegistrationError(ValueError):
    """Raised when a provider cannot be registered safely."""


class ProviderRegistry:
    """Own registered search providers without importing any provider SDK."""

    def __init__(self) -> None:
        self._providers: dict[str, SARSearchProvider] = {}

    def register(self, provider: SARSearchProvider) -> None:
        descriptor = provider.descriptor
        provider_id = descriptor.provider_id
        if not provider_id:
            raise ProviderRegistrationError("Provider ID is required.")
        if provider_id in self._providers:
            raise ProviderRegistrationError(f"Provider is already registered: {provider_id}")
        if ProviderCapability.SEARCH not in descriptor.capabilities:
            raise ProviderRegistrationError(f"Search capability is required: {provider_id}")
        if not descriptor.search_capabilities:
            raise ProviderRegistrationError(f"Search schema is required: {provider_id}")
        schema_keys = [
            (capability.mission, capability.product_types, capability.platforms)
            for capability in descriptor.search_capabilities
        ]
        if len(schema_keys) != len(set(schema_keys)):
            raise ProviderRegistrationError(f"Conflicting search schema: {provider_id}")
        if ProviderCapability.PROCESSING in descriptor.capabilities:
            raise ProviderRegistrationError(
                f"Processing capability does not belong in the SAR search registry: {provider_id}"
            )
        self._providers[provider_id] = provider

    def get(self, provider_id: str) -> SARSearchProvider | None:
        return self._providers.get(provider_id.strip().lower())

    def providers(self) -> tuple[SARSearchProvider, ...]:
        return tuple(self._providers.values())

    def descriptors(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(provider.descriptor for provider in self._providers.values())

    def descriptors_supporting(self, request: SearchRequest) -> tuple[ProviderDescriptor, ...]:
        """Return descriptor-only matches without invoking provider code."""

        return tuple(
            descriptor
            for descriptor in self.descriptors()
            if any(capability.supports(request).supported for capability in descriptor.search_capabilities)
        )

    def supporting(self, request: SearchRequest) -> tuple[SARSearchProvider, ...]:
        return tuple(provider for provider in self._providers.values() if provider.supports(request).supported)
