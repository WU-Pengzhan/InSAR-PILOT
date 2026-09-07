# Web GUI and API

Vue 3 + TypeScript + Quasar; Leaflet for SAR search, OpenLayers + Proj4js for
scientific product layers; Apache ECharts.
FastAPI /api/v1 and WebSocket; generated TypeScript interfaces from OpenAPI.

## Shell

Home: Recent Projects, New, Open, Explore.
Left: semantic Project Explorer with Project / Data / Processing / Products / QC /
Logs / Post-processing. Alternate Files View is lazy read-only filesystem browsing.
Center: object-driven tabs for Pipeline / Map / DEM / IFG / Baseline / QC / Run / Log.
Right: Inspector Properties / Metadata / Processing / QC / History.
The Inspector can collapse completely and restore its previous splitter width;
both preferences persist across refreshes. The header uses the original project logo.
Bottom: jobs, queue, progress, warnings and cancel. Compute Inspector shows capabilities.

Global/project search reuse the same component/service. Mission All is grouped,
not a mixed processing dataset. No wizard/Next/Previous model.

Pipeline shows all steps, acquisition/pair matrix, current execution, active output,
QC and freshness separately. Rerun preview shows expanded upstream scope.
Logs are diagnostic and paginated; structured Events are primary. Unknown progress
is indeterminate. Running jobs never steal focus.

## GIS

SAR search uses Leaflet with the original Esri World Imagery source through the
authenticated legacy tile adapter. No labels, administrative boundaries, terrain
or street-map fallback are added. Required imagery attribution remains visible.
The scientific map uses the same imagery basemap without changing product CRS.
Search supports two-corner AOI drawing, BBOX/WKT/KML/Shapefile, legacy mission
filters, selectable acquisition footprints, result pagination and selection size.
Imagery failures leave AOI and footprints usable and show an explicit notice.

Published spatial artifacts register layers automatically. Metadata registration
does not trigger full raster reads. Map-grid data and GUNW use actual CRS and axes.
Radar-grid products use verified geolocation derivatives or an image workspace and
footprint; never pretend radar pixels are EPSG:4326. Tiles/reprojection are cache.
Expose legend, style, nodata, pixel values, provenance and metadata.

ECharts: baseline network, acquisition timeline, QC distribution and durations.
Retain Chinese/English and light/dark themes.

## API groups

Projects (recent/create/open/import/revise/attach), Data (capabilities/search/
download/library/import), Pipelines (definitions/state/preview/submit), Runs
(history/detail/rerun/active/provenance), Jobs (list/cancel/resources), Artifacts/QC/
Layers, Events/logs, Compute.

Plans freeze revision and input versions; stale submission returns conflict.
Access files by registered resource IDs. Loopback-only session, Origin validation,
single service instance. Browser closure does not stop jobs. Launch reuses service;
--no-browser is supported. Distribute compiled frontend; no end-user Node/Electron.

## Acceptance

1440x900 and 1366x768, 100/125/150% browser scaling, Chinese/English, light/dark,
empty/loading/error/data, long names/paths, large tables, map zoom, tab switching
and splitters. Validate typecheck, components, browser integration and visual layout.
## Host file and directory selection

The Web preview uses an authenticated in-workbench picker for New Project, Open
Project, source imports, processor Python and NISAR templates. The picker lists
metadata on the processing host and returns absolute paths. It does not upload
SAR files, recursively enumerate SAFE contents or invoke Qt, Zenity, Windows
dialogs or browser-specific File System Access APIs. Firefox is supported by the
same ordinary HTTP and Vue components as Chromium browsers.

- Native Linux browser: browse the local Linux home, filesystem and mount points.
- Windows browser connected to WSL: browse the running distribution; Windows
  drives are available at their Linux mount points, commonly `/mnt/c` and `/mnt/d`.
- Optional pasted Windows drive paths use `wslpath`; current-distribution
  `\\wsl$\<distribution>\…` and `\\wsl.localhost\<distribution>\…` paths map to Linux.
  Other distributions and unmounted network shares are rejected explicitly.
- Selecting a parent and entering a new folder name only fills the form. Project
  creation validates an empty destination and creates it when the user submits.
- Imports can select multiple files and SAFE folders across directories. Cancel
  preserves the existing form. Runtime executable symlink paths are preserved.

`/api/v1/filesystem/locations`, `/filesystem/resolve` and
`/filesystem/directories/{resource_id}` require the same local session and Origin
checks as other APIs. Navigation IDs are signed for the service lifetime; no
arbitrary file-content endpoint is added. Listings are paginated and support
name filtering and hidden files. Errors leave the dialog usable for retry or
choosing a different directory. Selection does not authorize deletion or moving.

## Download management

Downloads have persistent entries in the left navigation and status bar, and
are also included in Jobs. Global and project-bound download submissions open
the same queue. Cards list every selected acquisition and planned SLC/RSLC/EOF
file before authentication returns progress, followed by paths, status, bytes,
speed, ETA and any available diagnostics. Unknown progress stays indeterminate.
Pause, resume, cancel and retry operate on the application download queue. Pause
stops transport while preserving partial files and aria2 resume data. Resume
creates a linked attempt from the frozen product selection; prior terminal
attempt records are retained. Pending stop states are visible until shutdown.

## File picker layout

The picker uses a fixed 920x700 CSS-pixel card capped by the viewport, with
compact spacing for short viewports. Navigation, empty/loading/error states,
long names and selection changes do not resize or reposition the card. Places
are a scrollable icon sidebar with short labels and full-path hover titles.
The editable address, breadcrumb trail, filter and action footer remain separate
from the internally scrolling directory list. Names and the selected path use
ellipsis with full-text titles; selected file chips scroll horizontally.

## Explicit application exit

Closing the browser keeps the service and detached jobs running. The header
shows backend connectivity and an Exit app action. The exit dialog checks all
registered projects, download queues and identifiable application/processor
workers. Active work blocks exit and links to Jobs; users pause/cancel downloads
or cancel processing there before retrying exit. An idle exit preserves projects,
history and downloaded files, stops the service and displays a completion page.
Unexpected disconnection is labelled separately and never treated as confirmed
exit. The page cannot close a browser tab opened by the user; it tells the user
when the tab can be closed. CLI --status and --stop never launch a service.
