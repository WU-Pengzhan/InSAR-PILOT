# Contributing to InSAR-PILOT

The product direction is Web only, Sentinel-1 first, then NISAR. Read
[AGENTS.md](AGENTS.md), the [current architecture](docs/architecture/overview.md)
and the [Sentinel page proposal](docs/architecture/sentinel-workbench.md).

## Work in small, reviewable page increments

Agree on the page's purpose, inputs, actions, output and failure states before
implementation. Establish domain/application/API contracts, then build the page
and validate it. Do not convert every roadmap item into a simultaneous task.
The five-page division is a proposal until reviewed with the user.

Do not develop new Qt UI features. Retained PySide6 code is migration material;
removing dependencies and changing installed entrypoints is a separate technical
cleanup, not an excuse to keep two product roadmaps.

The near-term product is a phase stack, with its exact scientific representation
still to be confirmed. Unwrapping and broad phase numerical comparisons are
deferred. Structural validity and honest execution status remain required.
Preserve official TOPS burst processing and existing ISCE3/openSEPPO behavior.

## Verification

Use the application Web Python environment for engine/API tests and the existing
insar environment for affected reused backend tests. For frontend changes run
`npm test` and `npm run build` in `frontend/`, then the relevant Playwright cases.
Run Ruff and applicable mypy checks for changed Python modules. Check documentation
with `python -m mkdocs build --strict` in an environment containing the docs tools.

Protect existing work and read-only scientific inputs. Keep runs, artifacts and logs
isolated. Do not rerun heavy scientific jobs for documentation or cosmetic changes.
Report evidence and limitations in [migration status](docs/architecture/migration.md).
Archived guidance is not a second source of current requirements.
