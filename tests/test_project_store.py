import json
import os
from pathlib import Path

from insar_pilot.domain.project import (
    APP_METADATA_DIR,
    DataDownloadConfig,
    LEGACY_APP_METADATA_DIR,
    LEGACY_APP_METADATA_DIRS,
    LEGACY_PROJECT_ROOT_FILE_NAMES,
    PROJECT_FILE_NAME,
    PROJECT_ROOT_FILE_NAME,
    ProjectDocument,
    ProjectState,
    ProjectStatus,
    RunStep,
    RunSubcommand,
    StepStatus,
    VisualizationConfig,
    WorkflowConfig,
)
from insar_pilot.services.project_store import ProjectLoadError, ProjectStore
from insar_pilot.bootstrap import create_default_project


def test_default_project_uses_current_conda_environment():
    assert create_default_project().environment.conda_env_name == os.environ.get("CONDA_DEFAULT_ENV", "")


def test_project_store_creates_root_workspace_layout(tmp_path: Path):
    root = tmp_path / "city_stack_project"
    project = ProjectStore().create_workspace(root)

    assert project.workspace.project_root == str(root)
    assert (root / PROJECT_ROOT_FILE_NAME).is_file()
    assert (root / "data" / "SLC").is_dir()
    assert (root / "data" / "Orbit").is_dir()
    assert (root / "data" / "DEM").is_dir()
    assert (root / "processing" / "work").is_dir()
    assert (root / "outputs" / "quicklooks").is_dir()
    assert (root / "logs").is_dir()
    assert (root / APP_METADATA_DIR / "cache").is_dir()
    assert project.workflow.input_path == str(root / "data" / "SLC")
    assert project.workflow.orbit_path == str(root / "data" / "Orbit")
    assert project.workflow.work_dir == str(root / "processing" / "work")
    assert project.download.output_dir == str(root / "data")


def test_project_store_loads_root_project_file_from_folder(tmp_path: Path):
    root = tmp_path / "root_project"
    store = ProjectStore()
    created = store.create_workspace(root)

    loaded = store.load(root)

    assert loaded.workspace.project_root == created.workspace.project_root
    assert loaded.project_file() == root / PROJECT_ROOT_FILE_NAME


def test_project_store_loads_legacy_root_project_file_from_folder(tmp_path: Path):
    root = tmp_path / "legacy_root_project"
    store = ProjectStore()
    project = ProjectDocument(
        workflow=WorkflowConfig(input_path=str(root / "data" / "SLC"), work_dir=str(root / "processing" / "work"))
    )
    legacy_name = LEGACY_PROJECT_ROOT_FILE_NAMES[0]
    legacy_file = root / legacy_name
    root.mkdir(parents=True)
    legacy_file.write_text(json.dumps(store._serialize(project)), encoding="utf-8")

    loaded = store.load(root)

    assert loaded.workflow.input_path.endswith("data/SLC")
    assert ProjectStore.resolve_project_file(root) == legacy_file


def test_project_store_loads_sentinel1_pilot_file_from_recent_project_folder(tmp_path: Path):
    root = tmp_path / "recent_project"
    store = ProjectStore()
    project = ProjectDocument(
        workspace=ProjectDocument().workspace,
        workflow=WorkflowConfig(input_path=str(root / "data" / "SLC"), work_dir=str(root / "processing" / "work")),
    )
    root.mkdir(parents=True)
    legacy_file = root / LEGACY_PROJECT_ROOT_FILE_NAMES[0]
    legacy_file.write_text(json.dumps(store._serialize(project)), encoding="utf-8")

    loaded = store.load(root)

    assert loaded.workflow.input_path.endswith("data/SLC")
    assert ProjectStore.resolve_project_file(root) == legacy_file


def test_project_store_missing_folder_project_reports_new_pilot_file(tmp_path: Path):
    root = tmp_path / "empty_project"
    root.mkdir()

    try:
        ProjectStore().load(root)
    except ProjectLoadError as exc:
        assert str(root / PROJECT_ROOT_FILE_NAME) in str(exc)
        assert ".insar_pilot/project.json" not in str(exc)
    else:
        raise AssertionError("Expected empty project folder to fail with project.pilot path.")


