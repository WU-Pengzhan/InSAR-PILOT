# InSAR-PILOT

<p align="center">
  <img src="../assets/branding/logo.png" width="560" alt="InSAR-PILOT logo">
</p>

**InSAR-PILOT** stands for **InSAR Processing Interface and Lightweight Orchestration Toolkit**. It is an open-source desktop workbench for SAR/InSAR processing that organizes data acquisition, orbit/DEM preparation, parameter setup, workflow execution, and quicklook visualization around a **project folder**.

The current version focuses on Sentinel-1 and the [ISCE2](https://github.com/isce-framework/isce2) TOPS stack workflow. InSAR-PILOT **does not reimplement** SAR processing — the real numerical work happens inside ISCE2 binaries; this tool builds correct commands and manages inputs and state around them.

![Start page](../assets/screenshots/start-page.png)

## Documentation

- [Installation](installation.md) — conda runtime + pip install, WSL2/Ubuntu notes
- [Quickstart](quickstart.md) — shortest GUI path
- [CLI](cli.md) — headless `insar-pilot-cli`
- [User Guide](user-guide.md) — page-by-page reference
- [Architecture](architecture.md) — layering and conventions for contributors
- [Troubleshooting](troubleshooting.md) — Qt/map/DEM/run_files issues
- [中文文档](../index.md)

## Features

- **Project workspace** — each project stores downloads, processing work files, logs, quicklooks, and `project.pilot`.
- **Data Acquisition** — Earthdata check, ASF Sentinel-1 SLC search, scene selection, SLC/EOF download, map preview, scene table.
- **Processing Setup** — data sources, EOF, DEM, AOI/BBox, IW swaths, reference scene, processing parameters, preflight, command preview.
- **Run Executor** — discovers and executes `run_files/run_*`; next/selected/remaining execution with step, subcommand, log, and exit-code visibility.
- **Results Quicklook** — scans outputs and previews/exports SLC, interferogram, and overlay quicklooks.
- **Headless CLI** — `insar-pilot-cli` reuses the same service layer; `project.pilot` and `logs/` are interchangeable between front-ends.

## License

Licensed under [Apache-2.0](https://github.com/WU-Pengzhan/InSAR-PILOT/blob/main/LICENSE). InSAR-PILOT is not an official ISCE2 project and does not modify ISCE2 algorithms; it respects and depends on the ISCE2 open-source work.
