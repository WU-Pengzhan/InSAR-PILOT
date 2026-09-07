from __future__ import annotations

import json
from pathlib import Path

from insar_pilot.backends import build_default_task_backend_registry
from insar_pilot.backends.isce3 import NisarIsce3TaskBackend, NisarRifgRunReport
from insar_pilot.domain.local_data import AssetRef
from insar_pilot.domain.task_runtime import RuntimeProfile, TaskRunRequest
from insar_pilot.providers.task_runtime import TaskExecutionContext


class _FakeRunner:
    def __init__(self, *, succeeded: bool = True, exit_code: int = 0) -> None:
        self.succeeded = succeeded
        self.exit_code = exit_code
        self.plan = None

    def run(self, plan, profile, **kwargs):
        self.plan = plan
        return NisarRifgRunReport(
            self.succeeded,
            self.exit_code,
            1.0,
            "/logs/nisar.log",
            plan.output_product,
            message="validated" if self.succeeded else "validation failed",
        )


def _runconfig(tmp_path: Path, *, product_type: str = "GUNW") -> Path:
    value = {
        "runconfig": {
            "groups": {
                "primary_executable": {"product_type": product_type},
                "product_path_group": {
                    "sas_output_file": str(tmp_path / "products" / f"{product_type}.h5"),
                    "scratch_path": str(tmp_path / "scratch"),
                },
                "processing": {"input_subset": {"list_of_frequencies": {"A": ["HH"]}}},
            }
        }
    }
    path = tmp_path / "runconfig.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _request(tmp_path: Path, runconfig: Path) -> TaskRunRequest:
    return TaskRunRequest(
        run_id="nisar-product-001",
        task_id="nisar.run_product",
        backend_id="isce3.nisar_rifg",
        inputs=(AssetRef(str(runconfig), "runconfig"),),
        output_dir=str(tmp_path / "task-output"),
        parameters={"timeout_seconds": 60},
    )


def test_nisar_task_backend_reuses_official_runconfig_and_runner(tmp_path: Path) -> None:
    runner = _FakeRunner()
    backend = NisarIsce3TaskBackend(runner)
    profile = RuntimeProfile(
        "local-nisar",
        "isce3.nisar_rifg",
        {"python_executable": "/opt/insar-nisar/bin/python"},
    )

    result = backend.run(_request(tmp_path, _runconfig(tmp_path)), profile, TaskExecutionContext())

    assert result.exit_code == 0
    assert result.outputs[0].role == "gunw"
    assert runner.plan.command == (
        "/opt/insar-nisar/bin/python",
        "-m",
        "nisar.workflows.insar",
        str(tmp_path / "runconfig.json"),
    )


def test_nisar_validation_failure_becomes_a_failed_task_exit_code(tmp_path: Path) -> None:
    runner = _FakeRunner(succeeded=False, exit_code=0)
    backend = NisarIsce3TaskBackend(runner)
    profile = RuntimeProfile("local-nisar", backend.backend_id, {"python_executable": "/python"})

    result = backend.run(_request(tmp_path, _runconfig(tmp_path)), profile, TaskExecutionContext())

    assert result.exit_code == 3
    assert result.message == "validation failed"


def test_default_task_backend_registry_contains_only_canonical_engine_adapters() -> None:
    registry = build_default_task_backend_registry()

    assert registry.require("isce2.topsstack").supports("sentinel1.run_official_stage")
    assert registry.require("isce3.nisar_rifg").supports("nisar.run_product")
