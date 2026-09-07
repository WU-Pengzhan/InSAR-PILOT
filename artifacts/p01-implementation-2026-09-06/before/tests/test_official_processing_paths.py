from __future__ import annotations

from pathlib import Path

import pytest

from insar_pilot.services.official_processing_paths import (
    Isce2TopsStageDiscovery,
    OfficialPlanError,
)


def test_isce2_run_files_are_the_ordered_stage_source_of_truth(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_files"
    run_dir.mkdir()
    (run_dir / "run_14_merge_burst_igram").write_text("mergeBursts.py\n", encoding="utf-8")
    (run_dir / "run_02_unpack_topo").write_text("SentinelWrapper.py\n", encoding="utf-8")
    (run_dir / "run_13_generate_burst_igram").write_text("generateIgram.py\n", encoding="utf-8")
    (run_dir / "notes.txt").write_text("not a stage\n", encoding="utf-8")

    stages = Isce2TopsStageDiscovery().discover(tmp_path)

    assert [stage.sequence for stage in stages] == [2, 13, 14]
    assert [Path(stage.source_path).name for stage in stages] == [
        "run_02_unpack_topo",
        "run_13_generate_burst_igram",
        "run_14_merge_burst_igram",
    ]
    assert stages[0].depends_on == ()
    assert stages[1].depends_on == (stages[0].stage_id,)
    assert stages[2].depends_on == (stages[1].stage_id,)


def test_isce2_stage_discovery_uses_numeric_order_and_rejects_ambiguity(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_files"
    run_dir.mkdir()
    (run_dir / "run_2_second").write_text("true\n", encoding="utf-8")
    (run_dir / "run_02_duplicate").write_text("true\n", encoding="utf-8")
    (run_dir / "run_10_tenth").write_text("true\n", encoding="utf-8")

    with pytest.raises(OfficialPlanError, match="duplicated"):
        Isce2TopsStageDiscovery().discover(tmp_path)


def test_isce2_stage_discovery_does_not_invent_merge_slc_then_ifg(tmp_path: Path) -> None:
    assert Isce2TopsStageDiscovery().discover(tmp_path) == ()
