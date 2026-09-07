"""Qt-free AOI search, manifest, access probe, and download orchestration for NISAR."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from insar_pilot.application.search import SearchApplicationService
from insar_pilot.domain.search import RemoteSARProduct, SearchPage, SearchRequest
from insar_pilot.download import session_auth
from insar_pilot.download.download_service import DownloadService
from insar_pilot.download.geometry import wkt_from_aoi_file
from insar_pilot.download.models import DownloadResult, DownloadTask, SceneRecord
from insar_pilot.download.network import NetworkConfig
from insar_pilot.providers.sar import build_default_sar_provider_registry

_SCHEMA_VERSION = 1
_HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"


@dataclass(frozen=True)
class NisarAcquisitionManifest:
    aoi_file: str
    aoi_wkt: str
    start_time: datetime
    end_time: datetime
    products: tuple[RemoteSARProduct, ...]
    provider_id: str = "asf-nisar"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "provider_id": self.provider_id,
            "aoi_file": self.aoi_file,
            "aoi_wkt": self.aoi_wkt,
            "start_time": _time_text(self.start_time),
            "end_time": _time_text(self.end_time),
            "products": [_product_to_dict(item) for item in self.products],
        }

    @classmethod
    def from_dict(cls, value: object) -> NisarAcquisitionManifest:
        if not isinstance(value, dict) or value.get("schema_version") != _SCHEMA_VERSION:
            raise ValueError("NISAR acquisition manifest schema is unsupported.")
        products = value.get("products")
        if not isinstance(products, list):
            raise TypeError("NISAR acquisition manifest products must be a list.")
        return cls(
            aoi_file=str(value.get("aoi_file", "")),
            aoi_wkt=str(value.get("aoi_wkt", "")),
            start_time=_parse_required_time(value.get("start_time")),
            end_time=_parse_required_time(value.get("end_time")),
            products=tuple(_product_from_dict(item) for item in products),
            provider_id=str(value.get("provider_id", "asf-nisar")),
        )


@dataclass(frozen=True)
class NisarDownloadAccessReport:
    accessible: bool
    hdf5_signature: bool
    range_supported: bool
    status_code: int | None
    message: str


class NisarAcquisitionService:
    """Coordinate NISAR-specific choices over mission-neutral boundaries."""

    def __init__(
        self,
        search_service: SearchApplicationService | None = None,
        download_service: DownloadService | None = None,
        *,
        network: NetworkConfig | None = None,
    ) -> None:
        self._network = network or NetworkConfig()
        self._search = search_service or SearchApplicationService(
            build_default_sar_provider_registry(network=self._network)
        )
        self._download = download_service or DownloadService()

    def search_aoi(
        self,
        aoi_file: str | Path,
        start_time: datetime,
        end_time: datetime,
        *,
        orbit_direction: str | None = None,
        path_number: int | None = None,
        frame: int | None = None,
        polarizations: tuple[str, ...] = (),
        frequency_bands: tuple[str, ...] = (),
        production_configuration: str = "PR",
        page: int = 1,
        page_size: int = 100,
    ) -> NisarAcquisitionManifest:
        source = Path(aoi_file).expanduser().resolve()
        aoi_wkt = wkt_from_aoi_file(source)
        options: dict[str, object] = {}
        if frame is not None:
            options["frame"] = frame
        if production_configuration.strip():
            options["production_configuration"] = production_configuration.strip().upper()
        request = SearchRequest(
            mission="NISAR",
            platforms=("NISAR",),
            product_type="RSLC",
            start_time=start_time,
            end_time=end_time,
            aoi_wkt=aoi_wkt,
            orbit_direction=orbit_direction,
            relative_orbit=path_number,
            polarizations=polarizations,
            frequency_bands=frequency_bands,
            page=page,
            page_size=page_size,
            provider_options={"asf-nisar": options},
        )
        page_result: SearchPage = self._search.search(request, provider_id="asf-nisar")
        return NisarAcquisitionManifest(
            aoi_file=str(source),
            aoi_wkt=aoi_wkt,
            start_time=start_time,
            end_time=end_time,
            products=page_result.items,
        )

    def create_download_tasks(
        self,
        manifest: NisarAcquisitionManifest,
        output_dir: str | Path,
        *,
        product_ids: tuple[str, ...] = (),
    ) -> list[DownloadTask]:
        selected = _select_products(manifest.products, product_ids)
        return list(self._download.create_rslc_tasks([_scene_from_product(item) for item in selected], output_dir))

    def download(
        self,
        manifest: NisarAcquisitionManifest,
        output_dir: str | Path,
        *,
        username: str = "",
        password: str = "",
        product_ids: tuple[str, ...] = (),
    ) -> list[DownloadResult]:
        tasks = self.create_download_tasks(manifest, output_dir, product_ids=product_ids)
        return self._download.download(
            tasks,
            username=username,
            password=password,
            network=self._network,
        )

    def probe_download_access(
        self,
        product: RemoteSARProduct,
        *,
        username: str,
        password: str,
    ) -> NisarDownloadAccessReport:
        """Read only the HDF5 signature from an authenticated product URL."""

        if not product.download_url:
            return NisarDownloadAccessReport(False, False, False, None, "Product has no download URL.")
        response = None
        try:
            session = session_auth.bulk_session(username, password, self._network)
            response = session.get(
                product.download_url,
                headers={"Range": "bytes=0-7"},
                stream=True,
                timeout=(self._network.timeout_seconds, 60),
            )
            response.raise_for_status()
            first = next(response.iter_content(chunk_size=8), b"")[:8]
            status = int(response.status_code)
            range_supported = status == 206 or bool(response.headers.get("content-range"))
            signature_ok = first == _HDF5_SIGNATURE
            return NisarDownloadAccessReport(
                signature_ok,
                signature_ok,
                range_supported,
                status,
                "Authenticated NISAR RSLC access succeeded." if signature_ok else "Response was not an HDF5 RSLC file.",
            )
        except Exception as exc:
            failure_status = int(response.status_code) if response is not None else None
            return NisarDownloadAccessReport(False, False, False, failure_status, f"NISAR access failed: {exc}")
        finally:
            if response is not None:
                response.close()

    @staticmethod
    def save_manifest(manifest: NisarAcquisitionManifest, path: str | Path) -> Path:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(manifest.to_dict(), ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except OSError:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise
        return target

    @staticmethod
    def load_manifest(path: str | Path) -> NisarAcquisitionManifest:
        source = Path(path).expanduser()
        return NisarAcquisitionManifest.from_dict(json.loads(source.read_text(encoding="utf-8")))


def _select_products(
    products: tuple[RemoteSARProduct, ...], product_ids: tuple[str, ...]
) -> tuple[RemoteSARProduct, ...]:
    if not product_ids:
        return products
    wanted = set(product_ids)
    selected = tuple(item for item in products if item.remote_product_id in wanted)
    missing = wanted.difference(item.remote_product_id for item in selected)
    if missing:
        raise KeyError(f"Manifest does not contain NISAR products: {', '.join(sorted(missing))}")
    return selected


def _scene_from_product(product: RemoteSARProduct) -> SceneRecord:
    metadata = product.provider_metadata
    file_name = str(metadata.get("file_name") or f"{product.remote_product_id}.h5")
    return SceneRecord(
        scene_id=product.remote_product_id,
        acquisition_time=_time_text(product.acquisition_time) if product.acquisition_time else "",
        platform="NISAR",
        orbit_direction=product.orbit_direction or "",
        relative_orbit=product.relative_orbit or 0,
        polarization="+".join(product.polarizations),
        size_mb=float(product.size_bytes or 0) / (1024 * 1024),
        download_url=product.download_url,
        file_name=file_name,
        footprint_geojson=dict(product.footprint),
    )


def _product_to_dict(product: RemoteSARProduct) -> dict[str, object]:
    return {
        "remote_product_id": product.remote_product_id,
        "provider_id": product.provider_id,
        "mission": product.mission,
        "platform": product.platform,
        "product_type": product.product_type,
        "acquisition_time": _time_text(product.acquisition_time) if product.acquisition_time else None,
        "orbit_direction": product.orbit_direction,
        "relative_orbit": product.relative_orbit,
        "polarizations": list(product.polarizations),
        "frequency_bands": list(product.frequency_bands),
        "footprint": dict(product.footprint),
        "size_bytes": product.size_bytes,
        "download_supported": product.download_supported,
        "download_url": product.download_url,
        "provider_metadata": dict(product.provider_metadata),
    }


def _product_from_dict(value: object) -> RemoteSARProduct:
    if not isinstance(value, dict):
        raise TypeError("Manifest product must be an object.")
    acquired = value.get("acquisition_time")
    return RemoteSARProduct(
        remote_product_id=str(value.get("remote_product_id", "")),
        provider_id=str(value.get("provider_id", "")),
        mission=str(value.get("mission", "")),
        platform=str(value.get("platform", "")),
        product_type=str(value.get("product_type", "")),
        acquisition_time=_parse_required_time(acquired) if acquired else None,
        orbit_direction=str(value["orbit_direction"]) if value.get("orbit_direction") else None,
        relative_orbit=int(value["relative_orbit"]) if value.get("relative_orbit") is not None else None,
        polarizations=tuple(str(item) for item in value.get("polarizations", [])),
        frequency_bands=tuple(str(item) for item in value.get("frequency_bands", [])),
        footprint=dict(value.get("footprint", {})),
        size_bytes=int(value["size_bytes"]) if value.get("size_bytes") is not None else None,
        download_supported=bool(value.get("download_supported", False)),
        download_url=str(value.get("download_url", "")),
        provider_metadata=dict(value.get("provider_metadata", {})),
    )


def _time_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _parse_required_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("Manifest time must be an ISO-8601 string.")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


__all__ = [
    "NisarAcquisitionManifest",
    "NisarAcquisitionService",
    "NisarDownloadAccessReport",
]
