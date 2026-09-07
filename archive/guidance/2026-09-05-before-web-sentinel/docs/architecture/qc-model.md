# Quality control

QCExtractor observes; QCPolicy evaluates; QCReport freezes an evaluation. Both
extractor and policy have versions. Reports reference runs/artifacts and source
files/datasets/events. Missing or incompatible evidence is UNKNOWN with a reason.

Metrics include value, unit, scope, sampling/mask/nodata method, threshold,
recommended range, explanation and provenance. Status: PASS/WARNING/FAIL/UNKNOWN.
Required structural checks block unless PASS. Scientific metrics are advisory
unless an explicit policy makes them gates. No default invented scientific limits.
Processing thresholds (e.g. ESD coherent-point selection) are not QC pass thresholds.
Reevaluate QC without rerunning the numerical processor when only policy changes.

## Sentinel matrix

| Step | Input QC | Runtime QC | Output/metrics |
|---|---|---|---|
| Prepare | SLC/IPF/AUX, orbit validity, AOI/IW, DEM datum | Download integrity, conversion/grid | Counts, missing orbits, DEM coverage |
| Reference | Reference/DEM/orbit | Unpack/topo events | Geometry closure, burst count, coverage |
| Secondary | Acquisition/orbit list | Per-acquisition completion | Burst/swath completeness, IPF |
| Baseline | Pair metadata | Pair completion | Bperp/Bpar, temporal baseline, connectivity |
| Overlaps | Geometry/burst layout | Extraction | Count and valid area |
| Overlap geo2rdr | Overlap/DEM | Mapping errors | Offset completeness/validity |
| Overlap resample | Offsets/SLC | Acquisition progress | Shape and valid ratio |
| Pair misreg | Overlap pairs | ESD/range warnings | Mean/median/std, coherent count, residual if available |
| Date misreg | Pair estimates | Solver/connectivity | Date corrections, constraints |
| Full geo2rdr | Date corrections/geometry | Mapping progress | Full offsets |
| Full resample | SLC/offsets | Resampling | Coregistered SLC, valid burst/pixel ratio |
| Common region | Stack burst set | Intersection | Common area and retained ratio |
| SLC merge | SLC/geometry | Merge | Sidecar closure, dimensions, coverage; seam extension |
| Burst IFG | Official pairs/bursts | Pair/burst progress | Complex dtype, finite/valid ratio |
| IFG merge | Burst IFG/valid region | Merge | Dimensions, nodata, coverage |
| Filter/coherence | IFG/parameters | Stage outcome | Coherence bounds, mean/quantiles/histogram |
| Unwrap | Phase/coherence/config | SNAPHU warnings/exit | Valid ratio, components when available |

## NISAR matrix

| Step/phase | Input QC | Runtime QC | Output/metrics |
|---|---|---|---|
| Dataset | RSLC/track/frame/look/frequency/polarization | Metadata errors | Compatibility, baseline, overlap |
| DEM | CRS/datum/AOI | Conversion grids | Coverage/nodata, terrain bounds/source |
| Subset | Granule/Range/AOI/terrain | openSEPPO timeout/cancel | HDF5 contract/count/window/coverage |
| Runconfig | Template/version/selections/bounds | Official schema | Configuration digest/compute |
| Geometry/resampling | RSLC/DEM | Official events/warnings | Available offset/residual/valid ratio |
| Dense/rubbersheet | Enabled flags/inputs | Official stage status | Available offsets/residual; disabled reason |
| RIFG | Pair/signal selection | Crossmul/filter | Product type, datasets, shapes/dtypes, phase/coherence |
| RUNW | RIFG/config | Unwrap | Shape agreement, valid ratio, components |
| GUNW | RUNW/EPSG/bounds | Geocode/corrections | CRS/axes, coverage, dimensions/dtypes/nodata |
| Publish | Required actual products | Validation/commit | Complete closure, lineage, checksums |

V1 priority: structural checks, existing baseline/misregistration readers and bounded
product statistics. Every unimplemented extractor reports UNKNOWN, not fabricated
values. Compute/duration/resource diagnostics do not prove scientific correctness.
