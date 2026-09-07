#!/usr/bin/env python3
"""Verify the installed ISCE2 runtime and InSAR-PILOT command paths."""

from __future__ import annotations

import subprocess
import sys

import eof  # noqa: F401
import isce
import isceobj  # noqa: F401  # ISCE2 exposes this after importing isce.
import snaphu  # noqa: F401
from osgeo import gdal  # noqa: F401
from PySide6.QtCore import qVersion

from insar_pilot import __version__
from insar_pilot.domain.project import EnvironmentConfig
from insar_pilot.services.env_probe import EnvironmentProbe
from insar_pilot.services.shell import ShellCommandBuilder


def main() -> int:
    report = EnvironmentProbe().probe(EnvironmentConfig())
    print(report.as_text())
    if not report.ok:
        return 1

    builder = ShellCommandBuilder(EnvironmentConfig())
    command_checks = (
        ("stackSentinel.py -h", {0}),
        ("SentinelWrapper.py -h", {0}),
        ("looks.py -h", {0}),
        ("imageMath.py -h", {0}),
        ("gdal2isce_xml.py -h", {0}),
        ("gdalinfo --version", {0}),
        ("gdal_translate --version", {0}),
        ("gdalwarp --version", {0}),
        ("aria2c --version", {0}),
        # SNAPHU uses exit status 1 after printing its help text.
        ("snaphu -h", {0, 1}),
    )
    for command, accepted_codes in command_checks:
        completed = subprocess.run(builder.wrap(command), capture_output=True, text=True, timeout=30)
        if completed.returncode not in accepted_codes:
            detail = (completed.stderr or completed.stdout).strip()
            print(f"[FAIL] {command}: {detail}", file=sys.stderr)
            return 1
        print(f"[OK] {command}")

    print(f"InSAR-PILOT {__version__}; ISCE2 {isce.release_version}; Qt {qVersion()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
