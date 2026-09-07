"""Bounded, process-identity-checked shutdown for local download attempts."""

from __future__ import annotations

import argparse
import fcntl
import os
import signal
import time
from contextlib import suppress
from pathlib import Path

from insar_pilot.domain.engine import digest, utc_now
from insar_pilot.infrastructure.application_state import ApplicationState


def process_state(pid: int) -> tuple[str, int, str] | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        return fields[0], int(fields[2]), fields[19]
    except (OSError, IndexError, ValueError):
        return None


def workers(app: ApplicationState, job_id: str) -> dict[int, str]:
    found = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            args = (entry / "cmdline").read_bytes().rstrip(b"\0").split(b"\0")
            expected = [b"-m", b"insar_pilot.application.engine_download", os.fsencode(app.root), job_id.encode()]
            state = process_state(int(entry.name))
            if args[1:] == expected and state and state[1] == int(entry.name) and state[0] != "Z":
                found[int(entry.name)] = state[2]
        except OSError:
            continue
    return found


def group_alive(pid: int, start: str) -> bool:
    leader = process_state(pid)
    if leader and leader[2] != start:
        raise RuntimeError("Download worker identity changed; refusing to signal a reused process ID.")
    return any(
        state and state[1] == pid and state[0] != "Z"
        for entry in Path("/proc").iterdir()
        if entry.name.isdigit()
        for state in [process_state(int(entry.name))]
    )


def signal_group(pid: int, start: str, signum: int) -> None:
    if group_alive(pid, start):
        with suppress(ProcessLookupError):
            os.killpg(pid, signum)


def stop_worker(app: ApplicationState, job_id: str) -> None:
    # Multiple clicks or API retries may spawn observers; only one owns shutdown.
    with (app.root / "library" / "partial" / f"control-{digest(job_id)}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        job = app.download(job_id)
        if not job.get("cancel_requested"):
            return
        identities = workers(app, job_id)
        started = time.monotonic()
        sent_term = sent_kill = False
        while any(group_alive(pid, start) for pid, start in identities.items()):
            elapsed = time.monotonic() - started
            if elapsed >= 8 and not sent_kill:
                for pid, start in identities.items():
                    signal_group(pid, start, signal.SIGKILL)
                sent_kill = True
            elif elapsed >= 3 and not sent_term:
                for pid, start in identities.items():
                    signal_group(pid, start, signal.SIGTERM)
                sent_term = True
            if elapsed >= 12:
                # Keep the pending state truthful; a repeated request can retry observation.
                return
            time.sleep(0.2)
        job = app.download(job_id)
        if job["status"] in {"QUEUED", "RUNNING"}:
            job.update(
                status="CANCELLED",
                finished_at=utc_now(),
                message="Transfer stopped; downloaded files and resume data were retained.",
            )
            app.save_download(job)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("state", type=Path)
    parser.add_argument("job_id")
    args = parser.parse_args()
    stop_worker(ApplicationState(args.state), args.job_id)
