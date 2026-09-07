# Implementation status and migration gates

Accepted sequence: Design → Model → Backend → GUI → Migration.
Do not infer delivery from this target specification. Legacy entrypoints remain
operational until their replacements pass corresponding scientific gates.

For a Chinese feature inventory, evidence boundaries and prioritized remaining
work, see the [2026-09-05 status review](status-review-2026-09-05.md).

| Phase | Work | Status |
|---|---|---|
| 0 | Architecture, legacy archive, baseline and guidance | Implemented; strict documentation build passes |
| 1 | Domain, revisions, SQLite, artifacts, lineage, QC, freshness | Core implemented; complete crash-injection acceptance remains |
| 2 | Jobs, isolated workspaces, official processor adapters | Headless execution works; Sentinel unwrap scientific gate fails |
| 3 | Library/search/download, QC/GIS backend, REST/events | Functional subset; preparation and reader coverage remain |
| 4 | Vue/Quasar workbench and browser acceptance | Functional preview; complete visual/E2E acceptance remains |
| 5 | Legacy import, scientific regression, default switch | Evidence-preserving import; default switch deferred |
| 6 | Remove superseded Qt paths; postprocessing input contract | Bundle inspection available; Qt removal deferred |

## Run the preview

Install the application separately from the processing environments:

```bash
python -m venv .venv-web
.venv-web/bin/pip install -e '.[web]'
.venv-web/bin/insar-pilot-web
# Without opening a browser:
.venv-web/bin/insar-pilot-web --no-browser
```

The package still declares legacy Qt dependencies until migration acceptance.
The new engine itself runs and is tested without Qt. Built frontend resources
are included; Node is needed only for frontend development. Existing entrypoints
retain their behavior.

Implemented use cases include projects, local import and shared Library,
grouped search, download-only and selection-to-project flows, prepared-input
pipeline configuration, reviewed execution plans, history, cancellation, QC,
active/freshness, logs/events, raster access, and legacy evidence import.
NISAR currently schedules one official numerical workflow; its preparation and
publication orchestration views are not yet fully represented as six domain steps.
Sentinel preserves all 16 official stages.

## Persistence safeguards implemented

- Revision checks, pending revision reconciliation, atomic project JSON writes,
  SQLite foreign keys/WAL and validation of manual definition edits.
- Immutable terminal Runs and Artifact records; fresh IDs, rerun relations,
  execution workspaces, logs and copied outputs.
- Scientific signatures include parameters, input versions, runtime package
  observations and template contents. Presentation does not change freshness.
- QC re-evaluation appends reports and updates usability without rewriting
  historical Run results or recomputing images.
- Published VRT/XML dependencies are frozen, including registered virtual ZIP
  sources. No hard links connect processing files to historical results.
- Per-execution worker leases exclude duplicate dispatch. Service recovery
  observes live workers; lost worker exit statuses remain interrupted.
  Uncommitted files never establish successful execution.
- Current worker launches import execution-owned source copies, so editing the
  app while a worker is queued cannot change its implementation. This safeguard
  was added after the initial regression workers started.

## Outstanding implementation and acceptance

These are not delivered capabilities:

- Full publication/queue crash injection and orphan reconciliation tooling;
  asynchronous strong content verification for external inputs.
- Complete DEM acquisition/vertical-grid proof and openSEPPO Range subset
  preparation in the new Data/Job workflow. Legacy capabilities remain available.
- Complete versioned output contracts and QC extractors for every Sentinel stage.
- Persistent multi-layer UI, full-resolution window/tile service and complete GIS
  interactions. Current maps use bounded display samples and a consistent scale.
- Complete response-model OpenAPI types, professional parameter forms, all
  translated messages and complete frontend component/E2E coverage.
- Native browser zoom at 125%/150%, large-list/map/splitter acceptance, download
  authentication integration, HKIA performance and CUDA acceptance.

## Recorded checks

- New headless suite: 33 tests passed in the separate Web environment.
- Legacy environment: 490 passed, 1 skipped;
  the skipped API module is exercised in the Web environment.
- Frontend type/build checks and three Vitest tests pass; chart/map code loads
  on demand, with production JS chunks below 500 kB.
