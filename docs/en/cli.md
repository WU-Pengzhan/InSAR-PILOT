# Legacy project CLI

`insar-pilot-cli` operates on legacy ProjectStore projects. Web uses a separate application store and Job Engine. Import a legacy project into a new Web project; do not alternate execution stores in place.

| Command | Purpose |
| --- | --- |
| `init <dir> [--name NAME]` | Create a legacy project |
| `generate <project_dir> [--dry-run]` | Preview or invoke the official generator; existing run_files/configs are protected |
| `run <project_dir> [--steps A[-B]] [--dry-run]` | Execute selected steps in order and stop on failure |
| `status <project_dir>` | Report step state and logs |

Exit codes: 0 success, 1 command failure, 2 usage/configuration error. Prepare valid inputs and an appropriate scientific runtime before generation/execution. Use isolated output directories for retries; preserve historical logs and results.
`insar-pilot-nisar --help` describes retained NISAR CLI capabilities. Current browser workflows are documented in the [user guide](user-guide.md).
