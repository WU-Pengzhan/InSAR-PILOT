"""Resolve local imported raster dependencies without rewriting their descriptors."""

import xml.etree.ElementTree as ET
from pathlib import Path


def source_closure(path: Path) -> list[Path]:
    pending = [path.resolve(strict=True)]
    found: dict[Path, None] = {}
    while pending:
        source = pending.pop().resolve(strict=True)
        if source in found:
            continue
        found[source] = None
        if source.is_dir():
            continue  # Directory snapshots track all SAFE members separately.
        for suffix in (".xml", ".vrt", ".hdr"):
            sidecar = Path(str(source) + suffix)
            if sidecar.is_file():
                pending.append(sidecar)
        if source.suffix.lower() not in {".xml", ".vrt"}:
            continue
        try:
            tree = ET.parse(source)
        except ET.ParseError:
            if source.suffix.lower() == ".vrt":
                raise ValueError("Imported VRT is malformed.") from None
            continue
        nodes = list(tree.iter("SourceFilename"))
        for prop in tree.iter("property"):
            value_node = prop.find("value")
            if prop.get("name", "").lower() in {"filename", "file_name"} and value_node is not None:
                nodes.append(value_node)
        for node in nodes:
            value = (node.text or "").strip()
            if not value:
                continue
            if value.startswith("/vsizip/"):
                archive, separator, _ = value[8:].partition(".zip/")
                if not separator:
                    raise ValueError("Unsupported virtual ZIP input.")
                value = archive + ".zip"
            elif value.startswith(("/vsi", "http://", "https://")):
                raise ValueError("Import a local materialized source for a reproducible raster reference.")
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = source.parent / candidate
            if not candidate.exists() and Path(str(candidate) + ".vrt").is_file():
                candidate = Path(str(candidate) + ".vrt")
            pending.append(candidate)
    return list(found)
