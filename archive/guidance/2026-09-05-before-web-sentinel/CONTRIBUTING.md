# Contributing to InSAR-PILOT

Read [AGENTS.md](AGENTS.md) and the [accepted architecture](docs/architecture/overview.md).
Only docs/architecture defines the next-generation target. Legacy documentation is
historical evidence. Preserve validated numerical processing and existing changes.

## Development and validation

Legacy regression uses the existing insar environment:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen python -m pytest -q
python -m ruff check src tests
```

New domain/application/infrastructure layers must be Qt-free. Test state transitions,
transaction recovery, immutable outputs, cancellation and API contracts before GUI.
Scientific regressions write only to new output directories, never golden sources.
Mocked tests cannot replace real processor validation. Record capabilities honestly
in [migration status](docs/architecture/migration.md).

GUI changes require frontend type/build checks and browser checks at 1440x900 and
1366x768, 100/125/150% zoom, Chinese/English, including empty/loading/error/long-path
states. Use object-based workspaces, structured events and backend-derived state.

Do not introduce universal scientific steps, overwrite Runs or Artifacts, expose
credentials in logs, or change official processing settings silently. Preserve legacy
entrypoints until the migration gates permit switching defaults.
