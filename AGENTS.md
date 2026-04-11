# AGENTS.md

## Project Intent
Build an open-source desktop GUI for Sentinel-1 TOPS stack processing with ISCE2 on Ubuntu WSL.

## Hard Rules
- Prefer PySide6/Qt.
- Prefer official ISCE2 topsStack CLI orchestration over re-implementing ISCE internals.
- Do not add remote download in v1.
- Preserve ISCE2 native output layout and filenames in the UI.
- Treat bbox as SNWE rectangle only unless code evidence proves polygon support.
- Treat adjacent-frame merge as conditional; do not assume it is always safe.
- Fail clearly when orbit/DEM/AUX/ISCE commands are missing.
- Keep milestones additive and testable.
- Default advanced parallelism to off unless it is proven stable.

## Environment Assumptions
- Ubuntu on WSL.
- Conda env: insar.
- ISCE2 path: /home/griffin/tools/isce2.

## Engineering Guidance
- Model workflow state at the run_file level.
- Capture raw stdout/stderr for every invoked command.
- Use absolute paths everywhere.
- Never hardcode final product names beyond what ISCE actually writes.
- Do not introduce heavy dependencies without a milestone-level reason.

## Non-Goals for v1
- Remote data download.
- Multi-sensor support.
- GIS-grade polygon editing.
- Replacing topsStack with a new processing engine.

# ISCE2 Sentinel-1 GUI project instructions

## Project mission

Build an open-source desktop GUI that helps users run Sentinel-1 TOPS stack interferogram workflows with an existing local ISCE2 installation. The app is a workflow orchestrator and usability layer over ISCE2, not a reimplementation of ISCE2 algorithms.

## Core product constraints

- Target platform: Ubuntu Linux on WSL first.
- Primary user: a user who already installed ISCE2 and related dependencies.
- First release supports Sentinel-1 TOPS stack only.
- First release stops at ISCE2-native interferometric outputs.
- Preserve native ISCE2 output structure and naming where practical.
- End users provide local ZIP/SAFE data, orbit directory, and DEM path manually.
- No remote download features in v1.

## Architecture rules

- Prefer PySide6 for the desktop GUI unless a stronger practical option is proven.
- Prefer orchestration of official ISCE2 workflows and generated run files over re-implementing processing logic.
- Before choosing CLI or Python-module orchestration, inspect the local ISCE2 code under /home/griffin/tools/isce2 and document the tradeoff.
- Treat stackSentinel.py and related topsStack scripts as the default workflow backbone unless code inspection proves otherwise.
- Keep the processing engine separate from the GUI layer.
- Use a persistent project/session model so runs can be resumed and inspected.

## Scope rules

- Milestone 1 must support:
  - selecting input data folder
  - optional unzip/extract step
  - selecting orbit folder
  - selecting DEM path
  - entering manual bbox/SNWE
  - generating the official ISCE2 workflow
  - executing it step by step or as a managed job
  - viewing logs and job status
- KML import is desirable but secondary.
- Interactive map AOI drawing is optional until feasibility is proven.
- Same-orbit adjacent-frame merge is conditional; do not promise it until feasibility is validated from ISCE2 code and a small proof-of-concept.

## UX rules

- Use a guided wizard-style workflow, not an expert-only control panel.
- Show required inputs, optional inputs, and validation errors clearly.
- Use plain language alongside ISCE2-native terminology.
- Always expose the underlying command/config/run-file paths for advanced users.
- Provide resumable job history and clear failure messages.

## Engineering rules

- Keep modules small and testable.
- Separate:
  - GUI
  - workflow/domain models
  - ISCE2 discovery/validation
  - job execution
  - log parsing
  - output discovery
- Add docstrings and concise comments where needed.
- Avoid large dependencies unless justified in docs.
- Add tests for pure-Python logic and parsers.
- For any ISCE2-specific claim, prefer evidence from local code inspection.

## Done criteria

A change is only done when:
- code is added in the right module
- the user flow is documented
- validation behavior is clear
- a runnable path exists for the feature
- tests or manual verification steps are documented
