# Pipeline and state model

Sentinel1TopsPipeline and NisarInsarPipeline share orchestration contracts, never a
universal scientific workflow. StepDefinition and StepRun are different objects.
Actual upstream execution plans are evidence interpreted by versioned adapters.

## State

Run: QUEUED → RUNNING → SUCCESS | FAILED | CANCELLED; QUEUED → CANCELLED.
No terminal rewrites. Retry creates a new Run and Job.

Step projection:
NOT_READY, READY, QUEUED, RUNNING, SUCCESS, FAILED, STALE, SKIPPED, CANCELLED.
Show current execution and active-result usability separately. Required missing
inputs/capabilities block readiness. SKIPPED is allowed only for optional/inapplicable
definition steps, never to bypass dependencies.

Artifact has independent integrity (UNVERIFIED/VALID/INVALID), availability
(AVAILABLE/MISSING), and current applicability (CURRENT/STALE). Historical SUCCESS
does not change to STALE.

## Freshness

Scientific signature = versioned definition/strategy + resolved scientific parameters
+ exact input artifacts/fingerprints + processor/template/scientifically relevant
environment. Dependency edges propagate upstream changes to descendants.
Explain causes and rerun scope. Style/layout changes do not invalidate science.
QC policy changes reevaluate gates, not the numerical product.

A submitted plan freezes revision, inputs and parameters. Later edits cannot alter it.
Completion promotes results atomically only if their signature still matches current
intent and required QC passes. Changing active versions reevaluates descendants.

## Isolation and rerun

Each PipelineExecution owns a fresh workspace. Sequential official TOPS commands
may share that mutable workspace. Each completed step freezes declared outputs and
their sidecar dependency closure before later steps can mutate working files.
Published artifacts never reference mutable scratch. Reflink/copy is allowed;
hard links are not an isolation mechanism. Paths are rewritten only in published
presentation/metadata copies, with verified resolvability.

Only audited checkpoint boundaries are reusable. Initial TOPS reruns may recompute
all required official predecessors from prepared inputs. Show expansion in the plan.
NISAR reruns the whole official product workflow; internal stages are observability
records, not independently runnable steps.

Plan preview returns ID, revision, exact inputs, scope and resource estimate.
Submission rejects a stale plan. Unknown estimates remain unknown.
