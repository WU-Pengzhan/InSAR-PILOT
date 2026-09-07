"""Task backend protocol, cancellation context, and validated registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from insar_pilot.domain.task_runtime import RuntimeProfile, TaskBackendResult, TaskLogEvent, TaskRunRequest
from insar_pilot.providers.local import CancellationToken, NeverCancelled


class TaskCancelled(RuntimeError):
    """Raised by cooperative task backends at a safe cancellation point."""


@dataclass(frozen=True)
class TaskExecutionContext:
    cancellation: CancellationToken = field(default_factory=NeverCancelled)
    log_sink: Callable[[TaskLogEvent], None] = field(default=lambda event: None)

    def raise_if_cancelled(self) -> None:
        if self.cancellation.is_cancelled():
            raise TaskCancelled("Task execution was cancelled.")

    def log(self, level: str, message: str, **fields: str | int | float | bool | None) -> None:
        self.log_sink(TaskLogEvent(datetime.now(timezone.utc), level, message, fields))


@runtime_checkable
class TaskBackend(Protocol):
    backend_id: str

    def supports(self, task_id: str) -> bool: ...

    def run(
        self,
        request: TaskRunRequest,
        profile: RuntimeProfile,
        context: TaskExecutionContext,
    ) -> TaskBackendResult: ...


class TaskBackendRegistry:
    def __init__(self) -> None:
        self._backends: dict[str, TaskBackend] = {}

    def register(self, backend: TaskBackend) -> None:
        if not isinstance(backend, TaskBackend):
            raise TypeError("Backend must implement the TaskBackend protocol.")
        backend_id = backend.backend_id.strip().lower()
        if not backend_id or backend_id != backend.backend_id:
            raise ValueError("backend_id must be a normalized lowercase identifier.")
        if backend_id in self._backends:
            raise ValueError(f"Task backend is already registered: {backend_id}")
        self._backends[backend_id] = backend

    def require(self, backend_id: str) -> TaskBackend:
        normalized = backend_id.strip().lower()
        backend = self._backends.get(normalized)
        if backend is None:
            raise LookupError(f"Task backend is unavailable: {normalized}")
        return backend


__all__ = [
    "TaskBackend",
    "TaskBackendRegistry",
    "TaskCancelled",
    "TaskExecutionContext",
]
