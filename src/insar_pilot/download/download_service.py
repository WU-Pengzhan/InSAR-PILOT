"""SLC download orchestration for GUI-native Sentinel-1 data preparation.

``DownloadService`` owns the sequential download loop (retry/skip/cancel policy)
and the aria2c subprocess handling. Cohesive sub-concerns live in sibling modules:
``task_state`` (pure result/telemetry helpers), ``session_auth`` (ASF/Earthdata
session + cookie flow) and ``orbit_service`` (EOF orbit downloads).

The aria2c invocation deliberately stays here: the test suite monkeypatches
``insar_pilot.download.download_service.shutil.which`` and
``insar_pilot.download.download_service.subprocess.Popen``, so ``shutil`` and
``subprocess`` must remain module-level imports resolved through this module, and
``_safe_subprocess_excerpt`` is exercised as ``DownloadService._safe_subprocess_excerpt``.
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import asf_search as asf
import requests

from insar_pilot.download import session_auth, task_state
from insar_pilot.download.models import DownloadResult, DownloadTask, SceneRecord
from insar_pilot.download.network import NetworkConfig
from insar_pilot.download.orbit_service import OrbitDownloadService

ProgressCallback = Callable[[DownloadTask], None]
CancelCheck = Callable[[], bool]


class DownloadService:
    """Create and run SLC/EOF download tasks."""

    def __init__(self, orbit_service: OrbitDownloadService | None = None, *, max_retries: int = 2) -> None:
        self.orbit_service = orbit_service or OrbitDownloadService()
        self.max_retries = max(0, int(max_retries))

    def create_tasks(
        self,
        scenes: list[SceneRecord],
        output_dir: str | Path,
        *,
        include_orbits: bool = True,
    ) -> list[DownloadTask]:
        """Create pending SLC tasks and optional precise orbit placeholders."""

        target = Path(output_dir).expanduser()
        tasks: list[DownloadTask] = []
        for index, scene in enumerate(scenes):
            slc_path = task_state.slc_path(target, scene)
            tasks.append(
                DownloadTask(
                    task_id=f"slc-{index + 1:03d}",
                    scene=scene,
                    output_dir=str(target),
                    product_type="SLC",
                    local_path=str(slc_path),
                    url=scene.download_url,
                )
            )
            if include_orbits:
                tasks.append(
                    DownloadTask(
                        task_id=f"orbit-{index + 1:03d}",
                        scene=scene,
                        output_dir=str(target),
                        product_type="ORBIT",
                        local_path=str(target / "Orbit" / f"{scene.scene_id}.EOF"),
                    )
                )
        return tasks

    def download(
        self,
        tasks: list[DownloadTask],
        *,
        username: str = "",
        password: str = "",
        network: NetworkConfig | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> list[DownloadResult]:
        """Run tasks sequentially and return final task outcomes."""

        network = network or NetworkConfig()
        session: requests.Session | None = None
        result_by_task_id: dict[str, DownloadResult] = {}
        slc_status_by_scene: dict[str, str] = {}
        retry_tasks: list[DownloadTask] = []
        deferred_orbits: list[DownloadTask] = []

        for task in tasks:
            product_type = task.product_type.upper()
            if product_type == "DEM":
                continue
            if cancel_check and cancel_check():
                result = self._result_from_task(task.with_updates(status="cancelled", message="Download cancelled."))
                result_by_task_id[task.task_id] = result
                if progress_callback:
                    progress_callback(task.with_updates(status=result.status, message=result.message))
                continue

            if product_type == "SLC":
                if session is None:
                    session = self._create_session(username, password, network)
                result = self._download_slc(task, session, network, progress_callback, cancel_check)
                slc_status_by_scene[task.scene.scene_id] = result.status
                result_by_task_id[task.task_id] = result
                if task_state.is_retryable_slc_failure(result):
                    retry_tasks.append(task)
            elif product_type == "ORBIT":
                slc_status = slc_status_by_scene.get(task.scene.scene_id)
                if slc_status == "failed" and task.scene.scene_id in {
                    retry_task.scene.scene_id for retry_task in retry_tasks
                }:
                    deferred_orbits.append(task)
                    continue
                if slc_status and slc_status not in {"completed", "skipped"}:
                    skipped = task.with_updates(
                        status="skipped",
                        message=f"Orbit skipped because SLC task ended as {slc_status}.",
                    )
                    if progress_callback:
                        progress_callback(skipped)
                    result = self._result_from_task(skipped)
                else:
                    result = self.orbit_service.download(
                        task, progress_callback=progress_callback, cancel_check=cancel_check
                    )
            else:
                result = self._result_from_task(task.with_updates(status="failed", message="Unknown product type."))
            result_by_task_id[task.task_id] = result

        if retry_tasks and not (cancel_check and cancel_check()):
            session = session or self._create_session(username, password, network)
            for attempt_index in range(1, self.max_retries + 1):
                if not retry_tasks or (cancel_check and cancel_check()):
                    break
                next_retry_tasks: list[DownloadTask] = []
                for task in retry_tasks:
                    if cancel_check and cancel_check():
                        cancelled = task.with_updates(status="cancelled", message="Download cancelled before retry.")
                        if progress_callback:
                            progress_callback(cancelled)
                        result = self._result_from_task(cancelled)
                        result_by_task_id[task.task_id] = result
                        slc_status_by_scene[task.scene.scene_id] = result.status
                        continue
                    retry_notice = task.with_updates(
                        status="running",
                        message=(
                            f"Retrying SLC download (attempt {attempt_index + 1}/{self.max_retries + 1})..."
                        ),
                    )
                    if progress_callback:
                        progress_callback(retry_notice)
                    result = self._download_slc(task, session, network, progress_callback, cancel_check)
                    result_by_task_id[task.task_id] = result
                    slc_status_by_scene[task.scene.scene_id] = result.status
                    if task_state.is_retryable_slc_failure(result):
                        next_retry_tasks.append(task)
                retry_tasks = next_retry_tasks

        for orbit_task in deferred_orbits:
            slc_status = slc_status_by_scene.get(orbit_task.scene.scene_id, "failed")
            if cancel_check and cancel_check():
                cancelled = orbit_task.with_updates(
                    status="cancelled", message="Download cancelled before orbit download."
                )
                if progress_callback:
                    progress_callback(cancelled)
                result_by_task_id[orbit_task.task_id] = self._result_from_task(cancelled)
                continue
            if slc_status in {"completed", "skipped"}:
                result_by_task_id[orbit_task.task_id] = self.orbit_service.download(
                    orbit_task,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                )
            else:
                skipped = orbit_task.with_updates(
                    status="skipped",
                    message=f"Orbit skipped because paired SLC task ended as {slc_status} after retries.",
                )
                if progress_callback:
                    progress_callback(skipped)
                result_by_task_id[orbit_task.task_id] = self._result_from_task(skipped)

        return [
            result_by_task_id[task.task_id]
            for task in tasks
            if task.product_type.upper() != "DEM" and task.task_id in result_by_task_id
        ]

    @staticmethod
    def _session(username: str = "", password: str = "", network: NetworkConfig | None = None) -> requests.Session:
        """Create the authenticated SLC download session.

        Kept as a narrow hook for tests and ASF/Earthdata cookie preparation.
        """

        return session_auth.bulk_session(username, password, network)

    def _create_session(self, username: str, password: str, network: NetworkConfig) -> requests.Session:
        try:
            return self._session(username, password, network)
        except TypeError:
            return self._session(username, password)

    @staticmethod
    def _obtain_asf_cookie(
        session: requests.Session,
        cookie_jar: MozillaCookieJar,
        username: str,
        password: str,
        network: NetworkConfig,
        auth_url: str = "",
    ) -> None:
        """Authenticate like ASF bulk-download scripts and persist cookies."""

        session_auth.obtain_asf_cookie(session, cookie_jar, username, password, network, auth_url=auth_url)

    def _download_slc(
        self,
        task: DownloadTask,
        session: requests.Session,
        network: NetworkConfig,
        progress_callback: ProgressCallback | None,
        cancel_check: CancelCheck | None,
    ) -> DownloadResult:
        final_path = Path(task.local_path).expanduser()
        final_path.parent.mkdir(parents=True, exist_ok=True)
        part_path = final_path.with_suffix(final_path.suffix + ".part")

        if final_path.is_file() and final_path.stat().st_size > 0:
            scene = task.scene.with_status("downloaded", final_path)
            skipped = task.with_updates(
                status="skipped",
                local_path=str(final_path),
                bytes_total=final_path.stat().st_size,
                bytes_done=final_path.stat().st_size,
                backend="existing",
                message="File already exists; skipped.",
            )
            if progress_callback:
                progress_callback(skipped)
            return self._result_from_task(skipped, scene=scene)

        url = task.url or self._resolve_scene_url(task.scene, network)
        if not url:
            failed = task.with_updates(status="failed", message="No ASF download URL was available for this scene.")
            if progress_callback:
                progress_callback(failed)
            return self._result_from_task(failed)

        aria2c = shutil.which("aria2c")
        if not aria2c:
            failed = task.with_updates(
                status="failed",
                url=url,
                local_path=str(part_path),
                backend="aria2",
                message="aria2c is required for SLC download but was not found on PATH.",
            )
            if progress_callback:
                progress_callback(failed)
            return self._result_from_task(failed)

        running = task.with_updates(
            status="running",
            url=url,
            local_path=str(part_path),
            bytes_done=part_path.stat().st_size if part_path.exists() else 0,
            backend="aria2",
            message=f"Preparing ASF authentication for aria2c download: {part_path}",
        )
        if progress_callback:
            progress_callback(running)

        try:
            total = self._preflight_slc_for_aria2(session, url, network)
            return self._download_slc_with_aria2(
                task,
                aria2c,
                session,
                network,
                url,
                final_path,
                part_path,
                total,
                progress_callback,
                cancel_check,
            )
        except Exception as exc:
            failed = task.with_updates(
                status="failed",
                url=url,
                local_path=str(part_path if part_path.exists() else final_path),
                backend="aria2",
                message=f"SLC download failed: {exc}",
            )
            if progress_callback:
                progress_callback(failed)
            return self._result_from_task(failed)

    def _preflight_slc_for_aria2(self, session: requests.Session, url: str, network: NetworkConfig) -> int:
        response = self._open_slc_response(session, url, network)
        try:
            response.raise_for_status()
            return int(response.headers.get("content-length", "0") or 0)
        finally:
            with contextlib.suppress(Exception):
                response.close()

    def _download_slc_with_aria2(
        self,
        task: DownloadTask,
        aria2c: str,
        session: requests.Session,
        network: NetworkConfig,
        url: str,
        final_path: Path,
        part_path: Path,
        total: int,
        progress_callback: ProgressCallback | None,
        cancel_check: CancelCheck | None,
    ) -> DownloadResult:
        cookie_path = self._cookie_file_for_aria2(session)
        command = [
            aria2c,
            "--continue=true",
            "--max-tries=1",
            "--allow-overwrite=true",
            "--auto-file-renaming=false",
            "--console-log-level=warn",
            "--summary-interval=1",
            "--show-console-readout=false",
            "--max-connection-per-server=4",
            "--split=4",
            "--min-split-size=1M",
            "--connect-timeout",
            str(max(int(network.timeout_seconds), 1)),
            "--timeout",
            "60",
            "--dir",
            str(part_path.parent),
            "--out",
            part_path.name,
        ]
        command.extend(self._aria2_network_args(network))
        if cookie_path:
            command.extend(["--load-cookies", cookie_path])
        command.append(url)

        started = time.monotonic()
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(  # noqa: S603 - command is an argv list and shell is not used.
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False,
            )
        except Exception as exc:
            if cookie_path:
                Path(cookie_path).unlink(missing_ok=True)
            raise RuntimeError(f"could not start aria2c: {exc}") from exc

        last_emit = 0.0
        try:
            while process.poll() is None:
                if cancel_check and cancel_check():
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    done = part_path.stat().st_size if part_path.exists() else 0
                    cancelled = task.with_updates(
                        status="cancelled",
                        url=url,
                        local_path=str(part_path),
                        bytes_total=total,
                        bytes_done=done,
                        speed_bps=task_state.speed_bps(done, started),
                        eta_seconds=None,
                        backend="aria2",
                        message=f"Download cancelled; partial file kept at {part_path}.",
                    )
                    if progress_callback:
                        progress_callback(cancelled)
                    return self._result_from_task(cancelled)
                now = time.monotonic()
                if progress_callback and now - last_emit >= 0.5:
                    done = part_path.stat().st_size if part_path.exists() else 0
                    speed = task_state.speed_bps(done, started)
                    progress_callback(
                        task.with_updates(
                            status="running",
                            url=url,
                            local_path=str(part_path),
                            bytes_total=total,
                            bytes_done=done,
                            speed_bps=speed,
                            eta_seconds=task_state.eta_seconds(done, total, speed),
                            backend="aria2",
                            message="Downloading SLC with aria2c...",
                        )
                    )
                    last_emit = now
                time.sleep(0.1)
            stdout, stderr = process.communicate()
        finally:
            if cookie_path:
                Path(cookie_path).unlink(missing_ok=True)

        if process.returncode != 0:
            detail = self._safe_subprocess_excerpt(stderr or stdout)
            raise RuntimeError(f"aria2c exited with status {process.returncode}" + (f": {detail}" if detail else "."))
        if not part_path.exists() or part_path.stat().st_size <= 0:
            raise RuntimeError("aria2c completed without producing a partial SLC file.")

        part_path.replace(final_path)
        scene = task.scene.with_status("downloaded", final_path)
        completed = task.with_updates(
            status="completed",
            url=url,
            local_path=str(final_path),
            bytes_total=final_path.stat().st_size,
            bytes_done=final_path.stat().st_size,
            speed_bps=0.0,
            eta_seconds=0.0,
            backend="aria2",
            message="SLC download completed with aria2c.",
        )
        if progress_callback:
            progress_callback(completed)
        return self._result_from_task(completed, scene=scene)

    @staticmethod
    def _aria2_network_args(network: NetworkConfig) -> list[str]:
        mode = network.normalized_mode()
        if mode == "direct":
            return ["--all-proxy="]
        if mode == "manual":
            args: list[str] = []
            proxies = network.proxy_dict()
            if proxies.get("http"):
                args.extend(["--http-proxy", proxies["http"]])
            if proxies.get("https"):
                args.extend(["--https-proxy", proxies["https"]])
            return args
        return []

    @staticmethod
    def _cookie_file_for_aria2(session: requests.Session) -> str:
        cookies = getattr(session, "cookies", None)
        if not cookies:
            return ""
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, prefix="isce2_aria2_", suffix=".cookies"
        ) as temp:
            path = temp.name
        try:
            jar = MozillaCookieJar(path)
            for cookie in cookies:
                jar.set_cookie(cookie)
            jar.save(ignore_discard=True, ignore_expires=True)
        except Exception:
            Path(path).unlink(missing_ok=True)
            return ""
        return path

    @staticmethod
    def _safe_subprocess_excerpt(text: str) -> str:
        cleaned = " ".join((text or "").strip().split())
        if not cleaned:
            return ""
        for marker in ("Authorization:", "Cookie:", "password=", "passwd="):
            index = cleaned.lower().find(marker.lower())
            if index >= 0:
                cleaned = cleaned[:index] + f"{marker} [redacted]"
        return cleaned[:240]

    def _open_slc_response(
        self,
        session: requests.Session,
        url: str,
        network: NetworkConfig,
    ) -> requests.Response:
        response = session.get(url, stream=True, timeout=(network.timeout_seconds, 60))
        if not self._needs_earthdata_reauth(response):
            return response

        username = str(getattr(session, "_earthdata_username", "") or "").strip()
        password = str(getattr(session, "_earthdata_password", "") or "")
        if not username or not password:
            raise RuntimeError(
                "ASF redirected the SLC request to Earthdata login. "
                "Enter and test Earthdata credentials before downloading."
            )

        with contextlib.suppress(Exception):
            response.close()
        cookie_jar = getattr(session, "_asf_cookie_jar", None)
        if cookie_jar is None:
            cookie_jar = session.cookies
        self._obtain_asf_cookie(
            session,
            cookie_jar,
            username,
            password,
            network,
            auth_url=response.url,
        )
        return session.get(url, stream=True, timeout=(network.timeout_seconds, 60))

    @staticmethod
    def _needs_earthdata_reauth(response: requests.Response) -> bool:
        final_url = getattr(response, "url", "") or ""
        status = int(getattr(response, "status_code", 0) or 0)
        return status in {401, 403} and "urs.earthdata.nasa.gov/oauth/authorize" in final_url

    @staticmethod
    def _resolve_scene_url(scene: SceneRecord, network: NetworkConfig | None = None) -> str:
        network = network or NetworkConfig()
        session = asf.ASFSession()
        if network.normalized_mode() == "direct":
            session.trust_env = False
        elif network.normalized_mode() == "manual":
            session.trust_env = False
            session.proxies.update(network.proxy_dict())
        options = asf.ASFSearchOptions(session=session)
        results = asf.granule_search([scene.scene_id], opts=options)
        if not results:
            return ""
        product = results[0]
        props = dict(getattr(product, "properties", {}) or {})
        for key in ("url", "downloadUrl", "downloadURL"):
            if props.get(key):
                return str(props[key])
        try:
            urls = product.get_urls()
        except Exception:
            return ""
        return str(urls[0]) if urls else ""

    @staticmethod
    def _result_from_task(task: DownloadTask, *, scene: SceneRecord | None = None) -> DownloadResult:
        return task_state.result_from_task(task, scene=scene)
