"""Mission-specific pair checks over the canonical local-product model."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from insar_pilot.domain.local_data import JsonValue, LocalSARProduct
from insar_pilot.domain.workflows import PairCompatibilityReport

_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")


class PairCompatibilityService:
    """Dispatch strict compatibility rules without hiding mission differences."""

    def check(self, left: LocalSARProduct, right: LocalSARProduct) -> PairCompatibilityReport:
        baseline = abs((right.start_time - left.start_time).total_seconds()) / 86_400.0
        if left.product_id == right.product_id:
            return self._report(False, left.mission, ("same_product",), left, right, baseline)
        if left.mission != right.mission:
            return self._report(False, None, ("cross_mission_pair",), left, right, baseline)
        if left.mission == "SENTINEL-1":
            return self._sentinel(left, right, baseline)
        if left.mission == "NISAR":
            return self._nisar(left, right, baseline)
        return self._report(False, left.mission, ("unsupported_mission",), left, right, baseline)

    def _sentinel(
        self,
        left: LocalSARProduct,
        right: LocalSARProduct,
        baseline: float,
    ) -> PairCompatibilityReport:
        reasons: list[str] = []
        warnings: list[str] = []
        if left.start_time == right.start_time and left.end_time == right.end_time:
            reasons.append("same_acquisition_time")
        if left.product_type != "SLC" or right.product_type != "SLC":
            reasons.append("sentinel_requires_slc")
        if left.acquisition_mode != right.acquisition_mode:
            reasons.append("acquisition_mode_mismatch")
        if left.acquisition_layout != right.acquisition_layout:
            reasons.append("acquisition_layout_mismatch")
        if not left.orbit_direction or not right.orbit_direction:
            reasons.append("orbit_direction_missing")
        elif left.orbit_direction != right.orbit_direction:
            reasons.append("orbit_direction_mismatch")
        if left.relative_orbit is None or right.relative_orbit is None:
            reasons.append("relative_orbit_missing")
        elif left.relative_orbit != right.relative_orbit:
            reasons.append("relative_orbit_mismatch")
        self._common_signal_reasons(left, right, reasons)
        self._footprint_reasons(left, right, reasons)

        left_swaths = _metadata_strings(left.native_metadata, "swaths")
        right_swaths = _metadata_strings(right.native_metadata, "swaths")
        if left_swaths and right_swaths and not set(left_swaths).intersection(right_swaths):
            reasons.append("swath_coverage_mismatch")
        elif not left_swaths or not right_swaths:
            warnings.append("swath_check_deferred")
        left_bursts = _metadata_strings(left.native_metadata, "bursts")
        right_bursts = _metadata_strings(right.native_metadata, "bursts")
        if left_bursts and right_bursts and not set(left_bursts).intersection(right_bursts):
            reasons.append("burst_coverage_mismatch")
        elif not left_bursts or not right_bursts:
            warnings.append("burst_check_deferred")
        return self._report(not reasons, left.mission, tuple(reasons), left, right, baseline, tuple(warnings))

    def _nisar(
        self,
        left: LocalSARProduct,
        right: LocalSARProduct,
        baseline: float,
    ) -> PairCompatibilityReport:
        reasons: list[str] = []
        if left.start_time == right.start_time and left.end_time == right.end_time:
            reasons.append("same_acquisition_time")
        if left.product_type != "RSLC" or right.product_type != "RSLC":
            reasons.append("nisar_requires_rslc")
        if left.track is None or right.track is None:
            reasons.append("track_missing")
        elif left.track != right.track:
            reasons.append("track_mismatch")
        if left.frame is None or right.frame is None:
            reasons.append("frame_missing")
        elif left.frame != right.frame:
            reasons.append("frame_mismatch")
        if not left.orbit_direction or not right.orbit_direction:
            reasons.append("orbit_direction_missing")
        elif left.orbit_direction != right.orbit_direction:
            reasons.append("orbit_direction_mismatch")
        left_look = _identification_text(left.native_metadata, "lookDirection")
        right_look = _identification_text(right.native_metadata, "lookDirection")
        if not left_look or not right_look:
            reasons.append("look_direction_missing")
        elif left_look.upper() != right_look.upper():
            reasons.append("look_direction_mismatch")
        self._common_signal_reasons(left, right, reasons)
        self._footprint_reasons(left, right, reasons)
        return self._report(not reasons, left.mission, tuple(reasons), left, right, baseline)

    @staticmethod
    def _common_signal_reasons(
        left: LocalSARProduct,
        right: LocalSARProduct,
        reasons: list[str],
    ) -> None:
        if not set(left.frequency_bands).intersection(right.frequency_bands):
            reasons.append("frequency_mismatch")
        if not set(left.polarizations).intersection(right.polarizations):
            reasons.append("polarization_mismatch")

    @staticmethod
    def _footprint_reasons(
        left: LocalSARProduct,
        right: LocalSARProduct,
        reasons: list[str],
    ) -> None:
        left_bbox = _wkt_bbox(left.footprint_wkt)
        right_bbox = _wkt_bbox(right.footprint_wkt)
        if left_bbox is None or right_bbox is None:
            reasons.append("footprint_missing")
        elif not _bboxes_overlap(left_bbox, right_bbox):
            reasons.append("spatial_coverage_mismatch")

    @staticmethod
    def _report(
        compatible: bool,
        mission: str | None,
        reasons: tuple[str, ...],
        left: LocalSARProduct,
        right: LocalSARProduct,
        baseline: float,
        warnings: tuple[str, ...] = (),
    ) -> PairCompatibilityReport:
        return PairCompatibilityReport(
            compatible=compatible,
            mission=mission,
            reason_codes=reasons,
            warnings=warnings,
            common_frequency_bands=tuple(set(left.frequency_bands).intersection(right.frequency_bands)),
            common_polarizations=tuple(set(left.polarizations).intersection(right.polarizations)),
            temporal_baseline_days=baseline,
        )


def _metadata_strings(metadata: Mapping[str, JsonValue], key: str) -> tuple[str, ...]:
    value = metadata.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(str(item).upper() for item in value if isinstance(item, (str, int)))


def _identification_text(metadata: Mapping[str, JsonValue], key: str) -> str:
    identification = metadata.get("identification")
    if not isinstance(identification, Mapping):
        return ""
    value = identification.get(key)
    return value if isinstance(value, str) else ""


def _wkt_bbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    # NISAR boundingPolygon currently contains lon/lat/height triples even
    # when its WKT tag omits ``Z``.  Read the first two ordinates of each
    # comma-delimited vertex instead of assuming a flat XY number stream.
    vertices: list[tuple[float, float]] = []
    for component in value.split(","):
        ordinates = _NUMBER.findall(component)
        if len(ordinates) >= 2:
            vertices.append((float(ordinates[0]), float(ordinates[1])))
    if len(vertices) < 3:
        return None
    longitudes = [vertex[0] for vertex in vertices]
    latitudes = [vertex[1] for vertex in vertices]
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def _bboxes_overlap(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    return not (
        left[2] < right[0]
        or right[2] < left[0]
        or left[3] < right[1]
        or right[3] < left[1]
    )


__all__ = ["PairCompatibilityService"]
