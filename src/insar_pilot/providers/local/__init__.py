"""Local SAR reader protocol and registry; production readers arrive in P2."""

from insar_pilot.providers.local.base import (
    CancellationToken,
    LocalSARProductReader,
    NeverCancelled,
    ReaderContext,
)
from insar_pilot.providers.local.nisar import NisarRslcReader
from insar_pilot.providers.local.registry import (
    LocalReaderRegistry,
    LocalSARProductReaderRegistry,
    ReaderRegistrationError,
    ReaderRegistry,
    build_default_local_reader_registry,
)
from insar_pilot.providers.local.sentinel1 import Sentinel1SafeReader

__all__ = [
    "CancellationToken",
    "LocalReaderRegistry",
    "LocalSARProductReader",
    "LocalSARProductReaderRegistry",
    "NeverCancelled",
    "NisarRslcReader",
    "ReaderContext",
    "ReaderRegistrationError",
    "ReaderRegistry",
    "Sentinel1SafeReader",
    "build_default_local_reader_registry",
]
