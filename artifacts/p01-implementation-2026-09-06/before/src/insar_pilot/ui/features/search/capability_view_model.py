"""Qt-free projection of provider search capabilities for Workbench controls."""

from __future__ import annotations

from dataclasses import dataclass

from insar_pilot.domain.search import (
    ProviderDescriptor,
    SearchCapability,
    SearchFilter,
    SearchFilterCapability,
)


def _ordered_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


@dataclass(frozen=True)
class SearchFormOptions:
    """Dependent options for one selected mission/product/platform context."""

    platforms: tuple[str, ...] = ()
    filters: tuple[SearchFilterCapability, ...] = ()
    page_size: int = 100
    available: bool = False

    def filter_capability(self, filter_name: SearchFilter) -> SearchFilterCapability | None:
        return next((item for item in self.filters if item.filter == filter_name), None)


class SearchCapabilityViewModel:
    """Aggregate declarative schemas without importing Qt or provider objects."""

    def __init__(self, descriptors: tuple[ProviderDescriptor, ...]) -> None:
        self._capabilities = tuple(
            capability
            for descriptor in descriptors
            for capability in descriptor.search_capabilities
        )

    def missions(self) -> tuple[str, ...]:
        return _ordered_unique(tuple(item.mission for item in self._capabilities))

    def product_types(self, mission: str) -> tuple[str, ...]:
        return _ordered_unique(
            tuple(
                product_type
                for capability in self._capabilities
                if capability.mission == mission
                for product_type in capability.product_types
            )
        )

    def options(self, mission: str, product_type: str, platform: str = "") -> SearchFormOptions:
        product_capabilities = tuple(
            item
            for item in self._capabilities
            if item.mission == mission and product_type in item.product_types
        )
        platforms = _ordered_unique(
            tuple(platform_name for item in product_capabilities for platform_name in item.platforms)
        )
        candidates = tuple(
            item
            for item in product_capabilities
            if not platform or platform in item.platforms
        )
        filters = self._merge_filters(candidates)
        page_size = min(
            (item.pagination.default_page_size for item in candidates),
            default=100,
        )
        return SearchFormOptions(
            platforms=platforms,
            filters=filters,
            page_size=page_size,
            available=bool(candidates),
        )

    @staticmethod
    def _merge_filters(capabilities: tuple[SearchCapability, ...]) -> tuple[SearchFilterCapability, ...]:
        merged: list[SearchFilterCapability] = []
        for filter_name in SearchFilter:
            definitions = tuple(
                definition
                for capability in capabilities
                if (definition := capability.filter_capability(filter_name)) is not None
            )
            if not definitions:
                continue
            if filter_name == SearchFilter.RELATIVE_ORBIT:
                minimum = min(item.minimum for item in definitions if item.minimum is not None)
                maximum = max(item.maximum for item in definitions if item.maximum is not None)
                merged.append(
                    SearchFilterCapability(filter_name, minimum=minimum, maximum=maximum)
                )
                continue
            choices = _ordered_unique(tuple(choice for item in definitions for choice in item.choices))
            merged.append(SearchFilterCapability(filter_name, choices=choices))
        return tuple(merged)
