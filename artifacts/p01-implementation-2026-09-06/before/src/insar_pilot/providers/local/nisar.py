"""Read-only NISAR RSLC HDF5 reader with a lazy optional h5py dependency."""

from __future__ import annotations

import hashlib
import importlib
from contextlib import suppress
from pathlib import Path
from typing import Any

from insar_pilot.domain.local_data import (
    AssetRef,
    JsonValue,
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
from insar_pilot.providers.local.base import ReaderContext
from insar_pilot.providers.local.path_utils import local_path, utc_datetime

_HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"
_IDENTIFICATION_PATH = "/science/LSAR/identification"
_RSLC_SWATHS_PATH = "/science/LSAR/RSLC/swaths"


class NisarRslcReader:
    """Project small identification datasets without reading RSLC image samples."""

    descriptor = ReaderDescriptor(
        reader_id="nisar.rslc",
        display_name="NISAR RSLC",
        schema_version=1,
        capabilities=(
            ReaderCapability(
                "NISAR",
                ("RSLC",),
                frozenset({ReaderSourceKind.FILE}),
                (".h5", ".hdf5"),
            ),
        ),
        priority=100,
    )

    def probe(self, source: AssetRef, context: ReaderContext) -> SupportReport:
        context.raise_if_cancelled(source=source, reader_id=self.descriptor.reader_id)
        path = local_path(source, self.descriptor.reader_id)
        if not path.is_file() or path.suffix.lower() not in {".h5", ".hdf5"}:
            return SupportReport.unsupported_source(self.descriptor.reader_id)
        self._check_signature(path, source)
        h5py = _load_h5py(source, self.descriptor.reader_id)
        try:
            with h5py.File(path, "r") as container:
                if _IDENTIFICATION_PATH not in container:
                    return SupportReport.unsupported_source(
                        self.descriptor.reader_id,
                        reason_code="missing_identification",
                        message="HDF5 file has no NISAR identification group.",
                    )
                identification = container[_IDENTIFICATION_PATH]
                mission = _scalar_text(identification, "missionId")
                product_type = _scalar_text(identification, "productType")
                if mission.upper() != "NISAR":
                    return SupportReport.unsupported_source(self.descriptor.reader_id)
                if product_type.upper() != "RSLC":
                    return SupportReport.unsupported_source(
                        self.descriptor.reader_id,
                        reason_code="wrong_product_type",
                        message=f"NISAR product type is {product_type or 'unknown'}, not RSLC.",
                        detected_product_type=product_type or None,
                    )
                if _RSLC_SWATHS_PATH not in container:
                    raise LocalReaderError(
                        ReaderErrorCode.MISSING_METADATA,
                        "NISAR RSLC has no /science/LSAR/RSLC/swaths group.",
                        source=source,
                        reader_id=self.descriptor.reader_id,
                    )
        except LocalReaderError:
            raise
        except OSError as exc:
            raise LocalReaderError(
                ReaderErrorCode.CORRUPT_CONTAINER,
                f"NISAR HDF5 could not be opened: {path}",
                source=source,
                reader_id=self.descriptor.reader_id,
            ) from exc
        return SupportReport.supported_source(
            self.descriptor.reader_id,
            100,
            detected_product_type="RSLC",
        )

    def read(self, source: AssetRef, context: ReaderContext) -> LocalSARProduct:
        context.raise_if_cancelled(source=source, reader_id=self.descriptor.reader_id)
        path = local_path(source, self.descriptor.reader_id)
        if not path.is_file():
            raise LocalReaderError(
                ReaderErrorCode.IO_ERROR,
                f"NISAR source was not found: {path}",
                source=source,
                reader_id=self.descriptor.reader_id,
            )
        self._check_signature(path, source)
        h5py = _load_h5py(source, self.descriptor.reader_id)
        try:
            with h5py.File(path, "r") as container:
                if _IDENTIFICATION_PATH not in container:
                    raise LocalReaderError(
                        ReaderErrorCode.MISSING_METADATA,
                        "NISAR HDF5 has no identification group.",
                        source=source,
                        reader_id=self.descriptor.reader_id,
                    )
                identification = container[_IDENTIFICATION_PATH]
                mission = _required_scalar_text(identification, "missionId", source, self.descriptor.reader_id)
                product_type = _required_scalar_text(
                    identification,
                    "productType",
                    source,
                    self.descriptor.reader_id,
                ).upper()
                if mission.upper() != "NISAR":
                    raise LocalReaderError(
                        ReaderErrorCode.UNSUPPORTED_PLATFORM,
                        f"HDF5 mission is {mission}, not NISAR.",
                        source=source,
                        reader_id=self.descriptor.reader_id,
                    )
                if product_type != "RSLC":
                    raise LocalReaderError(
                        ReaderErrorCode.WRONG_PRODUCT_TYPE,
                        f"NISAR local import accepts RSLC only, not {product_type}.",
                        source=source,
                        reader_id=self.descriptor.reader_id,
                    )
                if _RSLC_SWATHS_PATH not in container:
                    raise LocalReaderError(
                        ReaderErrorCode.MISSING_METADATA,
                        "NISAR RSLC has no swaths group.",
                        source=source,
                        reader_id=self.descriptor.reader_id,
                    )
                context.raise_if_cancelled(source=source, reader_id=self.descriptor.reader_id)
                product = self._build_product(path, source, context, container, identification)
        except LocalReaderError:
            raise
        except OSError as exc:
            raise LocalReaderError(
                ReaderErrorCode.CORRUPT_CONTAINER,
                f"NISAR HDF5 could not be opened: {path}",
                source=source,
                reader_id=self.descriptor.reader_id,
            ) from exc
        return product

    def _build_product(
        self,
        path: Path,
        source: AssetRef,
        context: ReaderContext,
        container: Any,
        identification: Any,
    ) -> LocalSARProduct:
        native_id = _scalar_text(identification, "granuleId") or path.stem
        platform = _scalar_text(identification, "platformName") or "NISAR"
        start_text = _required_scalar_text(
            identification,
            "zeroDopplerStartTime",
            source,
            self.descriptor.reader_id,
        )
        end_text = _required_scalar_text(
            identification,
            "zeroDopplerEndTime",
            source,
            self.descriptor.reader_id,
        )
        frequencies = _string_values(identification, "listOfFrequencies")
        swaths = container[_RSLC_SWATHS_PATH]
        if not frequencies:
            frequencies = tuple(
                key.removeprefix("frequency")
                for key in swaths
                if str(key).startswith("frequency")
            )
        assets: list[AssetRef] = [
            AssetRef(
                str(path),
                "source_product",
                media_type="application/x-hdf5",
                size_bytes=path.stat().st_size,
            )
        ]
        polarizations: set[str] = set()
        dataset_metadata: dict[str, JsonValue] = {}
        for frequency in sorted(set(frequencies)):
            context.raise_if_cancelled(source=source, reader_id=self.descriptor.reader_id)
            group_name = f"frequency{frequency}"
            if group_name not in swaths:
                continue
            group = swaths[group_name]
            listed = _string_values(group, "listOfPolarizations")
            if not listed:
                listed = tuple(
                    str(key)
                    for key in group
                    if len(str(key)) == 2 and str(key).isalpha()
                )
            for polarization in sorted(set(listed)):
                if polarization not in group:
                    continue
                dataset = group[polarization]
                if not hasattr(dataset, "shape"):
                    continue
                dataset_path = f"{_RSLC_SWATHS_PATH}/{group_name}/{polarization}"
                polarizations.add(polarization)
                assets.append(
                    AssetRef(
                        str(path),
                        "complex_radar_image",
                        subdataset=dataset_path,
                        media_type="application/x-hdf5",
                    )
                )
                item_metadata: dict[str, JsonValue] = {
                    "chunks": tuple(dataset.chunks) if dataset.chunks is not None else None,
                    "dtype": str(dataset.dtype),
                    "shape": tuple(dataset.shape),
                }
                dataset_metadata[dataset_path] = item_metadata
        if len(assets) == 1:
            raise LocalReaderError(
                ReaderErrorCode.MISSING_METADATA,
                "NISAR RSLC contains no readable frequency/polarization image datasets.",
                source=source,
                reader_id=self.descriptor.reader_id,
            )
        identification_metadata = {
            key: value
            for key in (
                "lookDirection",
                "productLevel",
                "productVersion",
                "processingType",
                "radarBand",
            )
            if (value := _scalar_text(identification, key))
        }
        stat = path.stat()
        fingerprint_text = "|".join(
            (
                native_id,
                start_text,
                end_text,
                ",".join(sorted(dataset_metadata)),
            )
        )
        return LocalSARProduct(
            product_id=stable_product_id("NISAR", "RSLC", native_id),
            native_product_id=native_id,
            mission="NISAR",
            platform=platform,
            product_type="RSLC",
            acquisition_mode="SCIENCE",
            acquisition_layout="FREQUENCY_SWATHS",
            start_time=utc_datetime(start_text, "zeroDopplerStartTime", source, self.descriptor.reader_id),
            end_time=utc_datetime(end_text, "zeroDopplerEndTime", source, self.descriptor.reader_id),
            orbit_direction=_scalar_text(identification, "orbitPassDirection") or None,
            orbit_identity=_scalar_text(identification, "absoluteOrbitNumber") or None,
            track=_scalar_int(identification, "trackNumber", source, self.descriptor.reader_id),
            frame=_scalar_int(identification, "frameNumber", source, self.descriptor.reader_id),
            relative_orbit=None,
            frequency_bands=tuple(frequencies),
            polarizations=tuple(polarizations),
            footprint_wkt=_scalar_text(identification, "boundingPolygon") or None,
            assets=tuple(assets),
            native_metadata={
                "datasets": dataset_metadata,
                "identification": identification_metadata,
            },
            reader_id=self.descriptor.reader_id,
            reader_schema_version=self.descriptor.schema_version,
            source_snapshot=SourceSnapshot(
                ReaderSourceKind.FILE.value,
                stat.st_size,
                stat.st_mtime_ns,
                fingerprint=hashlib.sha256(fingerprint_text.encode("utf-8")).hexdigest(),
            ),
        )

    def _check_signature(self, path: Path, source: AssetRef) -> None:
        try:
            with path.open("rb") as stream:
                signature = stream.read(len(_HDF5_SIGNATURE))
        except OSError as exc:
            raise LocalReaderError(
                ReaderErrorCode.IO_ERROR,
                f"NISAR source could not be read: {path}",
                source=source,
                reader_id=self.descriptor.reader_id,
            ) from exc
        if signature != _HDF5_SIGNATURE:
            raise LocalReaderError(
                ReaderErrorCode.CORRUPT_CONTAINER,
                f"File does not have an HDF5 signature: {path}",
                source=source,
                reader_id=self.descriptor.reader_id,
            )


def _load_h5py(source: AssetRef, reader_id: str) -> Any:
    try:
        return importlib.import_module("h5py")
    except ImportError as exc:
        raise LocalReaderError(
            ReaderErrorCode.DEPENDENCY_MISSING,
            "NISAR RSLC reading requires the optional h5py dependency.",
            source=source,
            reader_id=reader_id,
        ) from exc


def _scalar_value(group: Any, key: str) -> Any:
    if key not in group:
        return None
    value = group[key][()]
    if hasattr(value, "item") and not isinstance(value, (bytes, str)):
        with suppress(ValueError):
            value = value.item()
    return value


def _scalar_text(group: Any, key: str) -> str:
    value = _scalar_value(group, key)
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="strict").strip()
    return str(value).strip()


def _required_scalar_text(group: Any, key: str, source: AssetRef, reader_id: str) -> str:
    value = _scalar_text(group, key)
    if not value:
        raise LocalReaderError(
            ReaderErrorCode.MISSING_METADATA,
            f"NISAR identification is missing {key}.",
            source=source,
            reader_id=reader_id,
        )
    return value


def _string_values(group: Any, key: str) -> tuple[str, ...]:
    value = _scalar_value(group, key)
    if value is None:
        return ()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, list):
        value = [value]
    return tuple(
        item.decode("utf-8", errors="strict").strip() if isinstance(item, bytes) else str(item).strip()
        for item in value
        if item is not None
    )


def _scalar_int(group: Any, key: str, source: AssetRef, reader_id: str) -> int | None:
    value = _scalar_value(group, key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise LocalReaderError(
            ReaderErrorCode.MISSING_METADATA,
            f"NISAR identification value is not an integer: {key}",
            source=source,
            reader_id=reader_id,
        ) from exc


__all__ = ["NisarRslcReader"]
