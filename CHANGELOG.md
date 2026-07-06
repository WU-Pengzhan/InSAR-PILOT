# Changelog

All notable changes to this project are documented here.

## [1.0.0] - 2026-07-06

### Added

- First stable InSAR-PILOT release for guided Sentinel-1 SAR/InSAR desktop processing.
- `.pilot` project file workflow with protected JSON loading, legacy project compatibility, and project-folder defaults.
- InSAR-PILOT branding assets, GUI logo integration, window icon support, and refreshed documentation screenshots.
- Runtime environment probing for the active launch environment, including ISCE2 stack tools, GDAL, snaphu, and aria2c checks.
- Project start page with recent projects, project workspace actions, version information, and notices.

### Changed

- README and user guides now present InSAR-PILOT as a public v1.0.0 release powered by ISCE2.
- Setup and Data pages received layout, spacing, label, and interaction refinements for a cleaner desktop workflow.
- Processing setup now uses shorter operator-facing labels such as `SLC folder`, `EOF folder`, and `Work folder`.
- Recent project rows behave as full clickable items instead of selectable text blocks.
- Version metadata is aligned at `1.0.0`.

### Fixed

- Runtime root detection no longer fails when ISCE2 is installed outside the active conda prefix.
- Empty footprint maps no longer show unnecessary startup warnings.
- Required Parameters layout avoids overlapping editors and browse buttons.
- README files no longer expose internal GitHub branding-upload notes.

## [0.2.0] - 2026-07-05

### Added

- Project-based InSAR-PILOT shell with Start, Data, Setup, Run, and Results pages.
- Project workspace layout with project metadata, data folders, processing work folder, logs, quicklook outputs, and cache.
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
