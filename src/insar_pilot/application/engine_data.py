"""One mission-aware search/import use case for global and project workspaces."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from insar_pilot.application.search import SearchApplicationService
from insar_pilot.domain.engine import Profile
from insar_pilot.domain.local_data import AssetRef
from insar_pilot.domain.search import SearchRequest
from insar_pilot.infrastructure.application_state import ApplicationState
from insar_pilot.infrastructure.engine_store import EngineStore
from insar_pilot.providers.local import build_default_local_reader_registry
from insar_pilot.providers.sar import build_default_sar_provider_registry


def portable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {f.name: portable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {k: portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, frozenset, set)):
        return [portable(v) for v in value]
    return value


def capabilities() -> list[dict[str, Any]]:
    from insar_pilot.download.providers.asf_provider import ASFProvider

    result = list(portable(build_default_sar_provider_registry().descriptors()))
    for provider in result:
        if provider["provider_id"] == "asf-sentinel-1":
            provider["platform_status"] = [
                {
                    "platform": f"SENTINEL-1{c}",
                    "supported": ASFProvider.supports_platform(f"SENTINEL-1{c}"),
                    "note": "Archive data; no recent acquisitions."
                    if c == "B"
                    else "Availability depends on the requested dates and region.",
                }
                for c in "ABCD"
            ]
            provider["beam_modes"] = ["IW"]
    return result


def search(request: dict[str, Any]) -> list[dict[str, Any]]:
    missions = ["SENTINEL-1", "NISAR"] if request["mission"] == "All" else [request["mission"]]

    def one(mission: str) -> dict[str, Any]:
        try:
            query = SearchRequest(
                mission=mission,
                product_type="RSLC" if mission == "NISAR" else "SLC",
                start_time=datetime.fromisoformat(request["start"].replace("Z", "+00:00")),
                end_time=datetime.fromisoformat(request["end"].replace("Z", "+00:00")),
                aoi_wkt=request["aoi_wkt"],
                platforms=tuple(request.get("platforms", [])) if mission == "SENTINEL-1" else (),
                page=request.get("page", 1),
                page_size=request.get("page_size", 50),
                orbit_direction=request.get("orbit_direction") or None,
                relative_orbit=request.get("relative_orbit") if mission == "SENTINEL-1" else None,
                polarizations=tuple(request.get("polarizations", [])),
                frequency_bands=tuple(request.get("frequency_bands", [])) if mission == "NISAR" else (),
                provider_options=request.get("provider_options", {}),
            )
            from insar_pilot.download.network import NetworkConfig

            network = NetworkConfig.from_dict(request.get("_network", {}))
            page = SearchApplicationService(build_default_sar_provider_registry(network=network)).search(query)
            return {"mission": mission, "page": portable(page), "error": None}
        except Exception as exc:
            return {"mission": mission, "page": None, "error": str(exc)}

    with ThreadPoolExecutor(max_workers=len(missions)) as pool:
        return list(pool.map(one, missions))


def import_sources(
    app: ApplicationState,
    store: EngineStore,
    paths: list[str],
    role: str = "sar",
    *,
    acquisition_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    results = []
    registry = build_default_local_reader_registry()
    for path in paths:
        source = Path(path).expanduser().resolve(strict=True)
        if role == "sar":
            product = registry.read(AssetRef(str(source), "source_product"))
            profile = Profile.NISAR if product.mission == "NISAR" else Profile.SENTINEL1_TOPS
            metadata = portable(product)
            kind = "NisarRSLC" if profile is Profile.NISAR else "Sentinel1SLC"
        elif role in {"dem", "orbit"}:
            profile = Profile.UNASSIGNED
            metadata, kind = {"source_uri": str(source)}, "DEM" if role == "dem" else "OrbitEOF"
        else:
            raise ValueError("Unsupported import role.")
        metadata.update(acquisition_metadata or {})
        library = app.library_register(str(source), metadata)
        metadata["library_asset_id"] = library["asset_id"]
        artifact = store.register_source(source, kind, profile, metadata)
        results.append(artifact)
    return results


def import_legacy(app: ApplicationState, source: str, destination: str, name: str) -> dict[str, Any]:
    import json
    import shutil

    from insar_pilot.infrastructure.engine_store import atomic_json, file_digest
    from insar_pilot.services.project_store import ProjectStore
    from insar_pilot.services.result_catalog import ResultCatalogService

    legacy = ProjectStore().load(source)
    from dataclasses import asdict

    from insar_pilot.infrastructure.project_file import project_filename

    source_file = ProjectStore.resolve_project_file(source).resolve()
    from insar_pilot.domain.engine import validate_public_snapshot

    validate_public_snapshot(json.loads(source_file.read_text()))
    store = EngineStore.create(destination, name, filename=project_filename(name), storage_layout_version=2)
    evidence = store.metadata / "legacy_import"
    evidence.mkdir()
    shutil.copyfile(source_file, evidence / "source-project.json")
    history = []
    records = source_file.parent / ".insar_pilot" / "tasks" / "records"
    if records.is_dir():
        (evidence / "records").mkdir()
        for record in sorted(records.glob("*.json")):
            if record.stat().st_size > 4 * 1024 * 1024:
                continue
            raw = json.loads(record.read_text())
            # Preserve known evidence verbatim; absence of provenance stays absent.
            validate_public_snapshot(raw)
            shutil.copyfile(record, evidence / "records" / record.name)
            history.append({"source": str(record), "sha256": file_digest(record), "status": "imported_unverified"})

    store.revise(
        1,
        settings={
            "legacy_import": {
                "source": str(Path(source).resolve()),
                "configuration": asdict(legacy.workflow),
                "history_status": "unverified; no runs fabricated",
            }
        },
    )
    candidates = []
    root = Path(legacy.workflow.input_path) if legacy.workflow.input_path else legacy.workspace.slc_dir()
    if root.exists():
        candidates = [str(p) for p in root.rglob("*.zip")]
        candidates += [str(p) for p in root.rglob("*.SAFE") if p.is_dir()]
        candidates += [str(p) for p in root.rglob("*.h5") if p.is_file()]
    if candidates:
        artifacts = import_sources(app, store, candidates)
        missions = {a["mission"] for a in artifacts}
        if len(missions) == 1:
            store.attach_dataset([a["artifact_id"] for a in artifacts], Profile(missions.pop()), 2)
    results = []
    for product in ResultCatalogService().discover(Path(legacy.workflow.work_dir)):
        if not product.available or not Path(product.path).is_file():
            continue
        try:
            artifact = store.register_source(
                product.path,
                product.kind,
                Profile(store.project()["profile"]),
                {"legacy_result": asdict(product), "import_status": "imported_unverified"},
                {"grid_kind": "radar", "shape": [product.height, product.width]},
            )
            results.append({"artifact_id": artifact["artifact_id"], "source": product.path})
        except (OSError, ValueError) as exc:
            results.append({"source": product.path, "unavailable_reason": str(exc)})
    atomic_json(
        evidence / "manifest.json",
        {
            "source_project": str(source_file),
            "source_sha256": file_digest(source_file),
            "history": history,
            "results": results,
            "fabricated_runs": False,
        },
    )
    return app.register(store)
