# Troubleshooting

This page collects common runtime issues for InSAR-PILOT on WSL2/WSLg and Ubuntu Desktop.

## 1. GUI display backend does not start

Symptoms:

- the application exits before the main window appears
- Qt reports that `xcb` or `wayland` cannot be initialized
- dropdowns or popups behave incorrectly

The launcher probes display backends before creating the window:

- WSL2/WSLg prefers `xcb`, then falls back to `wayland`
- native Ubuntu Wayland prefers `wayland`, then falls back to `xcb`
- a user-provided `QT_QPA_PLATFORM` is always respected

Manual overrides:

```bash
QT_QPA_PLATFORM=xcb insar-pilot
```

```bash
QT_QPA_PLATFORM=wayland insar-pilot
```

For WSL2, make sure a graphical display is available:

```bash
echo "$DISPLAY"
echo "$WAYLAND_DISPLAY"
```

If Qt reports missing xcb runtime libraries:

```bash
sudo apt install -y libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0
```

For launcher diagnostics:

```bash
INSAR_PILOT_DEBUG_LAUNCH=1 insar-pilot
```

## 2. Map captures clicks or the window feels frozen

Symptoms:

- the startup page works normally
- after opening a project, the map pans but buttons/forms do not respond
- the issue appears on WSLg, multi-monitor layouts, maximized windows, or mixed DPI displays

Likely cause:

- QtWebEngine/Chromium created a native child window with stale event geometry.

Workaround:

```bash
INSAR_PILOT_MAP_BACKEND=native insar-pilot
```

This disables the Leaflet basemap and uses the native geometry preview so the rest of the GUI remains clickable.

## 3. Environment validation fails

Run validation from the Setup page first.

Check:

- the app was launched from the intended conda environment, for example `conda activate insar`
- ISCE2, GDAL, `snaphu`, `stackSentinel.py`, `sentineleof`, and `aria2c` are discoverable from the active runtime
- the project folder and processing work directory are writable
- the SLC, EOF orbit, and DEM paths exist

The application detects the runtime from the process used to launch it. Prefer:

```bash
conda activate insar
insar-pilot
```

## 4. ASF search or download fails

Check:

- Earthdata credentials are valid and tested in Data
- start/end dates are set
- AOI is a valid bbox or supported KML/WKT source
- `aria2c` is installed in the active environment
- the project `data/` directory is writable

SLC downloads require the aria2c backend for multipart resumable transfers. EOF downloads use the orbit-download tooling installed in the runtime environment.

## 5. DEM preparation fails

Checklist:

- DEM path exists and is readable
- GeoTIFF DEMs are geographic WGS84 grids when using direct import
- the height reference is selected correctly
- the processing work directory is writable
- inspect logs under `logs/` in the project folder

If DEM coverage warnings appear, use a DEM with spatial margin around the target bbox and swath coverage.

## 6. run_files execution fails

Use the Run page to inspect:

- failed step name
- subcommand index
- command text
- stdout/stderr log path
- exit code

Common fixes:

- rerun `Validate` and `Preflight` in Setup
- check write permissions in `processing/work/`
- confirm SLC SAFE/ZIP, EOF, and DEM inputs still exist
- use `Run Selected Step` after fixing a failed step

## 7. Where logs and project state live

For a project folder:

```text
project_root/
  insar_pilot_project.json
  logs/
  processing/work/
  .insar_pilot/cache/
```

Important logs include:

- workflow generation logs
- run-file batch and command logs
- DEM import/preparation logs
- visualization logs

## 8. Terminal warnings from QtWebEngine or DBus

Messages such as missing DBus sockets can appear in WSL/conda desktop sessions. If the GUI starts and works normally, they are usually harmless Chromium/desktop integration warnings.
