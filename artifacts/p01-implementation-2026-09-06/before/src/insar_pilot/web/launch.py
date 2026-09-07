"""Start or reuse the authenticated local workbench without importing Qt."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from insar_pilot.domain.engine import utc_now
from insar_pilot.infrastructure.engine_store import atomic_json
from insar_pilot.infrastructure.job_executor import process_identity


def open_browser(url: str) -> bool:
    """Use the Windows default browser from WSL without exposing the token in argv."""
    powershell = shutil.which("powershell.exe") if os.environ.get("WSL_DISTRO_NAME") else None
    if powershell:
        try:
            subprocess.run(
                [
                    powershell,
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "$taskLink = [Console]::In.ReadLine(); Start-Process -FilePath $taskLink -ErrorAction Stop",
                ],
                input=url + "\n",
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=15,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        return webbrowser.open(url)
    except webbrowser.Error:
        return False


def _alive(port: int, token: str) -> bool:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/v1/health", headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=1) as response:
            return bool(json.load(response).get("application") == "insar-pilot")
    except (OSError, ValueError, urllib.error.HTTPError):
        return False


def service_command(state: Path, *, stop: bool) -> int:
    """Inspect/stop an existing service; these commands never start one."""
    service_file = state / "service.json"
    if not service_file.exists():
        print("STOPPED — InSAR-PILOT Web is not running.")
        return 0
    config = json.loads(service_file.read_text())
    base = f"http://127.0.0.1:{config['port']}/api/v1/application"
    headers = {"Authorization": f"Bearer {config['token']}"}
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            urllib.request.Request(base + "/status", headers=headers), timeout=3
        ) as response:
            status = json.load(response)
    except urllib.error.HTTPError as exc:
        print(f"Unable to inspect the service (HTTP {exc.code}); it has not been stopped.")
        return 1
    except OSError:
        from insar_pilot.infrastructure.application_state import ApplicationState
        from insar_pilot.web.lifecycle import task_inventory

        inventory = task_inventory(ApplicationState(state))
        pid = config.get("pid")
        identity = process_identity(pid) if pid else None
        if identity and identity == config.get("process_start"):
            print("UNREACHABLE — the service process still exists. It is not confirmed stopped.")
            return 1
        if not inventory["can_exit"]:
            print("SERVICE OFFLINE — workers or unfinished task records remain. Restart the workbench to inspect them.")
            return 1
        print("STOPPED — no active application workers or tasks.")
        return 0
    if not stop:
        print(
            f"{status['state']} — {status['download_jobs']} download jobs, "
            f"{status['processing_jobs']} processing jobs, {status['worker_processes']} worker processes."
        )
        print("Closing the browser keeps the backend running. Exit the application with insar-pilot-web --stop.")
        return 0
    try:
        request = urllib.request.Request(base + "/shutdown", headers=headers, data=b"{}", method="POST")
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=5) as response:
            json.load(response)
    except urllib.error.HTTPError as exc:
        print(f"Not stopped: {json.load(exc).get('detail', 'Shutdown request rejected.')}")
        return 1
    except OSError:
        print("Exit is not confirmed. Check the backend with insar-pilot-web --status.")
        return 1
    pid = config.get("pid")
    identity = process_identity(pid) if pid else None
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not _alive(config["port"], config["token"]) and (not identity or process_identity(pid) != identity):
            print("STOPPED — InSAR-PILOT Web has exited.")
            return 0
        time.sleep(0.2)
    print("STOPPING — exit is not yet confirmed. Check again with insar-pilot-web --status.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="InSAR-PILOT local Web workbench (migration preview)")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--state", type=Path, default=Path.home() / ".local/state/insar-pilot")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--status", action="store_true", help="Show backend and task status without starting the service"
    )
    actions.add_argument("--stop", action="store_true", help="Exit the application when no tasks or workers are active")
    args = parser.parse_args()
    state = args.state.expanduser().resolve()
    if args.status or args.stop:
        return service_command(state, stop=args.stop)
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    service_file = state / "service.json"
    if args.serve:
        import uvicorn

        from insar_pilot.web.api import create_app

        config = json.loads(service_file.read_text())
        server: uvicorn.Server

        def request_exit() -> None:
            server.should_exit = True

        app = create_app(state, config["token"], request_exit=request_exit)
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=config["port"],
                access_log=False,
                log_level="warning",
            )
        )
        config.update(pid=os.getpid(), process_start=process_identity(os.getpid()), status="running")
        atomic_json(service_file, config)
        os.chmod(service_file, 0o600)
        try:
            server.run()
        finally:
            current = json.loads(service_file.read_text())
            if current.get("pid") == os.getpid():
                current.update(status="stopped", stopped_at=utc_now())
                atomic_json(service_file, current)
                os.chmod(service_file, 0o600)
        return 0
    with (state / "launch.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        config = json.loads(service_file.read_text()) if service_file.exists() else {}
        if not config or not _alive(config["port"], config["token"]):
            with socket.socket() as probe:
                try:
                    probe.bind(("127.0.0.1", args.port))
                except OSError:
                    probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            config = {"port": port, "token": secrets.token_urlsafe(32)}
            atomic_json(service_file, config)
            os.chmod(service_file, 0o600)
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
            with (state / "service.log").open("ab") as log:
                process = subprocess.Popen(
                    [sys.executable, "-m", "insar_pilot.web.launch", "--serve", "--state", str(state)],
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
            config.update(pid=process.pid, process_start=process_identity(process.pid))
            atomic_json(service_file, config)
            for _ in range(50):
                if _alive(port, config["token"]):
                    break
                if process.poll() is not None:
                    raise RuntimeError(f"Web service failed to start; see {state / 'service.log'}")
                time.sleep(0.2)
            else:
                raise RuntimeError("Local workbench startup timed out.")
    url = f"http://127.0.0.1:{config['port']}/"
    print(f"InSAR-PILOT Web: {url}")
    print("Closing the browser keeps the backend running. Use --status to check it, or --stop to exit when idle.")
    command = shlex.join(["insar-pilot-web", "--state", str(state)])
    print(f"Connect a new browser using: {command}")
    if not args.no_browser and not open_browser(f"{url}#token={config['token']}"):
        print("The service is running, but the browser could not be opened. Check your default browser or WSL interop.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
