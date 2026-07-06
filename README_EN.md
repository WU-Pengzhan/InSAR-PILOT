# InSAR-PILOT

**InSAR-PILOT** stands for **InSAR Processing Interface and Lightweight Orchestration Toolkit**.

**Subtitle: Open Desktop Workbench for Guided SAR/InSAR Processing**

[中文](README.md) | [Full User Guide](docs/USER_GUIDE_EN.md) | [Troubleshooting](docs/TROUBLESHOOTING.md)

InSAR-PILOT is an open-source, desktop, lightweight SAR/InSAR processing workbench. It organizes a project folder and guides operators through SAR data acquisition, orbit and DEM preparation, processing parameter configuration, workflow generation, execution monitoring, and quicklook visualization.

The current version focuses on Sentinel-1 processing with the official ISCE2 workflow. The long-term goal is to support multiple SAR sensors and time-series InSAR workflows, including SBAS- and StaMPS-based processing chains.

> Stage note: the current release is still in a testing stage. Validate the runtime, downloads, and processing outputs on small sample projects before using it in production workflows.

## Screenshots

![Start page](docs/assets/screenshots/start-page.png)

![Data acquisition](docs/assets/screenshots/data-acquisition.png)

![Processing setup](docs/assets/screenshots/processing-setup.png)

See the [full user guide](docs/USER_GUIDE_EN.md) for more screenshots.

## Features

- Project workspace: each project stores downloads, processing work files, logs, quicklooks, and `insar_pilot_project.json`.
- Data Acquisition: Earthdata account check, ASF Sentinel-1 SLC search, scene selection, SLC/EOF download, map preview, and scene table.
- Processing Setup: data sources, EOF orbit files, DEM, AOI/BBox, IW swaths, reference scene, processing parameters, preflight, and command preview.
- Run Executor: discovers and executes `run_files/run_*`; supports next/selected/remaining execution with step, subcommand, log, and exit-code visibility.
- Results Quicklook: scans outputs and previews/exports SLC, interferogram, and overlay quicklooks.
- Desktop compatibility: the launcher selects a suitable Qt display backend for WSL2/WSLg or Ubuntu Desktop and provides a native map fallback.

## Install and Launch

Recommended conda workflow:

```bash
git clone https://github.com/WU-Pengzhan/insar-pilot.git
cd insar-pilot

conda env create -f environment.yml
conda activate insar

pip install .
insar-pilot
```

Developer mode:

```bash
pip install -e .[dev]
insar-pilot
```

## Typical Workflow

1. Create or open a project folder.
2. Use Data to configure dates, AOI, orbit direction, polarization, and search Sentinel-1 scenes.
3. Select scenes and download SLC ZIPs plus EOF orbit files.
4. Use Setup to configure DEM, BBox/IW, and processing parameters, then run Validate/Prepare and Preflight.
5. Generate the official processing command and `run_files`.
6. Use Run to execute run files while inspecting logs, subcommand status, and failures.
7. Use Results to scan outputs and generate quicklooks.

Default project layout:

```text
project_root/
  insar_pilot_project.json
  data/
    SLC/
    Orbit/
    DEM/
  processing/work/
  outputs/quicklooks/
  logs/
  .insar_pilot/cache/
```

## Platform and Runtime

- Ubuntu Desktop or WSL2/WSLg.
- Python 3.10-3.12.
- Default conda environment name: `insar`.
- `environment.yml` installs GUI dependencies, ISCE2, GDAL, aria2, sentineleof, asf-search, and runtime utilities; SLC downloads require aria2c for multipart resumable transfers.
- Optional WebEngine map support: `pip install '.[map]'`.

For Qt, map, DEM, or run-file issues, start with [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Tests

The current development test environment is the existing `insar` environment:

```bash
conda run -n insar env PYTHONPATH=src QT_QPA_PLATFORM=offscreen pytest -q
```

## License

This project is licensed under [Apache-2.0](LICENSE).