def test_project_round_trip(tmp_path: Path):
    project = ProjectDocument(
        workflow=WorkflowConfig(
            input_path=str(tmp_path / "inputs"),
            work_dir=str(tmp_path / "work"),
            dem_height_reference="egm96",
            azimuth_looks=3,
            range_looks=9,
            aoi_source_path=str(tmp_path / "aoi.kml"),
            use_common_overlap=True,
        ),
        download=DataDownloadConfig(last_status="ready", last_message="module ready"),
        visualization=VisualizationConfig(
            mode="overlay",
            primary_input_path="/tmp/ref.slc",
            secondary_input_path="/tmp/pair.int",
            range_looks=4,
            azimuth_looks=2,
            overlay_brightness=0.6,
            export_dir="/tmp/exports",
            last_preview_path="/tmp/exports/overlay.bmp",
            last_log_path="/tmp/visual.log",
            last_render_summary="ok",
            last_render_signature="sig-123",
        ),
        state=ProjectState(
            status=ProjectStatus.GENERATED,
            current_step="run_01_unpack",
            prepared_dem_path=str(
                tmp_path / "work" / APP_METADATA_DIR / "dem_import" / "dem.dem.wgs84"
            ),
            prepared_signature="sig",
            steps=[
                RunStep(
                    name="run_01_unpack",
                    path="/tmp/run_01_unpack",
                    status=StepStatus.SUCCESS,
                    log_path="/tmp/run_01_unpack.log",
                    exit_code=0,
                    subcommands=[
                        RunSubcommand(
                            index=1,
                            command="echo ok",
                            status=StepStatus.SUCCESS,
                            log_path="/tmp/run_01_unpack.cmd_001.log",
                            exit_code=0,
                        )
                    ],
                )
            ],
        ),
    )

    store = ProjectStore()
    saved_path = store.save(project)
    loaded = store.load(saved_path)

    assert loaded.workflow.work_dir == str(tmp_path / "work")
    assert loaded.workflow.dem_height_reference == "egm96"
    assert loaded.workflow.azimuth_looks == 3
    assert loaded.workflow.range_looks == 9
    assert loaded.workflow.aoi_source_path.endswith("aoi.kml")
    assert loaded.workflow.use_common_overlap is True
    assert loaded.download.last_status == "ready"
    assert loaded.download.last_message == "module ready"
    assert loaded.visualization.mode == "overlay"
    assert loaded.visualization.primary_input_path == "/tmp/ref.slc"
    assert loaded.visualization.secondary_input_path == "/tmp/pair.int"
    assert loaded.visualization.overlay_brightness == 0.6
    assert loaded.visualization.last_preview_path.endswith(".bmp")
    assert loaded.visualization.last_render_signature == "sig-123"
    assert loaded.state.status == ProjectStatus.GENERATED
    assert loaded.state.prepared_signature == "sig"
    assert loaded.state.prepared_dem_path.endswith(".dem.wgs84")
    assert loaded.state.steps[0].status == StepStatus.SUCCESS
    assert loaded.state.steps[0].subcommands
    assert loaded.state.steps[0].subcommands[0].status == StepStatus.SUCCESS


def test_project_store_reads_legacy_metadata_dir(tmp_path: Path):
    work_dir = tmp_path / "work"
    project = ProjectDocument(
        workflow=WorkflowConfig(input_path=str(tmp_path / "inputs"), work_dir=str(work_dir))
    )
    store = ProjectStore()
    legacy_file = work_dir / LEGACY_APP_METADATA_DIR / PROJECT_FILE_NAME
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_text(json.dumps(store._serialize(project)), encoding="utf-8")

    loaded = store.load(work_dir)

    assert loaded.workflow.work_dir == str(work_dir)


def test_project_store_reads_old_sentinel_workbench_metadata_dir(tmp_path: Path):
    work_dir = tmp_path / "work"
    project = ProjectDocument(
        workflow=WorkflowConfig(input_path=str(tmp_path / "inputs"), work_dir=str(work_dir))
    )
    store = ProjectStore()
    legacy_file = work_dir / LEGACY_APP_METADATA_DIRS[0] / PROJECT_FILE_NAME
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_text(json.dumps(store._serialize(project)), encoding="utf-8")

    loaded = store.load(work_dir)

    assert loaded.workflow.work_dir == str(work_dir)


