"""Headless CLI entry point for InSAR-PILOT project workflows.

Provides ``init``/``generate``/``run``/``status`` subcommands that reuse the same
Qt-free service layer as the GUI (``ProjectStore``, ``StackWorkflowService``,
``ShellCommandBuilder``, ``runfile_plan``). Because both front-ends persist
through :class:`ProjectStore` into the same ``project.pilot`` file and write logs
under the project's ``logs/`` directory with identical naming, a project created
or advanced from the CLI is fully interchangeable with the GUI and vice versa.

Exit codes: ``0`` success, ``1`` a shelled command failed, ``2`` usage/config
errors (bad arguments, missing/malformed project, blocked generation).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from insar_pilot.cli.runner import HeadlessRunner
from insar_pilot.domain.project import (
    ProjectDocument,
    ProjectStatus,
    RunStep,
    RunSubcommand,
    StepStatus,
)
from insar_pilot.services.command_plan import CommandPlan
from insar_pilot.services.project_store import ProjectLoadError, ProjectStore
from insar_pilot.services.runfile_plan import (
    build_parallel_batch_command,
    parse_result_markers,
    parse_run_file,
    split_batches_for_parallelism,
)
from insar_pilot.services.stack_generator import StackWorkflowService

EXIT_OK = 0
EXIT_COMMAND_FAILED = 1
EXIT_USAGE = 2


class CliError(Exception):
    """A recoverable CLI failure carrying its own process exit code."""

    def __init__(self, message: str, code: int = EXIT_USAGE) -> None:
        super().__init__(message)
        self.code = code


# ----------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------
def _load(store: ProjectStore, project_dir: str) -> ProjectDocument:
    try:
        return store.load(project_dir)
    except ProjectLoadError as exc:
        raise CliError(str(exc), EXIT_USAGE) from exc


def _find_step(project: ProjectDocument, name: str) -> RunStep | None:
    for step in project.state.steps:
        if step.name == name:
            return step
    return None


def _find_subcommand(step: RunStep, index: int) -> RunSubcommand | None:
    for item in step.subcommands:
        if item.index == index:
            return item
    return None


def _parse_step_range(text: str, total: int) -> tuple[int, int]:
    raw = text.strip()
    try:
        if "-" in raw:
            low_text, high_text = raw.split("-", 1)
            low, high = int(low_text), int(high_text)
        else:
            low = high = int(raw)
    except ValueError as exc:
        raise CliError(f"Invalid --steps value '{text}'; use 'N' or 'A-B'.", EXIT_USAGE) from exc

    if low < 1 or high > total or low > high:
        raise CliError(
            f"--steps '{text}' is out of range; project has {total} step(s) (1-{total}).",
            EXIT_USAGE,
        )
    return low, high


def _select_steps(project: ProjectDocument, steps_arg: str) -> list[RunStep]:
    if not steps_arg.strip():
        return StackWorkflowService.remaining_steps(project)
    low, high = _parse_step_range(steps_arg, len(project.state.steps))
    return project.state.steps[low - 1 : high]


# ----------------------------------------------------------------------
# init
# ----------------------------------------------------------------------
def _cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.dir).expanduser()
    store = ProjectStore()
    if store.resolve_project_file(root).exists():
        raise CliError(f"A project already exists at {root}.", EXIT_USAGE)

    project = store.create_workspace(root)
    name = args.name.strip() or root.name
    print(f"Initialized project '{name}' at {project.workspace.root_path()}")
    print(f"Project file: {project.project_file()}")
    return EXIT_OK


# ----------------------------------------------------------------------
# generate
# ----------------------------------------------------------------------
def _cmd_generate(args: argparse.Namespace) -> int:
    store = ProjectStore()
    project = _load(store, args.project_dir)
    service = StackWorkflowService()

    try:
        command = service.build_generate_command(
            project,
            project.state.prepared_inputs,
            dem_path=project.state.prepared_dem_path,
        )
    except FileExistsError as exc:
        raise CliError(str(exc), EXIT_USAGE) from exc
    except (ValueError, OSError) as exc:
        raise CliError(f"Could not build the generation command: {exc}", EXIT_USAGE) from exc

    if args.dry_run:
        print(command)
        return EXIT_OK

    work_dir = project.resolved_work_dir()
    log_path = project.logs_dir() / "stack_generate.log"
    plan = CommandPlan(
        label="Generate processing workflow",
        command=command,
        cwd=str(work_dir),
        log_path=str(log_path),
        step_name="workflow generation",
        is_generation=True,
        kind="generation",
    )

    project.state.last_generated_command = command
    project.state.last_error = ""
    project.state.current_step = "workflow generation"
    project.state.status = ProjectStatus.RUNNING
    store.save(project)

    print(f"Generating workflow (log: {log_path}) ...")
    exit_code = HeadlessRunner(project.environment).run(plan)

    if exit_code == 0:
        service.synchronize_project_steps(project)
        project.state.status = ProjectStatus.GENERATED
        project.state.last_error = ""
        store.save(project)
        print(f"Workflow generated. {len(project.state.steps)} run step(s) discovered.")
        return EXIT_OK

    project.state.status = ProjectStatus.FAILED
    project.state.last_error = f"Workflow generation failed with exit code {exit_code}"
    store.save(project)
    print(f"Workflow generation failed (exit {exit_code}). See {log_path}", file=sys.stderr)
    return EXIT_COMMAND_FAILED


# ----------------------------------------------------------------------
# run
# ----------------------------------------------------------------------
def _prepare_plans(
    project: ProjectDocument,
    steps: list[RunStep],
    logs_dir: Path,
    runfile_parallel: int,
) -> list[CommandPlan]:
    """Build the batch command queue, mirroring RunController._run_steps.

    Also (re)initializes each step's subcommand list, log paths, and status so
    the persisted project.pilot matches what the GUI would write for the same
    run files.
    """

    plans: list[CommandPlan] = []
    work_dir = str(project.resolved_work_dir())
    for step in steps:
        run_file = Path(step.path)
        if not step.path or not run_file.expanduser().exists():
            raise CliError(f"Run file missing for {step.name}: {step.path}", EXIT_USAGE)
        try:
            parsed_batches = parse_run_file(run_file)
        except (OSError, ValueError) as exc:
            raise CliError(f"Run file parsing failed for {step.name}: {exc}", EXIT_USAGE) from exc
        if not parsed_batches:
            raise CliError(
                f"Run file parsing failed for {step.name}: no executable commands found.",
                EXIT_USAGE,
            )

        batches = split_batches_for_parallelism(parsed_batches, runfile_parallel)
        command_logs = {
            cmd.index: str(logs_dir / f"{step.name}.cmd_{cmd.index:03d}.log")
            for batch in batches
            for cmd in batch
        }
        step.subcommands = [
            RunSubcommand(
                index=cmd.index,
                command=cmd.command,
                status=StepStatus.PENDING,
                log_path=command_logs[cmd.index],
                exit_code=None,
            )
            for batch in batches
            for cmd in batch
        ]
        step.subcommands.sort(key=lambda item: item.index)
        step.status = StepStatus.PENDING
        step.exit_code = None
        step.last_message = ""
        step.log_path = str(logs_dir / f"{step.name}.batch_001.log")

        total_batches = len(batches)
        for batch_index, batch in enumerate(batches, start=1):
            batch_log_path = str(logs_dir / f"{step.name}.batch_{batch_index:03d}.log")
            plans.append(
                CommandPlan(
                    label=f"{step.name} [batch {batch_index}/{total_batches}]",
                    command=build_parallel_batch_command(batch, command_logs),
                    cwd=work_dir,
                    log_path=batch_log_path,
                    step_name=step.name,
                    is_generation=False,
                    kind="step_batch",
                    metadata={
                        "subcommand_indices": [cmd.index for cmd in batch],
                        "batch_index": batch_index,
                        "batch_total": total_batches,
                    },
                )
            )
    return plans


def _mark_batch_started(project: ProjectDocument, plan: CommandPlan) -> None:
    """Mirror RunController._handle_command_started for a step batch."""

    project.state.current_step = plan.step_name or plan.label
    step = _find_step(project, plan.step_name)
    if step is None:
        return
    step.status = StepStatus.RUNNING
    step.exit_code = None
    for sub_index in plan.metadata.get("subcommand_indices", []):
        subcommand = _find_subcommand(step, int(sub_index))
        if subcommand is not None:
            subcommand.status = StepStatus.RUNNING
            subcommand.exit_code = None


def _apply_batch_finished(project: ProjectDocument, plan: CommandPlan, exit_code: int) -> None:
    """Mirror RunController._handle_command_finished for a step batch."""

    step = _find_step(project, plan.step_name)
    if step is not None:
        sub_indices = [int(item) for item in plan.metadata.get("subcommand_indices", [])]
        try:
            marker_text = Path(plan.log_path).read_text(encoding="utf-8")
        except OSError:
            marker_text = ""
        marker_codes = parse_result_markers(marker_text)
        for sub_index in sub_indices:
            subcommand = _find_subcommand(step, sub_index)
            if subcommand is None:
                continue
            rc = marker_codes.get(sub_index)
            if rc is None:
                if exit_code != 0:
                    subcommand.status = StepStatus.FAILED
                    subcommand.exit_code = -1
                continue
            subcommand.exit_code = rc
            subcommand.status = StepStatus.SUCCESS if rc == 0 else StepStatus.FAILED

        failed_sub = next(
            (
                item
                for item in sorted(step.subcommands, key=lambda cmd: cmd.index)
                if item.status == StepStatus.FAILED
            ),
            None,
        )
        if failed_sub is not None or exit_code != 0:
            step.status = StepStatus.FAILED
            step.exit_code = exit_code
            failed_index = failed_sub.index if failed_sub is not None else "?"
            failed_cmd = failed_sub.command if failed_sub is not None else "(unknown command)"
            step.last_message = f"Failed subcommand #{failed_index}: {failed_cmd}"
        elif all(item.status == StepStatus.SUCCESS for item in step.subcommands):
            step.status = StepStatus.SUCCESS
            step.exit_code = 0
            step.last_message = "All subcommands completed successfully."
        else:
            step.status = StepStatus.RUNNING
            step.exit_code = None
            step.last_message = "Waiting for remaining batch commands."

    if step is None:
        if exit_code != 0:
            project.state.status = ProjectStatus.FAILED
            project.state.last_error = f"{plan.step_name} failed with exit code {exit_code}"
        else:
            project.state.status = ProjectStatus.RUNNING
    elif step.status == StepStatus.FAILED:
        project.state.status = ProjectStatus.FAILED
        project.state.last_error = step.last_message or f"{plan.step_name} failed with exit code {exit_code}"
    elif all(item.status == StepStatus.SUCCESS for item in project.state.steps):
        project.state.status = ProjectStatus.COMPLETED
    else:
        project.state.status = ProjectStatus.RUNNING


def _cmd_run(args: argparse.Namespace) -> int:
    store = ProjectStore()
    project = _load(store, args.project_dir)
    if not project.state.steps:
        raise CliError("No run steps found. Run 'generate' first.", EXIT_USAGE)

    steps = _select_steps(project, args.steps)
    if not steps:
        print("No pending steps to run.")
        return EXIT_OK

    logs_dir = project.logs_dir()
    runfile_parallel = max(1, project.workflow.num_proc)
    plans = _prepare_plans(project, steps, logs_dir, runfile_parallel)

    if args.dry_run:
        for plan in plans:
            print(f"# {plan.label}")
            print(plan.command)
        return EXIT_OK

    project.state.status = ProjectStatus.RUNNING
    project.state.current_step = steps[0].name
    project.state.last_error = ""
    store.save(project)

    runner = HeadlessRunner(project.environment)
    final_code = EXIT_OK
    for plan in plans:
        print(f"=== {plan.label} ===")
        _mark_batch_started(project, plan)
        exit_code = runner.run(plan)
        _apply_batch_finished(project, plan, exit_code)
        store.save(project)
        if exit_code != 0:
            final_code = EXIT_COMMAND_FAILED
            print(
                f"Step failed: {plan.step_name} (exit {exit_code}). See {plan.log_path}",
                file=sys.stderr,
            )
            break

    if final_code == EXIT_OK:
        if all(item.status == StepStatus.SUCCESS for item in project.state.steps):
            project.state.status = ProjectStatus.COMPLETED
        else:
            project.state.status = ProjectStatus.GENERATED
        store.save(project)
        print("Run finished.")
    return final_code


# ----------------------------------------------------------------------
# status
# ----------------------------------------------------------------------
def _cmd_status(args: argparse.Namespace) -> int:
    store = ProjectStore()
    project = _load(store, args.project_dir)
    print(f"Project: {project.workspace.root_path()}")
    print(f"Status:  {project.state.status.value}")

    steps = project.state.steps
    if not steps:
        print("No run steps. Run 'generate' first.")
        return EXIT_OK

    rows = [("#", "STEP", "STATUS", "LOG")]
    rows.extend(
        (str(index), step.name, step.status.value, step.log_path or "-")
        for index, step in enumerate(steps, start=1)
    )
    widths = [max(len(row[col]) for row in rows) for col in range(3)]
    for row in rows:
        print("  ".join(row[col].ljust(widths[col]) for col in range(3)) + f"  {row[3]}")
    return EXIT_OK


# ----------------------------------------------------------------------
# Argument parsing / entry point
# ----------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="insar-pilot-cli",
        description="Headless InSAR-PILOT project workflows for servers and automation.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a new project workspace.")
    p_init.add_argument("dir", help="Project root directory to create.")
    p_init.add_argument(
        "--name", default="", help="Human-readable project name (defaults to the directory name)."
    )
    p_init.set_defaults(func=_cmd_init)

    p_generate = sub.add_parser("generate", help="Build and run the stackSentinel.py generation command.")
    p_generate.add_argument("project_dir", help="Existing project directory.")
    p_generate.add_argument(
        "--dry-run", action="store_true", help="Print the command and exit without running it."
    )
    p_generate.set_defaults(func=_cmd_generate)

    p_run = sub.add_parser("run", help="Execute generated run_files steps sequentially.")
    p_run.add_argument("project_dir", help="Existing project directory.")
    p_run.add_argument(
        "--steps",
        default="",
        help="Step selection: 'N' or 'A-B' (1-based). Default: all pending steps.",
    )
    p_run.add_argument(
        "--dry-run", action="store_true", help="Print the planned commands and exit without running them."
    )
    p_run.set_defaults(func=_cmd_run)

    p_status = sub.add_parser("status", help="Print the run-step status table.")
    p_status.add_argument("project_dir", help="Existing project directory.")
    p_status.set_defaults(func=_cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        result: int = args.func(args)
        return result
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":  # pragma: no cover - module executed as a script
    raise SystemExit(main())
