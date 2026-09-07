"""Project mission-aware workflow and task eligibility from catalog selections."""

from __future__ import annotations

from itertools import combinations

from insar_pilot.domain.local_data import LocalSARProduct
from insar_pilot.domain.workflows import (
    BackendAvailability,
    PairCompatibilityReport,
    ParameterDescriptor,
    ProcessingStrategy,
    RecipeEligibility,
    TaskDescriptor,
    WorkflowEligibilityReport,
    WorkflowRecipeDescriptor,
)
from insar_pilot.services.product_compatibility import PairCompatibilityService
from insar_pilot.services.project_data_catalog import ProjectDataCatalog


class WorkflowRecipeRegistry:
    """Validated registry whose descriptors are portable to a future web API."""

    def __init__(self) -> None:
        self._recipes: dict[str, WorkflowRecipeDescriptor] = {}

    def register(self, descriptor: WorkflowRecipeDescriptor) -> None:
        if descriptor.recipe_id in self._recipes:
            raise ValueError(f"Workflow recipe is already registered: {descriptor.recipe_id}")
        for existing in self._recipes.values():
            if (
                existing.mission == descriptor.mission
                and existing.required_product_type == descriptor.required_product_type
            ):
                raise ValueError(
                    "Only one canonical processing recipe may be registered for "
                    f"{descriptor.mission} {descriptor.required_product_type}."
                )
            existing_task_ids = {task.task_id for task in existing.tasks}
            overlap = existing_task_ids.intersection(task.task_id for task in descriptor.tasks)
            if overlap:
                raise ValueError(f"Task IDs must be globally unique: {', '.join(sorted(overlap))}")
        self._recipes[descriptor.recipe_id] = descriptor

    def descriptors(self) -> tuple[WorkflowRecipeDescriptor, ...]:
        return tuple(self._recipes[key] for key in sorted(self._recipes))

    def for_mission(self, mission: str) -> tuple[WorkflowRecipeDescriptor, ...]:
        normalized = mission.strip().upper()
        return tuple(item for item in self.descriptors() if item.mission == normalized)


class WorkflowEligibilityService:
    """Return compatible and runnable as separate decisions."""

    def __init__(
        self,
        registry: WorkflowRecipeRegistry,
        compatibility: PairCompatibilityService | None = None,
    ) -> None:
        self._registry = registry
        self._compatibility = compatibility or PairCompatibilityService()

    def evaluate(self, products: tuple[LocalSARProduct, ...]) -> WorkflowEligibilityReport:
        product_ids = tuple(product.product_id for product in products)
        if not products:
            return WorkflowEligibilityReport(product_ids, (), ())
        pair_reports = tuple(self._compatibility.check(left, right) for left, right in combinations(products, 2))
        missions = {product.mission for product in products}
        if len(missions) != 1:
            return WorkflowEligibilityReport(product_ids, pair_reports, ())
        mission = next(iter(missions))
        recipes = tuple(
            self._evaluate_recipe(descriptor, products, pair_reports)
            for descriptor in self._registry.for_mission(mission)
        )
        return WorkflowEligibilityReport(product_ids, pair_reports, recipes)

    def evaluate_catalog(
        self,
        catalog: ProjectDataCatalog,
        product_ids: tuple[str, ...],
    ) -> WorkflowEligibilityReport:
        """Resolve a catalog selection without exposing persistence details to a UI."""

        entries = tuple(catalog.get(product_id) for product_id in product_ids)
        missing = tuple(product_id for product_id, entry in zip(product_ids, entries, strict=True) if entry is None)
        if missing:
            raise KeyError(f"Catalog selection contains unknown product IDs: {', '.join(missing)}")
        return self.evaluate(tuple(entry.product for entry in entries if entry is not None))

    @staticmethod
    def _evaluate_recipe(
        descriptor: WorkflowRecipeDescriptor,
        products: tuple[LocalSARProduct, ...],
        pair_reports: tuple[PairCompatibilityReport, ...],
    ) -> RecipeEligibility:
        reasons: list[str] = []
        count = len(products)
        if count < descriptor.min_products or (
            descriptor.max_products is not None and count > descriptor.max_products
        ):
            reasons.append("product_count_mismatch")
        if any(product.product_type != descriptor.required_product_type for product in products):
            reasons.append("product_type_mismatch")
        if any(not report.compatible for report in pair_reports):
            reasons.append("pair_incompatible")
        if descriptor.recipe_id == "sentinel1.tops.isce2" and any(
            product.acquisition_mode != "IW" or product.acquisition_layout != "TOPS_SWATHS"
            for product in products
        ):
            reasons.append("sentinel_isce2_requires_iw_tops")
        input_compatible = not reasons
        if descriptor.backend_availability is BackendAvailability.UNAVAILABLE:
            reasons.append("backend_unavailable")
        return RecipeEligibility(
            descriptor=descriptor,
            input_compatible=input_compatible,
            runnable=input_compatible and descriptor.backend_availability is BackendAvailability.AVAILABLE,
            reason_codes=tuple(reasons),
        )


def build_default_workflow_recipe_registry() -> WorkflowRecipeRegistry:
    registry = WorkflowRecipeRegistry()
    registry.register(_sentinel_recipe())
    registry.register(_nisar_recipe())
    return registry


