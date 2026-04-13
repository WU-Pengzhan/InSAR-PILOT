# UI/UX Redesign (Stage 2)

## Goal

Reorganize the desktop app around practitioner tasks while preserving the existing ISCE2 orchestration backend.

## Current Implemented Shell

Main window composition:

- top project header
- left workflow navigation
- center task page area
- right project summary sidebar
- bottom collapsible log console

Workflow pages currently implemented:

1. `Data Sources`
2. `AOI + BBox + IW`
3. `Processing Plan`
4. `Run Monitor`
5. `Results & Visualization`

## Implemented Capability Mapping

### Data Sources

- runtime configuration and environment validation
- dataset/orbit/DEM/AUX/workdir inputs
- data preparation and DEM import/conversion

### AOI + BBox + IW

- bbox SNWE input
- AOI import from KML/SHP to fill bbox
- IW recommendation from annotation geometry
- verify panel showing AOI/bbox/IW and auto-selected bursts
- DEM coverage overlay and warning summary

### Processing Plan

- workflow/coreg/looks/parallel/reference controls
- command preview and workflow generation

### Run Monitor

- step and subcommand visibility
- run next/selected/remaining execution controls
- live logs and run-file transparency

### Results & Visualization

- output discovery and browsing
- preview/export for SLC/interferogram/overlay
- preview reuse when render signature is unchanged

## Preserved Transparency

The UI keeps advanced-user observability visible:

- run-file paths
- generated command text
- step/subcommand status and exit codes
- log paths and log content
- output absolute paths

## Deferred / Out of Scope

- polygon AOI editing on a map canvas
- manual burst-range editing as processing input
- robust multi-frame merge UX

These remain future work and are not claimed as current functionality.

## Theme Direction

- light professional desktop style only
- restrained scientific visual language
- no dark-theme default

See [design-system.md](design-system.md) for concrete styling guidance.
