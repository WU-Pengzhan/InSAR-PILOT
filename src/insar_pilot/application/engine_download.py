"""Durable Sentinel/NISAR acquisition attempts with bounded cross-process transfers."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

from insar_pilot.domain.engine import digest, new_id, utc_now
from insar_pilot.download.credentials import load_earthdata_credentials
from insar_pilot.download.download_service import DownloadService
from insar_pilot.download.integrity import receipt_path
from insar_pilot.download.models import SceneRecord
from insar_pilot.download.network import NetworkConfig
from insar_pilot.download.public_metadata import public_metadata
from insar_pilot.infrastructure.application_state import ApplicationState


def aria2_executable(app: ApplicationState) -> str | None:
    with app.connection() as db:
        row = db.execute("SELECT body FROM preferences WHERE key='download.runtime'").fetchone()
    configured = json.loads(row[0]).get("aria2_executable") if row else None
    candidate = configured or shutil.which("aria2c")
    if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def submit(
    app: ApplicationState,
    product_ids: list[str],
    project_id: str | None = None,
    *,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not product_ids:
        raise ValueError("Select products first.")
    products = [app.remote(pid) for pid in dict.fromkeys(product_ids)]
    job = new_download(app, products, project_id, options=options)
    app.save_download(job)
    launch_worker(app, job)
    return app.download(job["job_id"])


def new_download(
    app: ApplicationState,
    products: list[dict[str, Any]],
    project_id: str | None,
    *,
    options: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from insar_pilot.application.acquisition import network_options

    executable = aria2_executable(app)
    if not executable and plan is None:
        raise ValueError("Select an available Linux aria2c executable in Download preparation first.")
    store = app.project(project_id) if project_id else None
    destination = str(store.layout.data) if store else str(app.root / "library")
    if plan:
        destination = plan["destination"]
    kind = "project" if store and Path(destination) == store.layout.data else "library"
    transfer_root = str(store.layout.transfers) if store and kind == "project" else str(app.root / "library")
    job_id = new_id()
    log_root = store.metadata / "records" if store else app.root / "records"
    return {
        "job_id": job_id,
        "worker_log": str(log_root / "downloads" / job_id / "worker.log"),
        "status": "QUEUED",
        "created_at": utc_now(),
        "products": public_metadata(products),
        "progress": [],
        "results": [],
        "cancel_requested": False,
        "message": "",
        "project_id": project_id,
        "aria2_executable": executable,
        "destination": destination,
        "destination_kind": kind,
        "project_name": store.project()["name"] if store else None,
        "transfer_root": transfer_root,
        "options": options or {"include_orbits": True, "include_dem": False, "buffer_m": 20000},
        "plan_id": plan["plan_id"] if plan else None,
        "files": plan["files"] if plan else [],
        "dem_plan": plan.get("dem") if plan else None,
        "gdal_executable": plan.get("gdal_executable") if plan else None,
        "network": plan.get("network") if plan else network_options(app),
    }


def launch_worker(app: ApplicationState, job: dict[str, Any]) -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    paths = [str(Path(job[key]).parent) for key in ("aria2_executable", "gdal_executable") if job.get(key)]
    environment["PATH"] = os.pathsep.join([*paths, environment.get("PATH", "")])
    log_path = Path(job.get("worker_log", str(app.root / "records/downloads" / job["job_id"] / "worker.log")))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        try:
            subprocess.Popen(
                [sys.executable, "-m", "insar_pilot.application.engine_download", str(app.root), job["job_id"]],
                env=environment,
                stdout=log,
                stderr=log,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            job.update(status="FAILED", finished_at=utc_now(), message="The download worker could not be started.")
            app.save_download(job)
            raise


def continue_download(app: ApplicationState, job_id: str, *, resume: bool) -> dict[str, Any]:
    old = app.download(job_id)
    plan = app.acquisition_plan(old["plan_id"]) if old.get("plan_id") else None
    job = new_download(app, old["products"], old.get("project_id"), options=old.get("options"), plan=plan)
    job.update(parent_job_id=job_id, root_job_id=old.get("root_job_id", job_id))
    for field in ("destination", "destination_kind", "transfer_root", "project_name"):
        if field in old:
            job[field] = old[field]
    app.continue_download(job_id, job, resume=resume)
    launch_worker(app, job)
    return app.download(job["job_id"])


def stop_download(app: ApplicationState, job_id: str, *, pause: bool) -> dict[str, Any]:
    if app.stop_download(job_id, pause=pause):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
        job = app.download(job_id)
        log_path = Path(job.get("worker_log", str(app.root / "records/downloads" / job_id / "worker.log"))).with_name(
            "control.log"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log:
            subprocess.Popen(
                [sys.executable, "-m", "insar_pilot.application.engine_download_control", str(app.root), job_id],
                env=environment,
                stdout=log,
                stderr=log,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
    return app.download(job_id)


@contextmanager
def transfer_slot(app: ApplicationState, cancelled: Any) -> Iterator[None]:
    """At most two four-connection workers, across every batch and process."""
    acquired = None
    while acquired is None:
        if cancelled():
            raise InterruptedError("Cancelled while waiting for the global transfer budget.")
        for number in range(2):
            handle = (app.root / "library" / "partial" / f"transfer-slot-{number}.lock").open("a")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = handle
                break
            except BlockingIOError:
                handle.close()
        if acquired is None:
            time.sleep(0.2)
    try:
        yield
    finally:
        acquired.close()


def execute(app: ApplicationState, job_id: str) -> None:
    # A duplicate launch or HTTP retry cannot execute the same attempt twice.
    with (app.root / "library" / "partial" / f"worker-{digest(job_id)}.lock").open("a") as owner:
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        _execute_owned(app, job_id)


def _execute_owned(app: ApplicationState, job_id: str) -> None:
    from insar_pilot.application.acquisition import product_key
    from insar_pilot.application.engine_data import import_sources

    job = app.download(job_id)
    if job["status"] in {"SUCCESS", "FAILED", "CANCELLED"}:
        return

    def cancelled() -> bool:
        return bool(app.download(job_id).get("cancel_requested"))

    if cancelled():
        job.update(status="CANCELLED", finished_at=utc_now())
        app.save_download(job)
        return
    job.update(status="RUNNING", started_at=utc_now())
    app.save_download(job)
    guard = threading.RLock()
    local_paths: dict[str, str] = {}
    transfer_root = Path(job.get("transfer_root", str(app.root / "library")))
    transfer_root.mkdir(parents=True, exist_ok=True)
    options = job.get("options", {"include_orbits": True})
    config = job.get("network") or {}
    network = NetworkConfig.from_dict(
        {k: config[k] for k in ("mode", "http_proxy", "https_proxy", "timeout_seconds") if k in config}
    )
    credentials = load_earthdata_credentials()
    workers = min(len(job["products"]), 1 if config.get("preset") == "stable" else 2) or 1
    last_progress: dict[str, float] = {}

    def report(task: Any, product: dict[str, Any] | None = None, terminal: bool = False) -> None:
        item = public_metadata(task.to_dict())
        item["message"] = DownloadService._safe_subprocess_excerpt(str(item.get("message", "")))
        role = task.product_type.upper()
        key = product_key(product) if product else "COP30"
        item.update(product_key=key, file_id=digest({"product": key, "role": role}))
        if item.get("url"):
            item["url"] = item["url"].split("?")[0]
        with guard:
            if not terminal and task.status == "running":
                now = time.monotonic()
                if now - last_progress.get(item["file_id"], 0) < 0.5:
                    return
                last_progress[item["file_id"]] = now
            target = "results" if terminal else "progress"
            rows = {r["file_id"]: r for r in job.get(target, []) if r.get("file_id")}
            rows[item["file_id"]] = item
            job[target] = list(rows.values())
            job["phase"] = task.status
            job["updated_at"] = utc_now()
            app.save_download(job)

    def publish(result: Any, product: dict[str, Any] | None, dem_plan: dict[str, Any] | None = None) -> Any:
        path = Path(result.local_path)
        staged_source = path
        if not path.is_file():
            raise ValueError("Acquisition returned success without a readable local file.")
        role = result.product_type.upper()
        if cancelled():
            raise InterruptedError("Publication cancelled.")
        if job.get("destination_kind") == "project" and path.is_relative_to(transfer_root):
            from insar_pilot.application.acquisition_storage import publish_source

            path = publish_source(path, Path(job["destination"]), role, transfer_root, cancelled)
            result = replace(result, local_path=str(path))
        receipt = receipt_path(path)
        integrity = (
            json.loads(receipt.read_text()) if receipt.exists() else {"checks": ["provider_download_validation"]}
        )
        metadata = {
            **public_metadata(product or {}),
            "role": role,
            "product_key": product_key(product) if product else "COP30",
            "integrity": integrity,
            "acquisition_plan_id": job.get("plan_id"),
            "attempt_id": job_id,
            "dem_coverage": dem_plan,
        }
        metadata["storage_kind"] = (
            "project"
            if job.get("destination_kind") == "project" and path.is_relative_to(Path(job["destination"]))
            else "reference"
        )
        asset = app.library_register(str(path), metadata)
        if job.get("project_id"):
            with guard:  # serialize project revisions from concurrent scenes
                store = app.project(job["project_id"])
                imported = import_sources(
                    app,
                    store,
                    [str(path)],
                    "sar" if role in {"SLC", "RSLC"} else "orbit" if role == "ORBIT" else "dem",
                    acquisition_metadata=metadata,
                )
                if product and role in {"SLC", "RSLC"}:
                    store.resolve_remote(product["remote_product_id"], imported[0]["artifact_id"])
        with guard:
            job.setdefault("published", []).append(
                {
                    "file_id": digest({"product": metadata["product_key"], "role": role}),
                    "asset_id": asset["asset_id"],
                    "role": role,
                    "path": str(path),
                }
            )
            app.save_download(job)
        if staged_source != path and staged_source.resolve().is_relative_to(transfer_root.resolve()):
            staged_source.unlink(missing_ok=True)
            receipt_path(staged_source).unlink(missing_ok=True)
        return result

    def one(product: dict[str, Any]) -> None:
        key = product_key(product)
        try:
            private = app.remote(key)
        except KeyError:
            private = product
        scene = SceneRecord(
            product["remote_product_id"],
            product.get("acquisition_time") or "",
            product["platform"],
            product.get("orbit_direction") or "",
            product.get("relative_orbit") or 0,
            ",".join(product.get("polarizations", [])),
            (product.get("size_bytes") or 0) / 1024**2,
            download_url=private.get("download_url", ""),
            footprint_geojson=product.get("footprint", {}),
        )
        service = DownloadService()
        service.connections = 2 if config.get("preset") == "stable" else 4
        service.limit_mib = float(config.get("limit_mib", 0)) / workers
        target = transfer_root / ("NISAR" if product["mission"] == "NISAR" else "Sentinel1")
        tasks = (
            service.create_rslc_tasks([scene], target)
            if product["mission"] == "NISAR"
            else service.create_tasks([scene], target, include_orbits=options.get("include_orbits", True))
        )
        try:
            with (app.root / "library" / "partial" / f"{key}.lock").open("a") as lock:
                while True:
                    if cancelled():
                        raise InterruptedError("Cancelled while waiting for scene identity lock.")
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        time.sleep(0.2)
                from insar_pilot.application.acquisition_storage import reusable_asset
                from insar_pilot.download.task_state import result_from_task

                missing = []
                results = []
                for task in tasks:
                    cached = reusable_asset(app, key, task.product_type.upper())
                    if cached:
                        results.append(
                            result_from_task(
                                task.with_updates(
                                    status="skipped",
                                    local_path=str(cached),
                                    message="Reused registered source version.",
                                    backend="library",
                                )
                            )
                        )
                    else:
                        missing.append(task)
                with transfer_slot(app, cancelled):
                    results.extend(
                        service.download(
                            missing,
                            username=credentials.username if credentials else "",
                            password=credentials.password if credentials else "",
                            network=network,
                            progress_callback=lambda t: report(t, product),
                            cancel_check=cancelled,
                        )
                        if missing
                        else []
                    )
                for result in results:
                    if (
                        result.status in {"completed", "downloaded", "skipped", "success"}
                        and Path(result.local_path).is_file()
                    ):
                        with guard:
                            result = publish(result, product)
                        if result.product_type in {"SLC", "RSLC"}:
                            with guard:
                                local_paths[product["remote_product_id"]] = result.local_path
                    report(result, product, True)
        except Exception as exc:
            status = "cancelled" if isinstance(exc, InterruptedError) or cancelled() else "failed"
            for task in tasks:
                report(
                    task.with_updates(
                        status=status, message=DownloadService._safe_subprocess_excerpt(f"{type(exc).__name__}: {exc}")
                    ),
                    product,
                    True,
                )

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(one, job["products"]))
        if options.get("include_dem") and not cancelled():
            from insar_pilot.application.acquisition_dem import coverage, legacy_plan
            from insar_pilot.download.cop30_service import Cop30AwsDemService
            from insar_pilot.download.dem_service import create_dem_task

            dem_task = create_dem_task(transfer_root, "COP30")
            try:
                resolved = coverage(job["products"], options.get("buffer_m", 20000), local_paths)
                estimate = job.get("dem_plan")
                if estimate and not set(resolved["tiles"]).issubset(set(estimate["tiles"])):
                    raise ValueError(
                        "Verified full-scene DEM exceeds the reviewed tile plan. Create an updated preview."
                    )
                job["dem_plan"] = resolved
                app.save_download(job)
                with (
                    (app.root / "library" / "partial" / "dem-cache.lock").open("a") as dem_lock,
                    transfer_slot(app, cancelled),
                ):
                    while True:
                        if cancelled():
                            raise InterruptedError("DEM wait cancelled.")
                        try:
                            fcntl.flock(dem_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except BlockingIOError:
                            time.sleep(0.2)
                    result = Cop30AwsDemService(workers=2).download(
                        dem_task,
                        legacy_plan(resolved),
                        network=network,
                        progress_callback=lambda t: report(t),
                        cancel_check=cancelled,
                    )
                if result.status in {"completed", "skipped"}:
                    result = publish(result, None, resolved)
                report(result, terminal=True)
            except Exception as exc:
                report(dem_task.with_updates(status="failed", message=str(exc)), terminal=True)
        job["status"] = (
            "CANCELLED"
            if cancelled()
            else "FAILED"
            if any(r["status"] not in {"completed", "downloaded", "skipped", "success"} for r in job["results"])
            else "SUCCESS"
        )
    except Exception as exc:
        job.update(
            status="CANCELLED" if cancelled() else "FAILED",
            message=DownloadService._safe_subprocess_excerpt(f"{type(exc).__name__}: {exc}"),
        )
    job.update(finished_at=utc_now(), cancel_requested=cancelled())
    app.save_download(job)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("job_id")
    args = parser.parse_args()
    execute(ApplicationState(args.state), args.job_id)