def _task(
    task_id: str,
    display_name: str,
    mission: str,
    product_type: str,
    recipe_id: str,
    backend_id: str,
    *,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    parameters: tuple[ParameterDescriptor, ...] = (),
    depends_on: tuple[str, ...] = (),
    overwrite_policy: str = "new_output",
) -> TaskDescriptor:
    return TaskDescriptor(
        task_id=task_id,
        display_name=display_name,
        applicable_missions=(mission,),
        required_product_types=(product_type,),
        input_roles=inputs,
        output_roles=outputs,
        parameters=parameters,
        workflow_recipe_id=recipe_id,
        backend_id=backend_id,
        depends_on=depends_on,
        overwrite_policy=overwrite_policy,
    )


def _sentinel_recipe() -> WorkflowRecipeDescriptor:
    recipe_id = "sentinel1.tops.isce2"
    backend_id = "isce2.topsstack"
    mission = "SENTINEL-1"
    product_type = "SLC"
    tasks = (
        _task(
            "sentinel1.validate_pair",
            "Validate Sentinel-1 stack",
            mission,
            product_type,
            recipe_id,
            backend_id,
            inputs=("source_product",),
            outputs=("validation_report",),
            parameters=(
                ParameterDescriptor("swaths", "string", default="1 2 3"),
                ParameterDescriptor("polarization", "string", default="VV"),
            ),
            overwrite_policy="replace_report",
        ),
        _task(
            "sentinel1.prepare_dem",
            "Prepare DEM",
            mission,
            product_type,
            recipe_id,
            backend_id,
            inputs=("source_product", "dem"),
            outputs=("prepared_dem",),
            depends_on=("sentinel1.validate_pair",),
        ),
        _task(
            "sentinel1.generate_run_files",
            "Generate official ISCE2 TOPS run files",
            mission,
            product_type,
            recipe_id,
            backend_id,
            inputs=("source_product", "prepared_dem", "orbit", "aux_cal"),
            outputs=("run_file",),
            depends_on=("sentinel1.prepare_dem",),
            parameters=(
                ParameterDescriptor("swaths", "string", default="1 2 3"),
                ParameterDescriptor("polarization", "string", default="VV"),
            ),
            overwrite_policy="error_if_exists",
        ),
        _task(
            "sentinel1.run_official_stage",
            "Run one generated ISCE2 stage",
            mission,
            product_type,
            recipe_id,
            backend_id,
            inputs=("run_file",),
            outputs=("stage_artifact",),
            depends_on=("sentinel1.generate_run_files",),
            parameters=(ParameterDescriptor("max_parallel", "integer", default=1),),
            overwrite_policy="replace_declared_outputs",
        ),
        _task(
            "sentinel1.catalog_products",
            "Register official ISCE2 products",
            mission,
            product_type,
            recipe_id,
            backend_id,
            inputs=("stage_artifact",),
            outputs=("product_catalog",),
            depends_on=("sentinel1.run_official_stage",),
            overwrite_policy="replace_report",
        ),
    )
    return WorkflowRecipeDescriptor(
        recipe_id,
        "Sentinel-1 TOPS / ISCE2",
        mission,
        product_type,
        2,
        None,
        backend_id,
        BackendAvailability.AVAILABLE,
        ProcessingStrategy.SENTINEL1_TOPS_BURST_IFG_THEN_MERGE,
        tasks,
    )


def _nisar_recipe() -> WorkflowRecipeDescriptor:
    recipe_id = "nisar.rslc_pair.isce3"
    backend_id = "isce3.nisar_rifg"
    mission = "NISAR"
    product_type = "RSLC"
    tasks = (
        _task(
            "nisar.validate_pair",
            "Validate NISAR RSLC pair",
            mission,
            product_type,
            recipe_id,
            backend_id,
            inputs=("source_product",),
            outputs=("validation_report",),
            parameters=(ParameterDescriptor("frequency", "string", required=True),),
            overwrite_policy="replace_report",
        ),
        _task(
            "nisar.prepare_dem",
            "Prepare DEM",
            mission,
            product_type,
            recipe_id,
            backend_id,
            inputs=("source_product", "dem"),
            outputs=("prepared_dem",),
            depends_on=("nisar.validate_pair",),
        ),
        _task(
            "nisar.build_runconfig",
            "Build ISCE3 runconfig",
            mission,
            product_type,
            recipe_id,
            backend_id,
            inputs=("source_product", "prepared_dem"),
            outputs=("runconfig",),
            depends_on=("nisar.prepare_dem",),
            parameters=(ParameterDescriptor("frequency", "string", required=True),),
            overwrite_policy="versioned_file",
        ),
        _task(
            "nisar.run_product",
            "Run official NISAR InSAR product workflow",
            mission,
            product_type,
            recipe_id,
            backend_id,
            inputs=("runconfig",),
            outputs=("insar_product",),
            depends_on=("nisar.build_runconfig",),
            parameters=(ParameterDescriptor("product_type", "string", default="RIFG"),),
            overwrite_policy="new_folder",
        ),
        _task(
            "nisar.catalog_products",
            "Register official ISCE3 products",
            mission,
            product_type,
            recipe_id,
            backend_id,
            inputs=("insar_product",),
            outputs=("product_catalog",),
            depends_on=("nisar.run_product",),
            overwrite_policy="replace_report",
        ),
    )
    return WorkflowRecipeDescriptor(
        recipe_id,
        "NISAR RSLC pair / ISCE3 RIFG",
        mission,
        product_type,
        2,
        2,
        backend_id,
        BackendAvailability.AVAILABLE,
        ProcessingStrategy.NISAR_ISCE3_INSAR_RUNCONFIG,
        tasks,
    )


__all__ = [
    "WorkflowEligibilityService",
    "WorkflowRecipeRegistry",
    "build_default_workflow_recipe_registry",
]
