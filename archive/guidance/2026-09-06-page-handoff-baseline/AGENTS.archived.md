# InSAR-PILOT development rules

Current direction, accepted by the user on 2026-09-05: **Web only; Sentinel-1 first; NISAR later; design and deliver one page at a time.**

## Read first

- [Product scope and architecture](docs/architecture/overview.md) defines the current direction.
- [Sentinel page proposal](docs/architecture/sentinel-workbench.md) separates accepted scope from page choices still awaiting discussion.
- [Implementation status](docs/architecture/migration.md) records delivered, pending and deferred work.
- Only current documents in `docs/architecture/` define the target. Dated reviews, `docs/legacy/` and `archive/` are historical evidence, never current task instructions.
- The latest user decision takes precedence over older acceptance gates.

## Product scope and workflow

- Stop developing the PySide6/Qt desktop interface. Web is the sole product direction.
- Existing Qt files and entrypoints may remain as migration source until a separately scoped dependency cleanup; their presence does not mandate desktop feature parity or continued GUI development.
- Prioritize the Sentinel-1 ISCE2 TOPS experience. Preserve NISAR/ISCE3/openSEPPO capabilities, but defer new NISAR UI and preparation work.
- One project locks to one sensor/mission profile. Sentinel and NISAR may have different processing pages and steps. Shared search/download infrastructure must retain mission-specific filters and acquisition strategies.
- The near-term scientific deliverable is a phase stack. The exact contract (coregistered complex SLC stack, wrapped interferogram stack, or both) is pending user clarification. Do not silently decide the product, looks, filtering or reference convention.
- Unwrapping, broad phase numerical comparisons, GUNW parity, CUDA and time series are deferred; they do not block current Sentinel page design.
- Preserve basic input compatibility, process exits and output readability/shape/asset checks. Deferred scientific QC must not become a fabricated PASS.
- Discuss page division first, then design → backend contract → implementation → focused acceptance for one agreed page. Do not implement all pages or both missions in one pass.
- Recipes are versioned scientific plans, not automatically one recipe per screen. Generated run files are execution evidence, not GUI identities.

## Scientific and data safeguards

- Preserve official ISCE2 TOPS and ISCE3 numerical algorithms, templates and scientific parameter meanings. Burst interferograms must precede merge; never replace that path with merged-SLC multiplication.
- Treat `/home/griffin/insar_projects/` inputs and golden data as read-only. Any requested scientific run writes to a new isolated directory.
- Never change scientific parameters or rewrite an old failure to claim success. Do not diagnose a failure from an unverified hypothesis.
- Separate StepDefinition, StepRun and Job. Retry uses new IDs; terminal runs, published artifacts and historical logs are immutable.
- Derive current state from registered inputs, runs, product contracts and signatures, not filenames or stdout alone. Stale does not rewrite historical success.
- Freeze commands, inputs, configuration and runtime/code provenance; credentials stay out of snapshots and logs.
- Keep domain code Qt/FastAPI/processor-SDK free. The Web UI calls application APIs; the Job Engine starts and cancels processing.
- Preserve existing uncommitted work. Archive superseded guidance with an inventory before replacement. Do not edit user-global skills/plugins as part of repository cleanup.

## Validation and reporting

- Run relevant model/storage/job/API tests before frontend checks when changing those layers. Use the separate Web environment for new engine/API tests.
- Use the existing `insar` environment only for relevant reused scientific/legacy backend tests; maintaining the Qt interface is not a new acceptance goal.
- For changed Python code run Ruff and applicable type checks. For changed Web code run type/build checks and focused component/browser acceptance.
- Check applicable Linux Firefox/Chromium and Windows-browser-to-WSL paths, Chinese/English, themes, empty/error/long-path states and relevant viewport/zoom behavior. State untested cases.
- Documentation-only work needs link/build checks, not a new SAR computation or exhaustive software test run.
- Update `docs/architecture/migration.md` with actual implementation status. Keep implemented, tested, scientifically validated, proposed and deferred distinct. Historical tests are not a new full-suite result.
