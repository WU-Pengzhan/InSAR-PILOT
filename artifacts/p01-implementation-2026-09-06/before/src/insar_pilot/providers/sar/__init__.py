"""SAR search provider protocol, adapters, and registry."""

from insar_pilot.download.network import NetworkConfig
from insar_pilot.providers.sar.asf_nisar import NISAR_SEARCH_CAPABILITY, ASFNisarSearchProvider
from insar_pilot.providers.sar.asf_sentinel1 import (
    SENTINEL1_PLATFORMS,
    SENTINEL1_SEARCH_CAPABILITY,
    ASFSentinel1SearchProvider,
)
from insar_pilot.providers.sar.base import SARSearchProvider
from insar_pilot.providers.sar.registry import ProviderRegistrationError, ProviderRegistry


def build_default_sar_provider_registry(*, network: NetworkConfig | None = None) -> ProviderRegistry:
    """Build the production registry for implemented ASF search adapters."""

    registry = ProviderRegistry()
    registry.register(ASFSentinel1SearchProvider(network=network))
    registry.register(ASFNisarSearchProvider(network=network))
    return registry


__all__ = [
    "ASFSentinel1SearchProvider",
    "ASFNisarSearchProvider",
    "NISAR_SEARCH_CAPABILITY",
    "ProviderRegistrationError",
    "ProviderRegistry",
    "SARSearchProvider",
    "SENTINEL1_PLATFORMS",
    "SENTINEL1_SEARCH_CAPABILITY",
    "build_default_sar_provider_registry",
]
