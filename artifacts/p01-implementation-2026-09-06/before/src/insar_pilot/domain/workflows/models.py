"""Immutable contracts for compatibility, recipes, and task projection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


def _identifier(value: str, field_name: str) -> str:
    normalized = value.strip().lower()
    if not _ID_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a stable lowercase identifier: {value}")
    return normalized


def _normalized(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({value.strip().upper() for value in values if value.strip()}))


class BackendAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ProcessingStrategy(str, Enum):
    """Canonical algorithm route owned by the upstream processing engine."""

    SENTINEL1_TOPS_BURST_IFG_THEN_MERGE = "sentinel1_tops_burst_ifg_then_merge"
    NISAR_ISCE3_INSAR_RUNCONFIG = "nisar_isce3_insar_runconfig"


@dataclass(frozen=True)
class OfficialStageDescriptor:
    """One stage discovered from an upstream engine's generated execution plan."""

    stage_id: str
    sequence: int
    display_name: str
    source_path: str
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_id", _identifier(self.stage_id, "stage_id"))
        object.__setattr__(
            self,
            "depends_on",
            tuple(dict.fromkeys(_identifier(value, "dependency") for value in self.depends_on)),
        )
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "source_path", self.source_path.strip())
        if self.sequence < 1:
            raise ValueError("Official stage sequence must be positive.")
        if not self.display_name or not self.source_path:
            raise ValueError("Official stage display_name and source_path are required.")
        if self.stage_id in self.depends_on:
            raise ValueError("An official stage cannot depend on itself.")


@dataclass(frozen=True)
class PairCompatibilityReport:
    """Stable explanation of whether two canonical products can be processed."""

    compatible: bool
    mission: str | None
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    common_frequency_bands: tuple[str, ...] = ()
    common_polarizations: tuple[str, ...] = ()
    temporal_baseline_days: float | None = None

    def __post_init__(self) -> None:
        reasons = tuple(dict.fromkeys(_identifier(value, "reason_code") for value in self.reason_codes))
        warnings = tuple(dict.fromkeys(_identifier(value, "warning") for value in self.warnings))
        if self.compatible and reasons:
            raise ValueError("A compatible report cannot contain incompatibility reasons.")
        if not self.compatible and not reasons:
            raise ValueError("An incompatible report requires at least one reason code.")
        object.__setattr__(self, "mission", self.mission.strip().upper() if self.mission else None)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "common_frequency_bands", _normalized(self.common_frequency_bands))
        object.__setattr__(self, "common_polarizations", _normalized(self.common_polarizations))


@dataclass(frozen=True)
class ParameterDescriptor:
    parameter_id: str
    value_type: str
    required: bool = False
    default: str | int | float | bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameter_id", _identifier(self.parameter_id, "parameter_id"))
        object.__setattr__(self, "value_type", _identifier(self.value_type, "value_type"))


@dataclass(frozen=True)
class TaskDescriptor:
    """One tool-like step whose applicability never depends on GUI labels."""

    task_id: str
    display_name: str
    applicable_missions: tuple[str, ...]
    required_product_types: tuple[str, ...]
    input_roles: tuple[str, ...]
    output_roles: tuple[str, ...]
    parameters: tuple[ParameterDescriptor, ...]
    workflow_recipe_id: str
    backend_id: str
    depends_on: tuple[str, ...] = ()
    overwrite_policy: str = "new_output"

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _identifier(self.task_id, "task_id"))
        object.__setattr__(self, "workflow_recipe_id", _identifier(self.workflow_recipe_id, "workflow_recipe_id"))
        object.__setattr__(self, "backend_id", _identifier(self.backend_id, "backend_id"))
        object.__setattr__(
            self,
            "depends_on",
            tuple(dict.fromkeys(_identifier(value, "dependency") for value in self.depends_on)),
        )
        object.__setattr__(self, "overwrite_policy", _identifier(self.overwrite_policy, "overwrite_policy"))
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "applicable_missions", _normalized(self.applicable_missions))
        object.__setattr__(self, "required_product_types", _normalized(self.required_product_types))
        object.__setattr__(self, "input_roles", tuple(_identifier(value, "input_role") for value in self.input_roles))
        object.__setattr__(
            self,
            "output_roles",
            tuple(_identifier(value, "output_role") for value in self.output_roles),
        )
        object.__setattr__(self, "parameters", tuple(self.parameters))
        if not self.display_name or not self.applicable_missions or not self.required_product_types:
            raise ValueError("Task display name, missions, and product types are required.")


@dataclass(frozen=True)
class WorkflowRecipeDescriptor:
    recipe_id: str
    display_name: str
    mission: str
    required_product_type: str
    min_products: int
    max_products: int | None
    backend_id: str
    backend_availability: BackendAvailability
    processing_strategy: ProcessingStrategy
    tasks: tuple[TaskDescriptor, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "recipe_id", _identifier(self.recipe_id, "recipe_id"))
        object.__setattr__(self, "backend_id", _identifier(self.backend_id, "backend_id"))
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "mission", self.mission.strip().upper())
        object.__setattr__(self, "required_product_type", self.required_product_type.strip().upper())
        object.__setattr__(self, "tasks", tuple(self.tasks))
        if self.min_products < 1:
            raise ValueError("min_products must be positive.")
        if self.max_products is not None and self.max_products < self.min_products:
            raise ValueError("max_products cannot be less than min_products.")
        if any(task.workflow_recipe_id != self.recipe_id for task in self.tasks):
            raise ValueError("Every task must belong to its containing recipe.")
        if any(task.backend_id != self.backend_id for task in self.tasks):
            raise ValueError("Every task must use its containing recipe backend.")
        task_ids = tuple(task.task_id for task in self.tasks)
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("Task IDs must be unique inside a recipe.")
        earlier: set[str] = set()
        for task in self.tasks:
            missing = set(task.depends_on).difference(earlier)
            if missing:
                joined = ", ".join(sorted(missing))
                raise ValueError(
                    f"Task dependencies must reference earlier tasks in the same recipe: {joined}"
                )
            earlier.add(task.task_id)


@dataclass(frozen=True)
class RecipeEligibility:
    descriptor: WorkflowRecipeDescriptor
    input_compatible: bool
    runnable: bool
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reason_codes",
            tuple(dict.fromkeys(_identifier(value, "reason_code") for value in self.reason_codes)),
        )
        if self.runnable and not self.input_compatible:
            raise ValueError("An incompatible recipe cannot be runnable.")
        if self.runnable and self.descriptor.backend_availability is not BackendAvailability.AVAILABLE:
            raise ValueError("A recipe with an unavailable backend cannot be runnable.")


@dataclass(frozen=True)
class WorkflowEligibilityReport:
    selection_product_ids: tuple[str, ...]
    pair_reports: tuple[PairCompatibilityReport, ...]
    recipes: tuple[RecipeEligibility, ...]

    @property
    def runnable_recipes(self) -> tuple[RecipeEligibility, ...]:
        return tuple(recipe for recipe in self.recipes if recipe.runnable)


__all__ = [
    "BackendAvailability",
    "PairCompatibilityReport",
    "OfficialStageDescriptor",
    "ParameterDescriptor",
    "ProcessingStrategy",
    "RecipeEligibility",
    "TaskDescriptor",
    "WorkflowEligibilityReport",
    "WorkflowRecipeDescriptor",
]
