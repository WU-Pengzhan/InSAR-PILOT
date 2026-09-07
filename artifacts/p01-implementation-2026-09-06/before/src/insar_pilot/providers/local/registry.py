"""Validated registry for local SAR product readers."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

from insar_pilot.domain.local_data import (
    AssetRef,
    LocalReaderError,
    LocalSARProduct,
    ReaderCapability,
    ReaderDescriptor,
    ReaderErrorCode,
    ReaderSourceKind,
    SupportReport,
)
from insar_pilot.providers.local.base import LocalSARProductReader, ReaderContext

_READER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class ReaderRegistrationError(ValueError):
    """Raised when a reader descriptor would make dispatch unsafe."""


class LocalSARProductReaderRegistry:
    """Select readers by lightweight probes and enforce their declared contract."""

    def __init__(self) -> None:
        self._readers: dict[str, LocalSARProductReader] = {}

    def register(self, reader: LocalSARProductReader) -> None:
        if not isinstance(reader, LocalSARProductReader):
            raise ReaderRegistrationError("Reader must implement probe() and read().")
        descriptor = reader.descriptor
        self._validate_descriptor(descriptor)
        if descriptor.reader_id in self._readers:
            raise ReaderRegistrationError(f"Reader is already registered: {descriptor.reader_id}")
        for existing in self.descriptors():
            conflict = _first_scope_conflict(existing, descriptor)
            if conflict is not None:
                raise ReaderRegistrationError(
                    "Product capability conflict between readers "
                    f"{existing.reader_id} and {descriptor.reader_id}: {_scope_text(conflict)}"
                )
        self._readers[descriptor.reader_id] = reader

    def get(self, reader_id: str) -> LocalSARProductReader | None:
        return self._readers.get(reader_id.strip().lower())

    def readers(self) -> tuple[LocalSARProductReader, ...]:
        return tuple(
            sorted(
                self._readers.values(),
                key=lambda reader: (-reader.descriptor.priority, reader.descriptor.reader_id),
            )
        )

    def descriptors(self) -> tuple[ReaderDescriptor, ...]:
        return tuple(reader.descriptor for reader in self._readers.values())

    def probe_all(
        self,
        source: AssetRef,
        context: ReaderContext | None = None,
    ) -> tuple[SupportReport, ...]:
        actual_context = context or ReaderContext()
        reports: list[SupportReport] = []
        for reader in self.readers():
            reader_id = reader.descriptor.reader_id
            actual_context.raise_if_cancelled(source=source, reader_id=reader_id)
            try:
                report = reader.probe(source, actual_context)
            except OSError as exc:
                raise LocalReaderError(
                    ReaderErrorCode.IO_ERROR,
                    f"Could not probe local source: {exc}",
                    source=source,
                    reader_id=reader_id,
                ) from exc
            self._validate_report(report, reader.descriptor, source)
            reports.append(report)
        return tuple(reports)

    def resolve(
        self,
        source: AssetRef,
        context: ReaderContext | None = None,
    ) -> LocalSARProductReader:
        actual_context = context or ReaderContext()
        reports = self.probe_all(source, actual_context)
        matches = [report for report in reports if report.supported]
        if not matches:
            reason_messages = tuple(report.message for report in reports if report.message)
            detail = f" ({'; '.join(reason_messages)})" if reason_messages else ""
            raise LocalReaderError(
                ReaderErrorCode.UNSUPPORTED_FORMAT,
                f"No registered reader supports this local source{detail}.",
                source=source,
            )
        highest_confidence = max(report.confidence for report in matches)
        strongest = [report for report in matches if report.confidence == highest_confidence]
        if len(strongest) != 1:
            reader_ids = ", ".join(sorted(report.reader_id for report in strongest))
            raise LocalReaderError(
                ReaderErrorCode.READER_CONFLICT,
                f"Multiple readers matched with confidence {highest_confidence}: {reader_ids}",
                source=source,
            )
        reader = self.get(strongest[0].reader_id)
        if reader is None:  # Guard against a malformed report or concurrent registry mutation.
            raise LocalReaderError(
                ReaderErrorCode.CONTRACT_VIOLATION,
                f"Probe selected an unregistered reader: {strongest[0].reader_id}",
                source=source,
            )
        return reader

    def read(
        self,
        source: AssetRef,
        context: ReaderContext | None = None,
    ) -> LocalSARProduct:
        actual_context = context or ReaderContext()
        reader = self.resolve(source, actual_context)
        descriptor = reader.descriptor
        actual_context.raise_if_cancelled(source=source, reader_id=descriptor.reader_id)
        try:
            product = reader.read(source, actual_context)
        except OSError as exc:
            raise LocalReaderError(
                ReaderErrorCode.IO_ERROR,
                f"Could not read local source: {exc}",
                source=source,
                reader_id=descriptor.reader_id,
            ) from exc
        actual_context.raise_if_cancelled(source=source, reader_id=descriptor.reader_id)
        self._validate_product(product, descriptor, source)
        return product

    @staticmethod
    def _validate_descriptor(descriptor: ReaderDescriptor) -> None:
        if not isinstance(descriptor, ReaderDescriptor):
            raise ReaderRegistrationError("Reader descriptor must be a ReaderDescriptor.")
        if not _READER_ID_PATTERN.fullmatch(descriptor.reader_id):
            raise ReaderRegistrationError(
                f"Reader ID is not a stable lowercase identifier: {descriptor.reader_id or '<empty>'}"
            )
        if not descriptor.display_name:
            raise ReaderRegistrationError(f"Reader display name is required: {descriptor.reader_id}")
        if (
            isinstance(descriptor.schema_version, bool)
            or not isinstance(descriptor.schema_version, int)
            or descriptor.schema_version < 1
        ):
            raise ReaderRegistrationError(f"Reader schema version must be a positive integer: {descriptor.reader_id}")
        if isinstance(descriptor.priority, bool) or not isinstance(descriptor.priority, int) or descriptor.priority < 0:
            raise ReaderRegistrationError(f"Reader priority must be a non-negative integer: {descriptor.reader_id}")
        if not descriptor.capabilities:
            raise ReaderRegistrationError(f"Reader requires at least one product capability: {descriptor.reader_id}")
        for capability in descriptor.capabilities:
            _validate_capability(capability, descriptor.reader_id)
        for index, capability in enumerate(descriptor.capabilities):
            for other in descriptor.capabilities[index + 1 :]:
                if capability.overlaps(other):
                    raise ReaderRegistrationError(
                        f"Duplicate or overlapping capability scope in {descriptor.reader_id}: "
                        f"{_scope_text(capability)}"
                    )

    @staticmethod
    def _validate_report(
        report: SupportReport,
        descriptor: ReaderDescriptor,
        source: AssetRef,
    ) -> None:
        if not isinstance(report, SupportReport):
            raise LocalReaderError(
                ReaderErrorCode.CONTRACT_VIOLATION,
                f"Reader {descriptor.reader_id} returned a non-SupportReport probe result.",
                source=source,
                reader_id=descriptor.reader_id,
            )
        if report.reader_id != descriptor.reader_id:
            raise LocalReaderError(
                ReaderErrorCode.CONTRACT_VIOLATION,
                f"Reader {descriptor.reader_id} returned probe provenance {report.reader_id}.",
                source=source,
                reader_id=descriptor.reader_id,
            )
        if (
            report.supported
            and report.detected_product_type is not None
            and not any(
                report.detected_product_type in capability.product_types for capability in descriptor.capabilities
            )
        ):
            raise LocalReaderError(
                ReaderErrorCode.CONTRACT_VIOLATION,
                f"Reader {descriptor.reader_id} supported an undeclared product type: {report.detected_product_type}.",
                source=source,
                reader_id=descriptor.reader_id,
            )

    @staticmethod
    def _validate_product(
        product: LocalSARProduct,
        descriptor: ReaderDescriptor,
        source: AssetRef,
    ) -> None:
        if not isinstance(product, LocalSARProduct):
            raise LocalReaderError(
                ReaderErrorCode.CONTRACT_VIOLATION,
                f"Reader {descriptor.reader_id} returned a non-LocalSARProduct value.",
                source=source,
                reader_id=descriptor.reader_id,
            )
        if product.reader_id != descriptor.reader_id:
            raise LocalReaderError(
                ReaderErrorCode.CONTRACT_VIOLATION,
                f"Product reader_id {product.reader_id} does not match {descriptor.reader_id}.",
                source=source,
                reader_id=descriptor.reader_id,
            )
        if product.reader_schema_version != descriptor.schema_version:
            raise LocalReaderError(
                ReaderErrorCode.CONTRACT_VIOLATION,
                "Product reader schema version does not match its reader descriptor.",
                source=source,
                reader_id=descriptor.reader_id,
            )
        source_kind = ReaderSourceKind(product.source_snapshot.source_kind)
        suffix = _source_suffix(source.uri)
        if not any(
            capability.covers(
                mission=product.mission,
                product_type=product.product_type,
                source_kind=source_kind,
                suffix=suffix,
            )
            for capability in descriptor.capabilities
        ):
            raise LocalReaderError(
                ReaderErrorCode.CONTRACT_VIOLATION,
                "Reader returned a product outside its registered product capability.",
                source=source,
                reader_id=descriptor.reader_id,
            )


LocalReaderRegistry = LocalSARProductReaderRegistry
ReaderRegistry = LocalSARProductReaderRegistry


def _validate_capability(capability: ReaderCapability, reader_id: str) -> None:
    if not isinstance(capability, ReaderCapability):
        raise ReaderRegistrationError(f"Reader capability must be a ReaderCapability: {reader_id}")
    if not capability.mission:
        raise ReaderRegistrationError(f"Reader capability mission is required: {reader_id}")
    if not capability.product_types:
        raise ReaderRegistrationError(f"Reader capability requires at least one product type: {reader_id}")
    if not capability.source_kinds:
        raise ReaderRegistrationError(f"Reader capability requires at least one source kind: {reader_id}")
    if capability.mission == "NISAR" and capability.product_types != ("RSLC",):
        raise ReaderRegistrationError("NISAR local readers may declare RSLC only; GSLC is unsupported.")
    if capability.mission.startswith("ALOS"):
        raise ReaderRegistrationError("ALOS remains search-only and cannot register a local reader.")


def _first_scope_conflict(
    existing: ReaderDescriptor,
    candidate: ReaderDescriptor,
) -> ReaderCapability | None:
    for capability in candidate.capabilities:
        if any(capability.overlaps(other) for other in existing.capabilities):
            return capability
    return None


def _scope_text(capability: ReaderCapability) -> str:
    products = "/".join(capability.product_types) or "<none>"
    kinds = "/".join(sorted(kind.value for kind in capability.source_kinds)) or "<none>"
    suffixes = "/".join(capability.suffixes) or "*"
    return f"{capability.mission}:{products}:{kinds}:{suffixes}"


def _source_suffix(uri: str) -> str:
    parsed = urlparse(uri)
    path = unquote(parsed.path) if parsed.scheme else uri
    return PurePosixPath(path).suffix.lower()


__all__ = [
    "build_default_local_reader_registry",
    "LocalReaderRegistry",
    "LocalSARProductReaderRegistry",
    "ReaderRegistrationError",
    "ReaderRegistry",
]


def build_default_local_reader_registry() -> LocalSARProductReaderRegistry:
    """Build the production registry without importing optional SDK objects into callers."""

    from insar_pilot.providers.local.nisar import NisarRslcReader
    from insar_pilot.providers.local.sentinel1 import Sentinel1SafeReader

    registry = LocalSARProductReaderRegistry()
    registry.register(Sentinel1SafeReader())
    registry.register(NisarRslcReader())
    return registry
