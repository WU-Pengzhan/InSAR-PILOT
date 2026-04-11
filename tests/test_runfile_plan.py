import subprocess
from pathlib import Path

from isce2_gui.services.runfile_plan import (
    build_parallel_batch_command,
    count_commands,
    parse_result_markers,
    parse_run_file_text,
    split_batches_for_parallelism,
)


def test_parse_run_file_splits_wait_boundaries():
    text = "\n".join(
        [
            "cmd1 &",
            "cmd2 &",
            "wait",
            "cmd3",
        ]
    )

    batches = parse_run_file_text(text)

    assert len(batches) == 2
    assert [item.command for item in batches[0]] == ["cmd1", "cmd2"]
    assert [item.command for item in batches[1]] == ["cmd3"]
    assert count_commands(batches) == 3


def test_parse_run_file_flushes_background_batch_without_wait():
    text = "\n".join(
        [
            "cmd1 &",
            "cmd2 &",
        ]
    )

    batches = parse_run_file_text(text)

    assert len(batches) == 1
    assert [item.command for item in batches[0]] == ["cmd1", "cmd2"]


def test_split_batches_respects_num_proc_limit():
    batches = parse_run_file_text("cmd1 &\ncmd2 &\ncmd3 &\nwait\n")

    split = split_batches_for_parallelism(batches, max_parallel=2)

    assert len(split) == 2
    assert [item.command for item in split[0]] == ["cmd1", "cmd2"]
    assert [item.command for item in split[1]] == ["cmd3"]


def test_build_parallel_batch_command_emits_result_markers():
    batches = parse_run_file_text("echo one &\necho two &\nwait\n")
    command = build_parallel_batch_command(
        batches[0],
        log_paths={
            1: "/tmp/cmd_001.log",
            2: "/tmp/cmd_002.log",
        },
    )

    assert "__ISCE_SUBCMD_RC__ 1" in command
    assert "__ISCE_SUBCMD_RC__ 2" in command


def test_parse_result_markers_extracts_exit_codes():
    text = "\n".join(
        [
            "noise line",
            "__ISCE_SUBCMD_RC__ 1 0",
            "__ISCE_SUBCMD_RC__ 2 1",
        ]
    )

    markers = parse_result_markers(text)

    assert markers == {1: 0, 2: 1}


def test_parallel_batch_exit_code_propagates_failure(tmp_path: Path):
    batches = parse_run_file_text("true &\nfalse &\nwait\n")
    batch_log = tmp_path / "batch.log"
    command = build_parallel_batch_command(
        batches[0],
        log_paths={
            1: str(tmp_path / "cmd_001.log"),
            2: str(tmp_path / "cmd_002.log"),
        },
    )

    completed = subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
    )
    batch_log.write_text(completed.stdout + completed.stderr, encoding="utf-8")
    markers = parse_result_markers(batch_log.read_text(encoding="utf-8"))

    assert completed.returncode == 1
    assert markers == {1: 0, 2: 1}
