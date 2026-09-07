"""Immutable, mission-neutral models for local SAR products."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import TypeAlias, cast

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


def _normalize_mission(value: str) -> str:
    normalized = value.strip().upper().replace("_", "-")
    if normalized in {"S1", "SENTINEL1", "SENTINEL-1"}:
        return "SENTINEL-1"
    return normalized


def _normalize_platform(value: str) -> str:
    normalized = value.strip().upper().replace("_", "-")
    aliases = {
        "S1A": "SENTINEL-1A",
        "S1B": "SENTINEL-1B",
        "S1C": "SENTINEL-1C",
        "S1D": "SENTINEL-1D",
        "SENTINEL1A": "SENTINEL-1A",
        "SENTINEL1B": "SENTINEL-1B",
        "SENTINEL1C": "SENTINEL-1C",
        "SENTINEL1D": "SENTINEL-1D",
    }
    return aliases.get(normalized, normalized)


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def _optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def _optional_non_negative(value: int | None, field_name: str) -> int | None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise ValueError(f"{field_name} must be a non-negative integer when provided.")
    return value


def _normalize_datetime(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone.")
    return value.astimezone(timezone.utc)


def _datetime_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be an ISO-8601 string.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid ISO-8601 datetime.") from exc
    return _normalize_datetime(parsed, field_name)


def _freeze_json(value: object, path: str = "$") -> JsonValue:
    """Validate and deeply freeze a JSON-compatible value."""

    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Native metadata contains a non-finite number at {path}.")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, JsonValue] = {}
        keys = tuple(value)
        if any(not isinstance(key, str) for key in keys):
            raise TypeError(f"Native metadata key at {path} must be a string.")
        for key in sorted(key for key in keys if isinstance(key, str)):
            frozen[key] = _freeze_json(value[key], f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, f"{path}[{index}]") for index, item in enumerate(value))
    raise TypeError(f"Native metadata value at {path} is not JSON-compatible: {type(value).__name__}.")


def _json_ready(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _json_ready(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping.")
    for key in value:
        if not isinstance(key, str):
            raise TypeError(f"{field_name} keys must be strings.")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a sequence.")
    return value


def stable_product_id(mission: str, product_type: str, native_product_id: str) -> str:
    """Build a path-independent ID from a validated mission-native product ID."""

    normalized_mission = _normalize_mission(_required_text(mission, "mission"))
    normalized_type = _required_text(product_type, "product_type").upper()
    native_id = _required_text(native_product_id, "native_product_id")
    if any(character in native_id for character in "\r\n\0"):
        raise ValueError("native_product_id cannot contain control line characters.")
    return f"{normalized_mission}:{normalized_type}:{native_id}"


class ReaderSourceKind(str, Enum):
    """Physical source shapes understood by local product readers."""

    FILE = "file"
    DIRECTORY = "directory"


@dataclass(frozen=True)
class AssetRef:
    """Serializable reference to a file or to one HDF5 subdataset."""

    uri: str
    role: str
    subdataset: str | None = None
    media_type: str = "application/octet-stream"
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        uri = _required_text(self.uri, "Asset URI")
        role = _required_text(self.role, "Asset role").lower()
        media_type = _required_text(self.media_type, "Asset media type").lower()
        subdataset = _optional_text(self.subdataset)
        if not _IDENTIFIER_PATTERN.fullmatch(role):
            raise ValueError(f"Asset role is not a stable identifier: {role}")
        if subdataset is not None and not subdataset.startswith("/"):
            raise ValueError("HDF5 subdataset paths must be absolute and start with '/'.")
        if subdataset is not None and "//" in subdataset:
            raise ValueError("HDF5 subdataset paths cannot contain empty components.")
        object.__setattr__(self, "uri", uri)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "subdataset", subdataset)
        object.__setattr__(self, "media_type", media_type)
        object.__setattr__(self, "size_bytes", _optional_non_negative(self.size_bytes, "size_bytes"))

    @property
    def is_hdf5_subdataset(self) -> bool:
        return self.subdataset is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "media_type": self.media_type,
            "role": self.role,
            "size_bytes": self.size_bytes,
            "subdataset": self.subdataset,
            "uri": self.uri,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> AssetRef:
        return cls(
            uri=str(value.get("uri", "")),
            role=str(value.get("role", "")),
            subdataset=(None if value.get("subdataset") is None else str(value["subdataset"])),
            media_type=str(value.get("media_type", "application/octet-stream")),
            size_bytes=_optional_int_from_data(value.get("size_bytes"), "size_bytes"),
        )


@dataclass(frozen=True)
class SourceSnapshot:
    """Bounded source identity used for later stale/changed checks."""

    source_kind: str
    size_bytes: int | None
    mtime_ns: int
    member_count: int | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        source_kind = _required_text(self.source_kind, "source_kind").lower()
        try:
            ReaderSourceKind(source_kind)
        except ValueError as exc:
            raise ValueError(f"Unsupported source kind: {source_kind}") from exc
        if isinstance(self.mtime_ns, bool) or not isinstance(self.mtime_ns, int) or self.mtime_ns < 0:
            raise ValueError("mtime_ns must be a non-negative integer.")
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(self, "size_bytes", _optional_non_negative(self.size_bytes, "size_bytes"))
        object.__setattr__(
            self,
            "member_count",
            _optional_non_negative(self.member_count, "member_count"),
        )
        object.__setattr__(self, "fingerprint", self.fingerprint.strip().lower())

    def to_dict(self) -> dict[str, object]:
        return {
            "fingerprint": self.fingerprint,
            "member_count": self.member_count,
            "mtime_ns": self.mtime_ns,
            "size_bytes": self.size_bytes,
            "source_kind": self.source_kind,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> SourceSnapshot:
        return cls(
            source_kind=str(value.get("source_kind", "")),
            size_bytes=_optional_int_from_data(value.get("size_bytes"), "size_bytes"),
            mtime_ns=_required_int_from_data(value.get("mtime_ns"), "mtime_ns"),
            member_count=_optional_int_from_data(value.get("member_count"), "member_count"),
            fingerprint=str(value.get("fingerprint", "")),
        )


@dataclass(frozen=True)
class LocalSARProduct:
    """Canonical local SAR product; paths and container layout remain references."""

    product_id: str
    native_product_id: str
    mission: str
    platform: str
    product_type: str
    acquisition_mode: str
    acquisition_layout: str
    start_time: datetime
    end_time: datetime
    orbit_direction: str | None
    orbit_identity: str | None
    track: int | None
    frame: int | None
    relative_orbit: int | None
    frequency_bands: tuple[str, ...]
    polarizations: tuple[str, ...]
    footprint_wkt: str | None
    assets: tuple[AssetRef, ...]
    native_metadata: Mapping[str, JsonValue]
    reader_id: str
    reader_schema_version: int
    source_snapshot: SourceSnapshot

    def __post_init__(self) -> None:
        native_product_id = _required_text(self.native_product_id, "native_product_id")
        mission = _normalize_mission(_required_text(self.mission, "mission"))
        platform = _normalize_platform(_required_text(self.platform, "platform"))
        product_type = _required_text(self.product_type, "product_type").upper()
        expected_product_id = stable_product_id(mission, product_type, native_product_id)
        if self.product_id.strip() != expected_product_id:
            raise ValueError("product_id must follow the stable '<MISSION>:<PRODUCT_TYPE>:<native_product_id>' rule.")
        start_time = _normalize_datetime(self.start_time, "start_time")
        end_time = _normalize_datetime(self.end_time, "end_time")
        if end_time < start_time:
            raise ValueError("end_time cannot be earlier than start_time.")
        reader_id = _required_text(self.reader_id, "reader_id").lower()
        if not _IDENTIFIER_PATTERN.fullmatch(reader_id):
            raise ValueError(f"reader_id is not a stable identifier: {reader_id}")
        if (
            isinstance(self.reader_schema_version, bool)
            or not isinstance(self.reader_schema_version, int)
            or self.reader_schema_version < 1
        ):
            raise ValueError("reader_schema_version must be a positive integer.")
        assets = tuple(sorted(tuple(self.assets), key=_asset_sort_key))
        if not assets:
            raise ValueError("A local SAR product requires at least one asset reference.")
        metadata = _mapping(self.native_metadata, "native_metadata")
        frozen_metadata = _freeze_json(metadata)
        if not isinstance(frozen_metadata, Mapping):
            raise TypeError("native_metadata must be a mapping.")

        object.__setattr__(self, "product_id", expected_product_id)
        object.__setattr__(self, "native_product_id", native_product_id)
        object.__setattr__(self, "mission", mission)
        object.__setattr__(self, "platform", platform)
        object.__setattr__(self, "product_type", product_type)
        object.__setattr__(self, "acquisition_mode", _required_text(self.acquisition_mode, "acquisition_mode").upper())
        object.__setattr__(
            self,
            "acquisition_layout",
            _required_text(self.acquisition_layout, "acquisition_layout").upper(),
        )
        object.__setattr__(self, "start_time", start_time)
        object.__setattr__(self, "end_time", end_time)
        direction = _optional_text(self.orbit_direction)
        object.__setattr__(self, "orbit_direction", direction.upper() if direction else None)
        object.__setattr__(self, "orbit_identity", _optional_text(self.orbit_identity))
        object.__setattr__(self, "track", _optional_non_negative(self.track, "track"))
        object.__setattr__(self, "frame", _optional_non_negative(self.frame, "frame"))
        object.__setattr__(
            self,
            "relative_orbit",
            _optional_non_negative(self.relative_orbit, "relative_orbit"),
        )
        object.__setattr__(self, "frequency_bands", _normalized_values(self.frequency_bands))
        object.__setattr__(self, "polarizations", _normalized_values(self.polarizations))
        object.__setattr__(self, "footprint_wkt", _optional_text(self.footprint_wkt))
        object.__setattr__(self, "assets", assets)
        object.__setattr__(self, "native_metadata", frozen_metadata)
        object.__setattr__(self, "reader_id", reader_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "acquisition_layout": self.acquisition_layout,
            "acquisition_mode": self.acquisition_mode,
            "assets": [asset.to_dict() for asset in self.assets],
            "end_time": _datetime_text(self.end_time),
            "footprint_wkt": self.footprint_wkt,
            "frame": self.frame,
            "frequency_bands": list(self.frequency_bands),
            "mission": self.mission,
            "native_metadata": _json_ready(self.native_metadata),
            "native_product_id": self.native_product_id,
            "orbit_direction": self.orbit_direction,
            "orbit_identity": self.orbit_identity,
            "platform": self.platform,
            "polarizations": list(self.polarizations),
            "product_id": self.product_id,
            "product_type": self.product_type,
            "reader_id": self.reader_id,
            "reader_schema_version": self.reader_schema_version,
            "relative_orbit": self.relative_orbit,
            "source_snapshot": self.source_snapshot.to_dict(),
            "start_time": _datetime_text(self.start_time),
            "track": self.track,
        }

    def to_json(self) -> str:
        """Return canonical UTF-8 JSON text suitable for deterministic sidecars."""

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> LocalSARProduct:
        assets_data = _sequence(value.get("assets", ()), "assets")
        snapshot_data = _mapping(value.get("source_snapshot", {}), "source_snapshot")
        metadata = _mapping(value.get("native_metadata", {}), "native_metadata")
        return cls(
            product_id=str(value.get("product_id", "")),
            native_product_id=str(value.get("native_product_id", "")),
            mission=str(value.get("mission", "")),
            platform=str(value.get("platform", "")),
            product_type=str(value.get("product_type", "")),
            acquisition_mode=str(value.get("acquisition_mode", "")),
            acquisition_layout=str(value.get("acquisition_layout", "")),
            start_time=_parse_datetime(value.get("start_time"), "start_time"),
            end_time=_parse_datetime(value.get("end_time"), "end_time"),
            orbit_direction=_string_or_none(value.get("orbit_direction")),
            orbit_identity=_string_or_none(value.get("orbit_identity")),
            track=_optional_int_from_data(value.get("track"), "track"),
            frame=_optional_int_from_data(value.get("frame"), "frame"),
            relative_orbit=_optional_int_from_data(value.get("relative_orbit"), "relative_orbit"),
            frequency_bands=_string_tuple(value.get("frequency_bands", ()), "frequency_bands"),
            polarizations=_string_tuple(value.get("polarizations", ()), "polarizations"),
            footprint_wkt=_string_or_none(value.get("footprint_wkt")),
            assets=tuple(AssetRef.from_dict(_mapping(item, "asset")) for item in assets_data),
            native_metadata=cast(Mapping[str, JsonValue], metadata),
            reader_id=str(value.get("reader_id", "")),
            reader_schema_version=_required_int_from_data(value.get("reader_schema_version"), "reader_schema_version"),
            source_snapshot=SourceSnapshot.from_dict(snapshot_data),
        )

    @classmethod
    def from_json(cls, value: str) -> LocalSARProduct:
        parsed = json.loads(value)
        return cls.from_dict(_mapping(parsed, "LocalSARProduct JSON"))


@dataclass(frozen=True)
class ReaderCapability:
    """Declared local input scope for one reader."""

    mission: str
    product_types: tuple[str, ...]
    source_kinds: frozenset[ReaderSourceKind]
    suffixes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        mission = _normalize_mission(self.mission)
        product_types = _normalized_values(self.product_types)
        source_kinds = frozenset(ReaderSourceKind(item) for item in self.source_kinds)
        suffixes = tuple(
            sorted(
                {
                    suffix if suffix.startswith(".") else f".{suffix}"
                    for raw_suffix in self.suffixes
                    if (suffix := raw_suffix.strip().lower())
                }
            )
        )
        object.__setattr__(self, "mission", mission)
        object.__setattr__(self, "product_types", product_types)
        object.__setattr__(self, "source_kinds", source_kinds)
        object.__setattr__(self, "suffixes", suffixes)

    def overlaps(self, other: ReaderCapability) -> bool:
        suffixes_overlap = (
            not self.suffixes or not other.suffixes or bool(set(self.suffixes).intersection(other.suffixes))
        )
        return (
            self.mission == other.mission
            and bool(set(self.product_types).intersection(other.product_types))
            and bool(self.source_kinds.intersection(other.source_kinds))
            and suffixes_overlap
        )

    def covers(
        self,
        *,
        mission: str,
        product_type: str,
        source_kind: ReaderSourceKind,
        suffix: str,
    ) -> bool:
        return (
            self.mission == _normalize_mission(mission)
            and product_type.strip().upper() in self.product_types
            and source_kind in self.source_kinds
            and (not self.suffixes or suffix.lower() in self.suffixes)
        )


@dataclass(frozen=True)
class ReaderDescriptor:
    """Stable identity, schema, priority, and product scopes for a reader."""

    reader_id: str
    display_name: str
    schema_version: int
    capabilities: tuple[ReaderCapability, ...]
    priority: int = 100

    def __post_init__(self) -> None:
        object.__setattr__(self, "reader_id", self.reader_id.strip().lower())
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "capabilities", tuple(self.capabilities))


@dataclass(frozen=True)
class SupportReport:
    """Lightweight result of asking one reader to probe one source."""

    supported: bool
    confidence: int
    reader_id: str
    detected_product_type: str | None = None
    reason_code: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.supported, bool):
            raise TypeError("Probe supported flag must be a boolean.")
        if isinstance(self.confidence, bool) or not 0 <= self.confidence <= 100:
            raise ValueError("Probe confidence must be between 0 and 100.")
        reader_id = self.reader_id.strip().lower()
        if not reader_id:
            raise ValueError("Probe report reader_id is required.")
        if self.supported and self.confidence == 0:
            raise ValueError("A supported probe report requires non-zero confidence.")
        if not self.supported and self.confidence != 0:
            raise ValueError("An unsupported probe report must have zero confidence.")
        object.__setattr__(self, "reader_id", reader_id)
        detected = _optional_text(self.detected_product_type)
        object.__setattr__(self, "detected_product_type", detected.upper() if detected else None)
        object.__setattr__(self, "reason_code", self.reason_code.strip().lower())
        object.__setattr__(self, "message", self.message.strip())

    @classmethod
    def supported_source(
        cls,
        reader_id: str,
        confidence: int,
        *,
        detected_product_type: str | None = None,
    ) -> SupportReport:
        return cls(True, confidence, reader_id, detected_product_type)

    @classmethod
    def unsupported_source(
        cls,
        reader_id: str,
        *,
        reason_code: str = "unsupported_format",
        message: str = "",
        detected_product_type: str | None = None,
    ) -> SupportReport:
        return cls(False, 0, reader_id, detected_product_type, reason_code, message)


ProbeResult = SupportReport


def _asset_sort_key(asset: AssetRef) -> tuple[str, str, str, str, int]:
    if not isinstance(asset, AssetRef):
        raise TypeError("assets must contain only AssetRef values.")
    return (
        asset.role,
        asset.uri,
        asset.subdataset or "",
        asset.media_type,
        asset.size_bytes if asset.size_bytes is not None else -1,
    )


def _normalized_values(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({item.strip().upper() for item in values if item.strip()}))


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("Optional string field must be a string or null.")
    return value


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    items = _sequence(value, field_name)
    if any(not isinstance(item, str) for item in items):
        raise TypeError(f"{field_name} values must be strings.")
    return tuple(item for item in items if isinstance(item, str))


def _required_int_from_data(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    return value


def _optional_int_from_data(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    return _required_int_from_data(value, field_name)


__all__ = [
    "AssetRef",
    "JsonScalar",
    "JsonValue",
    "LocalSARProduct",
    "ProbeResult",
    "ReaderCapability",
    "ReaderDescriptor",
    "ReaderSourceKind",
    "SourceSnapshot",
    "SupportReport",
    "stable_product_id",
]
