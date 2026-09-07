"""Reviewable, idempotent data acquisition plans and project binding."""

from __future__ import annotations

import fcntl
import json
import shutil
from pathlib import Path
from typing import Any

from insar_pilot.application.acquisition_dem import coverage
from insar_pilot.domain.engine import Profile, canonical, digest, new_id, utc_now
from insar_pilot.download.public_metadata import public_metadata
from insar_pilot.infrastructure.application_state import ApplicationState
from insar_pilot.infrastructure.engine_store import ConflictError, EngineStore, file_snapshot
from insar_pilot.infrastructure.project_file import project_filename


def product_key(product: dict[str, Any]) -> str:
    return digest({"provider": product["provider_id"], "product": product["remote_product_id"]})


def network_options(app: ApplicationState) -> dict[str, Any]:
    with app.connection() as db:
        row = db.execute("SELECT body FROM preferences WHERE key='download.network'").fetchone()
    return json.loads(row[0]) if row else {"mode": "direct", "preset": "balanced", "limit_mib": 0}


def readiness(app: ApplicationState) -> dict[str, Any]:
    from insar_pilot.application.engine_download import aria2_executable
    from insar_pilot.download.credentials import load_earthdata_credentials

    with app.connection() as db:
        row = db.execute("SELECT body FROM preferences WHERE key='download.runtime'").fetchone()
    config = json.loads(row[0]) if row else {}
    gdal = config.get("gdal_executable") or shutil.which("gdalwarp")
    info = str(Path(gdal).with_name("gdalinfo")) if gdal else shutil.which("gdalinfo")
    return {
        "aria2_available": bool(aria2_executable(app)),
        "aria2_executable": aria2_executable(app),
        "credentials_configured": load_earthdata_credentials() is not None,
        "credentials_validated": False,
        "gdal_available": bool(gdal and info and Path(info).is_file()),
        "gdal_executable": gdal,
        "library_path": str(app.root / "library"),
        "network": network_options(app),
        "range_subset_web_ready": False,
        "dem_preparation_web_ready": False,
        "dem_download_web_ready": True,
    }


def preview(app: ApplicationState, request: dict[str, Any]) -> dict[str, Any]:
    ids = list(dict.fromkeys(request["product_ids"]))
    if not 1 <= len(ids) <= 1000:
        raise ValueError("Select between 1 and 1000 products.")
    products = [public_metadata(app.remote(pid)) for pid in ids]
    keys = [product_key(p) for p in products]
    destination = request.get("project_id")
    revision = None
    new_project = request.get("new_project")
    if destination and new_project:
        raise ValueError("Choose one project target.")
    target_path = app.root / "library"
    if new_project:
        project_filename(new_project["name"])
        root = Path(new_project["path"]).expanduser().resolve()
        if new_project.get("parent_directory"):
            root = root / new_project["name"].strip()
        if root.exists() and any(root.iterdir()):
            raise ConflictError("A new project requires an empty directory.")
        if len({p["mission"] for p in products}) != 1:
            raise ConflictError("A processing project requires exactly one mission.")
        target_path = root / "data"
    if destination:
        current = app.project(destination).project()
        missions = {p["mission"] for p in products}
        profile = "sentinel1_tops" if missions == {"SENTINEL-1"} else "nisar" if missions == {"NISAR"} else ""
        if not profile or current["profile"] not in {"unassigned", profile}:
            raise ConflictError("Selection mission conflicts with this project.")
        revision = current["revision"]
        target_path = app.project(destination).layout.data
    options = {
        "include_orbits": bool(request.get("include_orbits", True)),
        "include_dem": bool(request.get("include_dem", False)),
        "buffer_m": float(request.get("buffer_m", 20000)),
    }
    files: list[dict[str, Any]] = []
    available = app.library()
    for product, key in zip(products, keys, strict=True):
        sar = "RSLC" if product["mission"] == "NISAR" else "SLC"
        roles = [sar] + (["ORBIT"] if sar == "SLC" and options["include_orbits"] else [])
        for role in roles:
            found = []
            for asset in available:
                meta = asset["metadata"]
                if (
                    key not in [meta.get("product_key"), *meta.get("product_keys", [])]
                    or meta.get("role") != role
                    or not meta.get("integrity")
                ):
                    continue
                try:
                    if file_snapshot(Path(asset["path"])) == asset["snapshot"]:
                        found.append(asset)
                except OSError:
                    pass
            files.append(
                {
                    "file_id": digest({"product": key, "role": role}),
                    "product_key": key,
                    "scene_id": product["remote_product_id"],
                    "role": role,
                    "size_bytes": product.get("size_bytes") if role == sar else None,
                    "status": "available" if found else "planned",
                    "library_asset_id": found[0]["asset_id"] if found else None,
                    "local_path": found[0]["path"] if found else None,
                }
            )
    dem = None
    blockers: list[str] = []
    if options["include_dem"]:
        local_paths = {f["scene_id"]: f["local_path"] for f in files if f["role"] == "SLC" and f.get("local_path")}
        dem = coverage(products, options["buffer_m"], local_paths if len(local_paths) == len(products) else None)
        files.append(
            {
                "file_id": digest(dem),
                "role": "DEM",
                "status": "waiting_for_geometry",
                "scene_id": "COP30",
                "size_bytes": None,
            }
        )
    ready = readiness(app)
    if any(f["role"] in {"SLC", "RSLC"} and f["status"] != "available" for f in files):
        if not ready["aria2_available"]:
            blockers.append("aria2c is unavailable.")
        if not ready["credentials_configured"]:
            blockers.append("Earthdata credentials are not configured (authentication has not been validated).")
    if dem and not ready["gdal_available"]:
        blockers.append("DEM mosaicking requires gdalwarp and gdalinfo; configure the GDAL executable.")
    known = sum(f["size_bytes"] or 0 for f in files if f["status"] != "available")
    dem_temp = 0
    if dem:
        w, s, e, n = dem["bounds"]
        dem_temp = int((e - w) * (n - s) * 3600**2 * 8 + dem["tile_count"] * 100 * 1024**2)
        dem["estimated_temporary_bytes"] = dem_temp
    disk_root = target_path
    while not disk_root.exists():
        disk_root = disk_root.parent
    disk = shutil.disk_usage(disk_root).free
    if known * 2 + dem_temp > disk:
        blockers.append("Insufficient disk space for sources and temporary files.")
    plan = {
        "plan_id": new_id(),
        "created_at": utc_now(),
        "product_ids": keys,
        "products": products,
        "product_signatures": [digest(p) for p in products],
        "options": options,
        "project_id": destination,
        "expected_revision": revision,
        "query_sources": public_metadata(request.get("query_sources", [])),
        "files": files,
        "dem": dem,
        "destination": str(target_path),
        "destination_kind": "project" if destination or new_project else "library",
        "new_project": new_project,
        "known_bytes": known,
        "unknown_files": sum(f["size_bytes"] is None for f in files),
        "free_bytes": disk,
        "blockers": blockers,
        "network": ready["network"],
        "gdal_executable": ready["gdal_executable"],
    }
    app.save_acquisition_plan(plan)
    return plan