- Targeted mypy checks pass across 17 new Python files; MkDocs strict build passes.
- Browser checks cover 1440×900 and 1366×768, English/light and Chinese/dark.
  Native zoom shortcuts did not change in-app browser scale, so zoom acceptance
  is not claimed.
- NISAR RIFG real execution passed; circular phase RMSE against the existing
  golden RIFG is 2.2309284281344733e-7 rad. Evidence:
  `artifacts/nextgen-nisar-rifg-regression.json`.
- Sentinel stages 1–15 succeeded. Stage 16 preserves the SNAPHU 1.4.2 error
  `one or more interferogram dimensions too large`. Looks remain 1×1.
- GUNW coordinate lookup was corrected for ISCE3 0.25 product grids. The first
  GUNW validation failure remains immutable; its isolated retry is separate.

## Gates

0: one non-conflicting target specification; preserve dirty working-tree baseline.
1: profile lock; unique runs; crash-safe project/artifact transactions; correct stale
propagation; QC-policy changes do not recompute numerical products.
2: headless submit/cancel/history; official command and template parity; complete
provenance/logs; reruns leave historical assets and sidecars unchanged.
3: library reuse and provider partial failure; Range/full download; verified DEM
vertical grids; product shape/dtype/CRS checks; correct radar semantics; event replay.
4: complete data entry flows and inspector; persistent jobs across browser closure;
typecheck, components, E2E and visual matrix.
5: new-directory import with no fabricated history; CPU real-data parity for both
processors before changing default or removing Qt dependencies.
6: keep legacy readers and evidence, expose standard postprocessing input bundles;
no placeholder scientific execution.

## Scientific regression

Use new output directories with YanAnHighway minimum Sentinel pair and NISAR golden
pair/subsets. Check burst seam, nodata, geometry, unwrap; HDF5 schema, shape/dtype,
axes/components, phase/coherence. HKIA is batch/performance evidence. Freeze metric-
specific tolerances from existing evidence; don't use broad tolerances to hide changes.
New runtime or CUDA must be validated independently. Unit mocks are not parity.
Raw/golden sources remain read-only.

## Scientific environment sensitivity found

The isolated GUNW retry succeeded and committed eight logical artifacts sharing
three HDF5 containers (RIFG, RUNW, GUNW). Its explicit OpenMP setting of four threads
produced a RIFG circular phase RMSE of 4.009463894577217e-4 rad against the golden
RIFG, exceeding the original environment's regression tolerance. GUNW repeatability
against the earlier numerical output showed 3.9412770788730723e-4 rad RMSE, while
coordinate axes and connected components were exact. This is an unresolved
scientific environment difference, not a passing golden comparison.

A further RIFG execution using the originally inherited thread settings succeeded:
phase RMSE 2.2309284281344733e-7 rad; coherence RMSE 7.442498054669359e-8. It passes
the recorded candidate tolerances of 5e-7 rad and 1.2e-7. This evidence does not
qualify arbitrary thread settings, CUDA, or the four-thread GUNW run.

Machine-readable evidence is in `artifacts/nextgen-nisar-products-regression.json`,
`artifacts/nextgen-nisar-rifg-regression.json` and
`artifacts/nextgen-sentinel-regression.json`. Original science environment packages,
golden data and legacy default entrypoints were not replaced.
## File picker follow-up

Implemented a shared host-side picker at the five Web path entry points: project
creation, project opening, source import, runtime executable and NISAR template.
It supports native Linux directory semantics and Windows browsers connected to
WSL, including mounted drives and optional drive/WSL UNC path translation. New
project folder selection is non-mutating until form submission; imports reference
existing files and SAFE directories without a browser upload.

Added headless API coverage for authentication, pagination, hidden names, Unicode,
permissions, missing paths, symlink preservation and cross-environment path rules;
component tests cover navigation, multi-selection, cancellation and recovery.
Focused Playwright tests cover existing-project opening, new-project creation,
multi-selection and dialog bounds in Firefox/Chromium, with an optional Windows
Edge project against the same WSL test server. This is targeted picker coverage,
not completion of the full GUI acceptance matrix or scientific migration gates.