def test_project_store_rejects_invalid_json(tmp_path: Path):
    path = tmp_path / "bad.pilot"
    path.write_text("{not-json", encoding="utf-8")

    try:
        ProjectStore().load(path)
    except ProjectLoadError as exc:
        assert "not valid JSON" in str(exc)
    else:
        raise AssertionError("Expected invalid JSON to be rejected.")


def test_project_store_rejects_non_project_json(tmp_path: Path):
    path = tmp_path / "notes.pilot"
    path.write_text(json.dumps({"hello": "world"}), encoding="utf-8")

    try:
        ProjectStore().load(path)
    except ProjectLoadError as exc:
        assert "does not look like" in str(exc)
    else:
        raise AssertionError("Expected non-project JSON to be rejected.")


def test_project_store_rejects_unsupported_schema(tmp_path: Path):
    path = tmp_path / "future.pilot"
    path.write_text(json.dumps({"schema_version": 999, "workflow": {}}), encoding="utf-8")

    try:
        ProjectStore().load(path)
    except ProjectLoadError as exc:
        assert "Unsupported project schema_version" in str(exc)
    else:
        raise AssertionError("Expected unsupported schema to be rejected.")


def test_project_store_rejects_oversized_project_file(tmp_path: Path, monkeypatch):
    path = tmp_path / "large.pilot"
    path.write_text(json.dumps({"workflow": {}, "padding": "x" * 256}), encoding="utf-8")
    monkeypatch.setattr(ProjectStore, "MAX_PROJECT_FILE_BYTES", 32)

    try:
        ProjectStore().load(path)
    except ProjectLoadError as exc:
        assert "too large" in str(exc)
    else:
        raise AssertionError("Expected oversized project file to be rejected.")


def test_workflow_defaults_for_legacy_project_payload():
    loaded = ProjectDocument.from_dict(
        {
            "environment": {},
            "workflow": {
                "input_path": "/tmp/in",
                "orbit_path": "/tmp/orb",
                "dem_path": "/tmp/dem.dem.wgs84",
            },
            "state": {},
        }
    )

    assert loaded.workflow.azimuth_looks == 1
    assert loaded.workflow.range_looks == 1
    assert loaded.workflow.aoi_source_path == ""
    assert loaded.workflow.use_common_overlap is False
    assert loaded.visualization.mode == "slc"
    assert loaded.visualization.range_looks == 1
    assert loaded.visualization.azimuth_looks == 1
    assert loaded.visualization.last_render_signature == ""
    assert loaded.download.last_status == "ready"


def test_workflow_common_overlap_string_flag_is_accepted():
    loaded = ProjectDocument.from_dict(
        {
            "environment": {},
            "workflow": {
                "use_common_overlap": "true",
            },
            "state": {},
        }
    )
    assert loaded.workflow.use_common_overlap is True


def test_visualization_legacy_signature_field_is_accepted():
    loaded = ProjectDocument.from_dict(
        {
            "environment": {},
            "workflow": {},
            "visualization": {
                "mode": "overlay",
                "last_preview_input_snapshot": "legacy-sig-1",
            },
            "state": {},
        }
    )

    assert loaded.visualization.mode == "overlay"
    assert loaded.visualization.last_render_signature == "legacy-sig-1"


def test_project_save_does_not_write_legacy_visual_signature_field(tmp_path: Path):
    project = ProjectDocument(
        workflow=WorkflowConfig(
            input_path=str(tmp_path / "inputs"),
            work_dir=str(tmp_path / "work"),
        ),
        visualization=VisualizationConfig(last_render_signature="sig-new"),
    )
    store = ProjectStore()
    saved_path = store.save(project)
    content = saved_path.read_text(encoding="utf-8")

    assert "last_render_signature" in content
    assert "last_preview_input_snapshot" not in content


def test_project_save_does_not_write_legacy_download_fields(tmp_path: Path):
    project = ProjectDocument(
        workflow=WorkflowConfig(
            input_path=str(tmp_path / "inputs"),
            work_dir=str(tmp_path / "work"),
        ),
        download=DataDownloadConfig(),
    )

    saved_path = ProjectStore().save(project)
    content = saved_path.read_text(encoding="utf-8")

    assert "password" not in content.lower()
    assert "download_dir" not in content
    assert "download_eof" not in content
    assert "last_manifest_path" not in content
