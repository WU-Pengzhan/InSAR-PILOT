"""Precise Sentinel A/B/C/D orbits from the public ASF S3 archive."""

from __future__ import annotations

import fcntl
import hashlib
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from insar_pilot.download.integrity import quarantine, receipt_path
from insar_pilot.download.models import DownloadResult, DownloadTask, SceneRecord
from insar_pilot.download.network import NetworkConfig
from insar_pilot.download.task_state import result_from_task
from insar_pilot.infrastructure.engine_store import atomic_json

ProgressCallback = Callable[[DownloadTask], None]
CancelCheck = Callable[[], bool]


class OrbitDownloadService:
    BASE_URL = "https://s1-orbits.s3.amazonaws.com"
    NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

    @staticmethod
    def _mission(scene: SceneRecord) -> str:
        identities = set()
        for value in (scene.scene_id, scene.file_name, scene.platform):
            match = re.match(r"^(?:S1|SENTINEL[- ]?1)([ABCD])(?:_|$)", value.upper())
            if match:
                identities.add(f"S1{match[1]}")
        if len(identities) != 1:
            raise ValueError("A unique Sentinel-1 A/B/C/D identity is required for orbit acquisition.")
        return identities.pop()

    @staticmethod
    def _scene_datetime(scene: SceneRecord) -> datetime:
        return datetime.fromisoformat(scene.acquisition_time.replace("Z", "+00:00")).replace(tzinfo=None)

    @classmethod
    def _scene_interval(cls, scene: SceneRecord) -> tuple[datetime, datetime]:
        matches = re.findall(r"(?<!\d)(\d{8}T\d{6})(?!\d)", scene.scene_id or scene.file_name)
        if len(matches) >= 2:
            return tuple(datetime.strptime(v, "%Y%m%dT%H%M%S") for v in matches[:2])  # type: ignore[return-value]
        # A start-only catalogue record is insufficient for an exact EOF match.
        raise ValueError("SLC start and stop times are required to match a precise orbit.")

    @staticmethod
    def _orbit_name_matches(name: str, acquisition: datetime, stop: datetime | None = None) -> bool:
        match = re.search(r"_V(\d{8}T\d{6})_(\d{8}T\d{6})\.EOF$", name)
        if not match:
            return False
        start, end = (datetime.strptime(v, "%Y%m%dT%H%M%S") for v in match.groups())
        return start <= acquisition.replace(tzinfo=None) and (stop or acquisition).replace(tzinfo=None) <= end

    @classmethod
    def validate(cls, path: Path, scene: SceneRecord) -> None:
        mission = cls._mission(scene)
        start, stop = cls._scene_interval(scene)
        name = path.name.removesuffix(".part")
        if not name.startswith(f"{mission}_OPER_AUX_POEORB_") or not cls._orbit_name_matches(name, start, stop):
            raise ValueError("EOF filename does not match satellite, precise orbit type and full SLC interval.")
        if path.stat().st_size > 32 * 1024**2:
            raise ValueError("EOF exceeds the metadata size limit.")
        try:
            root = ET.parse(path).getroot()
            values = {node.tag.split("}")[-1]: (node.text or "").strip() for node in root.iter()}
            xml_mission = re.sub(r"[^A-Z0-9]", "", values.get("Mission", "").upper()).replace("SENTINEL", "S")
            if xml_mission != mission or values.get("File_Type") != "AUX_POEORB":
                raise ValueError("EOF XML mission/type mismatch.")

            def date(key: str) -> datetime:
                return datetime.fromisoformat(values[key].removeprefix("UTC=").replace("Z", "+00:00")).replace(
                    tzinfo=None
                )

            if date("Validity_Start") > start or date("Validity_Stop") < stop:
                raise ValueError("EOF XML validity does not cover the complete SLC interval.")
            osv = [node for node in root.iter() if node.tag.split("}")[-1] == "OSV"]
            if len(osv) < 2:
                raise ValueError("EOF has insufficient orbit state vectors.")
            dates = []
            for vector in osv:
                fields = {n.tag.split("}")[-1]: n.text or "" for n in vector}
                dates.append(datetime.fromisoformat(fields["UTC"].removeprefix("UTC=")).replace(tzinfo=None))
                for field in ("X", "Y", "Z", "VX", "VY", "VZ"):
                    if not __import__("math").isfinite(float(fields[field])):
                        raise ValueError("EOF contains a non-finite state vector.")
            if min(dates) > start or max(dates) < stop or dates != sorted(set(dates)):
                raise ValueError("EOF state vectors do not span the acquisition in time order.")
            atomic_json(
                receipt_path(path),
                {
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                    "checks": ["precise_orbit", "satellite", "xml", "validity_interval", "state_vectors"],
                    "mission": mission,
                },
            )
        except (ET.ParseError, KeyError) as exc:
            raise ValueError("EOF XML is incomplete or malformed.") from exc

    @classmethod
    def _existing_orbit_file(cls, orbit_dir: Path, scene: SceneRecord) -> Path | None:
        for path in sorted(orbit_dir.glob(f"{cls._mission(scene)}_OPER_AUX_POEORB_*.EOF"), reverse=True):
            start, stop = cls._scene_interval(scene)
            if not cls._orbit_name_matches(path.name, start, stop):
                continue
            try:
                cls.validate(path, scene)
                return path
            except (ValueError, OSError):
                quarantine(path)
        return None

    def candidates(
        self, scene: SceneRecord, network: NetworkConfig, cache: Path, cancel_check: CancelCheck | None = None
    ) -> list[str]:
        import json

        mission = self._mission(scene)
        cache_file = cache / f"{mission}-precise-catalog.json"
        keys: list[str] = []
        if cache_file.exists() and time.time() - cache_file.stat().st_mtime < 3600:
            keys = json.loads(cache_file.read_text())
        else:
            token = ""
            with network.session() as session:
                for _page in range(30):
                    if cancel_check and cancel_check():
                        raise InterruptedError("Orbit catalogue lookup cancelled.")
                    params = {"list-type": "2", "prefix": f"AUX_POEORB/{mission}_", "max-keys": "1000"}
                    if token:
                        params["continuation-token"] = token
                    with session.get(self.BASE_URL, params=params, timeout=(network.timeout_seconds, 30)) as response:
                        response.raise_for_status()
                        tree = ET.fromstring(response.content)
                    keys.extend(n.text or "" for n in tree.findall(f"{self.NS}Contents/{self.NS}Key"))
                    token = tree.findtext(f"{self.NS}NextContinuationToken", "")
                    if not token:
                        break
                else:
                    raise ValueError("Orbit catalogue exceeds the bounded lookup limit.")
            atomic_json(cache_file, keys)
        start, stop = self._scene_interval(scene)
        return sorted((key for key in keys if self._orbit_name_matches(key, start, stop)), reverse=True)

    def download(
        self,
        task: DownloadTask,
        *,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
        network: NetworkConfig | None = None,
    ) -> DownloadResult:
        folder = Path(task.output_dir) / "Orbit"
        folder.mkdir(parents=True, exist_ok=True)
        # Several scenes can share one EOF; serialize cache/publication for the mission.
        try:
            with (folder / f"{self._mission(task.scene)}.lock").open("a") as lock:
                while True:
                    if cancel_check and cancel_check():
                        return result_from_task(task.with_updates(status="cancelled", message="Orbit wait cancelled."))
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        time.sleep(0.2)
                return self._download(
                    task, progress_callback=progress_callback, cancel_check=cancel_check, network=network
                )
        except ValueError as exc:
            return result_from_task(task.with_updates(status="failed", message=str(exc)))

    def _download(
        self,
        task: DownloadTask,
        *,
        progress_callback: ProgressCallback | None = None,
        cancel_check: CancelCheck | None = None,
        network: NetworkConfig | None = None,
    ) -> DownloadResult:
        network = network or NetworkConfig()
        folder = Path(task.output_dir) / "Orbit"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if cancel_check and cancel_check():
                raise InterruptedError("Orbit download cancelled.")
            existing = self._existing_orbit_file(folder, task.scene)
            if existing:
                return result_from_task(
                    task.with_updates(
                        status="skipped",
                        local_path=str(existing),
                        bytes_total=existing.stat().st_size,
                        bytes_done=existing.stat().st_size,
                        message="Precise EOF satellite, XML and validity verified locally.",
                    )
                )
            if progress_callback:
                progress_callback(task.with_updates(status="running", message="Resolving precise EOF from ASF..."))
            keys = self.candidates(task.scene, network, folder, cancel_check)
            if not keys:
                return result_from_task(
                    task.with_updates(
                        status="unavailable",
                        message="Precise EOF is not available for this satellite and interval. Retry later.",
                    )
                )
            key = keys[0]
            path = folder / Path(key).name
            part = folder / ".partial" / (path.name + ".part")
            part.parent.mkdir(exist_ok=True)
            with (
                network.session() as session,
                session.get(f"{self.BASE_URL}/{key}", stream=True, timeout=(network.timeout_seconds, 30)) as response,
            ):
                response.raise_for_status()
                expected = int(response.headers.get("Content-Length", 0))
                done = 0
                with part.open("wb") as stream:
                    for block in response.iter_content(256 * 1024):
                        if cancel_check and cancel_check():
                            raise InterruptedError("Orbit download cancelled.")
                        done += len(block)
                        if done > 32 * 1024**2:
                            raise ValueError("EOF exceeds the metadata size limit.")
                        stream.write(block)
                        if progress_callback:
                            progress_callback(
                                task.with_updates(status="running", bytes_done=done, bytes_total=expected)
                            )
                if expected and done != expected:
                    raise ValueError("EOF byte count mismatch.")
            self.validate(part, task.scene)
            part.replace(path)
            receipt_path(path).parent.mkdir(exist_ok=True)
            receipt_path(part).replace(receipt_path(path))
            result = task.with_updates(
                status="completed",
                local_path=str(path),
                bytes_total=done,
                bytes_done=done,
                message="Precise EOF identity, XML and full acquisition interval verified.",
            )
        except InterruptedError as exc:
            result = task.with_updates(status="cancelled", message=str(exc))
        except Exception as exc:
            result = task.with_updates(
                status="failed", message=f"Precise EOF acquisition failed: {type(exc).__name__}: {exc}"
            )
        if progress_callback:
            progress_callback(result)
        return result_from_task(result)
