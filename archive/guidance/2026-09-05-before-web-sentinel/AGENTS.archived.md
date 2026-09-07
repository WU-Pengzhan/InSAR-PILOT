# InSAR-PILOT development rules

The next-generation target specification is [docs/architecture/overview.md](docs/architecture/overview.md).
Only `docs/architecture/` defines the target architecture. Documents under
`docs/legacy/` describe historical implementations, not requirements for new code.

## Scientific invariants

- Preserve the validated ISCE2 TOPS and ISCE3 NISAR numerical workflows. Never
  replace burst interferograms with merged-SLC cross multiplication.
- Sentinel-1 and NISAR have independent scientific steps and configuration.
- Treat `/home/griffin/insar_projects/` inputs and golden results as read-only.
  Regression runs must use new output directories.
- Do not silently change upstream scientific settings or generated merge configs.

## Implementation boundaries

- Follow Design → Model → Backend → GUI → Migration and the migration gates.
- Domain models must not import Qt, FastAPI, or processor SDKs. The GUI only calls
  application APIs; process execution belongs to the Job Engine.
- A StepDefinition is not a StepRun. Every retry has a new ID and immutable terminal
  history. Never overwrite published artifacts or run logs.
- Derive current state from runs, input versions, dependencies, and QC. Never infer
  success from a directory or stdout text. Stale does not rewrite historical success.
- Capture complete input/configuration/environment provenance without credentials.
- Preserve existing uncommitted changes. Keep legacy CLI/GUI operational until the
  corresponding replacement passes scientific regression gates.
- New features must state their actual implementation status in
  `docs/architecture/migration.md`; do not label planned capabilities as delivered.

## Validation

Run meaningful headless domain/storage/job/API tests before GUI tests. Use the
existing `insar` environment for legacy regression. Keep scientific integration
checks separate from unit tests; passing mocks does not establish numerical parity.
Run Ruff and applicable type checks. Validate documentation links and Web builds.
