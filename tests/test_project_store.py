from pathlib import Path

from isce2_gui.domain.project import (
    ProjectDocument,
    ProjectState,
    ProjectStatus,
    RunStep,
    RunSubcommand,
    StepStatus,
    VisualizationConfig,
    WorkflowConfig,
)
from isce2_gui.services.project_store import ProjectStore


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
            prepared_dem_path=str(tmp_path / "work" / ".iscegui" / "dem_import" / "dem.dem.wgs84"),
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
