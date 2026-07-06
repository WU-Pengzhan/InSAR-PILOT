# Changelog

All notable changes to this project are documented here.

## [0.2.0] - 2026-07-05

### Added

- Project-based InSAR-PILOT shell with Start, Data, Setup, Run, and Results pages.
- Project workspace layout with `insar_pilot_project.json`, data folders, processing work folder, logs, quicklook outputs, and cache.
- Data Acquisition page for Earthdata credential checks, ASF Sentinel-1 SLC search, scene selection, SLC/EOF download, map preview, and scene table review.
- Unified Processing Setup page for data source validation, DEM/AOI/BBox/IW setup, preflight checks, command preview, and official workflow generation.
- Run Executor page with run-file step/subcommand status, selected/next/remaining execution controls, exit codes, and log paths.
- Results Quicklook page for output discovery, preview, and BMP export.
- WSL2/WSLg and Ubuntu Desktop launcher compatibility for Qt backend selection.
- Bilingual GitHub documentation with screenshots and detailed user guides.

### Changed

- Public product name is now `InSAR-PILOT`.
- Open-source documentation now clearly states that processing is orchestrated through the official ISCE2 stack workflow.
- UI and documentation are English-first inside the app, while repository documentation provides Chinese and English entry points.
- Version metadata is aligned at `0.2.0`.

### Removed

- Internal planning and UI design notes from the public repository root/docs.
- Experimental downstream conversion materials that are not part of the current Sentinel-1 processing workflow.
- Local build, test, cache, and bytecode artifacts from the release tree.