Picker validation on 2026-09-05: 39 headless tests and 8 component/unit tests
passed; production typecheck/build passed. Browser checks passed 5 cases in
Windows Edge against WSL and 10 in Linux Firefox/Chromium against WSL. A further
Firefox run with WSL environment variables unset passed 4 Linux-mode cases and
skipped the Windows-only path case. This checks native Linux path behavior in
the Ubuntu test environment; a separate bare-metal Linux installation was not
used. English/light and Chinese/dark dialogs were inspected at 1366×768.

Run `npm run build`, install Playwright browsers with
`npx playwright install --with-deps chromium firefox`, then `npm run test:e2e`
from `frontend/`. Set `PILOT_E2E_PYTHON` to the headless application interpreter
if needed. The test server creates temporary fixtures and has worker recovery
disabled. For Windows Edge testing, start `tests/web_browser_server.py` in WSL
and set `PILOT_E2E_BASE_URL=http://127.0.0.1:8767` in the Windows test process.
## Browser session follow-up

New tabs now reuse the existing HttpOnly session cookie without sending an empty
Authorization header or an invalid empty WebSocket subprotocol. Expired tab
credentials can fall back to a valid browser cookie; protected operations still
require authentication. A browser with no valid session sees connection
instructions before project APIs are called. Refresh alone cannot authenticate
a brand-new browser; use the launcher in the same application state directory.

On WSL, the launcher opens the Windows default browser through PowerShell interop
and passes the authenticated URL through stdin. Native Linux continues to use
the configured Linux browser. Failure to open a browser is now reported.
The Web extra and Web CI include `wsproto` so live event connections work with
the installed Uvicorn server. Scientific runtime packages were not modified.

Validated with 8 targeted Python tests, 13 frontend unit/component tests, a
production build and 6 session E2E cases across Windows Edge and Linux Firefox,
including a real cookie-authenticated WebSocket. No unauthenticated session-token
endpoint was added.

## Workbench shell and acquisition follow-up

Implemented the original logo, persistent Inspector collapse/restore and a
Leaflet SAR Explorer with imagery-only Esri tiles through the original tile
adapter. Search supports BBOX/WKT/KML/Shapefile, rectangle drawing, Sentinel and
NISAR filters, footprints, result pagination and selection size. Scientific GIS
retains OpenLayers and uses the same imagery-only basemap. No place-name or
administrative-boundary overlay or street-map fallback is added; attribution is
retained. Tiles use direct networking, matching search; this machine's inherited
proxy returned 403 while direct imagery requests returned valid JPEGs.

Download jobs reuse the original DownloadService and aria2c transport: Sentinel
SLC with EOF and NISAR full RSLC. The application can select an existing Linux
aria2c outside its PATH; workers freeze the executable selection and reuse the
existing Earthdata credential loader. The UI reports readiness, progress, bytes,
speed, ETA and cancellation. Lock waits are cancellable and repeated progress
saves are throttled. Project downloads bind EOF as orbit inputs rather than SAR.
The running preview now uses the existing insar environment's aria2c. Credentials
were found locally but were not authenticated remotely. No real download or
scientific processing was started for this UI change. Web Range subset and DEM
preparation remain unconnected; this is not full legacy acquisition UI parity.

Validation on 2026-09-05: 13 targeted Web/API tests, 78 legacy downloader tests,
13 frontend unit/component tests and six Explorer E2E cases passed across Linux
Firefox/Chromium and Windows Edge connected to WSL. Ruff, applicable mypy with
the application interpreter, and the production typecheck/build passed. Real
imagery was checked through the authenticated live endpoint (200 image/jpeg)
and visually at 1366x768 in English/light and Chinese/dark, including Inspector
collapse. Screenshots are `artifacts/nextgen-explorer-imagery-1366.png`,
`artifacts/nextgen-explorer-collapsed-1366.png` and
`artifacts/nextgen-explorer-zh-dark-1366.png`. This does not complete the broader
GUI scaling matrix or the remaining scientific migration gates.

## Download visibility and controls follow-up

