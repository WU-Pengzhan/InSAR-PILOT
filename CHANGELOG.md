# Changelog

All notable changes to this project are documented here.

## [0.1.0] - 2026-04-13

### Added
- Stage 2 practitioner workflow shell:
  - `Data Sources`
  - `AOI + BBox + IW`
  - `Processing Plan`
  - `Run Monitor`
  - `Results & Visualization`
- AOI import and verification enhancements:
  - KML/SHP AOI import to fill ISCE bbox
  - IW recommendation from Sentinel annotation geometry
  - verify overlay for AOI, bbox, IW, auto-selected bursts, and DEM coverage bounds
- DEM coverage assessment in verify flow (`full/partial/none`) with warnings.
- Visualization pipeline upgrades:
  - SLC / interferogram / overlay quicklook support
  - preview/export reuse when parameters and inputs are unchanged
- Run monitor improvements:
  - subcommand-level status tracking
  - selected-step execution support

### Changed
- UI theme standardized to light professional desktop style.
- WSL launch compatibility improved by defaulting `QT_QPA_PLATFORM=xcb` unless explicitly set.
- Project persistence expanded for Stage 2 workflow and visualization state.

### Quality
- Unit/integration tests expanded for AOI import, IW recommendation, DEM coverage, runfile planning, and visualization service.
