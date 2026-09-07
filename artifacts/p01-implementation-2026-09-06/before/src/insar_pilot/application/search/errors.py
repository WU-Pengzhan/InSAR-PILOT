"""Application-level errors for remote SAR search."""

from __future__ import annotations

from insar_pilot.domain.search import SupportReport


class SearchApplicationError(RuntimeError):
    """Base class for normalized search application failures."""


class InvalidSearchRequestError(SearchApplicationError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class SearchProviderNotFoundError(SearchApplicationError):
    def __init__(self, provider_id: str) -> None:
        super().__init__(f"Search provider is not registered: {provider_id}")
        self.provider_id = provider_id


class UnsupportedSearchError(SearchApplicationError):
    def __init__(self, provider_id: str, report: SupportReport) -> None:
        super().__init__(report.message or "No registered provider supports this request.")
        self.provider_id = provider_id
        self.report = report


class ProviderContractError(SearchApplicationError):
    """Raised when a provider returns objects outside the domain contract."""

