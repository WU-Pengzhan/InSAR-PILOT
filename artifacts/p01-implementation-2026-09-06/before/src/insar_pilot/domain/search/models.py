"""Mission-neutral domain models for remote SAR product search."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType


class ProviderCapability(str, Enum):
    """Capabilities advertised by a provider descriptor."""

    SEARCH = "search"
    DOWNLOAD = "download"
    PROCESSING = "processing"


class SearchFilter(str, Enum):
    """Cross-mission filters that can be advertised to the search form."""

    ORBIT_DIRECTION = "orbit_direction"
    RELATIVE_ORBIT = "relative_orbit"
    POLARIZATIONS = "polarizations"
    FREQUENCY_BANDS = "frequency_bands"


class PaginationMode(str, Enum):
    """Pagination contract exposed by one provider search capability."""

    NONE = "none"
    PAGE = "page"


def normalize_mission(value: str) -> str:
    normalized = value.strip().upper().replace("_", "-")
    if normalized in {"S1", "SENTINEL1", "SENTINEL-1"}:
        return "SENTINEL-1"
    return normalized


def normalize_platform(value: str) -> str:
    normalized = value.strip().upper().replace("_", "-")
    aliases = {
        "S1A": "SENTINEL-1A",
        "S1B": "SENTINEL-1B",
        "S1C": "SENTINEL-1C",
        "S1D": "SENTINEL-1D",
        "SENTINEL1A": "SENTINEL-1A",
        "SENTINEL1B": "SENTINEL-1B",
        "SENTINEL1C": "SENTINEL-1C",
        "SENTINEL1D": "SENTINEL-1D",
    }
    return aliases.get(normalized, normalize_mission(normalized))


def _ordered_unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


@dataclass(frozen=True)
class SearchFilterCapability:
    """Allowed values or numeric range for one cross-mission filter."""

    filter: SearchFilter
    choices: tuple[str, ...] = ()
    minimum: int | None = None
    maximum: int | None = None

    def __post_init__(self) -> None:
        choices = _ordered_unique(tuple(item.strip().upper() for item in self.choices if item.strip()))
        object.__setattr__(self, "choices", choices)
        if self.filter == SearchFilter.RELATIVE_ORBIT:
            if choices or self.minimum is None or self.maximum is None:
                raise ValueError("Relative-orbit capability requires an integer range and no choices.")
            if self.minimum < 1 or self.minimum > self.maximum:
                raise ValueError("Relative-orbit capability range is invalid.")
            return
        if self.minimum is not None or self.maximum is not None:
            raise ValueError(f"Choice filter {self.filter.value} cannot declare an integer range.")
        if not choices:
            raise ValueError(f"Choice filter {self.filter.value} requires at least one choice.")


@dataclass(frozen=True)
class SearchPagination:
    """Page-size limits used by the application service and search form."""

    mode: PaginationMode = PaginationMode.PAGE
    default_page_size: int = 100
    max_page_size: int = 1000

    def __post_init__(self) -> None:
        if self.default_page_size < 1:
            raise ValueError("Default page size must be positive.")
        if self.max_page_size < self.default_page_size:
            raise ValueError("Maximum page size must not be smaller than the default.")


@dataclass(frozen=True)
class SearchCapability:
    """Declarative search schema for one mission/product family."""

    mission: str
    product_types: tuple[str, ...]
    platforms: tuple[str, ...] = ()
    filters: tuple[SearchFilterCapability, ...] = ()
    pagination: SearchPagination = field(default_factory=SearchPagination)

    def __post_init__(self) -> None:
        mission = normalize_mission(self.mission)
        product_types = _ordered_unique(
            tuple(item.strip().upper() for item in self.product_types if item.strip())
        )
        platforms = _ordered_unique(
            tuple(normalize_platform(item) for item in self.platforms if item.strip())
        )
        filters = tuple(self.filters)
        if not mission:
            raise ValueError("Search capability mission is required.")
        if not product_types:
            raise ValueError("Search capability requires at least one product type.")
        filter_names = [item.filter for item in filters]
        if len(filter_names) != len(set(filter_names)):
            raise ValueError("Search capability cannot repeat a filter definition.")
        object.__setattr__(self, "mission", mission)
        object.__setattr__(self, "product_types", product_types)
        object.__setattr__(self, "platforms", platforms)
        object.__setattr__(self, "filters", filters)

    @property
    def supported_filters(self) -> frozenset[SearchFilter]:
        return frozenset(item.filter for item in self.filters)

    def filter_capability(self, filter_name: SearchFilter) -> SearchFilterCapability | None:
        return next((item for item in self.filters if item.filter == filter_name), None)

    def supports(self, request: SearchRequest) -> SupportReport:
        """Check a request using descriptor data only, without invoking a provider."""

        if request.mission != self.mission:
            return SupportReport.unsupported_request("unsupported_mission", "Mission is not advertised.")
        if request.product_type not in self.product_types:
            return SupportReport.unsupported_request(
                "unsupported_product_type",
                f"Product type {request.product_type} is not advertised for {self.mission}.",
            )
        invalid_platforms = [item for item in request.platforms if item not in self.platforms]
        if invalid_platforms:
            return SupportReport.unsupported_request(
                "unsupported_platform",
                f"Platform is not advertised: {', '.join(invalid_platforms)}.",
            )

        choice_filters = (
            (SearchFilter.ORBIT_DIRECTION, request.orbit_direction or ""),
            (SearchFilter.POLARIZATIONS, "+".join(request.polarizations)),
            (SearchFilter.FREQUENCY_BANDS, "+".join(request.frequency_bands)),
        )
        for filter_name, value in choice_filters:
            if not value:
                continue
            capability = self.filter_capability(filter_name)
            if capability is None or value not in capability.choices:
                return SupportReport.unsupported_request(
                    "unsupported_filter",
                    f"Filter {filter_name.value} does not support {value}.",
                )
        if request.relative_orbit is not None:
            capability = self.filter_capability(SearchFilter.RELATIVE_ORBIT)
            if (
                capability is None
                or capability.minimum is None
                or capability.maximum is None
                or not capability.minimum <= request.relative_orbit <= capability.maximum
            ):
                return SupportReport.unsupported_request(
                    "unsupported_filter",
                    f"Relative orbit {request.relative_orbit} is not advertised.",
                )
        if request.page < 1 or not 1 <= request.page_size <= self.pagination.max_page_size:
            return SupportReport.unsupported_request(
                "unsupported_pagination",
                "Requested page or page size is outside the advertised pagination limits.",
            )
        if self.pagination.mode == PaginationMode.NONE and request.page != 1:
            return SupportReport.unsupported_request(
                "unsupported_pagination",
                "This provider does not advertise multi-page search.",
            )
        return SupportReport.supported_request()


@dataclass(frozen=True)
class SearchRequest:
    """Cross-mission search request accepted by application services."""

    mission: str
    product_type: str
    start_time: datetime
    end_time: datetime
    aoi_wkt: str
    platforms: tuple[str, ...] = ()
    orbit_direction: str | None = None
    relative_orbit: int | None = None
    polarizations: tuple[str, ...] = ()
    frequency_bands: tuple[str, ...] = ()
    page: int = 1
    page_size: int = 100
    provider_options: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "mission", normalize_mission(self.mission))
        object.__setattr__(self, "product_type", self.product_type.strip().upper())
        object.__setattr__(self, "aoi_wkt", self.aoi_wkt.strip())
        object.__setattr__(
            self,
            "platforms",
            tuple(normalize_platform(item) for item in self.platforms if item.strip()),
        )
        direction = (self.orbit_direction or "").strip().upper()
        object.__setattr__(self, "orbit_direction", direction or None)
        object.__setattr__(
            self,
            "polarizations",
            tuple(item.strip().upper() for item in self.polarizations if item.strip()),
        )
        object.__setattr__(
            self,
            "frequency_bands",
            tuple(item.strip().upper() for item in self.frequency_bands if item.strip()),
        )
        options = {
            str(namespace): MappingProxyType(dict(values))
            for namespace, values in self.provider_options.items()
        }
        object.__setattr__(self, "provider_options", MappingProxyType(options))


@dataclass(frozen=True)
class RemoteSARProduct:
    """One remote search result, distinct from any imported Catalog product."""

    remote_product_id: str
    provider_id: str
    mission: str
    platform: str
    product_type: str
    acquisition_time: datetime | None
    orbit_direction: str | None = None
    relative_orbit: int | None = None
    polarizations: tuple[str, ...] = ()
    frequency_bands: tuple[str, ...] = ()
    footprint: Mapping[str, object] = field(default_factory=dict)
    size_bytes: int | None = None
    download_supported: bool = False
    download_url: str = ""
    provider_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "remote_product_id", self.remote_product_id.strip())
        object.__setattr__(self, "provider_id", self.provider_id.strip().lower())
        object.__setattr__(self, "mission", normalize_mission(self.mission))
        object.__setattr__(self, "platform", normalize_platform(self.platform))
        object.__setattr__(self, "product_type", self.product_type.strip().upper())
        direction = (self.orbit_direction or "").strip().upper()
        object.__setattr__(self, "orbit_direction", direction or None)
        object.__setattr__(
            self,
            "polarizations",
            tuple(item.strip().upper() for item in self.polarizations if item.strip()),
        )
        object.__setattr__(
            self,
            "frequency_bands",
            tuple(item.strip().upper() for item in self.frequency_bands if item.strip()),
        )
        object.__setattr__(self, "footprint", MappingProxyType(dict(self.footprint)))
        object.__setattr__(self, "provider_metadata", MappingProxyType(dict(self.provider_metadata)))


@dataclass(frozen=True)
class SearchPage:
    """One provider-normalized page of remote SAR products."""

    items: tuple[RemoteSARProduct, ...]
    provider_id: str
    page: int
    page_size: int
    next_page: int | None = None
    total_results: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "provider_id", self.provider_id.strip().lower())


@dataclass(frozen=True)
class ProviderDescriptor:
    """Stable metadata and capabilities for one registered provider."""

    provider_id: str
    display_name: str
    capabilities: frozenset[ProviderCapability]
    search_capabilities: tuple[SearchCapability, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", self.provider_id.strip().lower())
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))
        object.__setattr__(self, "search_capabilities", tuple(self.search_capabilities))

    @property
    def missions(self) -> tuple[str, ...]:
        return _ordered_unique(tuple(item.mission for item in self.search_capabilities))

    def has_capability(self, capability: ProviderCapability) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True)
class SupportReport:
    """Explain whether a provider can execute a specific request."""

    supported: bool
    reason_code: str = ""
    message: str = ""

    @classmethod
    def supported_request(cls) -> SupportReport:
        return cls(supported=True)

    @classmethod
    def unsupported_request(cls, reason_code: str, message: str) -> SupportReport:
        return cls(supported=False, reason_code=reason_code, message=message)
