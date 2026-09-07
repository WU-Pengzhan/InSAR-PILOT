"""Validate acquired source bytes before publishing or reusing them."""

from __future__ import annotations

import hashlib
import uuid
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from pathlib import Path

from insar_pilot.infrastructure.engine_store import atomic_json


def quarantine(path: Path) -> Path:
    target = path.parent / ".invalid" / uuid.uuid4().hex[:12] / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    path.replace(target)
    return target


def receipt_path(path: Path) -> Path:
    return path.parent / ".integrity" / (path.name + ".json")


def validate_source(
    path: Path,
    product_type: str,
    expected_bytes: int = 0,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, object]:
    """Check byte count and structure. SHA-256 is local identity, not provider proof."""
    size = path.stat().st_size
    if not size or (expected_bytes > 0 and size != expected_bytes):
        raise ValueError(f"Source size mismatch: {size} bytes; expected {expected_bytes or 'non-empty'}.")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            if cancel_check and cancel_check():
                raise InterruptedError("Source validation cancelled.")
            hasher.update(block)
    checks = ["size", "sha256_local"]
    if product_type.upper() == "SLC":
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                manifests = [n for n in names if n.endswith(".SAFE/manifest.safe")]
                annotations = [n for n in names if ".SAFE/annotation/" in n and n.endswith(".xml")]
                measurements = [n for n in names if ".SAFE/measurement/" in n and n.lower().endswith((".tiff", ".tif"))]
                if len(manifests) != 1 or not annotations or not measurements:
                    raise ValueError(
                        "ZIP does not contain a complete SAFE product (manifest, annotation, measurement)."
                    )
                if archive.getinfo(manifests[0]).file_size > 16 * 1024 * 1024:
                    raise ValueError("SAFE manifest exceeds the metadata limit.")
                manifest = ET.fromstring(archive.read(manifests[0]))
                root_name = manifests[0].split("/")[0]
                expected_name = path.name.removesuffix(".part").removesuffix(".zip")
                if expected_name.startswith(("S1A_", "S1B_", "S1C_", "S1D_")) and root_name != expected_name + ".SAFE":
                    raise ValueError("SAFE product identity differs from the requested SLC.")
                for node in manifest.iter():
                    href = node.attrib.get("href", "")
                    if href and root_name + "/" + href.removeprefix("./") not in names:
                        raise ValueError("SAFE manifest references a missing member.")
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    with archive.open(member) as stream:
                        while stream.read(8 * 1024 * 1024):
                            if cancel_check and cancel_check():
                                raise InterruptedError("ZIP integrity verification cancelled.")
                for name in measurements:
                    with archive.open(name) as measurement:
                        if measurement.read(4) not in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
                            raise ValueError("SAFE measurement is not a TIFF.")
                checks.extend(["safe_manifest", "zip_crc_all_members", "measurement_tiff_headers"])
        except (zipfile.BadZipFile, ET.ParseError) as exc:
            raise ValueError("SLC ZIP/SAFE integrity verification failed.") from exc
    else:
        # NISAR remains a complete HDF5 source, not a Sentinel ZIP.
        import h5py

        with h5py.File(path, "r") as dataset:
            if not list(dataset.keys()):
                raise ValueError("HDF5 source contains no groups.")
        checks.append("hdf5_readable")
    return {"bytes": size, "sha256": hasher.hexdigest(), "checks": checks, "provider_checksum_verified": False}


def validate_cached(
    path: Path,
    product_type: str,
    expected_bytes: int = 0,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, object]:
    # Always hash/validate source content: stat alone is not an integrity proof.
    report = validate_source(path, product_type, expected_bytes, cancel_check)
    atomic_json(receipt_path(path), report)
    return report
