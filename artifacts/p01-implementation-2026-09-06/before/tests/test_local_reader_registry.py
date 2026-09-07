from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from insar_pilot.domain.local_data import (
    AssetRef,
    LocalReaderError,
    LocalSARProduct,
    ReaderCapability,
    ReaderDescriptor,
    ReaderErrorCode,
    ReaderSourceKind,
    SourceSnapshot,
    SupportReport,
    stable_product_id,
)
from insar_pilot.providers.local import (
    LocalSARProductReader,
    LocalSARProductReaderRegistry,
    ReaderContext,
    ReaderRegistrationError,
)


def _capability(
    mission: str = "SENTINEL-1",
    product_type: str = "SLC",
    suffix: str = ".zip",
    source_kind: ReaderSourceKind = ReaderSourceKind.FILE,
) -> ReaderCapability:
    return ReaderCapability(mission, (product_type,), frozenset({source_kind}), (suffix,))


def _descriptor(
    reader_id: str,
    *,
    capability: ReaderCapability | None = None,
    schema_version: int = 1,
    priority: int = 100,
) -> ReaderDescriptor:
    return ReaderDescriptor(
        reader_id,
        reader_id,
        schema_version,
        (capability or _capability(),),
        priority,
    )


def _product(
    reader_id: str,
    *,
    schema_version: int = 1,
    mission: str = "SENTINEL-1",
    product_type: str = "SLC",
    source_kind: str = "file",
) -> LocalSARProduct:
    native_id = "NATIVE_PRODUCT_001"
    return LocalSARProduct(
        product_id=stable_product_id(mission, product_type, native_id),
        native_product_id=native_id,
        mission=mission,
        platform="S1A" if mission == "SENTINEL-1" else mission,
        product_type=product_type,
        acquisition_mode="IW",
        acquisition_layout="TOPS_SWATHS",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        orbit_direction="DESCENDING",
        orbit_identity=None,
        track=None,
        frame=None,
        relative_orbit=None,
        frequency_bands=("C",),
        polarizations=("VV",),
        footprint_wkt=None,
        assets=(AssetRef("/readonly/S1.zip", "source_product"),),
        native_metadata={},
        reader_id=reader_id,
        reader_schema_version=schema_version,
        source_snapshot=SourceSnapshot(source_kind, 100, 123),
    )


class _FakeReader:
    def __init__(
        self,
        descriptor: ReaderDescriptor,
        *,
        confidence: int = 90,
        supported: bool = True,
        product: LocalSARProduct | None = None,
        report_reader_id: str | None = None,
    ) -> None:
        self.descriptor = descriptor
        self.confidence = confidence
        self.supported = supported
        valid_product_reader_id = (
            descriptor.reader_id
            if re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", descriptor.reader_id)
            else "placeholder.reader"
        )
        self.product = product or _product(
            valid_product_reader_id,
            schema_version=max(descriptor.schema_version, 1),
        )
        self.report_reader_id = report_reader_id or descriptor.reader_id
        self.probe_calls = 0
        self.read_calls = 0

    def probe(self, source: AssetRef, context: ReaderContext) -> SupportReport:
        self.probe_calls += 1
        context.raise_if_cancelled(source=source, reader_id=self.descriptor.reader_id)
        if self.supported:
            return SupportReport.supported_source(
                self.report_reader_id,
                self.confidence,
                detected_product_type=self.product.product_type,
            )
        return SupportReport.unsupported_source(self.report_reader_id)

    def read(self, source: AssetRef, context: ReaderContext) -> LocalSARProduct:
        self.read_calls += 1
        context.raise_if_cancelled(source=source, reader_id=self.descriptor.reader_id)
        return self.product


def test_reader_protocol_registry_and_successful_dispatch() -> None:
    reader = _FakeReader(_descriptor("sentinel1.safe"))
    registry = LocalSARProductReaderRegistry()
    registry.register(reader)

    source = AssetRef("/readonly/S1.zip", "source_product")
    assert isinstance(reader, LocalSARProductReader)
    assert registry.get("SENTINEL1.SAFE") is reader
    assert registry.descriptors() == (reader.descriptor,)
    assert registry.resolve(source).descriptor == reader.descriptor
    assert registry.read(source) == reader.product
    assert reader.probe_calls == 2
    assert reader.read_calls == 1


@pytest.mark.parametrize("reader_id", ["", "bad reader", "-leading"])
def test_registry_validates_reader_id(reader_id: str) -> None:
    with pytest.raises(ReaderRegistrationError, match="Reader ID"):
        LocalSARProductReaderRegistry().register(_FakeReader(_descriptor(reader_id)))


def test_registry_validates_schema_version_and_duplicate_scope() -> None:
    invalid_schema = _FakeReader(_descriptor("invalid.schema", schema_version=0))
    duplicate_scope = ReaderDescriptor(
        "duplicate.scope",
        "Duplicate scope",
        1,
        (_capability(), _capability()),
    )

    with pytest.raises(ReaderRegistrationError, match="schema version"):
        LocalSARProductReaderRegistry().register(invalid_schema)
    with pytest.raises(ReaderRegistrationError, match="Duplicate or overlapping"):
        LocalSARProductReaderRegistry().register(_FakeReader(duplicate_scope))


