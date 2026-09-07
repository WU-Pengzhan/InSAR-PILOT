"""Read-only Sentinel-1 SLC reader for ZIP and unpacked SAFE products."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

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
from insar_pilot.providers.local.base import ReaderContext
from insar_pilot.providers.local.path_utils import local_path, utc_datetime

_PLATFORMS = frozenset({"SENTINEL-1A", "SENTINEL-1B", "SENTINEL-1C", "SENTINEL-1D"})


@dataclass(frozen=True)
class _ManifestSource:
    text: bytes
    source_kind: ReaderSourceKind
    member_count: int | None


class Sentinel1SafeReader:
    """Project Sentinel-1 SAFE metadata into the canonical local-product model."""

    descriptor = ReaderDescriptor(
        reader_id="sentinel1.safe",
        display_name="Sentinel-1 SAFE",
        schema_version=1,
        capabilities=(
            ReaderCapability("SENTINEL-1", ("SLC",), frozenset({ReaderSourceKind.FILE}), (".zip",)),
            ReaderCapability(
                "SENTINEL-1",
                ("SLC",),
                frozenset({ReaderSourceKind.DIRECTORY}),
                (".safe",),
            ),
        ),
        priority=100,
    )

    def probe(self, source: AssetRef, context: ReaderContext) -> SupportReport:
        context.raise_if_cancelled(source=source, reader_id=self.descriptor.reader_id)
        path = local_path(source, self.descriptor.reader_id)
        if not _has_supported_shape(path):
            return SupportReport.unsupported_source(self.descriptor.reader_id)
        try:
            manifest = self._read_manifest(path, source, context)
            root = ElementTree.fromstring(manifest.text)
        except LocalReaderError:
            raise
        except ElementTree.ParseError as exc:
            raise LocalReaderError(
                ReaderErrorCode.CORRUPT_CONTAINER,
                f"Sentinel-1 manifest is not valid XML: {path}",
                source=source,
                reader_id=self.descriptor.reader_id,
            ) from exc
        product_type = _first_text(root, "productType")
        family_name = _first_text(root, "familyName", preferred_value="SENTINEL-1")
        if family_name.upper() != "SENTINEL-1":
            return SupportReport.unsupported_source(self.descriptor.reader_id)
        if product_type.upper() != "SLC":
            return SupportReport.unsupported_source(
                self.descriptor.reader_id,
                reason_code="wrong_product_type",
                message=f"Sentinel-1 product type is {product_type or 'unknown'}, not SLC.",
                detected_product_type=product_type or None,
            )
        return SupportReport.supported_source(
            self.descriptor.reader_id,
            100,
            detected_product_type="SLC",
        )

    def read(self, source: AssetRef, context: ReaderContext) -> LocalSARProduct:
        context.raise_if_cancelled(source=source, reader_id=self.descriptor.reader_id)
        path = local_path(source, self.descriptor.reader_id)
        manifest = self._read_manifest(path, source, context)
        try:
            root = ElementTree.fromstring(manifest.text)
        except ElementTree.ParseError as exc:
            raise LocalReaderError(
                ReaderErrorCode.CORRUPT_CONTAINER,
                f"Sentinel-1 manifest is not valid XML: {path}",
                source=source,
                reader_id=self.descriptor.reader_id,
            ) from exc

        product_type = _required_text(root, "productType", source, self.descriptor.reader_id).upper()
        if product_type != "SLC":
            raise LocalReaderError(
                ReaderErrorCode.WRONG_PRODUCT_TYPE,
                f"Sentinel-1 local import accepts SLC only, not {product_type}.",
                source=source,
                reader_id=self.descriptor.reader_id,
            )
        family_name = _first_text(root, "familyName", preferred_value="SENTINEL-1").upper()
        number = _required_text(root, "number", source, self.descriptor.reader_id).upper()
        platform = f"{family_name}{number}"
        if platform not in _PLATFORMS:
            raise LocalReaderError(
                ReaderErrorCode.UNSUPPORTED_PLATFORM,
                f"Unsupported Sentinel-1 platform: {platform}",
                source=source,
                reader_id=self.descriptor.reader_id,
            )

        mode = _required_text(root, "mode", source, self.descriptor.reader_id).upper()
        start_text = _required_text(root, "startTime", source, self.descriptor.reader_id)
        stop_text = _required_text(root, "stopTime", source, self.descriptor.reader_id)
        native_id = _safe_native_id(path)
        absolute_orbit = _typed_text(root, "orbitNumber", "start")
        relative_orbit_text = _typed_text(root, "relativeOrbitNumber", "start")
        relative_orbit = _optional_int(relative_orbit_text, "relativeOrbitNumber", source, self.descriptor.reader_id)
        polarizations = tuple(_all_text(root, "transmitterReceiverPolarisation"))
        footprint = _footprint_wkt(_first_text(root, "coordinates"))
        ipf_version = _software_version(root)
        stat = path.stat()
        snapshot_size = stat.st_size if path.is_file() else None
        source_asset = AssetRef(
            uri=str(path),
            role="source_product",
            media_type="application/zip" if path.is_file() else "application/vnd.esa.safe",
            size_bytes=snapshot_size,
        )
        context.raise_if_cancelled(source=source, reader_id=self.descriptor.reader_id)
        return LocalSARProduct(
            product_id=stable_product_id("SENTINEL-1", "SLC", native_id),
            native_product_id=native_id,
            mission="SENTINEL-1",
            platform=platform,
            product_type="SLC",
            acquisition_mode=mode,
            acquisition_layout=_layout_for_mode(mode),
            start_time=utc_datetime(start_text, "startTime", source, self.descriptor.reader_id),
            end_time=utc_datetime(stop_text, "stopTime", source, self.descriptor.reader_id),
            orbit_direction=_first_text(root, "pass") or None,
            orbit_identity=absolute_orbit or None,
            track=None,
            frame=None,
            relative_orbit=relative_orbit,
            frequency_bands=("C",),
            polarizations=polarizations,
            footprint_wkt=footprint,
            assets=(source_asset,),
            native_metadata={
                "absolute_orbit": absolute_orbit or None,
                "ipf_version": ipf_version or None,
                "manifest_sha256": hashlib.sha256(manifest.text).hexdigest(),
            },
            reader_id=self.descriptor.reader_id,
            reader_schema_version=self.descriptor.schema_version,
            source_snapshot=SourceSnapshot(
                manifest.source_kind.value,
                snapshot_size,
                stat.st_mtime_ns,
                member_count=manifest.member_count,
                fingerprint=hashlib.sha256(manifest.text).hexdigest(),
            ),
        )

    def _read_manifest(self, path: Path, source: AssetRef, context: ReaderContext) -> _ManifestSource:
        if not path.exists():
            raise LocalReaderError(
                ReaderErrorCode.IO_ERROR,
                f"Sentinel-1 source was not found: {path}",
                source=source,
                reader_id=self.descriptor.reader_id,
            )
        if path.is_dir():
            if path.suffix.lower() != ".safe":
                raise LocalReaderError(
                    ReaderErrorCode.UNSUPPORTED_FORMAT,
                    f"Sentinel-1 directory must end with .SAFE: {path}",
                    source=source,
                    reader_id=self.descriptor.reader_id,
                )
            manifest_path = path / "manifest.safe"
            if not manifest_path.is_file():
                raise LocalReaderError(
                    ReaderErrorCode.MISSING_METADATA,
                    f"Sentinel-1 SAFE has no manifest.safe: {path}",
                    source=source,
                    reader_id=self.descriptor.reader_id,
                )
            if manifest_path.stat().st_size > context.metadata_read_budget_bytes:
                raise LocalReaderError(
                    ReaderErrorCode.CONTRACT_VIOLATION,
                    "Sentinel-1 manifest exceeds the configured metadata read budget.",
                    source=source,
                    reader_id=self.descriptor.reader_id,
                )
            return _ManifestSource(manifest_path.read_bytes(), ReaderSourceKind.DIRECTORY, None)
        if path.suffix.lower() != ".zip":
            raise LocalReaderError(
                ReaderErrorCode.UNSUPPORTED_FORMAT,
                f"Sentinel-1 file must be a ZIP product: {path}",
                source=source,
                reader_id=self.descriptor.reader_id,
            )
        try:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                manifest_info = next(
                    (info for info in infos if info.filename.lower().endswith("/manifest.safe")),
                    None,
                )
                if manifest_info is None:
                    raise LocalReaderError(
                        ReaderErrorCode.MISSING_METADATA,
                        f"Sentinel-1 ZIP has no manifest.safe: {path}",
                        source=source,
                        reader_id=self.descriptor.reader_id,
                    )
                if manifest_info.file_size > context.metadata_read_budget_bytes:
                    raise LocalReaderError(
                        ReaderErrorCode.CONTRACT_VIOLATION,
                        "Sentinel-1 manifest exceeds the configured metadata read budget.",
                        source=source,
                        reader_id=self.descriptor.reader_id,
                    )
                return _ManifestSource(archive.read(manifest_info), ReaderSourceKind.FILE, len(infos))
        except zipfile.BadZipFile as exc:
            raise LocalReaderError(
                ReaderErrorCode.CORRUPT_CONTAINER,
                f"Sentinel-1 ZIP is corrupt: {path}",
                source=source,
                reader_id=self.descriptor.reader_id,
            ) from exc


def _has_supported_shape(path: Path) -> bool:
    return (path.is_file() and path.suffix.lower() == ".zip") or (
        path.is_dir() and path.suffix.lower() == ".safe"
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_text(root: ElementTree.Element, name: str, *, preferred_value: str = "") -> str:
    fallback = ""
    for element in root.iter():
        if _local_name(element.tag) != name:
            continue
        value = (element.text or "").strip()
        if preferred_value and value.upper() == preferred_value.upper():
            return value
        if value and not fallback:
            fallback = value
    return fallback


def _required_text(
    root: ElementTree.Element,
    name: str,
    source: AssetRef,
    reader_id: str,
) -> str:
    value = _first_text(root, name)
    if not value:
        raise LocalReaderError(
            ReaderErrorCode.MISSING_METADATA,
            f"Sentinel-1 manifest is missing {name}.",
            source=source,
            reader_id=reader_id,
        )
    return value


def _typed_text(root: ElementTree.Element, name: str, type_value: str) -> str:
    for element in root.iter():
        if _local_name(element.tag) == name and element.attrib.get("type", "").lower() == type_value.lower():
            return (element.text or "").strip()
    return ""


def _all_text(root: ElementTree.Element, name: str) -> list[str]:
    return [
        value
        for element in root.iter()
        if _local_name(element.tag) == name and (value := (element.text or "").strip())
    ]


def _software_version(root: ElementTree.Element) -> str:
    for element in root.iter():
        if _local_name(element.tag) != "software":
            continue
        if "IPF" in element.attrib.get("name", "").upper() and element.attrib.get("version", "").strip():
            return element.attrib["version"].strip()
    return ""


def _safe_native_id(path: Path) -> str:
    name = path.name
    if name.lower().endswith(".zip"):
        name = name[:-4]
    if name.lower().endswith(".safe"):
        name = name[:-5]
    return name


def _layout_for_mode(mode: str) -> str:
    return {
        "IW": "TOPS_SWATHS",
        "EW": "TOPS_SWATHS",
        "SM": "STRIPMAP",
        "WV": "WAVE",
    }.get(mode, "MISSION_NATIVE")


def _optional_int(value: str, field_name: str, source: AssetRef, reader_id: str) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise LocalReaderError(
            ReaderErrorCode.MISSING_METADATA,
            f"Sentinel-1 {field_name} is not an integer: {value}",
            source=source,
            reader_id=reader_id,
        ) from exc


def _footprint_wkt(coordinates: str) -> str | None:
    if not coordinates:
        return None
    points: list[str] = []
    for token in coordinates.split():
        parts = token.split(",")
        if len(parts) < 2:
            return None
        latitude, longitude = parts[0], parts[1]
        points.append(f"{longitude} {latitude}")
    if len(points) < 3:
        return None
    if points[0] != points[-1]:
        points.append(points[0])
    return f"POLYGON(({','.join(points)}))"


__all__ = ["Sentinel1SafeReader"]
