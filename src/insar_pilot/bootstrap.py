"""Bootstrap helpers for the desktop application."""

from __future__ import annotations

import os

from insar_pilot.domain.project import EnvironmentConfig, ProjectDocument, ProjectState, WorkflowConfig
from insar_pilot.services.shell import resolve_isce_runtime_root


def create_default_project() -> ProjectDocument:
    """Return a new empty project using the environment that launched the GUI."""

    return ProjectDocument(
        environment=EnvironmentConfig(
            shell_init_path="",
            conda_env_name=os.environ.get("CONDA_DEFAULT_ENV", ""),
            isce_root=str(resolve_isce_runtime_root("") or ""),
        ),
        workflow=WorkflowConfig(),
        state=ProjectState(),
    )
