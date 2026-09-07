"""Check built distribution contents and Web-only launch metadata."""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path


def main() -> None:
    wheels = list(Path("dist").glob("*.whl"))
    sources = list(Path("dist").glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise SystemExit("Expected exactly one wheel and one source distribution")
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = wheel.namelist()
        metadata = wheel.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode()
        entrypoints = wheel.read(next(n for n in names if n.endswith(".dist-info/entry_points.txt"))).decode()
        assert "insar_pilot/web/static/index.html" in names
        assert any(n.startswith("insar_pilot/web/static/assets/") and n.endswith(".js") for n in names)
        assert not any(n.startswith(("insar_pilot/ui/", "insar_pilot/i18n/")) for n in names)
        assert not any("pyside" in line.lower() or "qtawesome" in line.lower()
                       for line in metadata.splitlines() if line.startswith("Requires-Dist:"))
        assert "insar-pilot = insar_pilot.web.launch:main" in entrypoints
    with tarfile.open(sources[0]) as source:
        names = source.getnames()
        assert any(n.endswith("/frontend/package-lock.json") for n in names)
        assert any(n.endswith("/src/insar_pilot/web/static/index.html") for n in names)
        assert not any("node_modules/" in n or "owned-browser-profile/" in n for n in names)
    print("Wheel and source distribution: Web assets, entrypoints and dependency checks passed.")


if __name__ == "__main__":
    main()
