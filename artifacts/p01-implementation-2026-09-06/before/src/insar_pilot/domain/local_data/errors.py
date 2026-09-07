"""Unified errors exposed by local SAR product readers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from insar_pilot.domain.local_data.models import AssetRef


class ReaderErrorCode(str, Enum):
    UNSUPPORTED_FORMAT = "unsupported_format"
    CORRUPT_CONTAINER = "corrupt_container"
    MISSING_METADATA = "missing_metadata"
    WRONG_PRODUCT_TYPE = "wrong_product_type"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    IO_ERROR = "io_error"
    CANCELLED = "cancelled"
    READER_CONFLICT = "reader_conflict"
    CONTRACT_VIOLATION = "contract_violation"
    DEPENDENCY_MISSING = "dependency_missing"


@dataclass(frozen=True)
class ReaderErrorDetails:
    """Portable context retained without leaking provider/container objects."""

    source_uri: str = ""
    reader_id: str = ""


class LocalReaderError(RuntimeError):
    """One stable error surface for probe and read failures."""

    def __init__(
        self,
        code: ReaderErrorCode,
        message: str,
        *,
        source: AssetRef | None = None,
        reader_id: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = ReaderErrorDetails(
            source_uri=source.uri if source is not None else "",
            reader_id=reader_id.strip().lower(),
        )


__all__ = ["LocalReaderError", "ReaderErrorCode", "ReaderErrorDetails"]
