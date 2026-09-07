"""Utilities for parsing and executing topsStack run files safely."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

RESULT_MARKER = "__ISCE_SUBCMD_RC__"
RESULT_PATTERN = re.compile(rf"{RESULT_MARKER}\s+(\d+)\s+(-?\d+)")


@dataclass(frozen=True)
class RunFileCommand:
    index: int
    command: str


def parse_run_file(path: Path) -> list[list[RunFileCommand]]:
    return parse_run_file_text(path.read_text(encoding="utf-8"))


def parse_run_file_text(text: str) -> list[list[RunFileCommand]]:
    batches: list[list[RunFileCommand]] = []
    current_batch: list[RunFileCommand] = []
    index = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "wait":
            if current_batch:
                batches.append(current_batch)
                current_batch = []
            continue

        is_background = line.endswith("&")
        if is_background:
            line = line[:-1].strip()
        if not line:
            continue

        index += 1
        command = RunFileCommand(index=index, command=line)
        if is_background:
            current_batch.append(command)
        else:
            if current_batch:
                batches.append(current_batch)
                current_batch = []
            batches.append([command])

    if current_batch:
        batches.append(current_batch)
    return batches


def split_batches_for_parallelism(
    batches: list[list[RunFileCommand]],
    max_parallel: int,
) -> list[list[RunFileCommand]]:
    parallel = max(1, int(max_parallel))
    output: list[list[RunFileCommand]] = []
    for batch in batches:
        if len(batch) <= parallel:
            output.append(batch)
            continue
        for start in range(0, len(batch), parallel):
            output.append(batch[start : start + parallel])
    return output


def count_commands(batches: list[list[RunFileCommand]]) -> int:
    return sum(len(batch) for batch in batches)


def build_parallel_batch_command(
    commands: list[RunFileCommand],
    log_paths: dict[int, str],
) -> str:
    if not commands:
        raise ValueError("Cannot build a batch command without subcommands.")

    lines = ["set +e", "failed=0"]
    for command in commands:
        log_path = log_paths.get(command.index)
        if not log_path:
            raise ValueError(f"Missing log path for subcommand index {command.index}.")
        lines.append(f"( {command.command} ) > {shlex.quote(log_path)} 2>&1 &")
        lines.append(f"pid_{command.index}=$!")

    for command in commands:
        lines.append(f"wait $pid_{command.index}")
        lines.append("rc=$?")
        lines.append(f'echo "{RESULT_MARKER} {command.index} $rc"')
        lines.append('if [ "$rc" -ne 0 ]; then failed=1; fi')

    lines.append("exit $failed")
    return "\n".join(lines)


def parse_result_markers(log_text: str) -> dict[int, int]:
    return {
        int(index_text): int(rc_text)
        for index_text, rc_text in RESULT_PATTERN.findall(log_text)
    }
