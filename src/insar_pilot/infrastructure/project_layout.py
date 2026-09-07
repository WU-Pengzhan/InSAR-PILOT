"""Versioned project locations; existing projects are never moved on open."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectLayout:
    root: Path
    version: int = 1

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version not in (1, 2):
            raise ValueError("Unsupported project storage layout.")

    @property
    def runs(self) -> Path:
        return self.root / (".insar_pilot/records/runs" if self.version == 2 else "runs")

    @property
    def workspaces(self) -> Path:
        return self.root / ("processing" if self.version == 2 else "workspaces")

    @property
    def artifacts(self) -> Path:
        return self.root / ("products" if self.version == 2 else "artifacts")

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def transfers(self) -> Path:
        return self.root / ".insar_pilot/transfers"

    def initialize(self) -> None:
        for path in (self.runs, self.workspaces, self.artifacts, self.root / "cache"):
            path.mkdir(parents=True, exist_ok=True)
        if self.version == 2:
            for role in ("slc", "orbit", "dem", "aux", "aoi"):
                (self.data / role).mkdir(parents=True, exist_ok=True)
            self.transfers.mkdir(parents=True, exist_ok=True)
