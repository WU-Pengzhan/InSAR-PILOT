# Web workbench guide

## Projects and interface

Start with New project, Open project, or Explore. Recent projects remain accessible; startup does not automatically reopen one. Choose a name and parent directory for a new project, or select an existing `.pilot` file.
Search without a project. Closing a project leaves background tasks running. A `.pilot` file alone does not include all imagery; portable backups and OS file associations are pending.
The left pane organizes projects, the center holds your task, and the inspector shows details. Resize the project pane, collapse the inspector, and switch language or theme from the header.

## Search and downloads

Search by AOI, date and mission-specific criteria, including Sentinel-1 A/B/C/D. Footprints describe coverage, not downloaded burst subsets. Keep selected scenes across searches.
Preview scenes, optional precise orbits, full-scene DEM coverage and destination before submitting. Switching projects cannot redirect existing downloads.
Filter and paginate history; pause, resume, cancel or retry. Earlier attempts remain visible. DEM acquisition does not establish scientific suitability or the required vertical datum.

## Processing and lifecycle

Data & preparation, Parameters & generation, Run, and Products & QC have basic underlying capabilities but are not yet fully delivered to the five-page design. Navigation is not evidence of a validated scientific workflow.
The exact phase-stack contract is pending. Unwrapping, time series and broad numerical comparisons are deferred; historical failures remain unchanged.
One window uses the workbench at a time. Others reconnect when released; unexpected disconnects expire after about 15 seconds plus retry delay. Closing the browser does not cancel tasks; explicit exit requires idle tasks. Runtime status detects components without installing environments.

[Troubleshooting](troubleshooting.md) · [Implementation status](../architecture/migration.md)
