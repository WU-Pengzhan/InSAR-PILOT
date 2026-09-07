"""Freeze ISCE/GDAL asset closures while leaving processor files untouched."""

from __future__ import annotations

import hashlib
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path


def copy_closure(
    sources: list[Path], workspace: Path, staging: Path, final: Path, external_inputs: set[Path] | None = None
) -> dict[Path, Path]:
    workspace = workspace.resolve()
    external_inputs = {p.resolve() for p in (external_inputs or set())}
    pending = list(sources)
    mapping: dict[Path, Path] = {}
    documents: dict[Path, ET.ElementTree[ET.Element[str]]] = {}
    links: list[tuple[ET.Element, Path, str, bool]] = []
    while pending:
        source = pending.pop().resolve(strict=True)
        if source in mapping:
            continue
        allowed_external = source in external_inputs or any(
            p.is_dir() and source.is_relative_to(p) for p in external_inputs
        )
        if (not source.is_relative_to(workspace) and not allowed_external) or not source.is_file():
            raise ValueError(f"Published asset dependency escapes workspace: {source}")
        relative = (
            source.relative_to(workspace)
            if source.is_relative_to(workspace)
            else Path("external") / hashlib.sha256(str(source).encode()).hexdigest()[:16] / source.name
        )
        destination = staging / "assets" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        mapping[source] = destination
        for suffix in (".xml", ".vrt", ".hdr"):
            sidecar = Path(str(source) + suffix)
            if sidecar.is_file():
                pending.append(sidecar)
        if source.suffix.lower() not in {".xml", ".vrt"}:
            continue
        try:
            tree = ET.parse(source)
        except ET.ParseError:
            # Upstream opaque XML-like configuration is not a GDAL/ISCE image descriptor.
            if source.suffix == ".vrt":
                raise ValueError(f"Invalid VRT: {source}") from None
            continue
        documents[source] = tree
        nodes = list(tree.iter("SourceFilename"))
        for prop in tree.iter("property"):
            if prop.get("name", "").lower() in {"filename", "file_name"}:
                value = prop.find("value")
                if value is not None:
                    nodes.append(value)
        for node in nodes:
            text = (node.text or "").strip()
            if not text:
                continue
            archive_member = ""
            if text.startswith("/vsizip/"):
                archive, separator, member = text[8:].partition(".zip/")
                if not separator:
                    raise ValueError(f"Unsupported virtual archive source: {text}")
                text, archive_member = archive + ".zip", member
            candidate = Path(text)
            if not candidate.is_absolute():
                relative = source.parent / candidate
                candidate = relative if relative.exists() else workspace / candidate
            virtual_name = False
            if not candidate.exists() and Path(str(candidate) + ".vrt").is_file():
                # ISCE's virtual SLC filename names the adjacent .slc.vrt.
                candidate = Path(str(candidate) + ".vrt")
                virtual_name = True
            candidate = candidate.resolve(strict=True)
            pending.append(candidate)
            links.append((node, candidate, archive_member, virtual_name))
    for node, source, member, virtual_name in links:
        destination = mapping[source]
        node.text = str(final / destination.relative_to(staging))
        if virtual_name:
            node.text = node.text.removesuffix(".vrt")
        if member:
            node.text = "/vsizip/" + node.text + "/" + member
        if node.tag == "SourceFilename":
            node.set("relativeToVRT", "0")
    for source, document in documents.items():
        document.write(mapping[source], encoding="UTF-8", xml_declaration=True)
    return mapping
