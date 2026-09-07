from pathlib import Path

from insar_pilot.domain.project import APP_METADATA_DIR, InputEntry, PreparedInputs, ProjectDocument, WorkflowConfig
from insar_pilot.services.preflight import PreflightService


def test_preflight_reports_missing_prepared_inputs(tmp_path: Path):
    input_dir = tmp_path / "SLC"
    orbit_dir = tmp_path / "Orbit"
    dem = tmp_path / "dem.dem.wgs84"
    input_dir.mkdir()
    orbit_dir.mkdir()
    dem.write_text("dem", encoding="utf-8")
    project = ProjectDocument(
        workflow=WorkflowConfig(
            input_path=str(input_dir),
            orbit_path=str(orbit_dir),
            dem_path=str(dem),
            work_dir=str(tmp_path / "work"),
        )
    )

    report = PreflightService().run(project)

    assert not report.ok
    assert any(check.key == "prepared_inputs" and check.blocking for check in report.checks)
    assert any(check.key == "prepared_manifest" and check.blocking for check in report.checks)


def test_preflight_reports_runfile_conflicts(tmp_path: Path):
    input_dir = tmp_path / "SLC"
    orbit_dir = tmp_path / "Orbit"
    dem = tmp_path / "dem.dem.wgs84"
    work = tmp_path / "work"
    manifest = work / APP_METADATA_DIR / "inputs" / "safe_inputs.txt"
    input_dir.mkdir()
    orbit_dir.mkdir()
    work.mkdir()
    (work / "run_files").mkdir()
    (work / "configs").mkdir()
    manifest.parent.mkdir(parents=True)
    manifest.write_text("/tmp/S1.SAFE\n", encoding="utf-8")
    dem.write_text("dem", encoding="utf-8")
    project = ProjectDocument(
        workflow=WorkflowConfig(
            input_path=str(input_dir),
            orbit_path=str(orbit_dir),
            dem_path=str(dem),
            work_dir=str(work),
        ),
    )
    project.state.prepared_inputs = PreparedInputs(
        manifest_path=str(manifest),
        entries=[InputEntry(path="/tmp/S1.SAFE", kind="safe")],
    )
    project.state.prepared_dem_path = str(dem)

    report = PreflightService().run(project)

    assert any(check.key == "conflict_run_files" and check.blocking for check in report.checks)
    assert any(check.key == "conflict_configs" and check.blocking for check in report.checks)


def test_aria2_capability_detection_available_and_missing(monkeypatch):
    service = PreflightService()
    monkeypatch.setattr("insar_pilot.services.preflight.shutil.which", lambda name: "/usr/bin/aria2c")
    assert service.check_aria2_capability().aria2c_available

    monkeypatch.setattr("insar_pilot.services.preflight.shutil.which", lambda name: None)
    assert not service.check_aria2_capability().aria2c_available
