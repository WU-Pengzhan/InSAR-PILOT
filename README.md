# ISCE2 Sentinel-1 TOPS GUI

Desktop workflow orchestrator for Sentinel-1 TOPS stacks using local ISCE2 on Ubuntu/WSL.

This app uses official ISCE2 `topsStack` scripts and `run_files`; it does not reimplement ISCE internals.

## Documentation

- English manual: [README_EN.md](README_EN.md)
- 简体中文手册: [README_ZH.md](README_ZH.md)

## Quick Start

```bash
source ~/.bashrc
conda activate insar
pip install -e .[dev]
isce2-gui
```

## What Stage 1 Includes

- Guided wizard for environment, inputs, execution, and visualization.
- Data precheck first, then workflow generation/execution.
- Run-file level execution with subcommand status tracking.
- SLC/INT/overlay quicklook preview and BMP export.
- Project persistence in `<work_dir>/.iscegui/project.json`.

## Version Scope and Notes

- Target platform: Ubuntu on WSL.
- Sensor/workflow: Sentinel-1 TOPS stack (ISCE2 topsStack).
- v1 non-goals: remote download, multi-sensor support, polygon AOI editing.

For complete usage instructions, troubleshooting, and step-by-step ISCE run descriptions, see the EN/ZH manuals above.
