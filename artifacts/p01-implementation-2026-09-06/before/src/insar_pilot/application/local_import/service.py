"""Application service that scans, reads, and catalogs local SAR inputs."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from insar_pilot.application.local_import.models import (
    ImportDisposition,
    ImportItemResult,
    LocalImportRequest,
    LocalImportResult,
)
from insar_pilot.domain.local_data import AssetRef, LocalReaderError, ReaderErrorCode
from insar_pilot.providers.local import LocalSARProductReaderRegistry, ReaderContext
from insar_pilot.services.project_data_catalog import CatalogError, CatalogMergeState, ProjectDataCatalog

_FILE_SUFFIXES = frozenset({".zip", ".h5", ".hdf5"})


class LocalImportApplicationService:
    """Synchronous Qt-free use case intended to run in a worker thread."""

    def __init__(
        self,
        registry: LocalSARProductReaderRegistry,
        catalog: ProjectDataCatalog,
    ) -> None:
        self._registry = registry
        self._catalog = catalog

    def execute(
        self,
        request: LocalImportRequest,
        context: ReaderContext | None = None,
    ) -> LocalImportResult:
        actual_context = context or ReaderContext()
        items: list[ImportItemResult] = []
        try:
            candidates = tuple(self._scan(request.sources, request.recursive, actual_context))
        except LocalReaderError as exc:
            if exc.code is ReaderErrorCode.CANCELLED:
                return LocalImportResult(tuple(items), cancelled=True)
            raise
        for candidate in candidates:
            source = AssetRef(str(candidate), "source_product")
            try:
                actual_context.raise_if_cancelled(source=source)
                product = self._registry.read(source, actual_context)
                merge_state = self._catalog.assess(product)
                disposition = self._disposition(
                    merge_state,
                    dry_run=request.dry_run,
                    replace_changed=request.replace_changed,
                )
                if not request.dry_run:
                    self._catalog.merge(
                        product,
                        replace_changed=request.replace_changed,
                        persist=True,
                    )
                items.append(ImportItemResult(str(candidate), disposition, product=product))
            except LocalReaderError as exc:
                if exc.code is ReaderErrorCode.CANCELLED:
                    return LocalImportResult(tuple(items), cancelled=True)
                items.append(
                    ImportItemResult(
                        str(candidate),
                        ImportDisposition.ERROR,
                        error_code=exc.code,
                        message=str(exc),
                    )
                )
            except OSError as exc:
                items.append(
                    ImportItemResult(
                        str(candidate),
                        ImportDisposition.ERROR,
                        error_code=ReaderErrorCode.IO_ERROR,
                        message=str(exc),
                    )
                )
            except CatalogError as exc:
                items.append(
                    ImportItemResult(
                        str(candidate),
                        ImportDisposition.ERROR,
                        error_code=ReaderErrorCode.IO_ERROR,
                        message=str(exc),
                    )
                )
        message = "no_candidates" if not candidates else ""
        return LocalImportResult(tuple(items), message=message)

    def _scan(
        self,
        sources: tuple[str, ...],
        recursive: bool,
        context: ReaderContext,
    ) -> Iterable[Path]:
        seen: set[Path] = set()
        for source_text in sources:
            context.raise_if_cancelled()
            source = Path(source_text).expanduser()
            if source.is_file() or _is_safe_directory(source):
                candidate = source.absolute()
                if candidate not in seen:
                    seen.add(candidate)
                    yield candidate
                continue
            if not source.exists():
                candidate = source.absolute()
                if candidate not in seen:
                    seen.add(candidate)
                    yield candidate
                continue
            if not source.is_dir():
                continue
            iterator = source.rglob("*") if recursive else source.iterdir()
            for candidate in sorted(iterator):
                context.raise_if_cancelled()
                if _is_safe_directory(candidate):
                    absolute = candidate.absolute()
                elif candidate.is_file() and candidate.suffix.lower() in _FILE_SUFFIXES:
                    if any(_is_safe_directory(parent) for parent in candidate.parents if parent != source.parent):
                        continue
                    absolute = candidate.absolute()
                else:
                    continue
                if absolute not in seen:
                    seen.add(absolute)
                    yield absolute

    @staticmethod
    def _disposition(
        state: CatalogMergeState,
        *,
        dry_run: bool,
        replace_changed: bool,
    ) -> ImportDisposition:
        if state is CatalogMergeState.UNCHANGED:
            return ImportDisposition.DUPLICATE
        if state is CatalogMergeState.CHANGED:
            if replace_changed:
                return ImportDisposition.WOULD_REPLACE if dry_run else ImportDisposition.REPLACED
            return ImportDisposition.CHANGED
        return ImportDisposition.WOULD_IMPORT if dry_run else ImportDisposition.IMPORTED


def _is_safe_directory(path: Path) -> bool:
    return path.is_dir() and path.suffix.lower() == ".safe"


__all__ = ["LocalImportApplicationService"]
