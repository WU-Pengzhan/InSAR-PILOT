"""Helpers for running all workflow commands inside the target WSL shell environment."""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from insar_pilot.domain.project import EnvironmentConfig


def _source_stack_dir(root: Path) -> Path:
    return root / "contrib" / "stack" / "topsStack"


def _conda_stack_dir(root: Path) -> Path:
    return root / "share" / "isce2" / "topsStack"


def is_source_isce_layout(root: Path) -> bool:
    return _source_stack_dir(root).exists() and (root / "applications").exists() and (root / "components").exists()


def is_conda_isce_layout(root: Path) -> bool:
    return _conda_stack_dir(root).exists()


def resolve_isce_runtime_root(configured_root: str = "") -> Path | None:
    """Return the best runtime root for source-tree or conda-style ISCE layouts."""

    candidates: list[Path] = []
    if configured_root.strip():
        candidates.append(Path(configured_root).expanduser())
    for name in ("ISCE_SRC", "ISCE_ROOT", "ISCE_HOME", "CONDA_PREFIX"):
        value = os.environ.get(name, "").strip()
        if value:
            candidates.append(Path(value).expanduser())

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve() if candidate.exists() else candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        if is_source_isce_layout(candidate) or is_conda_isce_layout(candidate):
            return candidate
    return None


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
        isce_root = resolve_isce_runtime_root(self.environment.isce_root)
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
            source_stack_dir = _source_stack_dir(isce_root)
            source_apps_dir = isce_root / "applications"
            source_components_dir = isce_root / "components"
            source_stack_parent = isce_root / "contrib" / "stack"
            conda_stack_dir = _conda_stack_dir(isce_root)
            conda_bin_dir = isce_root / "bin"

            # Source-tree ISCE2 layout.
            if is_source_isce_layout(isce_root):
                python_paths = [isce_root, source_components_dir, source_stack_parent]
                isce_home = Path(os.environ.get("ISCE_HOME", "")).expanduser()
                if str(isce_home) != "." and (isce_home / "packages").exists():
                    python_paths.insert(0, isce_home / "packages")
                python_prefix = ":".join(str(path) for path in python_paths)
                commands.extend(
                    [
                        f"export ISCE_ROOT={self.quote(str(isce_root))}",
                        f"export PATH={self.quote(f'{source_apps_dir}:{source_stack_dir}')}:$PATH",
                        f"export PYTHONPATH={self.quote(python_prefix)}:${{PYTHONPATH:-}}",
                    ]
                )
            # Conda-style layout (optional explicit root): rely mainly on conda env scripts.
            elif is_conda_isce_layout(isce_root):
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