def test_one_reader_can_declare_non_overlapping_zip_and_safe_scopes() -> None:
    descriptor = ReaderDescriptor(
        "sentinel1.safe",
        "Sentinel-1 SAFE",
        1,
        (
            _capability(suffix=".zip", source_kind=ReaderSourceKind.FILE),
            _capability(suffix=".safe", source_kind=ReaderSourceKind.DIRECTORY),
        ),
    )
    registry = LocalSARProductReaderRegistry()

    registry.register(_FakeReader(descriptor))

    assert registry.descriptors() == (descriptor,)


def test_registry_rejects_duplicate_id_and_cross_reader_product_conflict() -> None:
    registry = LocalSARProductReaderRegistry()
    registry.register(_FakeReader(_descriptor("sentinel1.safe")))

    with pytest.raises(ReaderRegistrationError, match="already registered"):
        registry.register(_FakeReader(_descriptor("sentinel1.safe")))
    with pytest.raises(ReaderRegistrationError, match="Product capability conflict"):
        registry.register(_FakeReader(_descriptor("sentinel1.alternative")))

    non_conflicting = _FakeReader(
        _descriptor("nisar.rslc", capability=_capability("NISAR", "RSLC", ".h5")),
        product=_product("nisar.rslc", mission="NISAR", product_type="RSLC"),
    )
    registry.register(non_conflicting)
    assert tuple(item.reader_id for item in registry.descriptors()) == (
        "sentinel1.safe",
        "nisar.rslc",
    )


def test_registry_enforces_current_nisar_and_alos_local_scope() -> None:
    with pytest.raises(ReaderRegistrationError, match="RSLC only"):
        LocalSARProductReaderRegistry().register(
            _FakeReader(_descriptor("nisar.gslc", capability=_capability("NISAR", "GSLC", ".h5")))
        )
    with pytest.raises(ReaderRegistrationError, match="search-only"):
        LocalSARProductReaderRegistry().register(
            _FakeReader(_descriptor("alos.slc", capability=_capability("ALOS", "SLC", ".zip")))
        )


def test_registry_reports_unsupported_and_equal_confidence_conflicts() -> None:
    source = AssetRef("/readonly/unknown.bin", "source_product")
    unsupported_registry = LocalSARProductReaderRegistry()
    unsupported_registry.register(_FakeReader(_descriptor("sentinel1.safe"), supported=False))
    with pytest.raises(LocalReaderError) as unsupported_error:
        unsupported_registry.resolve(source)
    assert unsupported_error.value.code == ReaderErrorCode.UNSUPPORTED_FORMAT

    conflict_registry = LocalSARProductReaderRegistry()
    conflict_registry.register(_FakeReader(_descriptor("sentinel1.safe"), confidence=80))
    conflict_registry.register(
        _FakeReader(
            _descriptor("nisar.rslc", capability=_capability("NISAR", "RSLC", ".h5")),
            confidence=80,
            product=_product("nisar.rslc", mission="NISAR", product_type="RSLC"),
        )
    )
    with pytest.raises(LocalReaderError) as conflict_error:
        conflict_registry.resolve(source)
    assert conflict_error.value.code == ReaderErrorCode.READER_CONFLICT


@pytest.mark.parametrize(
    ("product", "message"),
    [
        (_product("wrong.reader"), "reader_id"),
        (_product("sentinel1.safe", schema_version=2), "schema version"),
        (
            _product("sentinel1.safe", mission="OTHER", product_type="SLC"),
            "outside its registered",
        ),
    ],
)
def test_registry_rejects_reader_products_that_violate_the_descriptor(
    product: LocalSARProduct,
    message: str,
) -> None:
    registry = LocalSARProductReaderRegistry()
    registry.register(_FakeReader(_descriptor("sentinel1.safe"), product=product))

    with pytest.raises(LocalReaderError, match=message) as error:
        registry.read(AssetRef("/readonly/S1.zip", "source_product"))
    assert error.value.code == ReaderErrorCode.CONTRACT_VIOLATION


def test_registry_rejects_probe_product_type_outside_descriptor() -> None:
    registry = LocalSARProductReaderRegistry()
    product = _product("sentinel1.safe", mission="NISAR", product_type="RSLC")
    registry.register(_FakeReader(_descriptor("sentinel1.safe"), product=product))

    with pytest.raises(LocalReaderError, match="undeclared product type") as error:
        registry.resolve(AssetRef("/readonly/S1.zip", "source_product"))
    assert error.value.code == ReaderErrorCode.CONTRACT_VIOLATION


def test_probe_provenance_and_cancellation_are_enforced() -> None:
    bad_report_registry = LocalSARProductReaderRegistry()
    bad_report_registry.register(_FakeReader(_descriptor("sentinel1.safe"), report_reader_id="different.reader"))
    with pytest.raises(LocalReaderError) as report_error:
        bad_report_registry.resolve(AssetRef("/readonly/S1.zip", "source_product"))
    assert report_error.value.code == ReaderErrorCode.CONTRACT_VIOLATION

    class _Cancelled:
        def is_cancelled(self) -> bool:
            return True

    cancelled_reader = _FakeReader(_descriptor("sentinel1.safe"))
    cancelled_registry = LocalSARProductReaderRegistry()
    cancelled_registry.register(cancelled_reader)
    with pytest.raises(LocalReaderError) as cancelled_error:
        cancelled_registry.read(
            AssetRef("/readonly/S1.zip", "source_product"),
            ReaderContext(cancellation=_Cancelled()),
        )
    assert cancelled_error.value.code == ReaderErrorCode.CANCELLED
    assert cancelled_reader.probe_calls == 0
