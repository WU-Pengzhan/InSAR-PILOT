"""Publish verified source bytes into a project without overwriting a version."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from insar_pilot.download.integrity import receipt_path
from insar_pilot.infrastructure.engine_store import atomic_json, file_snapshot


def reusable_asset(app: Any, key: str, role: str) -> Path | None:
    for asset in app.library():
        meta = asset["metadata"]
        if role != meta.get("role") or not meta.get("integrity"):
            continue
        if key not in [meta.get("product_key"), *meta.get("product_keys", [])]:
            continue
        path = Path(asset["path"])
        try:
            if path.is_file() and file_snapshot(path) == asset["snapshot"]:
                return path
        except OSError:
            pass
    return None


def publish_source(source: Path, destination: Path, role: str, staging: Path, cancelled: Callable[[], bool]) -> Path:
    """Copy+hash to a hidden staging directory, then atomically publish a version.

    An identical existing version is verified, never overwritten. Retain the
    provider's source so an interrupted registration can retry without download.
    """
    roles = {"SLC": "slc", "RSLC": "slc", "ORBIT": "orbit", "DEM": "dem"}
    base = destination / roles[role]
    base.mkdir(parents=True, exist_ok=True)
    staging.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix="publish-", dir=staging))
    before = file_snapshot(source)
    hasher = hashlib.sha256()
    try:
        with source.open("rb") as inp, (pending / source.name).open("xb") as out:
            for block in iter(lambda: inp.read(8 * 1024 * 1024), b""):
                if cancelled():
                    raise InterruptedError("Source publication cancelled.")
                hasher.update(block)
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        if cancelled():
            raise InterruptedError("Source publication cancelled.")
        if before != file_snapshot(source):
            raise ValueError("Source changed during publication.")
        receipt = receipt_path(source)
        evidence = json.loads(receipt.read_text()) if receipt.exists() else {"checks": ["provider_download_validation"]}
        evidence["sha256"] = hasher.hexdigest()
        atomic_json(receipt_path(pending / source.name), evidence)
        target = base / hasher.hexdigest()
        if target.exists():
            existing = target / source.name
            with existing.open("rb") as inp:
                verifier = hashlib.sha256()
                for block in iter(lambda: inp.read(8 * 1024 * 1024), b""):
                    if cancelled():
                        raise InterruptedError("Source verification cancelled.")
                    verifier.update(block)
            if verifier.hexdigest() != hasher.hexdigest():
                raise ValueError("Published source version changed; refusing to overwrite it.")
        else:
            pending.rename(target)
            fd = os.open(base, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        return target / source.name
    finally:
        if pending.exists():
            shutil.rmtree(pending)
