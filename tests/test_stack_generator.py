from pathlib import Path

from isce2_gui.domain.project import PreparedInputs, ProjectDocument, WorkflowConfig
from isce2_gui.services.stack_generator import StackWorkflowService


def test_build_generate_command_uses_managed_empty_aux_dir(tmp_path: Path):
    project = ProjectDocument(
        workflow=WorkflowConfig(
            input_path=str(tmp_path / "inputs"),
            orbit_path=str(tmp_path / "orbits"),
            dem_path=str(tmp_path / "dem.dem"),
            work_dir=str(tmp_path / "work"),
            bbox_snwe="10 11 20 21",
        )
    )
    prepared = PreparedInputs(manifest_path=str(tmp_path / "work" / ".iscegui" / "inputs" / "safe_inputs.txt"))

    command = StackWorkflowService().build_generate_command(project, prepared)

    assert "stackSentinel.py" in command
    assert "-s" in command
    assert "-a" in command
    assert ".iscegui/aux_empty" in command
    assert "-b" in command
    assert "-z" in command
    assert "-r" in command


def test_build_generate_command_supports_custom_looks(tmp_path: Path):
    project = ProjectDocument(
        workflow=WorkflowConfig(
            input_path=str(tmp_path / "inputs"),
            orbit_path=str(tmp_path / "orbits"),
            dem_path=str(tmp_path / "dem.dem"),
            work_dir=str(tmp_path / "work"),
            azimuth_looks=5,
            range_looks=7,
        )
    )
    prepared = PreparedInputs(manifest_path=str(tmp_path / "work" / ".iscegui" / "inputs" / "safe_inputs.txt"))

    command = StackWorkflowService().build_generate_command(project, prepared)

    assert "-z 5" in command
    assert "-r 7" in command
    assert "--num_proc 1" in command
