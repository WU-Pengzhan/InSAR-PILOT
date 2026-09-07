#!/usr/bin/env python3
"""Verify the Web package and bundled interface without requiring a SAR runtime."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from insar_pilot import __version__
from insar_pilot.web import api


def main() -> int:
    for module in ("fastapi", "uvicorn", "wsproto", "asf_search", "rasterio", "h5py"):
        import_module(module)
    static = Path(api.__file__).parent / "static"
    if not (static / "index.html").is_file() or not list((static / "assets").glob("*.js")):
        print("FAIL: bundled Web interface is missing. Build frontend before packaging.")
        return 1
    print(f"InSAR-PILOT {__version__}: Web dependencies and bundled interface available.")
    print("ISCE2/ISCE3 are checked separately in Runtime status; no scientific validation performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
