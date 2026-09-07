# CLI

On servers without a display, `insar-pilot-cli` drives the same project state as the GUI. It reuses the exact same Qt-free service layer, so `project.pilot` and the `logs/` output are **fully interchangeable** between the two front-ends — a project created from the CLI can be continued in the GUI, and vice versa.

## Four subcommands

| Command | Purpose |
| --- | --- |
| `init <dir> [--name NAME]` | Create the standard project layout and `project.pilot`; `--name` defaults to the directory name |
| `generate <project_dir> [--dry-run]` | Build the `stackSentinel.py` command, refuse to overwrite existing `run_files`/`configs`, execute it, and sync the run steps; `--dry-run` prints the command and exits |
| `run <project_dir> [--steps A[-B]] [--dry-run]` | Run pending steps in order, stopping on the first non-zero exit and persisting each step's status; `--steps` selects a 1-based step or range |
| `status <project_dir>` | Print a compact step / status / log table |

## Typical flow

```bash
# 1. Create the standard project layout and project.pilot
insar-pilot-cli init /data/aoi_stack --name aoi_stack

# 2. Preview the generation command (no execution); then generate and sync run_files
insar-pilot-cli generate /data/aoi_stack --dry-run
insar-pilot-cli generate /data/aoi_stack

# 3. Run steps sequentially (stops on first non-zero exit); a range is also allowed
insar-pilot-cli run /data/aoi_stack
insar-pilot-cli run /data/aoi_stack --steps 2-5

# 4. Inspect per-step status and log paths
insar-pilot-cli status /data/aoi_stack
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | A shelled command failed |
| `2` | Usage/config error (bad arguments, missing/malformed project, blocked generation) |

## Scope and interoperability

- Data download, DEM, and AOI preparation are still done in the **GUI** today; the CLI focuses on **generation, execution, and status**. A common split: download and prepare SLC/EOF/DEM in the GUI, then move the project to a headless server for batch execution via the CLI.
- `run` uses the same per-step status, log naming, and batch splitting as the GUI, so you can switch back to the GUI's Run page at any point.
- Like the GUI, `generate` **will not** overwrite an existing `run_files`/`configs` — clear those directories first if you need to regenerate.

Full page reference: [User Guide](user-guide.md).
