# Contributing to InSAR-PILOT

Thanks for your interest in improving InSAR-PILOT. This guide covers the development
setup, how to run the checks, and the architecture rules the codebase relies on.

## Development setup

Day-to-day development uses the [uv](https://docs.astral.sh/uv/)-managed virtual
environment, which provides PySide6 and the standard library — everything the test
suite and linter need:

```bash
uv sync --extra dev
```

ISCE2 is **only** required to run real GUI processing, not to develop or test the
application. Tests and lint never invoke ISCE2. The full ISCE2/GDAL/aria2 runtime is
installed separately from `environment.yml` (conda env `insar`) and is exercised only
at GUI runtime.

## Running tests and lint

```bash
# Full test suite (headless Qt via the offscreen platform plugin)
QT_QPA_PLATFORM=offscreen uv run pytest -q

# Lint
uv run ruff check src tests
```

`QT_QPA_PLATFORM=offscreen` is required because many tests construct real Qt widgets.

## Architecture rules

The codebase is strictly layered. Please preserve these constraints:

1. **Strict layering `ui → services/download → domain`.** `services/`, `domain/`, and
   `download/` must stay Qt-free and unit-testable; only `ui/` may import Qt.
2. **All ISCE/processing subprocess work goes through `ShellCommandBuilder`
   (`services/shell.py`), never bare `subprocess`.** This ensures conda activation and
   the ISCE2 environment exports are applied to every command.
3. **Any new persisted field must be added to the relevant `domain` dataclass AND its
   `from_dict`,** with type coercion and backward compatibility for older
   `project.pilot` files.

## Pull request conventions

- Keep PRs small and focused on a single change.
- Add tests for new logic in `services/` or `download/` (both are Qt-free and
  `tmp_path`-friendly, so they run without a display).
- Make sure `uv run ruff check src tests` and the test suite pass before opening a PR.

## Adding a translation

Locale files live in `src/insar_pilot/i18n/locales/` as JSON, with English
(`en.json`) as the fallback. A Chinese (`zh`) locale is planned for this release; new
translations should follow the same key structure as `en.json`.
