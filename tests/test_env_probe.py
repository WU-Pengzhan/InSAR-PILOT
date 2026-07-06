import subprocess

from insar_pilot.domain.project import EnvironmentConfig
from insar_pilot.services.env_probe import EnvironmentProbe


def test_environment_probe_uses_detected_isce_src_when_configured_root_is_not_processing_layout(tmp_path, monkeypatch):
    conda_prefix = tmp_path / "conda" / "envs" / "insar"
    conda_prefix.mkdir(parents=True)
    isce_src = tmp_path / "isce2"
    stack_dir = isce_src / "contrib" / "stack" / "topsStack"
    stack_dir.mkdir(parents=True)
    (stack_dir / "stackSentinel.py").write_text("# stack", encoding="utf-8")
    (isce_src / "applications").mkdir(parents=True)
    (isce_src / "components").mkdir(parents=True)
    monkeypatch.setenv("ISCE_SRC", str(isce_src))

    def runner(argv, capture_output=True, text=True):
        command = argv[-1]
        if "Python processing modules" in command or "importlib.util" in command:
            return subprocess.CompletedProcess(argv, 0, "available\n", "")
        if "which" in command:
            return subprocess.CompletedProcess(argv, 0, "/usr/bin/tool\n", "")
        return subprocess.CompletedProcess(argv, 0, "available\n", "")

    report = EnvironmentProbe(runner=runner).probe(
        EnvironmentConfig(shell_init_path="", conda_env_name="insar", isce_root=str(conda_prefix))
    )
    runtime = next(check for check in report.checks if check.name == "Runtime root")

    assert runtime.ok is True
    assert "Configured root" in runtime.detail
    assert str(isce_src / "contrib" / "stack" / "topsStack" / "stackSentinel.py") in runtime.detail
    assert report.ok is True
