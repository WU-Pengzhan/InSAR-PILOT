"""Authenticated loopback API over the headless application services."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from insar_pilot.application.engine_data import capabilities, import_legacy, import_sources, search
from insar_pilot.application.engine_worker import launch_worker
from insar_pilot.domain.engine import Profile, nisar_definition, sentinel_definition
from insar_pilot.infrastructure.application_state import ApplicationState
from insar_pilot.infrastructure.engine_store import ConflictError, EngineStore
from insar_pilot.web.file_browser import (
    DirectoryPage,
    FileBrowser,
    FileLocations,
    ResolvedPath,
    ResolvePath,
    host_path,
)
from insar_pilot.web.imagery import ImageryTiles
from insar_pilot.web.lifecycle import task_inventory


class NewProject(BaseModel):
    path: str
    name: str = Field(min_length=1)
    profile: Profile = Profile.UNASSIGNED


class OpenProject(BaseModel):
    path: str


class LegacyImport(BaseModel):
    source: str
    destination: str
    name: str


class Revision(BaseModel):
    expected_revision: int = Field(ge=1)
    name: str | None = None
    aoi: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None
    pipelines: dict[str, Any] | None = None


class SourceImport(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=1000)
    role: str = "sar"


class AttachDataset(BaseModel):
    artifact_ids: list[str] = Field(min_length=1)
    profile: Profile
    expected_revision: int


class NewPipeline(BaseModel):
    profile: Profile
    inputs: dict[str, list[str]]
    parameters: dict[str, Any]
    environment: dict[str, Any]
    expected_revision: int


class Preview(BaseModel):
    through_step: str | None = None


class SearchQuery(BaseModel):
    mission: str = "SENTINEL-1"
    start: str
    end: str
    aoi_wkt: str
    platforms: list[str] = []
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=1000)
    orbit_direction: str | None = None
    relative_orbit: int | None = None
    polarizations: list[str] = []
    frequency_bands: list[str] = []
    provider_options: dict[str, Any] = {}


class DownloadSelection(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=1000)


class AOISelection(BaseModel):
    mode: Literal["bbox", "wkt", "file"]
    value: str = Field(min_length=1, max_length=100000)


class DownloadRuntime(BaseModel):
    aria2_executable: str


class ProjectSelection(DownloadSelection):
    project_id: str | None = None
    new_project: NewProject | None = None


class ScientificThreshold(BaseModel):
    metric_id: str
    minimum: float | None = None
    maximum: float | None = None
    blocking: bool = False


class QCEvaluation(BaseModel):
    policy_version: str = Field(min_length=1)
    thresholds: list[ScientificThreshold] = []


class RuntimeSettings(BaseModel):
    name: str = Field(min_length=1)
    python_executable: str
    processor: str
    omp_threads: int | None = Field(default=None, ge=1)


def create_app(
    state_root: Path,
    token: str,
    *,
    testing: bool = False,
    request_exit: Callable[[], None] | None = None,
) -> FastAPI:
    registry = ApplicationState(state_root)
    file_browser = FileBrowser(registry.root / "library")
    imagery = ImageryTiles()
    mutation_lock = asyncio.Lock()
    stopping = False

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        from insar_pilot.application.engine_recovery import recover_executions

        async def watch() -> None:
            while True:
                async with mutation_lock:
                    if not stopping:
                        await asyncio.to_thread(recover_executions, registry, state_root)
                await asyncio.sleep(10)

        task = asyncio.create_task(watch()) if not testing else None
        try:
            yield
        finally:
            imagery.close()
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="InSAR-PILOT Project Engine", version="2.0.0-alpha", docs_url=None, redoc_url=None, lifespan=lifespan
    )
    app.state.registry = registry
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"] + (["testserver"] if testing else [])
    )

    @app.middleware("http")
    async def authenticate(request: Request, call_next: Any) -> Response:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Untrusted Origin."}, status_code=403)
        if request.url.path.startswith(("/api/", "/openapi.json")):
            supplied = request.headers.get("authorization", "").removeprefix("Bearer ") or request.cookies.get(
                "pilot_session", ""
            )
            if not secrets.compare_digest(supplied, token):
                return JSONResponse({"detail": "Local session required."}, status_code=401)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            async with mutation_lock:
                if stopping:
                    return JSONResponse({"detail": "Application is shutting down."}, status_code=503)
                response: Response = await call_next(request)
        else:
            response = await call_next(request)
        if request.headers.get("authorization") == f"Bearer {token}":
            response.set_cookie("pilot_session", token, httponly=True, samesite="strict")
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(ConflictError)
    async def conflict(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(_request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse({"detail": f"Unknown resource: {exc}"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(OSError)
    async def filesystem(_request: Request, exc: OSError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return {"application": "insar-pilot", "version": "2.0.0-alpha", "status": "stopping" if stopping else "ok"}

    @app.get("/api/v1/application/status")
    def application_status() -> dict[str, Any]:
        return {
            "state": "STOPPING" if stopping else "RUNNING",
            "shutdown_supported": request_exit is not None,
            **task_inventory(registry),
        }

    async def finish_shutdown() -> None:
        # Allow the accepted response and status to reach the initiating browser.
        await asyncio.sleep(0.75)
        if request_exit:
            request_exit()

    @app.post("/api/v1/application/shutdown", status_code=202)
    def shutdown(background: BackgroundTasks) -> dict[str, Any]:
        nonlocal stopping
        status = application_status()
        if not status["can_exit"]:
            raise ConflictError(
                "Tasks or workers are still active. Open Jobs or Downloads and stop them before exiting."
            )
        if request_exit is None:
            raise ConflictError("Shutdown is unavailable in this server; start the application with insar-pilot-web.")
        stopping = True
        background.add_task(finish_shutdown)
        return {**status, "state": "STOPPING"}

    @app.get("/api/v1/maps/imagery/{z}/{x}/{y}")
    def imagery_tile(z: int, x: int, y: int) -> Response:
        status, content_type, data = imagery.fetch(z, x, y)
        return Response(
            data,
            status_code=status,
            media_type=content_type,
            headers={"Cache-Control": "private, max-age=3600" if status == 200 else "no-store"},
        )

    @app.get("/api/v1/filesystem/locations")
    def file_locations() -> FileLocations:
        return file_browser.locations()

    @app.post("/api/v1/filesystem/resolve")
    def resolve_file(body: ResolvePath) -> ResolvedPath:
        return file_browser.resolve(body.path)

    @app.get("/api/v1/filesystem/directories/{resource_id}")
    def directory_page(
        resource_id: str,
        offset: int = Query(default=0, ge=0, le=100000),
        limit: int = Query(default=200, ge=1, le=500),
        search: str = Query(default="", max_length=255),
        hidden: bool = False,
        directories_only: bool = False,
    ) -> DirectoryPage:
        return file_browser.browse(
            resource_id, offset=offset, limit=limit, search=search, hidden=hidden, directories_only=directories_only
        )

    @app.get("/api/v1/projects")
    def projects() -> list[dict[str, Any]]:
        return registry.recent()

    @app.post("/api/v1/projects", status_code=201)
    def create(body: NewProject) -> dict[str, Any]:
        return registry.register(EngineStore.create(host_path(body.path), body.name, body.profile))

    @app.post("/api/v1/projects/open")
    def open_project(body: OpenProject) -> dict[str, Any]:
        path = host_path(body.path)
        if path.name == "project.pilot" and path.is_file():
            path = path.parent
        return registry.register(EngineStore(path))

    @app.post("/api/v1/projects/import")
    def migrate(body: LegacyImport) -> dict[str, Any]:
        return import_legacy(registry, str(host_path(body.source)), str(host_path(body.destination)), body.name)

    @app.get("/api/v1/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        return registry.project(project_id).project()

    @app.patch("/api/v1/projects/{project_id}")
    def revise(project_id: str, body: Revision) -> dict[str, Any]:
        values = body.model_dump(exclude_unset=True)
        revision = values.pop("expected_revision")
        return registry.project(project_id).revise(revision, **values)

    @app.post("/api/v1/projects/{project_id}/sources")
    def sources(project_id: str, body: SourceImport) -> list[dict[str, Any]]:
        paths = [str(host_path(path)) for path in body.paths]
        return import_sources(registry, registry.project(project_id), paths, body.role)

    @app.post("/api/v1/projects/{project_id}/import-edits")
    def manual_edits(project_id: str, body: Revision) -> dict[str, Any]:
        return registry.project(project_id).import_definition_edits(body.expected_revision)

    @app.post("/api/v1/projects/{project_id}/datasets")
    def attach(project_id: str, body: AttachDataset) -> dict[str, Any]:
        return registry.project(project_id).attach_dataset(body.artifact_ids, body.profile, body.expected_revision)

    @app.post("/api/v1/projects/{project_id}/pipelines")
    def pipeline(project_id: str, body: NewPipeline) -> dict[str, str]:
        for values, key in ((body.environment, "python_executable"), (body.parameters, "template_path")):
            if values.get(key):
                values[key] = str(host_path(values[key]))
        definition = nisar_definition() if body.profile is Profile.NISAR else sentinel_definition()
        pid = registry.project(project_id).add_pipeline(
            definition, body.inputs, body.parameters, body.environment, body.expected_revision
        )
        return {"pipeline_id": pid}

    @app.get("/api/v1/projects/{project_id}/pipelines/{pipeline_id}/states")
    def states(project_id: str, pipeline_id: str) -> list[dict[str, Any]]:
        return registry.project(project_id).states(pipeline_id)

    @app.post("/api/v1/projects/{project_id}/pipelines/{pipeline_id}/plans")
    def preview(project_id: str, pipeline_id: str, body: Preview) -> dict[str, Any]:
        return registry.project(project_id).create_plan(pipeline_id, body.through_step)

    @app.post("/api/v1/projects/{project_id}/plans/{plan_id}/submit", status_code=202)
    def submit(project_id: str, plan_id: str) -> dict[str, Any]:
        store = registry.project(project_id)
        execution = store.submit(plan_id)
        if not testing:
            launch_worker(store, execution["execution_id"], state_root)
        return execution

    @app.post("/api/v1/projects/{project_id}/jobs/{job_id}/cancel")
    def cancel(project_id: str, job_id: str) -> dict[str, bool]:
        registry.project(project_id).cancel(job_id)
        return {"requested": True}

    @app.post("/api/v1/projects/{project_id}/runs/{run_id}/active")
    def adopt(project_id: str, run_id: str) -> dict[str, bool]:
        registry.project(project_id).set_active(run_id)
        return {"active": True}

    @app.get("/api/v1/projects/{project_id}/runs/{run_id}")
    def run_detail(project_id: str, run_id: str) -> dict[str, Any]:
        return registry.project(project_id).run(run_id)

    @app.post("/api/v1/projects/{project_id}/runs/{run_id}/rerun")
    def rerun(project_id: str, run_id: str) -> dict[str, Any]:
        store = registry.project(project_id)
        run = store.run(run_id)
        return store.create_plan(run["pipeline_id"], run["step_id"])

    @app.post("/api/v1/projects/{project_id}/runs/{run_id}/qc")
    def evaluate(project_id: str, run_id: str, body: QCEvaluation) -> dict[str, Any]:
        from dataclasses import asdict

        from insar_pilot.application.engine_qc import reevaluate

        report = reevaluate(
            registry.project(project_id), run_id, body.policy_version, [t.model_dump() for t in body.thresholds]
        )
        return {**asdict(report), "run_id": run_id, "gate_passed": report.gate_passed}

    @app.get("/api/v1/projects/{project_id}/postprocessing-inputs")
    def postprocessing(project_id: str) -> dict[str, Any]:
        store = registry.project(project_id)
        selected = []
        for pid in store.project()["pipelines"]:
            for step in store.states(pid):
                if step["active_usable"]:
                    selected.extend(store.run(step["active_run_id"])["output_artifact_ids"])
        artifacts = [store.artifact(aid) for aid in dict.fromkeys(selected)]
        required = ["unit", "wavelength", "phase_convention", "reference", "pair_dates"]
        return {
            "schema_version": 1,
            "artifact_ids": [a["artifact_id"] for a in artifacts],
            "artifacts": artifacts,
            "missing_metadata": {
                a["artifact_id"]: [k for k in required if not a["metadata"].get(k)] for a in artifacts
            },
            "processing_available": False,
        }

    @app.get("/api/v1/projects/{project_id}/runs/{run_id}/logs/{stream}")
    def log(project_id: str, run_id: str, stream: str, offset: int = 0, limit: int = 65536) -> dict[str, Any]:
        if stream not in {"stdout", "stderr"}:
            raise HTTPException(404)
        record = registry.project(project_id).run(run_id)
        path = Path(record[f"{stream}_log"])
        if not path.is_file():
            return {"text": "", "next_offset": 0}
        with path.open("rb") as handle:
            handle.seek(max(0, offset))
            text = handle.read(min(262144, max(1, limit))).decode("utf-8", errors="replace")
            return {"text": text, "next_offset": handle.tell()}

    @app.get("/api/v1/projects/{project_id}/events")
    def events(project_id: str, after: int = 0) -> list[dict[str, Any]]:
        return registry.project(project_id).events(after)

    @app.websocket("/api/v1/projects/{project_id}/events/ws")
    async def event_stream(websocket: WebSocket, project_id: str, after: int = 0) -> None:
        # ASGI servers may consume the raw header (notably wsproto).
        protocols = websocket.scope.get("subprotocols", [])
        supplied = protocols[-1] if len(protocols) == 2 else websocket.cookies.get("pilot_session", "")
        expected_origin = f"http://{websocket.headers.get('host')}"
        if (
            not secrets.compare_digest(supplied, token)
            or websocket.headers.get("origin", expected_origin) != expected_origin
        ):
            await websocket.close(code=1008)
            return
        await websocket.accept(subprotocol="pilot" if protocols and protocols[0] == "pilot" else None)
        try:
            store = registry.project(project_id)
            while True:
                rows = await asyncio.to_thread(store.events, after)
                if rows:
                    await websocket.send_json(rows)
                    after = rows[-1]["sequence"]
                else:
                    await websocket.send_json([])
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            return

    @app.get("/api/v1/projects/{project_id}/files")
    def files(project_id: str, relative: str = "") -> list[dict[str, Any]]:
        store = registry.project(project_id)
        target = (store.root / relative).resolve(strict=True)
        if not target.is_relative_to(store.root):
            raise HTTPException(403, "Path is outside project.")
        return [
            {
                "name": p.name,
                "relative": str(p.relative_to(store.root)),
                "directory": p.is_dir(),
                "size": p.stat().st_size if p.is_file() else None,
            }
            for p in sorted(target.iterdir())[:1000]
        ]

    @app.get("/api/v1/projects/{project_id}/artifacts/{artifact_id}/assets/{index}")
    def asset(project_id: str, artifact_id: str, index: int) -> FileResponse:
        artifact = registry.project(project_id).artifact(artifact_id)
        if index < 0 or index >= len(artifact["assets"]):
            raise HTTPException(404)
        path = artifact["assets"][index]["uri"]
        if not Path(path).is_file():
            raise ValueError("This asset is a directory reference; export individual registered files.")
        return FileResponse(path, filename=Path(path).name, media_type="application/octet-stream")

    @app.get("/api/v1/projects/{project_id}/artifacts/{artifact_id}/preview.png")
    def image(project_id: str, artifact_id: str) -> Response:
        from insar_pilot.web.raster import preview_png

        return Response(preview_png(registry.project(project_id).artifact(artifact_id)), media_type="image/png")

    @app.get("/api/v1/projects/{project_id}/artifacts/{artifact_id}/tiles/{z}/{x}/{y}.png")
    def tile(project_id: str, artifact_id: str, z: int, x: int, y: int) -> Response:
        import os
        import tempfile

        from insar_pilot.web.raster import tile_png

        store = registry.project(project_id)
        artifact = store.artifact(artifact_id)
        if not store.availability(artifact)[0]:
            raise ConflictError("Artifact is missing or changed.")
        if not 0 <= z <= 22 or not 0 <= x < 2**z or not 0 <= y < 2**z:
            raise ValueError("Invalid tile coordinate.")
        cache = store.root / "cache" / "tiles" / artifact_id / str(z) / str(x) / f"{y}.png"
        if not cache.is_file():
            data = tile_png(artifact, z, x, y)
            cache.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(dir=cache.parent)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            os.replace(name, cache)
        return Response(cache.read_bytes(), media_type="image/png")

    @app.get("/api/v1/projects/{project_id}/artifacts/{artifact_id}/display")
    def display(project_id: str, artifact_id: str) -> dict[str, Any]:
        from insar_pilot.web.raster import _read, display_range

        artifact = registry.project(project_id).artifact(artifact_id)
        low, high = display_range(_read(artifact))
        return {
            "minimum": low,
            "maximum": high,
            "sampling": "Bounded image sample, 2nd–98th percentile",
            "unit": artifact["metadata"].get("unit"),
            "nodata": "transparent",
        }

    @app.get("/api/v1/projects/{project_id}/artifacts/{artifact_id}/pixel")
    def sample(project_id: str, artifact_id: str, row: int, column: int) -> dict[str, Any]:
        from insar_pilot.web.raster import pixel_value

        return pixel_value(registry.project(project_id).artifact(artifact_id), row, column)

    @app.patch("/api/v1/projects/{project_id}/layers/{layer_id}")
    def style(project_id: str, layer_id: str, body: dict[str, Any]) -> dict[str, Any]:
        if set(body) - {"visible", "opacity", "name"}:
            raise ValueError("Unsupported layer presentation property.")
        if "opacity" in body and not 0 <= float(body["opacity"]) <= 1:
            raise ValueError("Layer opacity must be between zero and one.")
        from insar_pilot.domain.engine import canonical

        store = registry.project(project_id)
        with store.writer(), store.connection() as db:
            layer = store._body("layers", "layer_id", layer_id)
            layer.update(body)
            db.execute("UPDATE layers SET body=? WHERE layer_id=?", (canonical(layer), layer_id))
            store.event(db, "layer.styled", layer_id=layer_id)
        return layer

    @app.get("/api/v1/projects/{project_id}/{collection}")
    def collection(project_id: str, collection: str) -> list[dict[str, Any]]:
        return registry.project(project_id).list_objects(collection)

    @app.get("/api/v1/data/capabilities")
    def providers() -> list[dict[str, Any]]:
        return capabilities()

    @app.post("/api/v1/data/aoi")
    def prepare_aoi(body: AOISelection) -> dict[str, Any]:
        from math import isfinite

        from shapely.geometry import mapping
        from shapely.wkt import loads

        from insar_pilot.download.geometry import bbox_to_polygon, polygon_to_wkt, wkt_from_aoi_file

        if body.mode == "bbox":
            wkt = polygon_to_wkt(bbox_to_polygon(body.value))
        elif body.mode == "file":
            wkt = wkt_from_aoi_file(host_path(body.value))
        else:
            wkt = body.value
        try:
            geometry = loads(wkt)
        except Exception as exc:
            raise ValueError("AOI is not valid WKT.") from exc
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {"Point", "LineString", "Polygon"}:
            raise ValueError("Choose one valid WGS84 Point, LineString or Polygon AOI.")
        bounds = list(geometry.bounds)
        if not all(isfinite(v) for v in bounds) or not (
            -180 <= bounds[0] <= bounds[2] <= 180 and -90 <= bounds[1] <= bounds[3] <= 90
        ):
            raise ValueError("AOI coordinates must use WGS84 longitude/latitude within the world bounds.")
        return {"wkt": geometry.wkt, "geometry": mapping(geometry), "bounds": bounds}

    @app.get("/api/v1/data/download-readiness")
    def download_readiness() -> dict[str, Any]:
        from insar_pilot.application.engine_download import aria2_executable
        from insar_pilot.download.credentials import load_earthdata_credentials

        credentials = load_earthdata_credentials()
        aria2 = aria2_executable(registry)
        return {
            "core": "DownloadService",
            "transport": "aria2c",
            "aria2_available": bool(aria2),
            "aria2_executable": aria2,
            "credentials_configured": credentials is not None,
            "ready": bool(aria2 and credentials),
            "credentials_validated": False,
            "library_path": str(registry.root / "library"),
            "supported": ["Sentinel-1 SLC + EOF", "NISAR RSLC"],
            "range_subset_web_ready": False,
            "dem_preparation_web_ready": False,
        }

    @app.post("/api/v1/data/download-runtime")
    def download_runtime(body: DownloadRuntime) -> dict[str, Any]:
        import os

        from insar_pilot.domain.engine import canonical

        path = host_path(body.aria2_executable)
        if path.name != "aria2c" or not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError("Choose a Linux executable named aria2c.")
        with registry.connection() as db:
            db.execute(
                "INSERT OR REPLACE INTO preferences VALUES('download.runtime', ?)",
                (canonical({"aria2_executable": str(path)}),),
            )
        return download_readiness()

    @app.post("/api/v1/data/search")
    def find_data(body: SearchQuery) -> list[dict[str, Any]]:
        groups = search(body.model_dump())
        registry.save_search(groups)
        return groups

    @app.post("/api/v1/data/downloads", status_code=202)
    def download(body: DownloadSelection) -> dict[str, Any]:
        from insar_pilot.application.engine_download import submit

        return submit(registry, body.product_ids)

    @app.get("/api/v1/data/downloads")
    def downloads() -> list[dict[str, Any]]:
        return registry.downloads()

    @app.post("/api/v1/data/selection", status_code=202)
    def select_data(body: ProjectSelection) -> dict[str, Any]:
        from insar_pilot.application.engine_download import submit

        products = [registry.remote(pid) for pid in dict.fromkeys(body.product_ids)]
        missions = {p["mission"] for p in products}
        if len(missions) != 1:
            raise ValueError("Group the processing selection by mission before creating a dataset.")
        profile = Profile.NISAR if missions == {"NISAR"} else Profile.SENTINEL1_TOPS
        if bool(body.project_id) == bool(body.new_project):
            raise ValueError("Choose an existing project or a new project.")
        if body.new_project:
            store = EngineStore.create(host_path(body.new_project.path), body.new_project.name)
            registry.register(store)
        else:
            assert body.project_id is not None
            store = registry.project(body.project_id)
        if store.project()["profile"] not in {"unassigned", profile.value}:
            raise ConflictError("Selection mission conflicts with this project.")
        artifacts = [store.register_remote(p, profile) for p in products]
        project = store.attach_dataset([a["artifact_id"] for a in artifacts], profile, store.project()["revision"])
        job = submit(registry, body.product_ids, project["project_id"]) if not testing else None
        return {"project": project, "job": job}

    @app.post("/api/v1/data/downloads/{job_id}/cancel")
    def cancel_download(job_id: str) -> dict[str, Any]:
        from insar_pilot.application.engine_download import stop_download

        return stop_download(registry, job_id, pause=False)

    @app.post("/api/v1/data/downloads/{job_id}/pause")
    def pause_download(job_id: str) -> dict[str, Any]:
        from insar_pilot.application.engine_download import stop_download

        return stop_download(registry, job_id, pause=True)

    @app.post("/api/v1/data/downloads/{job_id}/resume", status_code=202)
    def resume_download(job_id: str) -> dict[str, Any]:
        from insar_pilot.application.engine_download import continue_download

        return continue_download(registry, job_id, resume=True)

    @app.post("/api/v1/data/downloads/{job_id}/retry", status_code=202)
    def retry_download(job_id: str) -> dict[str, Any]:
        from insar_pilot.application.engine_download import continue_download

        return continue_download(registry, job_id, resume=False)

    @app.get("/api/v1/data/library")
    def library() -> list[dict[str, Any]]:
        return registry.library()

    @app.get("/api/v1/compute")
    def compute() -> dict[str, Any]:
        import os
        import shutil
        import subprocess

        gpu: list[str] = []
        if shutil.which("nvidia-smi"):
            try:
                proc = subprocess.run(
                    ["nvidia-smi", "--query-gpu=index,uuid,name,memory.total,driver_version", "--format=csv,noheader"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                gpu = proc.stdout.strip().splitlines() if proc.returncode == 0 else []
            except subprocess.TimeoutExpired:
                pass
        return {
            "cpu_count": os.cpu_count(),
            "gpu_devices": gpu,
            "cuda_processing_validated": False,
            "available_modes": {"sentinel1_tops": ["CPU"], "nisar": ["CPU"]},
            "note": "GPU detection does not establish processor CUDA capability.",
        }

    @app.get("/api/v1/compute/profiles")
    def runtime_profiles() -> list[dict[str, Any]]:
        import json

        with registry.connection() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT body FROM preferences WHERE key LIKE 'runtime.%'")]

    @app.post("/api/v1/compute/profiles", status_code=201)
    def save_runtime(body: RuntimeSettings) -> dict[str, Any]:
        from insar_pilot.domain.engine import canonical, new_id
        from insar_pilot.infrastructure.engine_fingerprint import runtime_fingerprint

        if body.processor not in {"isce2", "isce3"}:
            raise ValueError("Choose isce2 or isce3.")
        body.python_executable = str(host_path(body.python_executable))
        result = {**body.model_dump(), "runtime_id": new_id()}
        result["observation"] = runtime_fingerprint(body.model_dump())
        with registry.connection() as db:
            db.execute("INSERT INTO preferences VALUES(?,?)", (f"runtime.{result['runtime_id']}", canonical(result)))
        return result

    frontend = Path(__file__).parent / "static"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="workbench")
    return app
