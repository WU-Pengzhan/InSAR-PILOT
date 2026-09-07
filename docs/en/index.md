# InSAR-PILOT Web workbench

Current direction: **Web only, Sentinel-1 first, NISAR later; design and deliver one page at a time.**

- [Current scope](../architecture/overview.md)
- [Implementation and deferred work](../architecture/migration.md)
- [Accepted Sentinel page structure](../architecture/sentinel-workbench.md)
- [Handoff index](../handoff/index.md)
- [Per-page prompts](../handoff/prompts.md)
- [Web usage and exit](user-guide.md)

The near-term deliverable is a phase stack, with its exact product contract awaiting
confirmation. Unwrapping and broad phase comparisons are deferred; basic input,
execution and output checks remain.

PySide6/Qt interface development is discontinued. Old installation/tutorial/CLI
material remains historical reference. Use `insar-pilot-web`; packaging dependency
and default-entrypoint cleanup is a separate task. This preview does not claim all
proposed pages or scientific validation paths are complete.
