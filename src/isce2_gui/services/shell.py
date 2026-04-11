"""Helpers for running all workflow commands inside the target WSL shell environment."""

from __future__ import annotations

import shlex
from pathlib import Path

from isce2_gui.domain.project import EnvironmentConfig


class ShellCommandBuilder:
    """Build bash commands with conda activation and explicit ISCE2 exports."""

    def __init__(self, environment: EnvironmentConfig) -> None:
        self.environment = environment

    @staticmethod
    def quote(value: str) -> str:
        return shlex.quote(value)

    def activation_snippet(self) -> str:
        shell_init = self.environment.shell_init_path.strip()
        conda_env = self.environment.conda_env_name.strip()
        isce_root = Path(self.environment.isce_root).expanduser()
        stack_dir = isce_root / "contrib" / "stack" / "topsStack"
        apps_dir = isce_root / "applications"
        conda_loader = (
            'for candidate in "$HOME/miniconda3/etc/profile.d/conda.sh" '
            '"$HOME/mambaforge/etc/profile.d/conda.sh" '
            '"$HOME/anaconda3/etc/profile.d/conda.sh"; do '
            'if [ -f "$candidate" ]; then . "$candidate"; break; fi; '
            "done"
        )
        python_prefix = ":".join(
            str(path)
            for path in (
                isce_root,
                isce_root / "components",
                isce_root / "contrib" / "stack",
            )
        )

        commands: list[str] = []
        if shell_init:
            commands.append(f". {self.quote(str(Path(shell_init).expanduser()))}")
        if conda_env:
            commands.append(conda_loader)
            commands.append(f"conda activate {self.quote(conda_env)}")

        commands.extend(
            [
                f"export ISCE_ROOT={self.quote(str(isce_root))}",
                f"export PATH={self.quote(f'{apps_dir}:{stack_dir}')}:$PATH",
                f"export PYTHONPATH={self.quote(python_prefix)}:${{PYTHONPATH:-}}",
            ]
        )
        return " && ".join(commands)

    def wrap(self, command: str, cwd: Path | None = None) -> list[str]:
        parts = [self.activation_snippet()]
        if cwd is not None:
            parts.append(f"cd {self.quote(str(cwd))}")
        parts.append(command)
        return ["bash", "-lc", " && ".join(part for part in parts if part)]
