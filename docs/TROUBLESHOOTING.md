# Troubleshooting

## 1. GUI starts but dropdown/popup menus behave incorrectly on WSLg

Symptom:
- dropdown menu does not close after selection
- popup appears detached or selection looks broken

Cause:
- Qt backend compatibility issue on some WSLg Wayland setups

Default behavior in this app:
- launcher sets `QT_QPA_PLATFORM=xcb` by default (only if user did not set it)

Manual override examples:

```bash
QT_QPA_PLATFORM=xcb isce2-gui
```

```bash
QT_QPA_PLATFORM=wayland isce2-gui
```

Use `xcb` if you see popup/dropdown issues.

## 2. `stackSentinel.py` / `SentinelWrapper.py` / GDAL tools not found

Run `Validate Environment` in `Data Sources` first.

Check:
- conda env is activated
- `isce2` is available in the active env (installed via `environment.yml`)
- ISCE root path is correct
- required commands are on PATH in your shell init

## 3. DEM import fails

Checklist:
- DEM exists and path is correct
- GeoTIFF is geographic WGS84 grid (for direct import path)
- height reference is correctly chosen (`EGM96` vs `WGS84`)
- inspect `.iscegui/logs/dem_import_*.log`

## 4. Verify warns that DEM coverage is partial/none

Meaning:
- selected bbox/IW/auto-burst extent is not fully covered by provided DEM

Impact:
- processing may still run, but geometry-dependent quality can degrade at margins

Recommendation:
- use DEM with larger spatial margin around expected burst coverage

## 5. `libtinfo.so.6` warnings in terminal

This is usually a shell/runtime library mismatch warning in mixed conda/system contexts.

If commands complete and outputs are valid, treat it as environment warning and continue.

## 6. Step status and rerun behavior

- `Run Next Step` selects from `pending/failed/cancelled`
- if you need to rerun a `success` step, use `Run Selected Step`

## 7. Where to inspect logs

Primary GUI logs:
- `<work_dir>/.iscegui/logs/`

Common files:
- `stack_generate.log`
- `run_*.batch_*.log`
- `run_*.cmd_*.log`
