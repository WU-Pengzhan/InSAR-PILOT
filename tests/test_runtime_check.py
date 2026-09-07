"""Runtime observations must come from the selected executable, not CPU presence."""

import json
import subprocess
import sys
from unittest.mock import patch

from fastapi.testclient import TestClient

from insar_pilot.application.runtime_check import check_runtime
from insar_pilot.web.api import create_app


def test_missing_python_and_actual_missing_processor(tmp_path):
    missing = check_runtime("isce2", str(tmp_path / "missing"))
    assert missing["status"] == "UNAVAILABLE" and missing["reason"] == "python_unavailable"
    actual = check_runtime("isce3", sys.executable)
    assert actual["status"] == "UNAVAILABLE"
    assert any(c["name"] == "ISCE3" and not c["ok"] for c in actual["checks"])


def test_probe_uses_job_environment_and_requires_every_check():
    rows = [{"name": "ISCE2", "ok": True, "detail": "2.6.5"}, {"name": "PROJ", "ok": False, "detail": "unavailable"}]
    completed = subprocess.CompletedProcess([], 0, "native import notice\nPILOT_RUNTIME_CHECK=" + json.dumps(rows))
    with patch("insar_pilot.application.runtime_check.subprocess.run", return_value=completed) as run:
        report = check_runtime("isce2", sys.executable)
        assert report["status"] == "UNAVAILABLE"
        assert run.call_args.args[0][0] == sys.executable
        assert run.call_args.kwargs["timeout"] == 25
        assert "PYTHONHOME" not in run.call_args.kwargs["env"]
        rows[1]["ok"] = True
        completed.stdout = "PILOT_RUNTIME_CHECK=" + json.dumps(rows)
        assert check_runtime("isce2", sys.executable)["status"] == "READY"


def test_failed_timeout_and_invalid_output_never_report_ready():
    for result in (
        subprocess.CompletedProcess([], 1, "secret", "secret"),
        subprocess.CompletedProcess([], 0, "invalid"),
    ):
        with patch("insar_pilot.application.runtime_check.subprocess.run", return_value=result):
            report = check_runtime("isce2", sys.executable)
            assert report["status"] != "READY" and "secret" not in json.dumps(report)
    with patch("insar_pilot.application.runtime_check.subprocess.run", side_effect=subprocess.TimeoutExpired([], 25)):
        report = check_runtime("isce3", sys.executable)
        assert report["status"] == "UNKNOWN" and report["reason"] == "probe_timeout"


def test_authenticated_api_reports_missing_runtime_and_unchecked_compute(tmp_path):
    with TestClient(create_app(tmp_path / "app", "test", testing=True)) as client:
        assert client.post("/api/v1/compute/check", json={"processor": "isce2"}).status_code == 401
        client.headers["Authorization"] = "Bearer test"
        assert client.post("/api/v1/compute/check", json={"processor": "invalid"}).status_code == 422
        report = client.post(
            "/api/v1/compute/check", json={"processor": "isce2", "python_executable": str(tmp_path / "missing")}
        ).json()
        assert report["status"] == "UNAVAILABLE"
        assert client.get("/api/v1/compute").json()["available_modes"]["nisar"] == []
