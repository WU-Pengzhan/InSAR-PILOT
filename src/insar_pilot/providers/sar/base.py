"""Provider protocol for mission-neutral SAR searches."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from insar_pilot.domain.search import ProviderDescriptor, SearchPage, SearchRequest, SupportReport


@runtime_checkable
class SARSearchProvider(Protocol):
    """Boundary implemented by every remote SAR search adapter."""

    descriptor: ProviderDescriptor

    def supports(self, request: SearchRequest) -> SupportReport: ...

    def search(self, request: SearchRequest) -> SearchPage: ...

