"""Persistent one-step task execution orchestration."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from dataclasses import replace
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path

from insar_pilot.domain.local_data import JsonValue
from insar_pilot.domain.task_runtime import (
    RuntimeProfile,
    TaskLogEvent,
    TaskOverwritePolicy,
    TaskRunRecord,
    TaskRunRequest,
    TaskStatus,
)
from insar_pilot.domain.workflows import TaskDescriptor
from insar_pilot.providers.task_runtime import (
    TaskBackendRegistry,
    TaskCancelled,
    TaskExecutionContext,
)


class TaskRunStoreError(RuntimeError):
    """Task state could not be durably read or written."""


class TaskRunStore:
    CURRENT_SCHEMA_VERSION = 1
    MAX_RECORD_BYTES = 4 * 1024 * 1024

    def __init__(self, project_root: str | Path) -> None:
        self.task_dir = Path(project_root).expanduser() / ".insar_pilot" / "tasks"
        self.records_dir = self.task_dir / "records"
        self.logs_dir = self.task_dir / "logs"

    def save(self, record: TaskRunRecord) -> Path:
        target = self.record_path(record.request.run_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(record.to_dict(), ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        self._atomic_write(target, f"{text}\n")
        return target

    def load(self, run_id: str) -> TaskRunRecord:
        path = self.record_path(run_id)
        try:
            if path.stat().st_size > self.MAX_RECORD_BYTES:
                raise TaskRunStoreError(f"Task record is too large: {path}")
            value = json.loads(path.read_text(encoding="utf-8"))
            return TaskRunRecord.from_dict(value)
        except TaskRunStoreError:
            raise
        except (JSONDecodeError, OSError, TypeError, ValueError) as exc:
            raise TaskRunStoreError(f"Task record is malformed or unreadable: {path}") from exc

    def list_records(self) -> tuple[TaskRunRecord, ...]:
        if not self.records_dir.exists():
            return ()
        return tuple(self.load(path.stem) for path in sorted(self.records_dir.glob("*.json")))

    def recover_interrupted(self) -> tuple[TaskRunRecord, ...]:
        """Mark non-terminal records left by a stopped process as failed and retryable."""

        recovered: list[TaskRunRecord] = []
        for record in self.list_records():
            if record.status.terminal:
                continue
            updated = replace(
                record,
                status=TaskStatus.FAILED,
                finished_at=datetime.now(timezone.utc),
                message="Task was interrupted before a terminal state was persisted.",
            )
            self.save(updated)
            recovered.append(updated)
        return tuple(recovered)

    def append_log(self, run_id: str, event: TaskLogEvent) -> Path:
        path = self.log_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event.to_dict(), ensure_ascii=False, allow_nan=False, sort_keys=True))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise TaskRunStoreError(f"Could not append task log: {path}") from exc
        return path

    def record_path(self, run_id: str) -> Path:
        return self.records_dir / f"{_safe_run_id(run_id)}.json"

    def log_path(self, run_id: str) -> Path:
        return self.logs_dir / f"{_safe_run_id(run_id)}.jsonl"

    @staticmethod
    def _atomic_write(target: Path, text: str) -> None:
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temp_path = Path(stream.name)
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, target)
        except OSError as exc:
            if temp_path is not None:
                with suppress(OSError):
                    temp_path.unlink(missing_ok=True)
            raise TaskRunStoreError(f"Could not atomically write task record: {target}") from exc


class TaskExecutionApplicationService:
    """Run exactly one descriptor through one registered backend."""

    def __init__(self, registry: TaskBackendRegistry, store: TaskRunStore) -> None:
        self._registry = registry
        self._store = store

    def execute(
        self,
        descriptor: TaskDescriptor,
        request: TaskRunRequest,
        profile: RuntimeProfile,
        context: TaskExecutionContext | None = None,
    ) -> TaskRunRecord:
        self._validate_contract(descriptor, request, profile)
        backend = self._registry.require(request.backend_id)
        if not backend.supports(request.task_id):
            raise ValueError(f"Backend {request.backend_id} does not support task {request.task_id}.")
        actual_context = context or TaskExecutionContext()
        now = datetime.now(timezone.utc)
        log_path = str(self._store.log_path(request.run_id))
        pending = TaskRunRecord(
            request=request,
            runtime_profile_id=profile.profile_id,
            status=TaskStatus.PENDING,
            created_at=now,
            log_path=log_path,
        )
        self._store.save(pending)
        conflict = self._output_conflict(request)
        if conflict:
            failed = replace(
                pending,
                status=TaskStatus.FAILED,
                finished_at=datetime.now(timezone.utc),
                message=conflict,
            )
            self._store.save(failed)
            return failed

        running = replace(pending, status=TaskStatus.RUNNING, started_at=datetime.now(timezone.utc))
        self._store.save(running)

        def log_sink(event: TaskLogEvent) -> None:
            self._store.append_log(request.run_id, event)
            actual_context.log_sink(event)

        backend_context = TaskExecutionContext(actual_context.cancellation, log_sink)
        try:
            backend_context.raise_if_cancelled()
            result = backend.run(request, profile, backend_context)
            backend_context.raise_if_cancelled()
        except TaskCancelled as exc:
            terminal = replace(
                running,
                status=TaskStatus.CANCELLED,
                finished_at=datetime.now(timezone.utc),
                message=str(exc),
            )
        except Exception as exc:  # Backend boundary: preserve a recoverable failed record.
            terminal = replace(
                running,
                status=TaskStatus.FAILED,
                finished_at=datetime.now(timezone.utc),
                message=str(exc),
            )
        else:
            status = TaskStatus.SUCCEEDED if result.exit_code == 0 else TaskStatus.FAILED
            terminal = replace(
                running,
                status=status,
                finished_at=datetime.now(timezone.utc),
                outputs=result.outputs,
                exit_code=result.exit_code,
                message=result.message,
            )
        self._store.save(terminal)
        return terminal

    def retry(
        self,
        original_run_id: str,
        new_run_id: str,
        descriptor: TaskDescriptor,
        profile: RuntimeProfile,
        *,
        parameter_updates: dict[str, JsonValue] | None = None,
        output_dir: str | None = None,
        overwrite_policy: TaskOverwritePolicy | None = None,
        context: TaskExecutionContext | None = None,
    ) -> TaskRunRecord:
        original = self._store.load(original_run_id)
        if not original.status.terminal:
            raise ValueError("Only a terminal task run can be retried.")
        parameters = dict(original.request.parameters)
        parameters.update(parameter_updates or {})
        request = TaskRunRequest(
            run_id=new_run_id,
            task_id=original.request.task_id,
            backend_id=original.request.backend_id,
            inputs=original.request.inputs,
            output_dir=output_dir or original.request.output_dir,
            parameters=parameters,
            overwrite_policy=overwrite_policy or original.request.overwrite_policy,
            attempt=original.request.attempt + 1,
            parent_run_id=original.request.run_id,
        )
        return self.execute(descriptor, request, profile, context)

    @staticmethod
    def _validate_contract(
        descriptor: TaskDescriptor,
        request: TaskRunRequest,
        profile: RuntimeProfile,
    ) -> None:
        if request.task_id != descriptor.task_id:
            raise ValueError("Task request does not match the selected TaskDescriptor.")
        if request.backend_id != descriptor.backend_id:
            raise ValueError("Task request backend does not match the TaskDescriptor.")
        if profile.backend_id != request.backend_id:
            raise ValueError("Runtime profile belongs to a different backend.")
        provided_roles = {asset.role for asset in request.inputs}
        missing_roles = set(descriptor.input_roles).difference(provided_roles)
        if missing_roles:
            raise ValueError(f"Task inputs are missing roles: {', '.join(sorted(missing_roles))}")

    def _output_conflict(self, request: TaskRunRequest) -> str:
        output = Path(request.output_dir).expanduser()
        if request.overwrite_policy in {
            TaskOverwritePolicy.ERROR_IF_EXISTS,
            TaskOverwritePolicy.NEW_DIRECTORY,
        } and output.exists():
            return f"Output path already exists under policy {request.overwrite_policy.value}: {output}"
        return ""


def _safe_run_id(run_id: str) -> str:
    normalized = run_id.strip().lower()
    if not normalized or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for character in normalized):
        raise ValueError(f"run_id is not safe for persistence: {run_id}")
    return normalized


__all__ = [
    "TaskExecutionApplicationService",
    "TaskRunStore",
    "TaskRunStoreError",
]
