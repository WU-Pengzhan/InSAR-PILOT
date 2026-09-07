"""Serializable values for one-step task execution and recovery."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import cast

from insar_pilot.domain.local_data import AssetRef, JsonValue


def _required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def _time(value: datetime | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone.")
    return value.astimezone(timezone.utc)


def _time_text(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def _parse_time(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be an ISO-8601 string or null.")
    return _time(datetime.fromisoformat(value.replace("Z", "+00:00")), field_name)


def _json_mapping(value: object, field_name: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise TypeError(f"{field_name} must be a string-keyed mapping.")
    return cast(Mapping[str, JsonValue], value)


def _freeze_json(value: object, field_name: str) -> JsonValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} cannot contain a non-finite number.")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError(f"{field_name} keys must be strings.")
        return MappingProxyType(
            {str(key): _freeze_json(item, field_name) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, field_name) for item in value)
    raise TypeError(f"{field_name} must contain JSON-compatible values.")


def _frozen_mapping(value: object, field_name: str) -> Mapping[str, JsonValue]:
    frozen = _freeze_json(_json_mapping(value, field_name), field_name)
    if not isinstance(frozen, Mapping):
        raise TypeError(f"{field_name} must be a mapping.")
    return frozen


def _json_ready(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value


class TaskOverwritePolicy(str, Enum):
    ERROR_IF_EXISTS = "error_if_exists"
    NEW_DIRECTORY = "new_directory"
    REPLACE_DECLARED_OUTPUTS = "replace_declared_outputs"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}


@dataclass(frozen=True)
class RuntimeProfile:
    profile_id: str
    backend_id: str
    settings: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", _required(self.profile_id, "profile_id").lower())
        object.__setattr__(self, "backend_id", _required(self.backend_id, "backend_id").lower())
        object.__setattr__(self, "settings", _frozen_mapping(self.settings, "settings"))


@dataclass(frozen=True)
class TaskRunRequest:
    run_id: str
    task_id: str
    backend_id: str
    inputs: tuple[AssetRef, ...]
    output_dir: str
    parameters: Mapping[str, JsonValue]
    overwrite_policy: TaskOverwritePolicy = TaskOverwritePolicy.NEW_DIRECTORY
    attempt: int = 1
    parent_run_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _required(self.run_id, "run_id").lower())
        object.__setattr__(self, "task_id", _required(self.task_id, "task_id").lower())
        object.__setattr__(self, "backend_id", _required(self.backend_id, "backend_id").lower())
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "output_dir", _required(self.output_dir, "output_dir"))
        object.__setattr__(self, "parameters", _frozen_mapping(self.parameters, "parameters"))
        if self.attempt < 1:
            raise ValueError("attempt must be positive.")
        parent_run_id = self.parent_run_id.strip().lower() if self.parent_run_id else None
        object.__setattr__(self, "parent_run_id", parent_run_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt": self.attempt,
            "backend_id": self.backend_id,
            "inputs": [item.to_dict() for item in self.inputs],
            "output_dir": self.output_dir,
            "overwrite_policy": self.overwrite_policy.value,
            "parameters": _json_ready(self.parameters),
            "parent_run_id": self.parent_run_id,
            "run_id": self.run_id,
            "task_id": self.task_id,
        }

    @classmethod
    def from_dict(cls, value: object) -> TaskRunRequest:
        if not isinstance(value, Mapping):
            raise TypeError("TaskRunRequest must be a mapping.")
        inputs = value.get("inputs", ())
        if not isinstance(inputs, list):
            raise TypeError("Task inputs must be a list.")
        attempt = value.get("attempt", 1)
        if isinstance(attempt, bool) or not isinstance(attempt, int):
            raise TypeError("Task attempt must be an integer.")
        parent = value.get("parent_run_id")
        if parent is not None and not isinstance(parent, str):
            raise TypeError("parent_run_id must be a string or null.")
        return cls(
            run_id=str(value.get("run_id", "")),
            task_id=str(value.get("task_id", "")),
            backend_id=str(value.get("backend_id", "")),
            inputs=tuple(AssetRef.from_dict(_mapping(item, "input")) for item in inputs),
            output_dir=str(value.get("output_dir", "")),
            parameters=_json_mapping(value.get("parameters", {}), "parameters"),
            overwrite_policy=TaskOverwritePolicy(str(value.get("overwrite_policy", "new_directory"))),
            attempt=attempt,
            parent_run_id=parent,
        )


@dataclass(frozen=True)
class TaskBackendResult:
    outputs: tuple[AssetRef, ...] = ()
    exit_code: int = 0
    message: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
            raise TypeError("exit_code must be an integer.")
        object.__setattr__(self, "outputs", tuple(self.outputs))
        object.__setattr__(self, "message", self.message.strip())


@dataclass(frozen=True)
class TaskLogEvent:
    timestamp: datetime
    level: str
    message: str
    fields: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _time(self.timestamp, "timestamp"))
        object.__setattr__(self, "level", _required(self.level, "level").lower())
        object.__setattr__(self, "message", self.message.rstrip())
        object.__setattr__(self, "fields", _frozen_mapping(self.fields, "fields"))

    def to_dict(self) -> dict[str, object]:
        return {
            "fields": _json_ready(self.fields),
            "level": self.level,
            "message": self.message,
            "timestamp": _time_text(self.timestamp),
        }


@dataclass(frozen=True)
class TaskRunRecord:
    request: TaskRunRequest
    runtime_profile_id: str
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    outputs: tuple[AssetRef, ...] = ()
    log_path: str = ""
    exit_code: int | None = None
    message: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_profile_id", _required(self.runtime_profile_id, "runtime_profile_id"))
        object.__setattr__(self, "created_at", _time(self.created_at, "created_at"))
        object.__setattr__(self, "started_at", _time(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", _time(self.finished_at, "finished_at"))
        object.__setattr__(self, "outputs", tuple(self.outputs))
        if self.status is TaskStatus.PENDING and self.started_at is not None:
            raise ValueError("A pending task cannot have started_at.")
        if self.status.terminal and self.finished_at is None:
            raise ValueError("A terminal task requires finished_at.")

    def to_dict(self) -> dict[str, object]:
        return {
            "created_at": _time_text(self.created_at),
            "exit_code": self.exit_code,
            "finished_at": _time_text(self.finished_at),
            "log_path": self.log_path,
            "message": self.message,
            "outputs": [item.to_dict() for item in self.outputs],
            "request": self.request.to_dict(),
            "runtime_profile_id": self.runtime_profile_id,
            "schema_version": 1,
            "started_at": _time_text(self.started_at),
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, value: object) -> TaskRunRecord:
        if not isinstance(value, Mapping):
            raise TypeError("TaskRunRecord must be a mapping.")
        if value.get("schema_version") != 1:
            raise ValueError("Unsupported task record schema_version.")
        outputs = value.get("outputs", ())
        if not isinstance(outputs, list):
            raise TypeError("Task outputs must be a list.")
        exit_code = value.get("exit_code")
        if exit_code is not None and (isinstance(exit_code, bool) or not isinstance(exit_code, int)):
            raise TypeError("exit_code must be an integer or null.")
        created_at = _parse_time(value.get("created_at"), "created_at")
        if created_at is None:
            raise ValueError("created_at is required.")
        return cls(
            request=TaskRunRequest.from_dict(value.get("request")),
            runtime_profile_id=str(value.get("runtime_profile_id", "")),
            status=TaskStatus(str(value.get("status", ""))),
            created_at=created_at,
            started_at=_parse_time(value.get("started_at"), "started_at"),
            finished_at=_parse_time(value.get("finished_at"), "finished_at"),
            outputs=tuple(AssetRef.from_dict(_mapping(item, "output")) for item in outputs),
            log_path=str(value.get("log_path", "")),
            exit_code=exit_code,
            message=str(value.get("message", "")),
        )


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise TypeError(f"{field_name} must be a string-keyed mapping.")
    return cast(Mapping[str, object], value)


__all__ = [
    "RuntimeProfile",
    "TaskBackendResult",
    "TaskLogEvent",
    "TaskOverwritePolicy",
    "TaskRunRecord",
    "TaskRunRequest",
    "TaskStatus",
]