def commit(app: ApplicationState, request: dict[str, Any], *, testing: bool = False) -> dict[str, Any]:
    """Checkpoint each durable step under a cross-process idempotency lock."""
    from insar_pilot.application.engine_download import launch_worker, new_download

    plan = app.acquisition_plan(request["plan_id"])
    request_key = request["idempotency_key"]
    signature = digest(request)
    with (app.root / "library" / "partial" / "acquisition-submit.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with app.connection() as db:
            row = db.execute(
                "SELECT signature,body FROM acquisition_submissions WHERE request_key=?", (request_key,)
            ).fetchone()
        if row:
            if row[0] != signature:
                raise ConflictError("Idempotency key was already used for different content.")
            result: dict[str, Any] = json.loads(row[1])
            if result.get("complete"):
                if result.get("job"):
                    current_job = app.download(result["job"]["job_id"])
                    if current_job["status"] == "QUEUED" and not testing:
                        launch_worker(app, current_job)
                    result["job"] = current_job
                return result
        else:
            result = {"plan_id": plan["plan_id"], "project": None, "job": None, "complete": False}

        def checkpoint() -> None:
            with app.connection() as db:
                db.execute(
                    "INSERT OR REPLACE INTO acquisition_submissions VALUES(?,?,?)",
                    (request_key, signature, canonical(result)),
                )

        if not row:
            if plan.get("new_project") != request.get("new_project") and plan.get("destination_kind") == "project":
                raise ConflictError("Project destination changed; refresh the preview.")
            if plan.get("destination_kind") == "library" and request.get("new_project"):
                raise ConflictError("Preview the new project destination before committing.")
            disk_root = Path(plan["destination"])
            while not disk_root.exists():
                disk_root = disk_root.parent
            required = plan["known_bytes"] * 2 + (plan.get("dem") or {}).get("estimated_temporary_bytes", 0)
            if request.get("start_download", True) and shutil.disk_usage(disk_root).free < required:
                raise ValueError("Insufficient disk space; refresh the preview.")
            if [digest(public_metadata(app.remote(k))) for k in plan["product_ids"]] != plan["product_signatures"]:
                raise ConflictError("Catalogue metadata changed; refresh the acquisition preview.")
            if plan["project_id"] and request.get("project_id") != plan["project_id"]:
                raise ConflictError("The preview belongs to another project.")
            if request.get("start_download", True):
                live = readiness(app)
                blockers = [
                    b for b in plan["blockers"] if "credentials" not in b and "aria2c" not in b and "gdalwarp" not in b
                ]
                needs_sar = any(f["role"] in {"SLC", "RSLC"} and f["status"] != "available" for f in plan["files"])
                if needs_sar and not (live["aria2_available"] and live["credentials_configured"]):
                    blockers.append("Configure aria2c and Earthdata before starting downloads.")
                if plan["options"]["include_dem"] and not live["gdal_available"]:
                    blockers.append("GDAL is unavailable.")
                if blockers and not testing:
                    raise ValueError(" ".join(blockers))
            checkpoint()
        new_project = request.get("new_project")
        pid = request.get("project_id")
        if new_project or pid:
            missions = {p["mission"] for p in plan["products"]}
            if len(missions) != 1:
                raise ConflictError("A processing project requires exactly one mission.")
            profile = Profile.SENTINEL1_TOPS if missions == {"SENTINEL-1"} else Profile.NISAR
            if result.get("project"):
                store = app.project(result["project"]["project_id"])
            elif new_project:
                filename = project_filename(new_project["name"])
                path = Path(new_project["path"]).expanduser().resolve()
                if new_project.get("parent_directory"):
                    path = path / new_project["name"].strip()
                # Crash recovery uses the registered intent, never another unrelated project.
                result.setdefault("new_path", str(path))
                checkpoint()
                if (path / ".insar_pilot").exists():
                    store = EngineStore(path)
                    if store.project().get("settings", {}).get("acquisition_request") != request_key:
                        raise ConflictError("Project directory already exists; choose another directory.")
                else:
                    store = EngineStore.create(
                        path,
                        new_project["name"],
                        initial_settings={"acquisition_request": request_key},
                        filename=filename,
                        storage_layout_version=2,
                    )
                result["project"] = app.register(store)
                checkpoint()
            else:
                store = app.project(str(pid))
                current = store.project()
                expected = request.get("expected_revision")
                if expected is None or expected != plan["expected_revision"] or current["revision"] != expected:
                    raise ConflictError("Project revision changed; refresh the preview.")
                if current["profile"] not in {"unassigned", profile.value}:
                    raise ConflictError("Selection mission conflicts with this project.")
                result["project"] = current
                checkpoint()
            # Dataset provenance makes recovery/addition idempotent.
            current = store.project()
            already = any(d.get("acquisition_plan_id") == plan["plan_id"] for d in current["datasets"])
            if not already:
                artifacts = store.list_objects("artifacts")
                bound = {aid for d in current["datasets"] for aid in d["artifact_ids"]}
                existing_keys = {a["metadata"].get("product_key") for a in artifacts if a["artifact_id"] in bound}
                additions = []
                for p in plan["products"]:
                    if product_key(p) in existing_keys:
                        continue
                    candidates = [a for a in artifacts if a["metadata"].get("product_key") == product_key(p)]
                    additions.append(
                        candidates[0]
                        if candidates
                        else store.register_remote({**p, "product_key": product_key(p)}, profile)
                    )
                if additions:
                    current = store.attach_dataset(
                        [a["artifact_id"] for a in additions],
                        profile,
                        current["revision"],
                        acquisition_plan_id=plan["plan_id"],
                        query_sources=plan["query_sources"],
                    )
                result["project"] = current
            checkpoint()
        if request.get("start_download", True) and not result.get("job"):
            project_id = result["project"]["project_id"] if result["project"] else None
            active = [
                j
                for j in app.downloads()
                if j["status"] in {"QUEUED", "RUNNING"}
                and not j.get("cancel_requested")
                and j.get("project_id") == project_id
                and j.get("options") == plan["options"]
                and j.get("destination") == plan["destination"]
                and {product_key(p) for p in j["products"]} == set(plan["product_ids"])
            ]
            job = (
                active[0]
                if active
                else new_download(app, plan["products"], project_id, options=plan["options"], plan=plan)
            )
            result["job"] = job
            checkpoint()
            app.save_download(job)
        elif result.get("job"):
            app.save_download(result["job"])
        result["complete"] = True
        checkpoint()
    if result["job"] and not testing:
        try:
            launch_worker(app, result["job"])
            result["job"] = app.download(result["job"]["job_id"])
        except OSError:
            result["job"] = app.download(result["job"]["job_id"])
        with app.connection() as db:
            db.execute(
                "UPDATE acquisition_submissions SET body=? WHERE request_key=?", (canonical(result), request_key)
            )
    return result
