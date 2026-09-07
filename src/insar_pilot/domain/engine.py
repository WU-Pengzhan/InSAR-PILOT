"""Qt-free, versioned values for the next-generation project engine."""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def new_id() -> str:
    return uuid.uuid4().hex


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}", value):
        raise ValueError("Invalid resource identifier.")
    return value


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def snapshot(value: Any) -> Any:
    """Detach mutable caller values and reject non-JSON/nonfinite data."""
    return json.loads(canonical(value))


def validate_public_snapshot(value: Any) -> None:
    """Credentials belong to a local credential provider, never persisted intent."""
    from urllib.parse import parse_qs, urlsplit

    forbidden = {
        "password",
        "passwd",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "secret",
        "authorization",
        "cookie",
        "client_secret",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower().replace("-", "_") in forbidden and item:
                raise ValueError("Use a credential reference; secret values cannot be persisted.")
            validate_public_snapshot(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            validate_public_snapshot(item)
    elif isinstance(value, str) and value.startswith(("https://", "http://")):
        parsed = urlsplit(value)
        if parsed.password or parsed.username or forbidden.intersection(parse_qs(parsed.query)):
            raise ValueError("Persist the public resource identity, not a credential-bearing URL.")


class Profile(str, Enum):
    UNASSIGNED = "unassigned"
    SENTINEL1_TOPS = "sentinel1_tops"
    NISAR = "nisar"


class RunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def terminal(self) -> bool:
        return self in {self.SUCCESS, self.FAILED, self.CANCELLED}


class StepStatus(str, Enum):
    NOT_READY = "NOT_READY"
    READY = "READY"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    STALE = "STALE"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class Integrity(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VALID = "VALID"
    INVALID = "INVALID"


class QCStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class QCMetric:
    metric_id: str
    value: float | int | str | bool | None
    unit: str = ""
    source: str = ""
    scope: str = ""
    extractor_version: str = "1"
    sampling: str = "metadata"


@dataclass(frozen=True)
class QCCheck:
    check_id: str
    metric_id: str
    minimum: float | None = None
    maximum: float | None = None
    expected: Any = None
    blocking: bool = False
    version: str = "1"

    def evaluate(self, metric: QCMetric | None) -> dict[str, Any]:
        result: dict[str, Any] = {"check": asdict(self), "metric": asdict(metric) if metric else None}
        if metric is None or metric.value is None:
            status, reason = QCStatus.UNKNOWN, "Metric unavailable."
        elif self.expected is not None:
            passed = type(metric.value) is type(self.expected) and metric.value == self.expected
            status, reason = (QCStatus.PASS if passed else QCStatus.FAIL), "Expected value check."
        elif self.minimum is not None or self.maximum is not None:
            value = metric.value
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                status, reason = QCStatus.UNKNOWN, "A finite numerical metric is required."
            else:
                passed = (self.minimum is None or value >= self.minimum) and (
                    self.maximum is None or value <= self.maximum
                )
                status, reason = (QCStatus.PASS if passed else QCStatus.FAIL), "Configured range check."
        else:
            status, reason = QCStatus.UNKNOWN, "Observed metric; no acceptance threshold configured."
        return {**result, "status": status.value, "explanation": reason}


@dataclass(frozen=True)
class QCReport:
    report_id: str = field(default_factory=new_id)
    policy_version: str = "1"
    checks: tuple[dict[str, Any], ...] = ()
    created_at: str = field(default_factory=utc_now)

    @property
    def gate_passed(self) -> bool:
        return all(not c["check"]["blocking"] or c["status"] == "PASS" for c in self.checks)


@dataclass(frozen=True)
class StepDefinition:
    step_id: str
    title: str
    depends_on: tuple[str, ...] = ()
    input_roles: tuple[str, ...] = ()
    output_roles: tuple[str, ...] = ()
    version: str = "1"
    optional: bool = False
    official_label: str = ""


@dataclass(frozen=True)
class PipelineDefinition:
    definition_id: str
    profile: Profile
    steps: tuple[StepDefinition, ...]
    version: str = "1"

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for step in self.steps:
            identifier(step.step_id)
            if step.step_id in seen or not set(step.depends_on).issubset(seen):
                raise ValueError("Pipeline steps must be unique and topologically ordered.")
            seen.add(step.step_id)

    def to_dict(self) -> dict[str, Any]:
        return dict(snapshot(asdict(self)))


SENTINEL_LABELS = (
    "unpack_topo_reference",
    "unpack_secondary_slc",
    "average_baseline",
    "extract_burst_overlaps",
    "overlap_geo2rdr",
    "overlap_resample",
    "pairs_misreg",
    "timeseries_misreg",
    "fullBurst_geo2rdr",
    "fullBurst_resample",
    "extract_stack_valid_region",
    "merge_reference_secondary_slc",
    "generate_burst_igram",
    "merge_burst_igram",
    "filter_coherence",
    "unwrap",
)


def sentinel_definition() -> PipelineDefinition:
    steps: list[StepDefinition] = []
    for label in SENTINEL_LABELS:
        step_id = f"sentinel1.{label.lower()}"
        steps.append(
            StepDefinition(
                step_id,
                label.replace("_", " "),
                (steps[-1].step_id,) if steps else (),
                ("slc", "dem", "orbit") if not steps else (),
                (label,),
                official_label=label,
            )
        )
    return PipelineDefinition("sentinel1.tops.isce2", Profile.SENTINEL1_TOPS, tuple(steps))


def nisar_definition() -> PipelineDefinition:
    # The official product workflow is one independently executable science step.
    # Preparation and publication are application operations, not fake ISCE3 jobs.
    return PipelineDefinition(
        "nisar.insar.isce3",
        Profile.NISAR,
        (
            StepDefinition(
                "nisar.insar",
                "Official NISAR InSAR",
                input_roles=("reference", "secondary", "dem"),
                output_roles=("insar_product",),
            ),
        ),
    )


def step_signature(
    definition: dict[str, Any],
    parameters: dict[str, Any],
    inputs: list[dict[str, Any]],
    environment: dict[str, Any],
) -> str:
    return digest(
        {
            "definition": definition,
            "parameters": parameters,
            "inputs": sorted(inputs, key=lambda item: (item["role"], item["artifact_id"])),
            "environment": environment,
        }
    )


@dataclass(frozen=True)
class OutputAsset:
    path: str
    role: str
    subdataset: str | None = None


@dataclass(frozen=True)
class ArtifactOutput:
    artifact_type: str
    assets: tuple[OutputAsset, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
    spatial: dict[str, Any] = field(default_factory=dict)
    temporal: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PostProcessingInputBundle:
    artifact_ids: tuple[str, ...]
    pair_network: tuple[tuple[str, str], ...] = ()
    schema_version: int = 1
    missing_metadata: tuple[str, ...] = ()
