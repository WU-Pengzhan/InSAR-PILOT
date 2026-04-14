"""Persistent project/session models."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any

APP_METADATA_DIR = ".iscegui"
PROJECT_FILE_NAME = "project.json"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    GENERATED = "generated"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class EnvironmentConfig:
    shell_init_path: str = "~/.bashrc"
    conda_env_name: str = "isce-master"
    isce_root: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EnvironmentConfig":
        return cls(**(data or {}))


@dataclass
class WorkflowConfig:
    input_path: str = ""
    orbit_path: str = ""
    dem_path: str = ""
    dem_height_reference: str = ""
    aux_path: str = ""
    work_dir: str = ""
    bbox_snwe: str = ""
    aoi_source_path: str = ""
    use_common_overlap: bool = False
    extract_zips: bool = False
    extract_dir: str = ""
    workflow: str = "interferogram"
    coregistration: str = "NESD"
    num_connections: int = 1
    swath_numbers: str = "1 2 3"
    polarization: str = "vv"
    reference_date: str = ""
    num_proc: int = 1
    azimuth_looks: int = 1
    range_looks: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WorkflowConfig":
        payload = dict(data or {})
        if "num_connections" in payload:
            payload["num_connections"] = int(payload["num_connections"])
        if "num_proc" in payload:
            payload["num_proc"] = int(payload["num_proc"])
        if "azimuth_looks" in payload:
            payload["azimuth_looks"] = int(payload["azimuth_looks"])
        if "range_looks" in payload:
            payload["range_looks"] = int(payload["range_looks"])
        if "use_common_overlap" in payload:
            raw = payload["use_common_overlap"]
            if isinstance(raw, str):
                payload["use_common_overlap"] = raw.strip().lower() in {"1", "true", "yes", "on"}
            else:
                payload["use_common_overlap"] = bool(raw)
        return cls(**payload)

    def resolved_work_dir(self) -> Path:
        if self.work_dir.strip():
            return Path(self.work_dir).expanduser()
        if self.input_path.strip():
            return Path(self.input_path).expanduser() / "isce_gui_work"
        raise ValueError("A working directory cannot be resolved before input_path is set.")

    def resolved_extract_dir(self) -> Path:
        if self.extract_dir.strip():
            return Path(self.extract_dir).expanduser()
        return self.resolved_work_dir() / APP_METADATA_DIR / "extracted_safe"

    @staticmethod
    def _parse_bbox(text: str) -> tuple[float, float, float, float] | None:
        text = text.strip().replace(",", " ")
        if not text:
            return None

        parts = text.split()
        if len(parts) != 4:
            raise ValueError("SNWE bbox must contain exactly four numbers: south north west east.")

        try:
            south, north, west, east = [float(part) for part in parts]
        except ValueError as exc:
            raise ValueError(
                "SNWE bbox must contain numeric values: south north west east."
            ) from exc

        if not (-90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
            raise ValueError("SNWE bbox latitude must be within [-90, 90].")
        if not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0):
            raise ValueError("SNWE bbox longitude must be within [-180, 180].")
        if south >= north or west >= east:
            raise ValueError("SNWE bbox must satisfy south < north and west < east.")
        return south, north, west, east

    def normalized_bbox(self) -> str:
        parsed = self._parse_bbox(self.bbox_snwe)
        if parsed is None:
            return ""
        south, north, west, east = parsed
        return " ".join(f"{value:g}" for value in (south, north, west, east))

    def bbox_components(self) -> tuple[str, str, str, str]:
        parsed = self._parse_bbox(self.bbox_snwe)
        if parsed is None:
            return "", "", "", ""
        return tuple(f"{value:g}" for value in parsed)


@dataclass
class VisualizationConfig:
    mode: str = "slc"
    primary_input_path: str = ""
    secondary_input_path: str = ""
    range_looks: int = 1
    azimuth_looks: int = 1
    overlay_brightness: float = 0.5
    export_dir: str = ""
    last_preview_path: str = ""
    last_log_path: str = ""
    last_render_summary: str = ""
    last_render_signature: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "VisualizationConfig":
        payload = dict(data or {})
        if "range_looks" in payload:
            payload["range_looks"] = int(payload["range_looks"])
        if "azimuth_looks" in payload:
            payload["azimuth_looks"] = int(payload["azimuth_looks"])
        if "overlay_brightness" in payload:
            payload["overlay_brightness"] = float(payload["overlay_brightness"])
        if not payload.get("last_render_signature") and payload.get("last_preview_input_snapshot"):
            payload["last_render_signature"] = payload["last_preview_input_snapshot"]
        allowed = {item.name for item in fields(cls)}
        payload = {key: value for key, value in payload.items() if key in allowed}
        return cls(**payload)


@dataclass
class InputEntry:
    path: str
    kind: str
    ipf_version: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InputEntry":
        return cls(**data)


@dataclass
class PreparedInputs:
    manifest_path: str = ""
    extract_dir: str = ""
    aux_required: bool = False
    entries: list[InputEntry] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PreparedInputs":
        payload = data or {}
        entries = [InputEntry.from_dict(item) for item in payload.get("entries", [])]
        return cls(
            manifest_path=payload.get("manifest_path", ""),
            extract_dir=payload.get("extract_dir", ""),
            aux_required=bool(payload.get("aux_required", False)),
            entries=entries,
            notes=list(payload.get("notes", [])),
        )


@dataclass
class RunStep:
    name: str
    path: str
    status: StepStatus = StepStatus.PENDING
    log_path: str = ""
    exit_code: int | None = None
    last_message: str = ""
    subcommands: list["RunSubcommand"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunStep":
        payload = dict(data)
        payload["status"] = StepStatus(payload.get("status", StepStatus.PENDING.value))
        payload["subcommands"] = [
            RunSubcommand.from_dict(item) for item in payload.get("subcommands", [])
        ]
        return cls(**payload)


@dataclass
class RunSubcommand:
    index: int
    command: str
    status: StepStatus = StepStatus.PENDING
    log_path: str = ""
    exit_code: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunSubcommand":
        payload = dict(data)
        payload["index"] = int(payload.get("index", 0))
        payload["status"] = StepStatus(payload.get("status", StepStatus.PENDING.value))
        return cls(**payload)


@dataclass
class ProjectState:
    status: ProjectStatus = ProjectStatus.DRAFT
    current_step: str = ""
    steps: list[RunStep] = field(default_factory=list)
    prepared_inputs: PreparedInputs = field(default_factory=PreparedInputs)
    prepared_dem_path: str = ""
    prepared_signature: str = ""
    last_validation: str = ""
    last_generated_command: str = ""
    last_error: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProjectState":
        payload = data or {}
        return cls(
            status=ProjectStatus(payload.get("status", ProjectStatus.DRAFT.value)),
            current_step=payload.get("current_step", ""),
            steps=[RunStep.from_dict(item) for item in payload.get("steps", [])],
            prepared_inputs=PreparedInputs.from_dict(payload.get("prepared_inputs", {})),
            prepared_dem_path=payload.get("prepared_dem_path", ""),
            prepared_signature=payload.get("prepared_signature", ""),
            last_validation=payload.get("last_validation", ""),
            last_generated_command=payload.get("last_generated_command", ""),
            last_error=payload.get("last_error", ""),
        )


@dataclass
class ProjectDocument:
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)
    state: ProjectState = field(default_factory=ProjectState)
    schema_version: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectDocument":
        return cls(
            environment=EnvironmentConfig.from_dict(data.get("environment")),
            workflow=WorkflowConfig.from_dict(data.get("workflow")),
            visualization=VisualizationConfig.from_dict(data.get("visualization")),
            state=ProjectState.from_dict(data.get("state")),
            schema_version=int(data.get("schema_version", 1)),
        )

    def resolved_work_dir(self) -> Path:
        return self.workflow.resolved_work_dir()

    def metadata_dir(self) -> Path:
        return self.resolved_work_dir() / APP_METADATA_DIR

    def logs_dir(self) -> Path:
        return self.metadata_dir() / "logs"

    def project_file(self) -> Path:
        return self.metadata_dir() / PROJECT_FILE_NAME

    def synchronize_steps(self, run_files: list[Path]) -> None:
        existing = {step.name: step for step in self.state.steps}
        updated: list[RunStep] = []
        for run_file in sorted(run_files, key=lambda item: item.name):
            previous = existing.get(run_file.name)
            updated.append(
                RunStep(
                    name=run_file.name,
                    path=str(run_file),
                    status=previous.status if previous else StepStatus.PENDING,
                    log_path=previous.log_path if previous else str(self.logs_dir() / f"{run_file.name}.log"),
                    exit_code=previous.exit_code if previous else None,
                    last_message=previous.last_message if previous else "",
                    subcommands=list(previous.subcommands) if previous else [],
                )
            )
        self.state.steps = updated
