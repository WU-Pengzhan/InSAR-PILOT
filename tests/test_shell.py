from isce2_gui.domain.project import EnvironmentConfig
from isce2_gui.services.shell import ShellCommandBuilder


def test_activation_snippet_contains_expected_exports(tmp_path):
    isce_root = tmp_path / "isce2"
    (isce_root / "contrib" / "stack" / "topsStack").mkdir(parents=True)
    (isce_root / "applications").mkdir(parents=True)
    (isce_root / "components").mkdir(parents=True)

    builder = ShellCommandBuilder(
        EnvironmentConfig(
            shell_init_path="~/.bashrc",
            conda_env_name="isce-master",
            isce_root=str(isce_root),
        )
    )

    snippet = builder.activation_snippet()

    assert ". " in snippet
    assert "conda activate isce-master" in snippet
    assert f"export ISCE_ROOT={isce_root}" in snippet
    assert f"{isce_root}/applications" in snippet
    assert f"{isce_root}/components" in snippet


def test_activation_snippet_does_not_auto_detect_isce_when_root_empty():
    builder = ShellCommandBuilder(
        EnvironmentConfig(
            shell_init_path="~/.bashrc",
            conda_env_name="isce-master",
            isce_root="",
        )
    )
    snippet = builder.activation_snippet()
    assert "conda activate isce-master" in snippet
    assert "CONDA_PREFIX" not in snippet
    assert "stackSentinel.py" not in snippet


def test_wrap_preserves_command():
    builder = ShellCommandBuilder(EnvironmentConfig())
    argv = builder.wrap("stackSentinel.py -h", cwd=None)
    assert argv[0] == "bash"
    assert argv[1] == "-lc"
    assert "stackSentinel.py -h" in argv[2]
