from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from insar_pilot.domain.local_data import AssetRef, LocalSARProduct, SourceSnapshot, stable_product_id
from insar_pilot.domain.workflows import BackendAvailability, ProcessingStrategy
from insar_pilot.services.project_data_catalog import ProjectDataCatalog
from insar_pilot.services.workflow_eligibility import (
    WorkflowEligibilityService,
    build_default_workflow_recipe_registry,
)


def _product(native_id: str, mission: str, day: int, *, mode: str = "IW") -> LocalSARProduct:
    nisar = mission == "NISAR"
    product_type = "RSLC" if nisar else "SLC"
    start = datetime(2026, 1, day, tzinfo=timezone.utc)
    return LocalSARProduct(
        product_id=stable_product_id(mission, product_type, native_id),
        native_product_id=native_id,
        mission=mission,
        platform=mission if nisar else "S1A",
        product_type=product_type,
        acquisition_mode="SCIENCE" if nisar else mode,
        acquisition_layout="FREQUENCY_SWATHS" if nisar else ("TOPS_SWATHS" if mode == "IW" else "STRIPMAP"),
        start_time=start,
        end_time=start + timedelta(minutes=1),
        orbit_direction="ASCENDING",
        orbit_identity=None,
        track=13 if nisar else None,
        frame=71 if nisar else None,
        relative_orbit=None if nisar else 12,
        frequency_bands=("A",) if nisar else ("C",),
        polarizations=("HH",) if nisar else ("VV",),
        footprint_wkt="POLYGON((0 0,2 0,2 2,0 2,0 0))",
        assets=(AssetRef(f"/readonly/{native_id}", "source_product"),),
        native_metadata={"identification": {"lookDirection": "Left"}} if nisar else {},
        reader_id="nisar.rslc" if nisar else "sentinel1.safe",
        reader_schema_version=1,
        source_snapshot=SourceSnapshot("file", 1, day),
    )


def test_sentinel_recipe_maps_existing_isce2_and_has_no_nisar_tasks() -> None:
    service = WorkflowEligibilityService(build_default_workflow_recipe_registry())
    report = service.evaluate((_product("S1_1", "SENTINEL-1", 1), _product("S1_2", "SENTINEL-1", 2)))

    assert len(report.recipes) == 1
    recipe = report.recipes[0]
    assert recipe.descriptor.recipe_id == "sentinel1.tops.isce2"
    assert recipe.descriptor.backend_availability is BackendAvailability.AVAILABLE
    assert recipe.runnable
    task_ids = {task.task_id for task in recipe.descriptor.tasks}
    assert recipe.descriptor.processing_strategy is ProcessingStrategy.SENTINEL1_TOPS_BURST_IFG_THEN_MERGE
    assert "sentinel1.run_official_stage" in task_ids
    assert "sentinel1.esd" not in task_ids
    assert "sentinel1.merge_bursts" not in task_ids
    assert not any(task_id.startswith("nisar.") for task_id in task_ids)


def test_nisar_recipe_is_runnable_through_the_official_isce3_backend() -> None:
    service = WorkflowEligibilityService(build_default_workflow_recipe_registry())
    report = service.evaluate((_product("N1", "NISAR", 1), _product("N2", "NISAR", 2)))

    assert len(report.recipes) == 1
    recipe = report.recipes[0]
    assert recipe.descriptor.recipe_id == "nisar.rslc_pair.isce3"
    assert recipe.input_compatible
    assert recipe.runnable
    assert recipe.reason_codes == ()
    assert report.runnable_recipes == (recipe,)
    task_ids = {task.task_id for task in recipe.descriptor.tasks}
    assert recipe.descriptor.processing_strategy is ProcessingStrategy.NISAR_ISCE3_INSAR_RUNCONFIG
    assert {"nisar.build_runconfig", "nisar.run_product", "nisar.catalog_products"}.issubset(task_ids)
    assert "nisar.dense_offsets" not in task_ids
    assert "nisar.rubbersheet" not in task_ids
    assert not any(task_id.startswith("sentinel1.") for task_id in task_ids)


def test_mixed_selection_projects_no_recipe_and_sentinel_stripmap_is_not_isce2_eligible() -> None:
    service = WorkflowEligibilityService(build_default_workflow_recipe_registry())
    mixed = service.evaluate((_product("S1", "SENTINEL-1", 1), _product("N1", "NISAR", 2)))
    assert mixed.recipes == ()
    assert mixed.pair_reports[0].reason_codes == ("cross_mission_pair",)

    stripmap = service.evaluate(
        (
            _product("SM1", "SENTINEL-1", 1, mode="SM"),
            _product("SM2", "SENTINEL-1", 2, mode="SM"),
        )
    )
    assert not stripmap.recipes[0].input_compatible
    assert "sentinel_isce2_requires_iw_tops" in stripmap.recipes[0].reason_codes


def test_recipe_descriptors_have_mission_scoped_tasks_and_overwrite_contracts() -> None:
    registry = build_default_workflow_recipe_registry()
    for recipe in registry.descriptors():
        assert recipe.tasks
        for task in recipe.tasks:
            assert task.applicable_missions == (recipe.mission,)
            assert task.required_product_types == (recipe.required_product_type,)
            assert task.workflow_recipe_id == recipe.recipe_id
            assert task.backend_id == recipe.backend_id
            assert task.overwrite_policy
        completed: set[str] = set()
        for task in recipe.tasks:
            assert set(task.depends_on).issubset(completed)
            completed.add(task.task_id)


def test_catalog_selection_is_resolved_by_product_id(tmp_path: Path) -> None:
    products = (_product("S1_1", "SENTINEL-1", 1), _product("S1_2", "SENTINEL-1", 2))
    catalog = ProjectDataCatalog(tmp_path)
    for product in products:
        catalog.merge(product, persist=False)
    service = WorkflowEligibilityService(build_default_workflow_recipe_registry())

    report = service.evaluate_catalog(catalog, tuple(product.product_id for product in products))

    assert report.recipes[0].runnable
