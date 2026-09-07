"""GUI-independent local process groups with durable logs and cancellation."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from insar_pilot.domain.engine import utc_now
from insar_pilot.infrastructure.engine_store import EngineStore


def process_identity(pid: int) -> str | None:
    try:
        # /proc field 22; comm can contain spaces/parentheses.
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return fields[19]
    except (OSError, IndexError):
        return None


def terminate_group(process: subprocess.Popen[Any], grace: float = 5) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


class LocalJobExecutor:
    def execute(self, store: EngineStore, run_id: str, argv: list[str], environment: dict[str, str]) -> int:
        run = store.run(run_id)
        if store.cancelled(run["job_id"]):
            return -signal.SIGTERM
        with (
            Path(run["stdout_log"]).open("ab", buffering=0) as stdout,
            Path(run["stderr_log"]).open("ab", buffering=0) as stderr,
        ):
            process = subprocess.Popen(
                argv,
                cwd=run["working_directory"],
                env=environment,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            store.update_job(
                run["job_id"], pid=process.pid, process_start=process_identity(process.pid), heartbeat=utc_now()
            )
            last_heartbeat = time.monotonic()
            try:
                while process.poll() is None:
                    if store.cancelled(run["job_id"]):
                        terminate_group(process)
                        break
                    if time.monotonic() - last_heartbeat >= 2:
                        store.update_job(run["job_id"], heartbeat=utc_now())
                        last_heartbeat = time.monotonic()
                    time.sleep(0.1)
                return int(process.wait())
            except BaseException:
                terminate_group(process)
                raise
            finally:
                os.fsync(stdout.fileno())
                os.fsync(stderr.fileno())

    @staticmethod
    def recover(store: EngineStore) -> None:
        """Do not double-start live processes after an application restart."""
        for job in store.list_objects("jobs"):
            if job["status"] != "RUNNING":
                continue
            pid = job.get("pid")
            if pid and process_identity(pid) == job.get("process_start"):
                store.update_job(job["job_id"], recovery="live_process_requires_observation")
            else:
                from insar_pilot.domain.engine import RunStatus

                store.finish(
                    job["run_id"],
                    RunStatus.FAILED,
                    None,
                    failure_kind="interrupted",
                    message="Worker stopped before a terminal result was committed.",
                )
