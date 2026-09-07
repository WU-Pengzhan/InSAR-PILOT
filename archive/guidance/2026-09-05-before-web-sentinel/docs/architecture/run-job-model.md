# Run, Job and provenance

A Run is a scientific record; a Job is its compute execution entity. Download-only
jobs can have no run_id. Default scheduler allows one heavy scientific job; existing
download internals retain their own bounded concurrency.

## Required run snapshot

IDs (run/pipeline/step/execution/parent), UTC lifecycle times, status/failure reason,
resolved parameter snapshot and configuration files, input artifact IDs/roles/versions/
fingerprints, output IDs, cwd, exact argv/commands/order and script digest,
runtime profile snapshot, processor/dependency versions, application version/git
revision and dirty-code digest/diff, requested/actual CPU/GPU mode and device UUID,
driver/CUDA, stdout/stderr/native logs, exit code, QC references, resource statistics
and known reproduction limitations. Credentials are references, never values.

## Lifecycle

A process is launched only by JobExecutor in a new process group. Logs are flushed
continuously. Native combined streams are labeled combined. Terminal status waits for
process completion, structural QC and artifact publication. Exit 0 with a failed
product contract is FAILED with original exit_code=0 and artifact_contract reason.

Cancel requests terminate the process group, wait, then kill if needed. No partial
artifact promotion. Browser closure does not cancel. Worker identity/heartbeat/lease
are persisted; restart checks whether a worker is still alive before reconciling.
Unrecoverable started jobs become FAILED/interrupted. Queued work can be revalidated.

## Events

Structured events are durable with scope-local monotonic sequences. WebSocket
replays after a cursor; clients deduplicate. Coalesce frequent progress; do not insert
each stdout line into SQLite. Slow clients never block processing. Provide paginated
log reads. Unknown totals/telemetry remain unknown.

Terminal run state, artifacts, QC, active and event outbox are one DB transaction.
