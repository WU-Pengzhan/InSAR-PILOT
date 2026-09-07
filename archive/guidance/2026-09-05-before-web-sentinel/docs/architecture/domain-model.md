# Domain model

All identities are stable opaque IDs; timestamps are timezone-aware UTC. JSON must
be finite and credential-free. Definitions and snapshots are versioned.

| Object | Meaning and relationships |
|---|---|
| Project | ID, name, schema, locked profile, AOI, configuration revision |
| ProjectProfile | unassigned / sentinel1_tops / nisar |
| DatasetRevision | Mission-specific, versioned membership and selection |
| DatasetBinding | Project reference to an exact dataset revision and purpose |
| Pipeline | Project-scoped instance of a versioned mission definition |
| StepDefinition | Stable scientific role, parameters, input/output roles, dependencies, QC |
| PipelineStep | Definition instance and current desired parameters |
| PipelineExecution | Frozen plan, configuration revision, range, workspace lease |
| StepRun | One execution with exact input/config/runtime provenance |
| Job | Queued/running compute entity, optional run_id, resource lease and process identity |
| Artifact | Immutable logical product with physical assets and lineage |
| AssetRef | File/container URI, role, HDF5 subdataset, media type, size and fingerprint |
| QCMetric | Observed value/unit, scope, sample/mask, extractor and source |
| QCCheck | Versioned rule, threshold, suggested range and gate behavior |
| QCReport | Evaluation linking metrics, checks, runs and artifacts |
| Event | Scope sequence, ID, type, timestamp and structured payload |
| Layer | Presentation reference to spatial artifact, grid, style and service |

Project → DatasetBinding → DatasetRevision → source Artifacts.
Project → Pipeline → PipelineStep → StepDefinition.
Pipeline → PipelineExecution → StepRuns → Jobs.
StepRun → input/output Artifacts; Run/Artifact → QCReports; Artifact → Layers.

Keep provider results, processing datasets and physical assets distinct. One HDF5
container may back multiple logical artifacts. Imported data have provenance but no
invented creating Run. PostProcessingInputBundle references versioned artifacts,
pair network, grids, units, wavelength, masks/coherence and provenance; it implements
no time-series algorithm.
