# Quickstart (GUI)

The shortest path to a running GUI. Assumes you have completed the conda [Installation](installation.md), can launch `insar-pilot`, and hold a valid [Earthdata](https://urs.earthdata.nasa.gov/) account.

## Launch

```bash
conda activate insar
insar-pilot
```

## Four pages, one line

The UI is organized by processing order — move left to right:

1. **New/Open project** — pick a project folder. All data, logs, state, and outputs bind to it.
2. **Data Acquisition** — test Earthdata credentials → set dates/AOI/orbit direction/polarization → search Sentinel-1 scenes → select and download SLC ZIPs and EOF orbit files.
3. **Processing Setup** — validate the runtime → confirm SLC/EOF/DEM and work directory → set AOI/BBox, IW swaths, reference scene, and processing parameters → run Preflight → preview and generate the `stackSentinel.py` command and `run_files`.
4. **Run Executor** — execute `run_files/run_*`, watching step/subcommand status, logs, and exit codes.
5. **Results Quicklook** — scan outputs, preview/export SLC, interferogram, and overlay quicklooks.

![Processing setup](../assets/screenshots/processing-setup.png)

## Key tips

- Validate the runtime, downloads, and outputs on a **small sample** before production.
- After a failure, inspect the subcommand log, fix inputs or runtime issues, then continue with `Run Selected Step` / `Run Next Step` — no need to restart from scratch.
- Generation **refuses to overwrite** an existing `run_files`/`configs` directory.

## Next

- Field-by-field behavior: [User Guide](user-guide.md).
- Headless servers: [CLI](cli.md).
