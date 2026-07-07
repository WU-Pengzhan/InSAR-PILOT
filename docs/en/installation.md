# Installation

InSAR-PILOT targets **Ubuntu Desktop** and **WSL2/WSLg** with Python 3.10–3.12. Running real processing needs ISCE2/GDAL/aria2, which **cannot be installed via pip/uv** — you must use a conda environment.

## Two scenarios

- **Development / testing only** — a lightweight uv-managed virtual environment is enough; no ISCE2 required.
- **Running GUI processing** — needs the full conda runtime from `environment.yml`.

## Runtime install (conda, recommended)

```bash
git clone https://github.com/WU-Pengzhan/InSAR-PILOT.git
cd InSAR-PILOT

conda env create -f environment.yml   # default env name: insar
conda activate insar

pip install .
insar-pilot
```

`environment.yml` installs the GUI dependencies, ISCE2, GDAL, aria2, sentineleof, asf-search, and runtime utilities. SLC downloads require `aria2c` for multipart resumable transfers.

Optional WebEngine map support:

```bash
pip install '.[map]'
```

!!! note "The launching process is the runtime"
    InSAR-PILOT detects the runtime (ISCE2/GDAL/snaphu/stack tools) from the **process that launches it**. Always `conda activate insar` before `insar-pilot`, or the Setup page's environment validation will fail.

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
