from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from insar_pilot.application.local_import import (
    ImportDisposition,
    LocalImportApplicationService,
    LocalImportRequest,
)
from insar_pilot.domain.local_data import (
    AssetRef,
    LocalReaderError,
    LocalSARProduct,
    ReaderErrorCode,
    SourceSnapshot,
    stable_product_id,
)
from insar_pilot.providers.local import ReaderContext
from insar_pilot.services.project_data_catalog import ProjectDataCatalog


class _PathRegistry:
    def read(self, source: AssetRef, context: ReaderContext | None = None) -> LocalSARProduct:
        actual_context = context or ReaderContext()
        actual_context.raise_if_cancelled(source=source)
        path = Path(source.uri)
        if path.name.startswith("bad"):
            raise LocalReaderError(ReaderErrorCode.CORRUPT_CONTAINER, "bad fixture", source=source)
        stat = path.stat()
        mission = "NISAR" if path.suffix == ".h5" else "SENTINEL-1"
        product_type = "RSLC" if mission == "NISAR" else "SLC"
        native_id = path.stem.removesuffix(".SAFE")
        return LocalSARProduct(
            product_id=stable_product_id(mission, product_type, native_id),
            native_product_id=native_id,
            mission=mission,
            platform=mission if mission == "NISAR" else "S1A",
            product_type=product_type,
            acquisition_mode="SCIENCE" if mission == "NISAR" else "IW",
            acquisition_layout="FREQUENCY_SWATHS" if mission == "NISAR" else "TOPS_SWATHS",
            start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
            orbit_direction="ASCENDING",
            orbit_identity=None,
            track=1 if mission == "NISAR" else None,
            frame=2 if mission == "NISAR" else None,
            relative_orbit=12 if mission == "SENTINEL-1" else None,
            frequency_bands=("L",) if mission == "NISAR" else ("C",),
            polarizations=("HH",) if mission == "NISAR" else ("VV",),
            footprint_wkt=None,
            assets=(AssetRef(str(path), "source_product", size_bytes=stat.st_size),),
            native_metadata={},
            reader_id="nisar.rslc" if mission == "NISAR" else "sentinel1.safe",
            reader_schema_version=1,
            source_snapshot=SourceSnapshot(
                "directory" if path.is_dir() else "file",
                None if path.is_dir() else stat.st_size,
                stat.st_mtime_ns,
            ),
        )


class _Cancelled:
    def is_cancelled(self) -> bool:
        return True


def _service(project: Path) -> LocalImportApplicationService:
    return LocalImportApplicationService(_PathRegistry(), ProjectDataCatalog(project))  # type: ignore[arg-type]


def test_import_scans_both_missions_and_round_trips_catalog(tmp_path: Path) -> None:
    data = tmp_path / "readonly-data"
    data.mkdir()
    (data / "sentinel.zip").write_bytes(b"zip")
    (data / "nisar.h5").write_bytes(b"h5")
    (data / "ignore.txt").write_text("ignore", encoding="utf-8")
    catalog = ProjectDataCatalog(tmp_path / "project")
    service = LocalImportApplicationService(_PathRegistry(), catalog)  # type: ignore[arg-type]

    result = service.execute(LocalImportRequest((str(data),)))

    assert [item.disposition for item in result.items] == [
        ImportDisposition.IMPORTED,
        ImportDisposition.IMPORTED,
    ]
    assert {entry.product.mission for entry in catalog.entries()} == {"NISAR", "SENTINEL-1"}
    assert len(ProjectDataCatalog(tmp_path / "project").load().entries()) == 2
    assert sorted(path.name for path in data.iterdir()) == ["ignore.txt", "nisar.h5", "sentinel.zip"]


def test_import_dry_run_duplicate_changed_partial_error_and_cancel(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    good = data / "good.zip"
    good.write_bytes(b"one")
    (data / "bad.h5").write_bytes(b"bad")
    project = tmp_path / "project"
    service = _service(project)

    dry_run = service.execute(LocalImportRequest((str(good),), dry_run=True))
    assert dry_run.items[0].disposition is ImportDisposition.WOULD_IMPORT
    assert not (project / ".insar_pilot").exists()

    first = service.execute(LocalImportRequest((str(data),)))
    assert [item.disposition for item in first.items] == [ImportDisposition.ERROR, ImportDisposition.IMPORTED]
    assert first.error_count == 1 and first.imported_count == 1
    duplicate = service.execute(LocalImportRequest((str(good),)))
    assert duplicate.items[0].disposition is ImportDisposition.DUPLICATE

    good.write_bytes(b"changed")
    changed = service.execute(LocalImportRequest((str(good),)))
    assert changed.items[0].disposition is ImportDisposition.CHANGED
    replaced = service.execute(LocalImportRequest((str(good),), replace_changed=True))
    assert replaced.items[0].disposition is ImportDisposition.REPLACED

    cancelled = service.execute(
        LocalImportRequest((str(good),)),
        ReaderContext(cancellation=_Cancelled()),
    )
    assert cancelled.cancelled and cancelled.items == ()


def test_safe_directory_is_one_import_unit(tmp_path: Path) -> None:
    safe = tmp_path / "S1_TEST.SAFE"
    safe.mkdir()
    (safe / "nested.h5").write_bytes(b"not a separate product")

    result = _service(tmp_path / "project").execute(LocalImportRequest((str(tmp_path),)))

    assert len(result.items) == 1
    assert result.items[0].source_uri.endswith("S1_TEST.SAFE")


def test_empty_directory_has_structured_no_candidates_summary(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    result = _service(tmp_path / "project").execute(LocalImportRequest((str(empty),)))

    assert result.items == ()
    assert result.message == "no_candidates"
    assert not (tmp_path / "project" / ".insar_pilot").exists()
