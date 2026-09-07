"""Canonical local SAR product contracts."""

from insar_pilot.domain.local_data.errors import LocalReaderError, ReaderErrorCode, ReaderErrorDetails
from insar_pilot.domain.local_data.models import (
    AssetRef,
    JsonScalar,
    JsonValue,
    LocalSARProduct,
    ProbeResult,
    ReaderCapability,
    ReaderDescriptor,
    ReaderSourceKind,
    SourceSnapshot,
    SupportReport,
    stable_product_id,
)

__all__ = [
    "AssetRef",
    "JsonScalar",
    "JsonValue",
    "LocalReaderError",
    "LocalSARProduct",
    "ProbeResult",
    "ReaderCapability",
    "ReaderDescriptor",
    "ReaderErrorCode",
    "ReaderErrorDetails",
    "ReaderSourceKind",
    "SourceSnapshot",
    "SupportReport",
    "stable_product_id",
]
