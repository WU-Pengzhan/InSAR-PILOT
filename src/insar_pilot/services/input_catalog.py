"""Input scanning, IPF version detection, and optional ZIP extraction."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from insar_pilot.domain.project import APP_METADATA_DIR, InputEntry, PreparedInputs, WorkflowConfig


SAFE_NAMESPACE = "{http://www.esa.int/safe/sentinel-1.0}"


@dataclass
class InputCatalogReport:
    entries: list[InputEntry] = field(default_factory=list)
    aux_required: bool = False

    def as_text(self) -> str:
        if not self.entries:
            return "No Sentinel-1 ZIP or SAFE inputs were detected."

        lines = [f"Detected {len(self.entries)} Sentinel-1 inputs:"]
        for entry in self.entries:
            version = entry.ipf_version or "unknown"
            lines.append(f"- {entry.kind.upper()}: {entry.path} (IPF {version})")
        lines.append("")
        lines.append(
            "AUX_CAL requirement: required"
            if self.aux_required
            else "AUX_CAL requirement: optional (the app can supply an empty aux directory)."
        )
        return "\n".join(lines)


class InputCatalogService:
    """Prepare an explicit SAFE/ZIP manifest for stackSentinel.py."""

    def scan(self, input_dir: Path) -> InputCatalogReport:
        directory = input_dir.expanduser()
        if not directory.is_dir():
            raise ValueError(f"Input folder was not found: {directory}")

        entries: list[InputEntry] = []
        for path in sorted(directory.rglob("*"), key=lambda item: str(item).lower()):
            if path.is_dir() and path.name.endswith(".SAFE"):
                version = self.detect_ipf_version(path)
                entries.append(InputEntry(path=str(path), kind="safe", ipf_version=version or ""))
            elif path.is_file() and path.suffix.lower() == ".zip":
                version = self.detect_ipf_version(path)
                entries.append(InputEntry(path=str(path), kind="zip", ipf_version=version or ""))

        if not entries:
            raise ValueError(f"No Sentinel-1 ZIP or SAFE inputs were found in {directory}")

        aux_required = any(entry.ipf_version == "002.36" for entry in entries)
        return InputCatalogReport(entries=entries, aux_required=aux_required)

    def detect_ipf_version(self, path: Path) -> str | None:
        manifest_text = self._read_manifest_text(path)
        return self.extract_processing_version_from_manifest_text(manifest_text)

    @staticmethod
    def extract_processing_version_from_manifest_text(text: str) -> str | None:
        root = ET.fromstring(text)
        processing = root.find('.//metadataObject[@ID="processing"]')
        if processing is None:
            return None

        software = processing.find(
            f".//xmlData/{SAFE_NAMESPACE}processing/{SAFE_NAMESPACE}facility/{SAFE_NAMESPACE}software"
        )
        if software is None:
            return None
        return software.attrib.get("version")

    def prepare_inputs(
        self,
        workflow: WorkflowConfig,
        work_dir: Path,
        report: InputCatalogReport,
        logger: Callable[[str], None] | None = None,
    ) -> PreparedInputs:
        log = logger or (lambda _: None)
        inputs_dir = work_dir / APP_METADATA_DIR / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)

        output_entries: list[InputEntry] = []
        extract_dir = workflow.resolved_extract_dir()
        if workflow.extract_zips:
            extract_dir.mkdir(parents=True, exist_ok=True)

        for entry in report.entries:
            source = Path(entry.path)
            if workflow.extract_zips and entry.kind == "zip":
                extracted = self.extract_zip_to_safe(source, extract_dir, log)
                output_entries.append(InputEntry(path=str(extracted), kind="safe", ipf_version=entry.ipf_version))
            else:
                output_entries.append(entry)

        manifest_path = inputs_dir / "safe_inputs.txt"
        manifest_path.write_text(
            "\n".join(item.path for item in output_entries) + "\n",
            encoding="utf-8",
        )

        notes = [
            f"Prepared {len(output_entries)} input entries.",
            f"Manifest written to {manifest_path}.",
        ]
        if workflow.extract_zips:
            notes.append(f"ZIP extraction directory: {extract_dir}")

        return PreparedInputs(
            manifest_path=str(manifest_path),
            extract_dir=str(extract_dir if workflow.extract_zips else ""),
            aux_required=report.aux_required,
            entries=output_entries,
            notes=notes,
        )

    def extract_zip_to_safe(
        self,
        zip_path: Path,
        destination_dir: Path,
        logger: Callable[[str], None],
    ) -> Path:
        with zipfile.ZipFile(zip_path, "r") as archive:
            root_name = self._find_safe_root_name(archive.namelist(), zip_path)
            target_dir = destination_dir / root_name
            if target_dir.exists():
                logger(f"Skip extraction, SAFE already exists: {target_dir}")
                return target_dir

            logger(f"Extract ZIP to SAFE: {zip_path.name} -> {target_dir}")
            archive.extractall(destination_dir)
            return target_dir

    @staticmethod
    def _find_safe_root_name(names: list[str], zip_path: Path) -> str:
        for name in names:
            clean = name.rstrip("/")
            parts = clean.split("/")
            for part in parts:
                if part.endswith(".SAFE"):
                    return part

        stem = zip_path.stem
        return stem if stem.endswith(".SAFE") else f"{stem}.SAFE"

    @staticmethod
    def _read_manifest_text(path: Path) -> str:
        if path.is_dir():
            manifest_path = path / "manifest.safe"
            return manifest_path.read_text(encoding="utf-8")

        with zipfile.ZipFile(path, "r") as archive:
            manifest_name = next(
                name for name in archive.namelist() if name.endswith("manifest.safe")
            )
            return archive.read(manifest_name).decode("utf-8")
