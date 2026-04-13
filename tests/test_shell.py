from isce2_gui.domain.project import EnvironmentConfig
from isce2_gui.services.shell import ShellCommandBuilder


def test_activation_snippet_contains_expected_exports():
    builder = ShellCommandBuilder(
        EnvironmentConfig(
            shell_init_path="~/.bashrc",
            conda_env_name="isce-master",
            isce_root="/opt/isce2",
        )
    )

    snippet = builder.activation_snippet()

    assert ". " in snippet
    assert "conda activate isce-master" in snippet
    assert "export ISCE_ROOT=/opt/isce2" in snippet
    assert "/opt/isce2/applications" in snippet
    assert "/opt/isce2/components" in snippet


def test_wrap_preserves_command():
    builder = ShellCommandBuilder(EnvironmentConfig())
    argv = builder.wrap("stackSentinel.py -h", cwd=None)
    assert argv[0] == "bash"
    assert argv[1] == "-lc"
    assert "stackSentinel.py -h" in argv[2]
