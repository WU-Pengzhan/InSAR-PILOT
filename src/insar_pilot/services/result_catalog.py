"""Discover logical radar products produced by the ISCE2 stack workflow."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

_DATE_RE = re.compile(r"(?<!\d)(\d{8})(?!\d)")
_PAIR_RE = re.compile(r"(?<!\d)(\d{8})_(\d{8})(?!\d)")


@dataclass(frozen=True)
class ResultProduct:
    """One user-facing result, independent of its XML/VRT sidecars."""

    product_id: str
    kind: str
    path: str
    display_name: str
    reference_date: str = ""
    secondary_date: str = ""
    variant: str = ""
    paired_slc_path: str = ""
    width: int | None = None
    height: int | None = None
    available: bool = True
    warning: str = ""

    @property
    def pair_label(self) -> str:
        if self.reference_date and self.secondary_date:
            return f"{self.reference_date} / {self.secondary_date}"
        return self.reference_date


class ResultCatalogService:
    """Build a compact catalog from stable merged-product locations."""

    CORE_KINDS = ("slc", "wrapped_interferogram", "coherence", "unwrapped_phase")
    _SUPPORTED_CUSTOM_SUFFIXES = {
        ".vrt",
        ".tif",
        ".tiff",
        ".xml",
        ".slc",
        ".int",
        ".cor",
        ".unw",
        ".hgt",
        ".los",
        ".lat",
        ".lon",
        ".rdr",
        ".dem",
        ".float",
    }

    def discover(self, work_dir: Path, *, reference_date: str = "") -> list[ResultProduct]:
        work_dir = Path(work_dir).expanduser()
        products: list[ResultProduct] = []
        slc_by_date = self._discover_slcs(work_dir / "merged" / "SLC", reference_date)
        products.extend(slc_by_date.values())

        pair_root = work_dir / "merged" / "interferograms"
        if pair_root.is_dir():
            for pair_dir in sorted((item for item in pair_root.iterdir() if item.is_dir()), key=lambda p: p.name):
                pair = _PAIR_RE.search(pair_dir.name)
                if pair is None:
                    continue
                ref_date, sec_date = pair.groups()
                products.extend(
                    self._discover_pair_products(
                        pair_dir,
                        ref_date=ref_date,
                        sec_date=sec_date,
                        paired_slc=slc_by_date.get(ref_date),
                    )
                )

        order = {kind: index for index, kind in enumerate(self.CORE_KINDS)}
        return sorted(
            products,
            key=lambda item: (
                order.get(item.kind, 99),
                item.reference_date,
                item.secondary_date,
                item.variant,
            ),
        )

    def product_from_path(self, path: Path) -> ResultProduct:
        """Classify a compatible file selected through the advanced browser."""

        path = Path(path).expanduser()
        if not path.is_file():
            raise ValueError(f"Result file was not found: {path}")
        if path.suffix.lower() not in self._SUPPORTED_CUSTOM_SUFFIXES and not self._has_isce_sidecar(path):
            raise ValueError("Select an ISCE data/XML/VRT file or a GeoTIFF image.")

        lower_name = path.name.lower()
        if ".slc" in lower_name:
            kind = "slc"
        elif ".cor" in lower_name or "coherence" in lower_name:
            kind = "coherence"
        elif ".unw" in lower_name or "unwrapped" in lower_name:
            kind = "unwrapped_phase"
        elif ".int" in lower_name or "interferogram" in lower_name:
            kind = "wrapped_interferogram"
        else:
            kind = "custom_raster"

        pair = _PAIR_RE.search(str(path))
        dates = _DATE_RE.findall(str(path))
        ref_date = pair.group(1) if pair else (dates[0] if dates else "")
        sec_date = pair.group(2) if pair else ""
        variant = "filtered" if "filt" in lower_name else "unfiltered"
        preferred = self._normalize_selected_path(path)
        width, height = self._read_dimensions(preferred)
        identity = hashlib.sha1(str(preferred.resolve()).encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
        return ResultProduct(
            product_id=f"custom:{kind}:{identity}",
            kind=kind,
            path=str(preferred),
            display_name=self._display_name(kind, ref_date, sec_date, variant, custom_name=path.name),
            reference_date=ref_date,
            secondary_date=sec_date,
            variant=variant,
            width=width,
            height=height,
        )

    def _discover_slcs(self, root: Path, reference_date: str) -> dict[str, ResultProduct]:
        products: dict[str, ResultProduct] = {}
        if not root.is_dir():
            return products
        for date_dir in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda p: p.name):
            match = _DATE_RE.search(date_dir.name)
            if match is None:
                continue
            date = match.group(1)
            candidates = [item for item in date_dir.iterdir() if item.is_file() and ".slc" in item.name.lower()]
            source = self._preferred_source(candidates)
            if source is None:
                continue
            width, height = self._read_dimensions(source)
            role = "reference" if date == reference_date else "coregistered"
            products[date] = ResultProduct(
                product_id=f"slc:{date}",
                kind="slc",
                path=str(source),
                display_name=self._display_name("slc", date, "", role),
                reference_date=date,
                variant=role,
                width=width,
                height=height,
            )
        return products

    def _discover_pair_products(
        self,
        pair_dir: Path,
        *,
        ref_date: str,
        sec_date: str,
        paired_slc: ResultProduct | None,
    ) -> list[ResultProduct]:
        grouped: dict[tuple[str, str], list[Path]] = {}
        for path in pair_dir.iterdir():
            if not path.is_file():
                continue
            lower_name = path.name.lower()
            if ".unw" in lower_name:
                key = ("unwrapped_phase", "unwrapped")
            elif ".cor" in lower_name:
                key = ("coherence", "coherence")
            elif ".int" in lower_name:
                key = ("wrapped_interferogram", "filtered" if "filt" in lower_name else "unfiltered")
            else:
                continue
            grouped.setdefault(key, []).append(path)

        products: list[ResultProduct] = []
        for (kind, variant), candidates in grouped.items():
            source = self._preferred_source(candidates)
            if source is None:
                continue
            width, height = self._read_dimensions(source)
            missing_slc = kind == "wrapped_interferogram" and paired_slc is None
            products.append(
                ResultProduct(
                    product_id=f"{kind}:{ref_date}_{sec_date}:{variant}",
                    kind=kind,
                    path=str(source),
                    display_name=self._display_name(kind, ref_date, sec_date, variant),
                    reference_date=ref_date,
                    secondary_date=sec_date,
                    variant=variant,
                    paired_slc_path=paired_slc.path if paired_slc else "",
                    width=width,
                    height=height,
                    warning=(
                        "No merged reference-date SLC was found; overlay will use abs(INT)."
                        if missing_slc
                        else ""
                    ),
                )
            )
        return products

    @staticmethod
    def _display_name(
        kind: str,
        reference_date: str,
        secondary_date: str,
        variant: str,
        *,
        custom_name: str = "",
    ) -> str:
        pair = f"{reference_date} / {secondary_date}" if secondary_date else reference_date
        if kind == "slc":
            role = "reference" if variant == "reference" else "coregistered"
            return f"SLC · {pair} · {role}" if pair else f"SLC · {custom_name}"
        if kind == "wrapped_interferogram":
            suffix = "filtered" if variant == "filtered" else "unfiltered"
            return f"INT · {pair} · {suffix}" if pair else f"INT · {custom_name}"
        if kind == "coherence":
            return f"Coherence · {pair}" if pair else f"Coherence · {custom_name}"
        if kind == "unwrapped_phase":
            return f"Unwrapped phase · {pair}" if pair else f"Unwrapped phase · {custom_name}"
        if kind == "custom_raster":
            return f"Other raster · {custom_name}"
        return custom_name or pair

    @classmethod
    def _preferred_source(cls, candidates: list[Path]) -> Path | None:
        logical: dict[str, list[Path]] = {}
        for candidate in candidates:
            logical.setdefault(cls._logical_stem(candidate), []).append(candidate)
        if not logical:
            return None
        # A filtered and unfiltered INT are intentionally separate groups before this call.
        paths = next(iter(logical.values())) if len(logical) == 1 else max(logical.values(), key=len)
        return min(paths, key=cls._source_rank)

    @staticmethod
    def _logical_stem(path: Path) -> str:
        name = path.name.lower()
        for suffix in (".full.vrt", ".full.xml", ".vrt", ".xml"):
            if name.endswith(suffix):
                return name[: -len(suffix)]
        return name

    @staticmethod
    def _source_rank(path: Path) -> tuple[int, str]:
        name = path.name.lower()
        if name.endswith(".full.vrt"):
            return 0, name
        if name.endswith(".vrt"):
            return 1, name
        if not name.endswith(".xml"):
            return 2, name
        return 3, name

    @classmethod
    def _normalize_selected_path(cls, path: Path) -> Path:
        if path.suffix.lower() == ".xml":
            if path.with_suffix("").exists():
                return path.with_suffix("")
            if path.with_suffix(".vrt").exists():
                return path.with_suffix(".vrt")
        return path

    @staticmethod
    def _has_isce_sidecar(path: Path) -> bool:
        return Path(f"{path}.xml").is_file() or Path(f"{path}.vrt").is_file()

    @staticmethod
    def _read_dimensions(path: Path) -> tuple[int | None, int | None]:
        vrt = path if path.suffix.lower() == ".vrt" else Path(f"{path}.vrt")
        if not vrt.is_file():
            return None, None
        try:
            root = ElementTree.parse(vrt).getroot()
            width = int(root.attrib["rasterXSize"])
            height = int(root.attrib["rasterYSize"])
        except (OSError, ElementTree.ParseError, KeyError, TypeError, ValueError):
            return None, None
        return width, height
