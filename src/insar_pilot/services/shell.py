"""Helpers for running all workflow commands inside the target WSL shell environment."""

from __future__ import annotations

import shlex
from pathlib import Path

from insar_pilot.domain.project import EnvironmentConfig


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
        isce_root_text = self.environment.isce_root.strip()
        isce_root = Path(isce_root_text).expanduser() if isce_root_text else None
        conda_loader = (
            'for candidate in "$HOME/miniconda3/etc/profile.d/conda.sh" '
            '"$HOME/mambaforge/etc/profile.d/conda.sh" '
            '"$HOME/anaconda3/etc/profile.d/conda.sh"; do '
            'if [ -f "$candidate" ]; then . "$candidate"; break; fi; '
            "done"
        )

        commands: list[str] = []
        if shell_init:
            commands.append(f". {self.quote(str(Path(shell_init).expanduser()))}")
        if conda_env:
            commands.append(conda_loader)
            commands.append(f"conda activate {self.quote(conda_env)}")

        if isce_root is not None:
            source_stack_dir = isce_root / "contrib" / "stack" / "topsStack"
            source_apps_dir = isce_root / "applications"
            source_components_dir = isce_root / "components"
            source_stack_parent = isce_root / "contrib" / "stack"
            conda_stack_dir = isce_root / "share" / "isce2" / "topsStack"
            conda_bin_dir = isce_root / "bin"

            # Source-tree ISCE2 layout.
            if source_stack_dir.exists() and source_apps_dir.exists():
                python_prefix = ":".join(
                    str(path)
                    for path in (
                        isce_root,
                        source_components_dir,
                        source_stack_parent,
                    )
                )
                commands.extend(
                    [
                        f"export ISCE_ROOT={self.quote(str(isce_root))}",
                        f"export PATH={self.quote(f'{source_apps_dir}:{source_stack_dir}')}:$PATH",
                        f"export PYTHONPATH={self.quote(python_prefix)}:${{PYTHONPATH:-}}",
                    ]
                )
            # Conda-style layout (optional explicit root): rely mainly on conda env scripts.
            elif conda_stack_dir.exists():
                commands.extend(
                    [
                        f"export ISCE_ROOT={self.quote(str(isce_root))}",
                        f"export PATH={self.quote(f'{conda_bin_dir}:{conda_stack_dir}')}:$PATH",
                    ]
                )

        return " && ".join(commands)

    def wrap(self, command: str, cwd: Path | None = None) -> list[str]:
        parts = [self.activation_snippet()]
        if cwd is not None:
            parts.append(f"cd {self.quote(str(cwd))}")
        parts.append(command)
        return ["bash", "-lc", " && ".join(part for part in parts if part)]

    @classmethod
    def wrap_without_activation(cls, command: str, cwd: Path | None = None) -> list[str]:
        parts = []
        if cwd is not None:
            parts.append(f"cd {cls.quote(str(cwd))}")
        parts.append(command)
        return ["bash", "-lc", " && ".join(parts)]
