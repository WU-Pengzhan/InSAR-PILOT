# ISCE2 Sentinel-1 TOPS GUI

Desktop workflow orchestrator for Sentinel-1 TOPS stacks using local ISCE2 on Ubuntu/WSL.

This app uses official ISCE2 `topsStack` scripts and `run_files`; it does not reimplement ISCE internals.

## Documentation

- English manual: [README_EN.md](README_EN.md)
- 简体中文手册: [README_ZH.md](README_ZH.md)
- UI/UX redesign notes: [docs/ui-ux-redesign.md](docs/ui-ux-redesign.md)
- Design system notes: [docs/design-system.md](docs/design-system.md)
- Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## Quick Start

```bash
# clone repository or extract a GitHub release source archive, then:
conda env create -f environment.yml
conda activate isce-master
pip install .
isce2-gui
```


## Current Stage 2 Features

- Practitioner workflow pages:
  - `Data Sources`
  - `AOI + BBox + IW`
  - `Processing Plan`
  - `Run Monitor`
  - `Results & Visualization`
- Environment validation, data preparation, workflow generation, and run-file execution.
- Subcommand-level run status tracking and selected-step rerun.
- AOI import from KML/SHP to auto-fill bbox, IW recommendation, and geometry verify.
- Verify overlay for AOI, bbox, IW, auto-selected bursts, and DEM coverage bounds.
- SLC/interferogram/overlay quicklook preview and BMP export.
- Project persistence in `<work_dir>/.iscegui/project.json`.

## Version Scope and Notes

- Target platform: Ubuntu on WSL.
- Sensor/workflow: Sentinel-1 TOPS stack (ISCE2 topsStack).
- On WSL/WSLg only, the launcher defaults to `QT_QPA_PLATFORM=xcb` to avoid dropdown/popup issues.

For complete usage instructions, troubleshooting, and step-by-step ISCE run descriptions, see the EN/ZH manuals above.
