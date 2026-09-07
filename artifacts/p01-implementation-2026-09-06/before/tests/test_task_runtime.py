from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from insar_pilot.domain.local_data import AssetRef
from insar_pilot.domain.task_runtime import (
    RuntimeProfile,
    TaskBackendResult,
    TaskOverwritePolicy,
    TaskRunRecord,
    TaskRunRequest,
    TaskStatus,
)
from insar_pilot.providers.task_runtime import TaskBackendRegistry, TaskExecutionContext
from insar_pilot.services.task_runtime import (
    TaskExecutionApplicationService,
    TaskRunStore,
    TaskRunStoreError,
)
from insar_pilot.services.workflow_eligibility import build_default_workflow_recipe_registry


class _FakeBackend:
    backend_id = "isce2.topsstack"

    def __init__(self, *, exit_code: int = 0, fail: bool = False) -> None:
        self.exit_code = exit_code
        self.fail = fail
        self.calls = 0

    def supports(self, task_id: str) -> bool:
        return task_id == "sentinel1.validate_pair"

    def run(
        self,
        request: TaskRunRequest,
        profile: RuntimeProfile,
        context: TaskExecutionContext,
    ) -> TaskBackendResult:
        self.calls += 1
        context.raise_if_cancelled()
        context.log("info", "fake task started", attempt=request.attempt)
        if self.fail:
            raise RuntimeError("fake backend failed")
        return TaskBackendResult(
            outputs=(AssetRef(f"{request.output_dir}/validation.json", "validation_report"),),
            exit_code=self.exit_code,
            message="done" if self.exit_code == 0 else "non-zero",
        )


class _Cancelled:
    def is_cancelled(self) -> bool:
        return True


def _descriptor():
    recipe = next(
        item
        for item in build_default_workflow_recipe_registry().descriptors()
        if item.recipe_id == "sentinel1.tops.isce2"
    )
    return next(task for task in recipe.tasks if task.task_id == "sentinel1.validate_pair")


def _request(tmp_path: Path, run_id: str = "run-001", **overrides) -> TaskRunRequest:
    values = {
        "run_id": run_id,
        "task_id": "sentinel1.validate_pair",
        "backend_id": "isce2.topsstack",
        "inputs": (
            AssetRef("/readonly/S1A.zip", "source_product"),
            AssetRef("/readonly/S1B.zip", "source_product"),
        ),
        "output_dir": str(tmp_path / run_id),
        "parameters": {"swaths": "1 2 3", "polarization": "VV"},
    }
    values.update(overrides)
    return TaskRunRequest(**values)


def _service(tmp_path: Path, backend: _FakeBackend) -> tuple[TaskExecutionApplicationService, TaskRunStore]:
    registry = TaskBackendRegistry()
    registry.register(backend)
    store = TaskRunStore(tmp_path)
    return TaskExecutionApplicationService(registry, store), store


def test_one_step_success_persists_record_and_structured_log(tmp_path: Path) -> None:
    backend = _FakeBackend()
    service, store = _service(tmp_path, backend)
    observed = []

    record = service.execute(
        _descriptor(),
        _request(tmp_path),
        RuntimeProfile("local-isce2", "isce2.topsstack", {}),
        TaskExecutionContext(log_sink=observed.append),
    )

    assert record.status is TaskStatus.SUCCEEDED
    assert record.exit_code == 0 and backend.calls == 1
    assert record.outputs[0].role == "validation_report"
    assert store.load("run-001") == record
    log_lines = store.log_path("run-001").read_text(encoding="utf-8").splitlines()
    assert json.loads(log_lines[0])["message"] == "fake task started"
    assert observed[0].fields["attempt"] == 1


