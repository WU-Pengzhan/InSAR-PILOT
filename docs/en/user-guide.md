# InSAR-PILOT User Guide

<p align="center">
  <img src="../assets/branding/logo.png" width="640" alt="InSAR-PILOT logo">
</p>

[Home](index.md) | [中文手册](../user-guide.md) | [Troubleshooting](troubleshooting.md)

## 1. Purpose

**InSAR-PILOT** stands for **InSAR Processing Interface and Lightweight Orchestration Toolkit**.

It is an open-source desktop processing workbench for Ubuntu Desktop and WSL2/WSLg. It organizes SAR data acquisition, processing setup, official workflow generation, run-file execution, and quicklook inspection around a project folder.

The current version focuses on Sentinel-1 processing with the official ISCE2 workflow. The long-term goal is to support more SAR sensors and time-series InSAR workflows, including SBAS- and StaMPS-based processing chains.

v1.0.0 is the first stable release. Validate the runtime, download path, and processing outputs on small sample projects before moving into production workflows.

## 2. Start Page and Project Workspace

![Start page](../assets/screenshots/start-page.png)

The application starts from a project page. Production work should always use a dedicated project folder so data, logs, state, and outputs stay together.

Default project layout:

```text
project_root/
  project.pilot
  data/
    SLC/
    Orbit/
    DEM/
  processing/work/
  outputs/quicklooks/
  logs/
  .insar_pilot/cache/
```

`project.pilot` stores GUI state, download settings, processing configuration, execution state, and quicklook settings. The file uses the dedicated InSAR-PILOT suffix while keeping an auditable JSON payload internally. Legacy `insar_pilot_project.json` files can still be loaded. Native processing outputs remain in the processing work directory.

## 3. Data Acquisition

![Data acquisition](../assets/screenshots/data-acquisition.png)

The Data page prepares Sentinel-1 inputs:

- test Earthdata/ASF credentials
- enter dates, AOI, orbit direction, relative orbit, and polarization
- search ASF Sentinel-1 SLC scenes
- inspect footprints and metadata in the map/table workspace
- select scenes and download SLC ZIPs plus EOF orbit files
- import the downloaded workspace into Setup

Recommended order: test credentials first, then define search filters. Download progress does not reset the map view, and logs only auto-scroll when the user is already at the bottom.

## 4. Processing Setup

![Processing setup](../assets/screenshots/processing-setup.png)

Setup centralizes pre-processing configuration:

- validate ISCE2/GDAL/snaphu/stack tools in the active runtime
- confirm Sentinel-1 input folder, EOF folder, DEM path, and work directory
- prepare ZIP/SAFE input manifests
- set AOI/BBox, IW swaths, reference scene, and polarization
- configure workflow, coregistration, looks, and parallelism
- run Preflight for paths, permissions, missing inputs, DEM/EOF readiness, and run_files/configs conflicts
- preview and generate the official processing command and `run_files`

Primary screens show operator-level choices. Full paths, commands, and diagnostics remain available in Technical Details or logs.

## 5. Run Executor

![Run executor](../assets/screenshots/run-executor.png)

The Run page executes and recovers processing:

- `Run Next Step` executes the next pending/failed/cancelled step
- `Run Selected Step` reruns the selected step
- `Run Remaining Steps` runs the remaining workflow
- `Stop` requests cancellation of active execution

Each step and subcommand records status, log path, exit code, and messages. After a failure, inspect the subcommand log, fix inputs or runtime issues, then continue with selected/next execution.

## 6. Results Quicklook

![Results quicklook](../assets/screenshots/results-quicklook.png)

Results is limited to output browsing and visualization:

- scan processing outputs
- browse discovered SLC, interferogram, merged products, and quicklooks
- generate SLC, interferogram, or overlay previews
- export BMP quicklooks

This page does not own workflow state. State is stored in the project file, Run page, and logs.

## 7. Relationship to ISCE2

InSAR-PILOT's current Sentinel-1 processing capability is built around [ISCE2](https://github.com/isce-framework/isce2) and its official [stack processors / TOPS stack](https://github.com/isce-framework/isce2/blob/main/contrib/stack/README.md). ISCE2 is an open-source InSAR scientific computing environment; InSAR-PILOT adds a desktop interface, project workspace, and execution monitor around its Sentinel-1 TOPS workflow.

> Attribution and scope: InSAR-PILOT is not an official ISCE2 project, does not modify ISCE2 algorithms, and does not reinterpret ISCE2 outputs as a new processing engine. This project respects and depends on the ISCE2 open-source work while providing a clearer interface for input preparation, command generation, run-file execution, and log inspection.

The GUI:

- collects and saves parameters
- prepares input folders and DEM products
- builds the official `stackSentinel.py` command
- parses generated `run_files/run_*`
- executes run files through the shell
- displays logs, status, exit codes, and outputs

The GUI does not modify ISCE2 algorithms, fake outputs, or hide run files as a black box.

## 8. Install, Launch, and Test

Install:

```bash
conda env create -f environment.yml
conda activate insar
pip install .
insar-pilot
```

Optional map support:

```bash
pip install '.[map]'
```

Tests:

```bash
conda run -n insar env PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest -q
```

## 9. Headless / CLI

For servers without a display, `insar-pilot-cli` reuses the same Qt-free service
layer as the GUI, so `project.pilot` and the `logs/` output are interchangeable
between the two front-ends. Four subcommands:

- `init <dir> [--name NAME]` — create the standard project layout and `project.pilot`.
- `generate <project_dir> [--dry-run]` — build the `stackSentinel.py` command,
  refuse to overwrite existing `run_files`/`configs`, execute it, and sync the
  discovered run steps. `--dry-run` prints the command and exits.
- `run <project_dir> [--steps A[-B]] [--dry-run]` — run pending steps in order,
  stopping on the first non-zero exit and persisting each step's status. `--steps`
  selects a 1-based step or range.
- `status <project_dir>` — print a compact step/status/log table.

Exit codes: `0` success, `1` a shelled command failed, `2` usage/config error.
Data/DEM/AOI preparation is still done in the GUI today.

```bash
insar-pilot-cli init /data/aoi_stack --name aoi_stack
insar-pilot-cli generate /data/aoi_stack --dry-run
insar-pilot-cli generate /data/aoi_stack
insar-pilot-cli run /data/aoi_stack --steps 2-5
insar-pilot-cli status /data/aoi_stack
```