Added persistent Downloads navigation, a combined Jobs view and full acquisition
and SLC/RSLC/EOF file lists, including the pre-transfer authentication/lock phase.
Download cards expose pause, resume, cancel and retry with paths, progress and
linked attempt history. Project-bound submissions open Downloads as well.

Pause records separate queue intent, so existing workers can still finish their
immutable attempt as CANCELLED while the queue is displayed as PAUSED. Resume
and retry atomically reserve a new attempt from the original product snapshot;
duplicate continuation requests are rejected. Completed files and aria2 partial
data are retained and handled by the original downloader on continuation.
A detached observer gives cooperative cancellation time to finish, then verifies
worker command, application state directory, job ID, process group and start
identity before terminating an unresponsive group. It confirms exit before
finalizing an interrupted attempt. No user transfer was paused or cancelled
as part of deploying these controls. This is download management only; science
Run states and numerical execution are unchanged.

Validation: 20 targeted headless Web/API/control tests, 78 legacy downloader
tests, 13 frontend tests, six browser cases across Linux Firefox/Chromium and
Windows Edge connected to WSL, production build, Ruff and applicable mypy passed.
Control tests include a real inert process group with a child, retained partial
files, process identity reuse rejection, old-worker writes, frozen selection,
terminal-history preservation and duplicate resume protection. Browser cases use
fixture API responses; no real SAR transfer or remote authentication was started
for acceptance. Chinese/dark layout was inspected at 1366x768.

## File picker presentation follow-up

Replaced the long shortcut-path strip with a Places sidebar, labelled icons and
full-path hover titles. Added a styled address bar, breadcrumb trail, file-type
column, loaded-item count and fixed selection/action footer. Card geometry is
fixed and viewport-capped; only the lists and breadcrumb/selection strips scroll.
A compact short-viewport layout preserves usable content and action buttons.

Validation: six host-picker API tests, 13 frontend tests, production typecheck
and build, and 18 picker browser cases across Linux Firefox/Chromium and Windows
Edge passed. Bounds were compared across populated, empty, filtered and long-name
directories at 1366x768 and an effective 911x512 viewport. A further compact
new-project check retained its dimensions when name validation failed. These
are effective viewport checks rather than OS/browser zoom certification. English
light and Chinese dark screenshots were inspected and saved under
artifacts/nextgen-picker-light-1366.png and nextgen-picker-dark-1366.png.

The user's existing test download queue was explicitly cancelled at their request;
zero active download queues and zero remaining download workers were confirmed.
Downloaded files and partial resume data were retained.

## Sentinel-1 satellite selection

The SAR Explorer now exposes A/B/C/D as independently selectable checkboxes,
defaulting to all four. The same selection applies to the Sentinel group in
All-mission search. Empty selection is rejected before sending a request. The
existing ASF adapter already supports exact multi-platform queries and merges
their results; no processor or download behavior changed. Installed ASF platform
mappings for A/B/C/D were verified locally without a remote search. Six adapter
tests, the production typecheck/build and Explorer browser tests passed; browser
checks verify the exact ABCD and A+D request arrays and reject empty selection.

## Application exit follow-up

Implemented authenticated /application/status and /application/shutdown, a
header state indicator, an explicit exit dialog and distinct expected-exit /
unexpected-disconnection screens. Shutdown is idle-only: persisted active tasks
and identified detached workers prevent it. Mutating requests and recovery
dispatch share a gate; accepted shutdown stops further mutations and recovery
before signalling Uvicorn to exit. Scientific cancellation behavior is unchanged.
The launcher records its process identity and final service exit, and supplies
--status / --stop without implicitly starting a new server. Local control calls
bypass environment proxies. Paused download queues and historical files persist.

Validated with 13 lifecycle/launcher/API tests (including a real isolated service
start/status/stop/restart), 13 frontend tests, nine lifecycle browser cases across
Firefox/Chromium/Windows Edge, production build, Ruff and applicable mypy. Tests
cover authenticated idle exit, active work refusal, new-mutation rejection after
shutdown, worker detection, Origin validation and unexpected-disconnection text.
Browser interaction fixtures do not stop the user's running service.
