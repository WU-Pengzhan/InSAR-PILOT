"""Persisted download-only jobs backed by the existing downloader and Library."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from insar_pilot.domain.engine import digest, new_id, utc_now
from insar_pilot.download.credentials import load_earthdata_credentials
from insar_pilot.download.download_service import DownloadService
from insar_pilot.download.models import SceneRecord
from insar_pilot.infrastructure.application_state import ApplicationState


def aria2_executable(app: ApplicationState) -> str | None:
    with app.connection() as db:
        row = db.execute("SELECT body FROM preferences WHERE key='download.runtime'").fetchone()
    configured = json.loads(row[0]).get("aria2_executable") if row else None
    candidate = configured or shutil.which("aria2c")
    if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def submit(app: ApplicationState, product_ids: list[str], project_id: str | None = None) -> dict[str, Any]:
    if not product_ids:
        raise ValueError("Select products first.")
    products = [app.remote(pid) for pid in dict.fromkeys(product_ids)]
    job = new_download(app, products, project_id)
    app.save_download(job)
    launch_worker(app, job)
    return app.download(job["job_id"])


def new_download(app: ApplicationState, products: list[dict[str, Any]], project_id: str | None) -> dict[str, Any]:
    executable = aria2_executable(app)
    if not executable:
        raise ValueError("Select an available Linux aria2c executable in Download preparation first.")
    job: dict[str, Any] = {
        "job_id": new_id(),
        "status": "QUEUED",
        "created_at": utc_now(),
        "products": products,
        "progress": [],
        "results": [],
        "cancel_requested": False,
        "message": "",
        "project_id": project_id,
        "aria2_executable": executable,
        "destination": str(app.root / "library"),
    }
    return job


def launch_worker(app: ApplicationState, job: dict[str, Any]) -> None:
    executable = job["aria2_executable"]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    environment["PATH"] = str(Path(executable).parent) + os.pathsep + environment.get("PATH", "")
    with (app.root / "download-worker.log").open("ab") as log:
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
    previous = app.download(job_id)
    job = new_download(app, previous["products"], previous.get("project_id"))
    job["parent_job_id"] = job_id
    app.continue_download(job_id, job, resume=resume)
    launch_worker(app, job)
    return app.download(job["job_id"])


def stop_download(app: ApplicationState, job_id: str, *, pause: bool) -> dict[str, Any]:
    if app.stop_download(job_id, pause=pause):
        # A separate bounded observer also handles old workers blocked in authentication.
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
        with (app.root / "download-worker.log").open("ab") as log:
            subprocess.Popen(
                [sys.executable, "-m", "insar_pilot.application.engine_download_control", str(app.root), job_id],
                env=environment,
                stdout=log,
                stderr=log,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
    return app.download(job_id)


def execute(app: ApplicationState, job_id: str) -> None:
    job = app.download(job_id)
    if job["status"] in {"SUCCESS", "FAILED", "CANCELLED"}:
        return

    def cancelled() -> bool:
        latest = app.download(job_id)
        return bool(latest["cancel_requested"])

    if cancelled():
        job.update(status="CANCELLED", finished_at=utc_now())
        app.save_download(job)
        return
    job.update(status="RUNNING", started_at=utc_now())
    app.save_download(job)
    try:
        credentials = load_earthdata_credentials()
        if credentials is None:
            raise ValueError("Earthdata credentials are unavailable; configure the existing local credential provider.")
        job.setdefault("results", [])
        for product in job["products"]:
            if cancelled():
                job.update(status="CANCELLED", cancel_requested=True)
                break
            identity = digest({"provider": product["provider_id"], "product": product["remote_product_id"]})
            job.update(current_product_id=product["remote_product_id"], phase="waiting_for_lock")
            app.save_download(job)
            with (app.root / "library" / "partial" / f"{identity}.lock").open("a") as lock:
                while True:
                    if cancelled():
                        job.update(status="CANCELLED", cancel_requested=True)
                        break
                    try:
                        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        time.sleep(0.25)
                if job["status"] == "CANCELLED":
                    break
                is_nisar = product["mission"] == "NISAR"
                scene = SceneRecord(
                    product["remote_product_id"],
                    product["acquisition_time"] or "",
                    product["platform"],
                    product.get("orbit_direction") or "",
                    product.get("relative_orbit") or 0,
                    ",".join(product["polarizations"]),
                    (product.get("size_bytes") or 0) / 1024**2,
                    download_url=product["download_url"],
                    footprint_geojson=product.get("footprint", {}),
                )
                service = DownloadService()
                target = app.root / "library" / ("NISAR" if is_nisar else "Sentinel1")
                tasks = (
                    service.create_rslc_tasks([scene], target)
                    if is_nisar
                    else service.create_tasks([scene], target, include_orbits=True)
                )
                job.update(phase="connecting", progress=[task.to_dict() for task in tasks])
                app.save_download(job)

                last_update = 0.0
                last_status: tuple[str, str] | None = None

                def progress(task: Any) -> None:
                    nonlocal last_update, last_status
                    now = time.monotonic()
                    status = (task.task_id, task.status)
                    if status == last_status and now - last_update < 0.5:
                        return
                    last_update, last_status = now, status
                    job["phase"] = "transferring"
                    progress_by_id = {item["task_id"]: item for item in job["progress"]}
                    progress_by_id[task.task_id] = task.to_dict()
                    job["progress"] = list(progress_by_id.values())
                    job["cancel_requested"] = cancelled()
                    app.save_download(job)

                results = service.download(
                    tasks,
                    username=credentials.username,
                    password=credentials.password,
                    progress_callback=progress,
                    cancel_check=cancelled,
                )
                for result in results:
                    job["results"].append(result.to_dict())
                    if (
                        result.status in {"completed", "downloaded", "skipped", "success"}
                        and Path(result.local_path).is_file()
                    ):
                        app.library_register(result.local_path, product)
                        if job.get("project_id") and result.product_type.upper() in {"SLC", "RSLC", "ORBIT"}:
                            from insar_pilot.application.engine_data import import_sources

                            store = app.project(job["project_id"])
                            role = "orbit" if result.product_type.upper() == "ORBIT" else "sar"
                            imported = import_sources(app, store, [result.local_path], role)
                            if role == "sar":
                                store.resolve_remote(product["remote_product_id"], imported[0]["artifact_id"])
                    elif result.status == "cancelled":
                        job.update(status="CANCELLED", cancel_requested=True)
                        break
                    else:
                        raise RuntimeError(result.message or f"Download outcome: {result.status}")
            if job["status"] == "CANCELLED":
                break
            app.save_download(job)
        if job["status"] == "RUNNING":
            job["status"] = "SUCCESS"
    except Exception as exc:
        job.update(status="FAILED", message=str(exc))
    job["finished_at"] = utc_now()
    job["cancel_requested"] = bool(job.get("cancel_requested") or cancelled())
    app.save_download(job)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("job_id")
    args = parser.parse_args()
    execute(ApplicationState(args.state), args.job_id)
