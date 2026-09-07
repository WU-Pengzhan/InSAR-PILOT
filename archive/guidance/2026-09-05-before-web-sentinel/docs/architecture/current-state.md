# Current state assessment

Baseline inspected 2026-09-05: 166 Python source files, 57 test modules, 461 tests
passing in the existing insar environment. The working tree contains substantial
pre-existing modifications and untracked production adapters; these are assets,
not disposable changes. See baseline.json for source hashes and Git state.

## Classification

| Classification | Assets | Action |
|---|---|---|
| KEEP | Official TOPS/ISCE3 workflows, validated templates and data | Preserve scientific settings and algorithms |
| KEEP | SAFE/HDF5 readers, AOI/IW/burst, orbit parsing, compatibility rules | Preserve behavior and characterization |
| ADAPT | ASF, download, EOF, DEM, credentials and network services | Library, jobs and structured provenance |
| ADAPT | Stack generator, run-file batch parser, NISAR/openSEPPO runners | Isolated workspaces and new run lifecycle |
| ADAPT | Preflight, DEM checks, HDF5 validators, baseline/ESD | Structured QC |
| ADAPT | Result catalog, sidecar readers, visualization | Artifact readers and presentation derivatives |
| REWRITE | ProjectState, JSON task persistence, active state | Revisioned project definition and SQLite |
| REWRITE | Controllers, QSettings, startup, Qt execution glue | Web/API and independent job engine |
| REMOVE after gates | Qt GUI, QThread/QProcess, wizard | Keep legacy entrypoints until replacement parity |

## Findings

- RunStep is keyed by run-file name; reruns reuse status and log paths.
- The newer ISCE2 adapter isolates task logs but executes in the run file's parent
  workspace. Its output-directory policy does not isolate scientific outputs.
- TaskRunStore permits saving an existing ID. NEW_DIRECTORY checks conflicts but
  does not allocate directories. Environment history records only a profile ID.
- Recipe AVAILABLE declarations include preparation/catalog tasks not implemented
  by the registered single-stage processor backend.
- State is distributed between project JSON, catalog sidecars, task JSON and scans.
- NISAR and openSEPPO have separate lifecycle implementations; cancellation and
  stdout/stderr durability need a common process-group executor.
- Current result discovery is primarily ISCE directory-based. No durable layer registry.
- DEM EGM2008 conversion requires verified PROJ grids; a successful command alone
  cannot demonstrate the vertical conversion actually happened.
- GPU presence is not processor CUDA capability. Existing NISAR numerical evidence is CPU.
- Old architecture and roadmaps disagree about NISAR readiness and mandate Qt.

## Evidence

Sentinel's actual YanAnHighway plan contains 16 stages through unwrap, including
burst IFG generation followed by merge. Merged-SLC cross multiplication differs at
burst seams and is not an alternative production path.

NISAR evidence is retained in the repository artifacts directory:
nisar-aoi-e2e-2026-09-04.json and
nisar-remote-subset-comparison-2026-09-04.json. It records CPU RIFG/RUNW/GUNW and
remote subset comparisons, not CUDA acceptance.

Read-only regression sources:
- /home/griffin/insar_projects/YanAnHighway
- /home/griffin/insar_projects/HKIA_S1
- /home/griffin/insar_projects/golden/nisar

Unit tests do not establish scientific parity.
