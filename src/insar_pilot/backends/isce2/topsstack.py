"""Task adapter for one official ISCE2 topsStack generated run file."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from insar_pilot.domain.local_data import AssetRef, JsonValue
from insar_pilot.domain.task_runtime import RuntimeProfile, TaskBackendResult, TaskRunRequest
from insar_pilot.providers.task_runtime import TaskCancelled, TaskExecutionContext
from insar_pilot.services.runfile_plan import (
    build_parallel_batch_command,
    parse_run_file,
    split_batches_for_parallelism,
)


class Isce2TopsStackTaskBackend:
    """Execute only stages emitted by the official ``stackSentinel.py`` plan."""

    backend_id = "isce2.topsstack"
    _TASK_ID = "sentinel1.run_official_stage"

    def supports(self, task_id: str) -> bool:
        return task_id == self._TASK_ID

    def run(
        self,
        request: TaskRunRequest,
        profile: RuntimeProfile,
        context: TaskExecutionContext,
    ) -> TaskBackendResult:
        if not self.supports(request.task_id):
            raise ValueError(f"Unsupported ISCE2 TOPS task: {request.task_id}")
        run_file = _single_run_file(request.inputs)
        work_dir = run_file.parent.parent
        if run_file.parent.name != "run_files":
            raise ValueError("The official ISCE2 stage must be located under work_dir/run_files.")

        max_parallel = _positive_integer(request.parameters.get("max_parallel", 1), "max_parallel")
        batches = split_batches_for_parallelism(parse_run_file(run_file), max_parallel)
        if not batches:
            raise ValueError(f"Official ISCE2 run file contains no commands: {run_file}")

        task_output = Path(request.output_dir).expanduser()
        task_output.mkdir(parents=True, exist_ok=True)
        environment = _runtime_environment(profile)
        for batch_index, batch in enumerate(batches, start=1):
            context.raise_if_cancelled()
            log_paths = {
                command.index: str(task_output / f"command_{command.index:03d}.log")
                for command in batch
            }
            command_text = build_parallel_batch_command(batch, log_paths)
            context.log(
                "info",
                "Starting official ISCE2 run-file batch.",
                run_file=str(run_file),
                batch=batch_index,
                batch_count=len(batches),
            )
            exit_code = _run_batch(command_text, work_dir, environment, context)
            context.log(
                "info" if exit_code == 0 else "error",
                "Official ISCE2 run-file batch finished.",
                batch=batch_index,
                exit_code=exit_code,
            )
            if exit_code != 0:
                return TaskBackendResult(
                    outputs=(AssetRef(str(task_output), "stage_artifact"),),
                    exit_code=exit_code,
                    message=f"ISCE2 stage failed in batch {batch_index}/{len(batches)}.",
                )

        return TaskBackendResult(
            outputs=(AssetRef(str(task_output), "stage_artifact"),),
            message=f"Official ISCE2 stage completed: {run_file.name}",
        )


def _single_run_file(inputs: tuple[AssetRef, ...]) -> Path:
    assets = tuple(asset for asset in inputs if asset.role == "run_file")
    if len(assets) != 1:
        raise ValueError("ISCE2 stage execution requires exactly one run_file asset.")
    asset = assets[0]
    if asset.subdataset is not None:
        raise ValueError("An ISCE2 run_file cannot be an HDF5 subdataset.")
    path = Path(asset.uri).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Official ISCE2 run file was not found: {path}")
    return path


def _positive_integer(value: JsonValue, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer.")
    return value


def _runtime_environment(profile: RuntimeProfile) -> dict[str, str]:
    environment = os.environ.copy()
    configured = profile.settings.get("environment", {})
    if not isinstance(configured, Mapping):
        raise TypeError("ISCE2 runtime environment must be a mapping.")
    for key, value in configured.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError("ISCE2 runtime environment keys and values must be strings.")
        environment[key] = value
    return environment


def _run_batch(
    command_text: str,
    work_dir: Path,
    environment: Mapping[str, str],
    context: TaskExecutionContext,
) -> int:
    process = subprocess.Popen(  # noqa: S603 - command text comes from official generated run files.
        ("bash", "-c", command_text),
        cwd=work_dir,
        env=environment,
        start_new_session=True,
    )
    while process.poll() is None:
        if context.cancellation.is_cancelled():
            _terminate_process_group(process)
            raise TaskCancelled("Official ISCE2 stage was cancelled.")
        time.sleep(0.1)
    return int(process.returncode)


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except ProcessLookupError:
        return
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


__all__ = ["Isce2TopsStackTaskBackend"]
