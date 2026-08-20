# Installation

InSAR-PILOT targets **Ubuntu Desktop** and **WSL2/WSLg**. The Python package supports 3.10–3.12; the complete processing environment currently pins Python 3.10 for ISCE2/GDAL compatibility. Real processing needs ISCE2/GDAL/aria2 and cannot be installed with pip/uv alone, so it requires a conda environment.

## Two scenarios

- **Development / testing only** — a lightweight uv-managed virtual environment is enough; no ISCE2 required.
- **Running GUI processing** — needs the full conda runtime from `environment.yml`.

## One-command runtime install (recommended)

```bash
# After downloading and extracting the GitHub Release source ZIP:
cd InSAR-PILOT
bash install.sh
conda activate insar
insar-pilot
```

Users only need an initialized Conda installation and network access to `conda-forge`; ISCE2, GDAL, Git, and system Python packages do not need to be preinstalled. `install.sh` creates or updates the default `insar` environment, installs the application and complete runtime, and verifies it. Use `bash install.sh my-insar` to select another environment name.

`environment.yml` installs the GUI, QtWebEngine map, ISCE2 2.6.5, GDAL, aria2, sentineleof, asf-search, and SNAPHU. SLC downloads require `aria2c` for multipart resumable transfers.

!!! note "The launching process is the runtime"
    InSAR-PILOT detects the runtime (ISCE2/GDAL/snaphu/stack tools) from the **process that launches it**. Activate the environment where InSAR-PILOT is installed before starting it; `insar` is only the example name used here. Project files never switch Conda environments.

## Development install (uv, no ISCE2)

Day-to-day development uses the repo's uv-managed virtual environment, which provides PySide6 and the standard library — enough for the test suite and linter:

```bash
uv sync --extra dev

# Full test suite (headless Qt, offscreen platform plugin)
QT_QPA_PLATFORM=offscreen uv run pytest -q

# Lint
uv run ruff check src tests
```

See the [Contributing guide](https://github.com/WU-Pengzhan/InSAR-PILOT/blob/main/CONTRIBUTING.md) for details.

## WSL2 / Ubuntu notes

- The launcher auto-selects a suitable Qt display backend (`xcb`/`wayland`) for WSL2/WSLg vs. native Ubuntu; a user-provided `QT_QPA_PLATFORM` always wins.
- If Qt reports missing xcb runtime libraries:

    ```bash
    sudo apt install -y libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0
    ```

- More display-backend, map, DEM, and run_files issues: [Troubleshooting](troubleshooting.md).

## Next

- Get the GUI running fast: [Quickstart](quickstart.md).
- Full end-to-end flow: [User Guide](user-guide.md).
