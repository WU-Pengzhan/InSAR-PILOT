"""Detached, single-machine execution worker. Browser/server lifetimes are irrelevant."""

from __future__ import annotations

import argparse
import fcntl
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from insar_pilot.application.engine_processing import (
    application_provenance,
    build_nisar,
    build_sentinel_generation,
    freeze_run_evidence,
    nisar_outputs,
    runtime_environment,
    sentinel_outputs,
    sentinel_stage_commands,
    workspace_inventory,
)
from insar_pilot.application.engine_qc import sentinel_metrics, structural_report
from insar_pilot.domain.engine import RunStatus, canonical, utc_now
from insar_pilot.infrastructure.engine_fingerprint import runtime_matches
from insar_pilot.infrastructure.engine_store import EngineStore, atomic_json
from insar_pilot.infrastructure.job_executor import LocalJobExecutor, process_identity


def launch_worker(store: EngineStore, execution_id: str, application_state: Path) -> int:
    application_state.mkdir(parents=True, exist_ok=True)
    # Queued workers import an execution-owned source tree. Editing the application
    # while a worker waits cannot mix loaded old modules with new source evidence.
    code_root = store.metadata / "execution-code" / execution_id
    with store.writer():
        if not code_root.exists():
            code_root.parent.mkdir(exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix=f".{execution_id}.", suffix=".partial", dir=code_root.parent))
            shutil.copytree(
                Path(__file__).resolve().parents[1],
                temporary / "insar_pilot",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "static"),
            )
            atomic_json(temporary / "provenance.json", application_provenance())
            os.replace(temporary, code_root)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(code_root)
    with (application_state / "worker.log").open("ab") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "insar_pilot.application.engine_worker",
                str(store.root),
                execution_id,
                "--state",
                str(application_state),
            ],
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    return process.pid


def execute(store: EngineStore, execution_id: str, application_state: Path) -> None:
    # This lease survives API/server restarts and excludes duplicate dispatches.
    with (store.metadata / f"execution-{execution_id}.lock").open("a") as lease:
        try:
            fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        execution = store._body("executions", "execution_id", execution_id)
        execution["worker"] = {
            "pid": os.getpid(),
            "process_start": process_identity(os.getpid()),
            "started_at": utc_now(),
        }
        with store.connection() as db:
            db.execute("UPDATE executions SET body=? WHERE execution_id=?", (canonical(execution), execution_id))
        # A previous worker may have died while its independently grouped child
        # continued. Observe it; its unknown exit status cannot establish success.
        for rid in execution["run_ids"]:
            run = store.run(rid)
            if run["status"] != "RUNNING":
                continue
            job = store._body("jobs", "job_id", run["job_id"])
            pid, identity = job.get("pid"), job.get("process_start")
            cancelled_at = None
            while pid and identity and process_identity(pid) == identity:
                if store.cancelled(job["job_id"]):
                    if cancelled_at is None:
                        cancelled_at = time.monotonic()
                    try:
                        os.killpg(pid, signal.SIGKILL if time.monotonic() - cancelled_at > 5 else signal.SIGTERM)
                    except ProcessLookupError:
                        break
                time.sleep(0.2)
            store.finish(
                rid,
                RunStatus.CANCELLED if store.cancelled(job["job_id"]) else RunStatus.FAILED,
                None,
                failure_kind="interrupted",
                message="Worker exit status or publication was not committed; retry creates a new Run.",
            )
        _execute(store, execution_id, application_state)


