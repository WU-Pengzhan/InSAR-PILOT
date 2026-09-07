"""Re-dispatch persisted execution leases after a local service restart."""

from __future__ import annotations

import logging
from pathlib import Path

from insar_pilot.application.engine_worker import launch_worker
from insar_pilot.infrastructure.application_state import ApplicationState
from insar_pilot.infrastructure.job_executor import process_identity


def recover_executions(registry: ApplicationState, state_root: Path) -> None:
    for project in registry.recent():
        if not project["available"]:
            continue
        try:
            store = registry.project(project["project_id"])
            active = {r["execution_id"] for r in store.list_objects("runs") if r["status"] in {"QUEUED", "RUNNING"}}
            for execution in store.list_objects("executions"):
                if execution["execution_id"] not in active:
                    continue
                worker = execution.get("worker", {})
                pid, identity = worker.get("pid"), worker.get("process_start")
                if pid and identity and process_identity(pid) == identity:
                    continue
                launch_worker(store, execution["execution_id"], state_root)
        except (OSError, ValueError, KeyError):
            logging.getLogger(__name__).exception("Could not recover project %s", project["project_id"])
