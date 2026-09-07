"""Portable request and result values for local SAR import."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from insar_pilot.domain.local_data import LocalSARProduct, ReaderErrorCode


class ImportDisposition(str, Enum):
    IMPORTED = "imported"
    WOULD_IMPORT = "would_import"
    DUPLICATE = "duplicate"
    CHANGED = "changed"
    REPLACED = "replaced"
    WOULD_REPLACE = "would_replace"
    ERROR = "error"


@dataclass(frozen=True)
class LocalImportRequest:
    sources: tuple[str, ...]
    dry_run: bool = False
    replace_changed: bool = False
    recursive: bool = True

    def __post_init__(self) -> None:
        normalized = tuple(value.strip() for value in self.sources if value.strip())
        if not normalized:
            raise ValueError("At least one local import source is required.")
        object.__setattr__(self, "sources", normalized)


@dataclass(frozen=True)
class ImportItemResult:
    source_uri: str
    disposition: ImportDisposition
    product: LocalSARProduct | None = None
    error_code: ReaderErrorCode | None = None
    message: str = ""


@dataclass(frozen=True)
class LocalImportResult:
    items: tuple[ImportItemResult, ...]
    cancelled: bool = False
    message: str = ""

    @property
    def imported_count(self) -> int:
        return sum(
            item.disposition in {ImportDisposition.IMPORTED, ImportDisposition.REPLACED}
            for item in self.items
        )

    @property
    def error_count(self) -> int:
        return sum(item.disposition is ImportDisposition.ERROR for item in self.items)


__all__ = [
    "ImportDisposition",
    "ImportItemResult",
    "LocalImportRequest",
    "LocalImportResult",
]
