# InSAR-PILOT

**A local, project-based SAR/InSAR Web workbench.**

[中文](README.md) · [Current architecture](docs/architecture/overview.md) · [Implementation status](docs/architecture/migration.md) · [Sentinel page structure](docs/architecture/sentinel-workbench.md)

## Product direction

As of 2026-09-05, Web is the only interface under active development. Complete the
Sentinel-1 / ISCE2 TOPS experience first, then address NISAR / ISCE3 separately.
Each project locks to a sensor profile; processing screens may differ by mission.

The near-term deliverable is a phase stack; the precise coregistered-SLC versus
wrapped-interferogram contract awaits confirmation. Unwrapping investigation and
broad phase numerical comparisons are deferred. Input compatibility, honest process
status and basic output structure checks remain necessary.

The five-page responsibilities were accepted on 2026-09-06. Design and deliver
one page at a time; the accepted structure is not a claim of completed implementation.

PySide6/Qt interface development is discontinued. Preserve reusable scientific
algorithms, download services, readers, NISAR/openSEPPO and historical evidence.

## Available preview

The Web preview provides projects and input references, grouped search, Sentinel
ABCD selection, imagery-only maps, host-side file selection, download controls,
prepared-input plans, isolated execution history, logs, basic products/QC/maps,
language/theme controls, a collapsible Inspector and explicit application exit.
Preparation, professional parameter forms and product interactions remain incomplete.

```bash
python -m venv .venv-web
.venv-web/bin/pip install -e '.[web]'
.venv-web/bin/insar-pilot-web
```

The launcher also supports `--no-browser`, `--status` and `--stop`.
Closing a browser does not cancel tasks. Explicit idle exit stops the service.
Ubuntu browsers and Windows browsers connected to WSL use the same Web frontend.

Packaging still contains Qt dependencies and the old `insar-pilot` default entrypoint.
Use `insar-pilot-web`; dependency/entrypoint cleanup is a separate scoped task,
not a requirement to continue desktop feature development. Scientific environments
are selected explicitly and are not replaced by the Web application environment.

## Development and evidence

Read [AGENTS.md](AGENTS.md), [CONTRIBUTING.md](CONTRIBUTING.md) and the
[handoff index](docs/handoff/index.md). Use the [per-page prompts](docs/handoff/prompts.md)
to start design, implementation or continuation tasks.
Only current `docs/architecture/` documents define the target; dated reviews and
`docs/legacy/` / `archive/` are historical evidence.
The pre-decision guidance snapshot and hashes are in
`archive/guidance/2026-09-05-before-web-sentinel/`; this is not a full source/data backup.

This local preview is not a claim that the public release or documentation site
already matches the working tree. Licensed under [Apache-2.0](LICENSE).
