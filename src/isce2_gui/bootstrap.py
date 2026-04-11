"""Bootstrap helpers for the desktop application."""

from isce2_gui.domain.project import EnvironmentConfig, ProjectDocument, ProjectState, WorkflowConfig


def create_default_project() -> ProjectDocument:
    """Return a new empty project with sensible WSL defaults."""

    return ProjectDocument(
        environment=EnvironmentConfig(),
        workflow=WorkflowConfig(),
        state=ProjectState(),
    )

