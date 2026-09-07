"""Persistent project-local catalog for canonical SAR products."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from json import JSONDecodeError
from pathlib import Path

from insar_pilot.domain.local_data import LocalSARProduct, SourceSnapshot


class CatalogError(RuntimeError):
    """Base error for catalog persistence and integrity failures."""


class CatalogLoadError(CatalogError):
    """Raised when a sidecar cannot be safely restored."""


class CatalogWriteError(CatalogError):
    """Raised when an atomic sidecar update fails."""


class CatalogMergeState(str, Enum):
    """Relationship between a candidate product and an existing entry."""

    NEW = "new"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class CatalogSourceState(str, Enum):
    """Cheap state of the primary source relative to its saved snapshot."""

    CURRENT = "current"
    CHANGED = "changed"
    MISSING = "missing"
    UNCHECKABLE = "uncheckable"


@dataclass(frozen=True)
class CatalogEntry:
    """One durable product record and its original import timestamp."""

    product: LocalSARProduct
    imported_at: datetime

    def __post_init__(self) -> None:
        if self.imported_at.tzinfo is None or self.imported_at.utcoffset() is None:
            raise ValueError("imported_at must include a timezone.")
        object.__setattr__(self, "imported_at", self.imported_at.astimezone(timezone.utc))

    def to_dict(self) -> dict[str, object]:
        return {
            "imported_at": self.imported_at.isoformat().replace("+00:00", "Z"),
            "product": self.product.to_dict(),
            "schema_version": ProjectDataCatalog.CURRENT_SCHEMA_VERSION,
        }

    @classmethod
    def from_dict(cls, value: object) -> CatalogEntry:
        if not isinstance(value, dict):
            raise TypeError("Catalog sidecar must contain a JSON object.")
        schema_version = value.get("schema_version")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise TypeError("Catalog schema_version must be an integer.")
        if schema_version != ProjectDataCatalog.CURRENT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported catalog schema_version: {schema_version}")
        imported_at_value = value.get("imported_at")
        if not isinstance(imported_at_value, str):
            raise TypeError("Catalog imported_at must be an ISO-8601 string.")
        imported_at = datetime.fromisoformat(imported_at_value.replace("Z", "+00:00"))
        product_value = value.get("product")
        if not isinstance(product_value, dict):
            raise TypeError("Catalog product must contain a JSON object.")
        return cls(LocalSARProduct.from_dict(product_value), imported_at)


@dataclass(frozen=True)
class CatalogMergeResult:
    """Result of assessing or writing one product."""

    state: CatalogMergeState
    entry: CatalogEntry
    persisted: bool


class ProjectDataCatalog:
    """Store product sidecars under one project's ``.insar_pilot`` directory."""

    CURRENT_SCHEMA_VERSION = 1
    MAX_SIDECAR_BYTES = 8 * 1024 * 1024

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser()
        self.catalog_dir = self.project_root / ".insar_pilot" / "catalog"
        self.products_dir = self.catalog_dir / "products"
        self._entries: dict[str, CatalogEntry] = {}

    def entries(self) -> tuple[CatalogEntry, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))

    def get(self, product_id: str) -> CatalogEntry | None:
        return self._entries.get(product_id)

    def load(self) -> ProjectDataCatalog:
        """Restore all sidecars without creating project directories."""

        loaded: dict[str, CatalogEntry] = {}
        if not self.products_dir.exists():
            self._entries = loaded
            return self
        if not self.products_dir.is_dir():
            raise CatalogLoadError(f"Catalog products path is not a directory: {self.products_dir}")
        for path in sorted(self.products_dir.glob("*.sar.json")):
            try:
                if path.stat().st_size > self.MAX_SIDECAR_BYTES:
                    raise CatalogLoadError(f"Catalog sidecar is too large: {path}")
                payload = json.loads(path.read_text(encoding="utf-8"))
                entry = CatalogEntry.from_dict(payload)
            except CatalogLoadError:
                raise
            except (JSONDecodeError, OSError, TypeError, ValueError) as exc:
                raise CatalogLoadError(f"Catalog sidecar is malformed or unreadable: {path}") from exc
            product_id = entry.product.product_id
            if product_id in loaded:
                raise CatalogLoadError(f"Duplicate catalog product_id: {product_id}")
            expected_name = self.sidecar_path(product_id).name
            if path.name != expected_name:
                raise CatalogLoadError(
                    f"Catalog sidecar filename does not match product_id: {path.name}"
                )
            loaded[product_id] = entry
        self._entries = loaded
        return self

    def assess(self, product: LocalSARProduct) -> CatalogMergeState:
        existing = self.get(product.product_id)
        if existing is None:
            return CatalogMergeState.NEW
        if existing.product.to_json() == product.to_json():
            return CatalogMergeState.UNCHANGED
        return CatalogMergeState.CHANGED

    def merge(
        self,
        product: LocalSARProduct,
        *,
        replace_changed: bool = False,
        persist: bool = True,
        imported_at: datetime | None = None,
    ) -> CatalogMergeResult:
        """Merge a reader result, requiring an explicit opt-in for changed data."""

        state = self.assess(product)
        existing = self.get(product.product_id)
        if state is CatalogMergeState.UNCHANGED and existing is not None:
            return CatalogMergeResult(state, existing, False)
        if state is CatalogMergeState.CHANGED and not replace_changed and existing is not None:
            return CatalogMergeResult(state, existing, False)
        entry = CatalogEntry(product, imported_at or datetime.now(timezone.utc))
        if persist:
            self._write_entry(entry)
        self._entries[product.product_id] = entry
        return CatalogMergeResult(state, entry, persist)

    def source_state(self, product_id: str) -> CatalogSourceState:
        """Perform a bounded stat-only stale check; deep validation requires re-import."""

        entry = self.get(product_id)
        if entry is None:
            raise KeyError(product_id)
        source_assets = tuple(asset for asset in entry.product.assets if asset.role == "source_product")
        if len(source_assets) != 1 or source_assets[0].subdataset is not None:
            return CatalogSourceState.UNCHECKABLE
        source = Path(source_assets[0].uri).expanduser()
        if not source.exists():
            return CatalogSourceState.MISSING
        try:
            stat = source.stat()
        except OSError:
            return CatalogSourceState.UNCHECKABLE
        snapshot = entry.product.source_snapshot
        if stat.st_mtime_ns != snapshot.mtime_ns:
            return CatalogSourceState.CHANGED
        if snapshot.size_bytes is not None and source.is_file() and stat.st_size != snapshot.size_bytes:
            return CatalogSourceState.CHANGED
        return CatalogSourceState.CURRENT

    def sidecar_path(self, product_id: str) -> Path:
        digest = hashlib.sha256(product_id.encode("utf-8")).hexdigest()
        return self.products_dir / f"{digest}.sar.json"

    def _write_entry(self, entry: CatalogEntry) -> None:
        self.products_dir.mkdir(parents=True, exist_ok=True)
        target = self.sidecar_path(entry.product.product_id)
        payload = json.dumps(
            entry.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.products_dir,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temp_path = Path(stream.name)
                stream.write(payload)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, target)
        except OSError as exc:
            if temp_path is not None:
                with suppress(OSError):
                    temp_path.unlink(missing_ok=True)
            raise CatalogWriteError(f"Could not atomically write catalog sidecar: {target}") from exc

    def replace_all_for_test(self, entries: Iterable[CatalogEntry]) -> None:
        """Replace only in-memory entries; useful for pure service composition tests."""

        self._entries = {entry.product.product_id: entry for entry in entries}


def snapshots_equal(left: SourceSnapshot, right: SourceSnapshot) -> bool:
    """Public semantic helper for clients that need a source-only comparison."""

    return left == right


__all__ = [
    "CatalogEntry",
    "CatalogError",
    "CatalogLoadError",
    "CatalogMergeResult",
    "CatalogMergeState",
    "CatalogSourceState",
    "CatalogWriteError",
    "ProjectDataCatalog",
    "snapshots_equal",
]
