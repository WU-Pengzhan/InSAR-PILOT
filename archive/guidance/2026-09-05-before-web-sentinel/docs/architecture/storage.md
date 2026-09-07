# Storage design

Project layout:
- project.pilot — readable JSON intent, never full history.
- .insar_pilot/state.sqlite — revisions, datasets, pipelines, plans, runs/jobs,
  artifacts, edges, QC, active, events and layers.
- runs/<run_id>/snapshot.json, config/, logs/.
- workspaces/<execution_id>/ — mutable official processing workspace.
- artifacts/<artifact_id>/manifest.json and assets/ — published immutable data.
- cache/tiles, previews, statistics — rebuildable derivatives.

Application database stores preferences, recent projects, profiles and unscoped
download jobs. Library database stores shared input identity, versions, locations
and availability. Do not duplicate authoritative job state across databases.

SQLite uses foreign keys, WAL, busy timeout, explicit transactions and schema
migrations. One project writer; supported storage must provide local locking
semantics. WSL defaults to its Linux filesystem.

Project updates: durable pending revision → atomic project.pilot replace → accepted
revision/event transaction. Recovery reconciles hashes before scheduling.
Artifact publish: stage/validate/manifest → atomic directory publish → transaction
registering outputs, QC, terminal run, active and events. Orphans require evidence
reconciliation; existence is not success.

Do not place credentials in any snapshot. Strong hashes and versioned asset identity
are independent of physical path. External availability is rechecked. Reflink/copy,
never hard links, isolate mutable work from immutable history. Cache deletion cannot
remove raw inputs or scientific outputs.