def test_output_conflict_is_recorded_without_calling_backend(tmp_path: Path) -> None:
    backend = _FakeBackend()
    service, store = _service(tmp_path, backend)
    output = tmp_path / "existing"
    output.mkdir()
    request = _request(
        tmp_path,
        output_dir=str(output),
        overwrite_policy=TaskOverwritePolicy.ERROR_IF_EXISTS,
    )

    record = service.execute(_descriptor(), request, RuntimeProfile("local", backend.backend_id, {}))

    assert record.status is TaskStatus.FAILED
    assert "already exists" in record.message
    assert backend.calls == 0
    assert store.load(record.request.run_id) == record


@pytest.mark.parametrize(
    ("backend", "context", "status"),
    [
        (_FakeBackend(exit_code=7), None, TaskStatus.FAILED),
        (_FakeBackend(fail=True), None, TaskStatus.FAILED),
        (_FakeBackend(), TaskExecutionContext(cancellation=_Cancelled()), TaskStatus.CANCELLED),
    ],
)
def test_failure_nonzero_and_cancellation_are_terminal_and_recoverable(
    tmp_path: Path,
    backend: _FakeBackend,
    context: TaskExecutionContext | None,
    status: TaskStatus,
) -> None:
    service, store = _service(tmp_path, backend)
    record = service.execute(
        _descriptor(),
        _request(tmp_path),
        RuntimeProfile("local", backend.backend_id, {}),
        context,
    )
    assert record.status is status and record.finished_at is not None
    assert store.load(record.request.run_id) == record


def test_retry_updates_parameters_output_and_lineage(tmp_path: Path) -> None:
    backend = _FakeBackend(exit_code=3)
    service, store = _service(tmp_path, backend)
    original = service.execute(
        _descriptor(),
        _request(tmp_path),
        RuntimeProfile("local", backend.backend_id, {}),
    )
    backend.exit_code = 0

    retried = service.retry(
        original.request.run_id,
        "run-002",
        _descriptor(),
        RuntimeProfile("local", backend.backend_id, {}),
        parameter_updates={"swaths": "2"},
        output_dir=str(tmp_path / "new-output"),
    )

    assert retried.status is TaskStatus.SUCCEEDED
    assert retried.request.attempt == 2
    assert retried.request.parent_run_id == "run-001"
    assert retried.request.parameters["swaths"] == "2"
    assert store.load("run-002") == retried


def test_registry_contract_and_defensive_store_load(tmp_path: Path) -> None:
    registry = TaskBackendRegistry()
    backend = _FakeBackend()
    registry.register(backend)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(backend)
    with pytest.raises(LookupError, match="unavailable"):
        registry.require("isce3.nisar_rifg")

    store = TaskRunStore(tmp_path)
    path = store.record_path("bad-record")
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(TaskRunStoreError, match="malformed"):
        store.load("bad-record")


def test_store_recovers_interrupted_record_and_runtime_values_are_immutable(tmp_path: Path) -> None:
    store = TaskRunStore(tmp_path)
    request = _request(tmp_path)
    pending = TaskRunRecord(
        request=request,
        runtime_profile_id="local",
        status=TaskStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    store.save(pending)

    recovered = store.recover_interrupted()

    assert len(recovered) == 1
    assert recovered[0].status is TaskStatus.FAILED
    assert "interrupted" in recovered[0].message
    with pytest.raises(TypeError):
        request.parameters["swaths"] = "3"  # type: ignore[index]


def test_task_contract_rejects_wrong_backend_missing_roles_and_unsafe_run_id(tmp_path: Path) -> None:
    service, _ = _service(tmp_path, _FakeBackend())
    profile = RuntimeProfile("local", "isce2.topsstack", {})
    with pytest.raises(ValueError, match="does not match"):
        service.execute(
            _descriptor(),
            _request(tmp_path, backend_id="isce3.nisar_rifg"),
            profile,
        )
    with pytest.raises(ValueError, match="missing roles"):
        service.execute(
            _descriptor(),
            _request(tmp_path, inputs=(AssetRef("/readonly/dem", "dem"),)),
            profile,
        )
    with pytest.raises(ValueError, match="safe for persistence"):
        service.execute(_descriptor(), _request(tmp_path, run_id="../escape"), profile)
