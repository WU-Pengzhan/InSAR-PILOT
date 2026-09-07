"""Local service status and idle-only application shutdown."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from insar_pilot.infrastructure.application_state import ApplicationState
from insar_pilot.infrastructure.job_executor import process_identity


def owned_workers(state_root: Path) -> set[int]:
    """Find detached application workers without exposing command arguments."""
    found: set[int] = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = (entry / "cmdline").read_bytes().rstrip(b"\0").split(b"\0")
            if len(args) < 5 or args[1] != b"-m" or not process_identity(int(entry.name)):
                continue
            if args[2] in {
                b"insar_pilot.application.engine_download",
                b"insar_pilot.application.engine_download_control",
            } and args[3] == os.fsencode(state_root):
                found.add(int(entry.name))
            if args[2] == b"insar_pilot.application.engine_worker" and args[-2:] == [
                b"--state",
                os.fsencode(state_root),
            ]:
                found.add(int(entry.name))
        except OSError:
            continue
    return found


def task_inventory(registry: ApplicationState) -> dict[str, Any]:
    processing = 0
    unavailable = 0
    workers = owned_workers(registry.root)
    for project in registry.recent():
        if not project["available"]:
            continue
        try:
            for job in registry.project(project["project_id"]).list_objects("jobs"):
                processing += job["status"] in {"QUEUED", "RUNNING"}
                pid, identity = job.get("pid"), job.get("process_start")
                if pid and identity and process_identity(pid) == identity:
                    workers.add(pid)
        except (OSError, ValueError, KeyError):
            unavailable += 1
    downloads = registry.downloads()
    downloading = sum(job["status"] in {"QUEUED", "RUNNING"} for job in downloads)
    return {
        "processing_jobs": processing,
        "download_jobs": downloading,
        "paused_downloads": sum(job["display_status"] == "PAUSED" for job in downloads),
        "worker_processes": len(workers),
        "unreadable_projects": unavailable,
        "can_exit": not (processing or downloading or workers or unavailable),
    }
