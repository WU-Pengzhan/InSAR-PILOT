"""Qt-free protocol and execution context for local SAR product readers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from insar_pilot.domain.local_data import (
    AssetRef,
    LocalReaderError,
    LocalSARProduct,
    ReaderDescriptor,
    ReaderErrorCode,
    SupportReport,
)


@runtime_checkable
class CancellationToken(Protocol):
    """Cooperative cancellation boundary shared by scanning and reader I/O."""

    def is_cancelled(self) -> bool: ...


@dataclass(frozen=True)
class NeverCancelled:
    """Default token for synchronous callers that do not need cancellation."""

    def is_cancelled(self) -> bool:
        return False


@dataclass(frozen=True)
class ReaderContext:
    """Bounded execution inputs; readers must honor both fields."""

    cancellation: CancellationToken = field(default_factory=NeverCancelled)
    metadata_read_budget_bytes: int = 1_048_576

    def __post_init__(self) -> None:
        if (
            isinstance(self.metadata_read_budget_bytes, bool)
            or not isinstance(self.metadata_read_budget_bytes, int)
            or self.metadata_read_budget_bytes < 1
        ):
            raise ValueError("metadata_read_budget_bytes must be a positive integer.")
        if not isinstance(self.cancellation, CancellationToken):
            raise TypeError("cancellation must implement CancellationToken.")

    def raise_if_cancelled(
        self,
        *,
        source: AssetRef | None = None,
        reader_id: str = "",
    ) -> None:
        if self.cancellation.is_cancelled():
            raise LocalReaderError(
                ReaderErrorCode.CANCELLED,
                "Local product reading was cancelled.",
                source=source,
                reader_id=reader_id,
            )


@runtime_checkable
class LocalSARProductReader(Protocol):
    """Boundary implemented by each container-specific local product reader."""

    descriptor: ReaderDescriptor

    def probe(self, source: AssetRef, context: ReaderContext) -> SupportReport: ...

    def read(self, source: AssetRef, context: ReaderContext) -> LocalSARProduct: ...


__all__ = [
    "CancellationToken",
    "LocalSARProductReader",
    "NeverCancelled",
    "ReaderContext",
]
