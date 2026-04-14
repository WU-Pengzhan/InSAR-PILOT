# ISCE2 Sentinel-1 TOPS GUI (English Manual)

## 1. Overview

This desktop app orchestrates local ISCE2 `topsStack` workflows on Ubuntu/WSL.
It is a usability layer over official ISCE2 scripts and generated `run_files`.

Current Stage 2 workflow pages:

1. `Data Sources`
2. `AOI + BBox + IW`
3. `Processing Plan`
4. `Run Monitor`
5. `Results & Visualization`

## 2. Environment Requirements

- Ubuntu (WSL preferred)
- Conda environment (default name in docs: `isce-master`)
- ISCE2 included in `environment.yml` (`isce2` dependency)
- Required command-line tools discoverable in your runtime shell

The GUI validates environment/tool availability from `Data Sources`.

## 3. Install and Launch

### 3.1 Clone repository

```bash
git clone https://github.com/WU-Pengzhan/isce-master.git
cd isce-master
```

You can also download and extract the GitHub release source archive, then run the same commands from the extracted root folder.

### 3.2 Create conda environment

```bash
conda env create -f environment.yml
conda activate isce-master
```

### 3.3 Install GUI package

```bash
pip install .
```

Developer mode:

```bash
pip install -e .[dev]
```

### 3.4 Start application

```bash
isce2-gui
```

Alternative:

```bash
python -m isce2_gui
```

## 4. Recommended User Flow

### 4.1 Data Sources

- Configure shell/conda/ISCE root (runtime section)
- Select input dataset folder (ZIP/SAFE), orbit folder, DEM path, optional AUX, work dir
- If DEM is GeoTIFF, choose height reference (`EGM96` or `WGS84`)
- Click `Validate & Prepare Data`

### 4.2 AOI + BBox + IW

- Optional AOI import (`.kml` / `.shp`) to auto-fill ISCE bbox
- Set bbox as SNWE decimal degrees (or use common overlap mode)
- Select IW swaths
- Click `Recommend IW` and `Verify Geometry`
- Verify plot overlays:
  - AOI
  - ISCE bbox
  - IW footprints
  - auto-selected burst footprints
  - DEM coverage bounds

### 4.3 Processing Plan

- Set workflow/coregistration/connectivity/looks/parallel settings/reference date
- Generate official stack command and `run_files`

### 4.4 Run Monitor

- Execute by `Run Next Step`, `Run Selected Step`, or `Run Remaining Steps`
- Inspect per-step and per-subcommand status, exit codes, and logs

### 4.5 Results & Visualization

- Browse discovered outputs
- Preview/export quicklooks:
  - SLC
  - interferogram phase
  - SLC background + phase overlay

## 5. Project Metadata Layout

Given `<work_dir>`, GUI metadata is stored under:

- `<work_dir>/.iscegui/project.json`
- `<work_dir>/.iscegui/logs/`
- `<work_dir>/.iscegui/inputs/`
- `<work_dir>/.iscegui/dem_import/`
- `<work_dir>/.iscegui/visualize/`

Native ISCE outputs remain in standard folders (`run_files/`, `reference/`, `coreg_secondarys/`, `merged/`, etc.).

## 6. Key Processing Notes

- BBox is SNWE rectangle only.
- Empty bbox (common overlap mode) is not a hard final crop.
- GeoTIFF import path expects geographic WGS84 grid.
- Vertical reference conversion is user-driven (`EGM96` vs `WGS84`).
- Burst-level controls are verify-only in UI (processing remains swath-level).

## 7. Frequent Output Targets

- Interferogram/coherence products in `merged/interferograms/`
- Merged SLC products in `merged/SLC/`
- Quicklook BMP exports under `.iscegui/visualize/`
- Troubleshooting logs under `.iscegui/logs/`

## 8. WSL Notes

- On WSL/WSLg only, app defaults to `QT_QPA_PLATFORM=xcb` when not explicitly set.
- You can still override manually:

```bash
QT_QPA_PLATFORM=wayland isce2-gui
```

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common failures and fixes.

## 9. Validation Commands

```bash
ruff check src tests
PYTHONPATH=src pytest -q
python -m build
```
