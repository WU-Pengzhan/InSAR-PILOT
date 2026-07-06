from insar_pilot.domain.project import EnvironmentConfig
from insar_pilot.services.shell import ShellCommandBuilder, resolve_isce_runtime_root


def test_activation_snippet_contains_expected_exports(tmp_path):
    isce_root = tmp_path / "isce2"
    (isce_root / "contrib" / "stack" / "topsStack").mkdir(parents=True)
    (isce_root / "applications").mkdir(parents=True)
    (isce_root / "components").mkdir(parents=True)

    builder = ShellCommandBuilder(
        EnvironmentConfig(
            shell_init_path="~/.bashrc",
            conda_env_name="insar",
            isce_root=str(isce_root),
        )
    )

    snippet = builder.activation_snippet()

    assert ". " in snippet
    assert "conda activate insar" in snippet
    assert f"export ISCE_ROOT={isce_root}" in snippet
    assert f"{isce_root}/applications" in snippet
    assert f"{isce_root}/components" in snippet


def test_activation_snippet_does_not_auto_detect_isce_when_root_empty():
    builder = ShellCommandBuilder(
        EnvironmentConfig(
            shell_init_path="~/.bashrc",
            conda_env_name="insar",
            isce_root="",
        )
    )
    snippet = builder.activation_snippet()
    assert "conda activate insar" in snippet
    assert "CONDA_PREFIX" not in snippet
    assert "stackSentinel.py" not in snippet


def test_activation_snippet_falls_back_to_isce_src_when_configured_root_is_conda_prefix(tmp_path, monkeypatch):
    conda_prefix = tmp_path / "conda" / "envs" / "insar"
    conda_prefix.mkdir(parents=True)
    isce_src = tmp_path / "isce2"
    (isce_src / "contrib" / "stack" / "topsStack").mkdir(parents=True)
    (isce_src / "applications").mkdir(parents=True)
    (isce_src / "components").mkdir(parents=True)
    monkeypatch.setenv("ISCE_SRC", str(isce_src))

    builder = ShellCommandBuilder(
        EnvironmentConfig(shell_init_path="", conda_env_name="insar", isce_root=str(conda_prefix))
    )
    snippet = builder.activation_snippet()

    assert resolve_isce_runtime_root(str(conda_prefix)) == isce_src
    assert f"export ISCE_ROOT={isce_src}" in snippet
    assert f"{isce_src}/components" in snippet
    assert f"{isce_src}/contrib/stack/topsStack" in snippet


def test_wrap_preserves_command():
    builder = ShellCommandBuilder(EnvironmentConfig())
    argv = builder.wrap("stackSentinel.py -h", cwd=None)
    assert argv[0] == "bash"
    assert argv[1] == "-lc"
    assert "stackSentinel.py -h" in argv[2]


def test_wrap_without_activation_skips_conda(tmp_path):
    argv = ShellCommandBuilder.wrap_without_activation(
        "python -m insar_pilot --help",
        cwd=tmp_path,
    )

    assert argv[0] == "bash"
    assert "conda activate" not in argv[2]
    assert "python -m insar_pilot --help" in argv[2]