def _execute(store: EngineStore, execution_id: str, application_state: Path) -> None:
    execution = store._body("executions", "execution_id", execution_id)
    pipeline = execution["pipeline_snapshot"]
    workspace = Path(execution["working_directory"])
    application_state.mkdir(parents=True, exist_ok=True)
    with (application_state / "compute.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        executor = LocalJobExecutor()
        failed = False
        for index, (rid, step) in enumerate(zip(execution["run_ids"], execution["steps"], strict=True)):
            run = store.run(rid)
            if RunStatus(run["status"]).terminal:
                failed = failed or run["status"] != "SUCCESS"
                continue
            if failed or store.cancelled(run["job_id"]):
                store.finish(rid, RunStatus.CANCELLED, None, failure_kind="upstream_failed" if failed else "cancelled")
                failed = True
                continue
            exit_code = None
            try:
                if not runtime_matches(pipeline):
                    raise ValueError("Processor runtime changed after submission; build a new execution plan.")
                environment = runtime_environment(pipeline["environment"])
                provenance = application_provenance()
                provenance = {
                    **provenance,
                    "requested_compute": pipeline["parameters"].get("compute_mode", "CPU"),
                    "actual_compute": "CPU",
                    "thread_environment": {
                        key: environment.get(key)
                        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
                    },
                }
                is_nisar = pipeline["definition"]["profile"] == "nisar"
                if is_nisar:
                    commands = [build_nisar(store, pipeline, workspace)]
                elif index == 0:
                    commands = [build_sentinel_generation(store, pipeline, workspace)]
                else:
                    commands = sentinel_stage_commands(
                        workspace, step, Path(run["stdout_log"]).parent, pipeline["parameters"].get("num_proc", 1)
                    )
                store.begin(rid, commands, provenance)
                # Save exact configs independently of later workspace mutation.
                config_dir = store.root / "runs" / rid / "config"
                config_dir.mkdir(exist_ok=True)
                freeze_run_evidence(store.root / "runs" / rid, workspace, pipeline["environment"])
                if is_nisar:
                    config = next((workspace / "runconfig").glob("*.json"))
                    (config_dir / config.name).write_bytes(config.read_bytes())
                before = workspace_inventory(workspace)
                command_index = 0
                while command_index < len(commands):
                    command = commands[command_index]
                    exit_code = executor.execute(store, rid, command, environment)
                    if exit_code != 0 or store.cancelled(run["job_id"]):
                        break
                    if not is_nisar and index == 0 and command_index == 0:
                        commands += sentinel_stage_commands(
                            workspace, step, Path(run["stdout_log"]).parent, pipeline["parameters"].get("num_proc", 1)
                        )
                        with store.connection() as db:
                            running = store.run(rid)
                            running["commands"] = commands
                            store._update_run(db, running)
                        atomic_json(store.root / "runs" / rid / "snapshot.json", running)
                    command_index += 1
                freeze_run_evidence(store.root / "runs" / rid, workspace, pipeline["environment"])
                if store.cancelled(run["job_id"]):
                    store.finish(rid, RunStatus.CANCELLED, exit_code, failure_kind="cancelled")
                    failed = True
                elif exit_code != 0:
                    store.finish(rid, RunStatus.FAILED, exit_code, failure_kind="processor_exit")
                    failed = True
                else:
                    if is_nisar:
                        outputs, metrics = nisar_outputs(workspace, pipeline["parameters"])
                    else:
                        outputs = sentinel_outputs(workspace, before, step)
                        metrics = list(sentinel_metrics(workspace, step["official_label"]))
                    report = structural_report(True, "Validated actual processor outputs.", tuple(metrics))
                    staged = store.publish_outputs(rid, outputs)
                    result = store.finish(rid, RunStatus.SUCCESS, 0, staged, report)
                    failed = result["status"] != "SUCCESS"
            except Exception as exc:
                if not RunStatus(store.run(rid)["status"]).terminal:
                    store.finish(
                        rid,
                        RunStatus.FAILED,
                        exit_code,
                        report=structural_report(False, str(exc)),
                        failure_kind="adapter_error",
                        message=str(exc),
                    )
                failed = True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("execution_id")
    parser.add_argument("--state", required=True)
    args = parser.parse_args()
    execute(EngineStore(args.project), args.execution_id, Path(args.state))


if __name__ == "__main__":
    main()
