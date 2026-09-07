# Sentinel1TopsPipeline

Source: actual YanAnHighway run_files and ISCE2 2.6.5 TOPS installation.
Prepare data/AUX, EOF/DEM and environment, then generate official
stackSentinel.py -W interferogram configuration.

| Official label | Scientific step |
|---|---|
| unpack_topo_reference | Reference unpack and geometry |
| unpack_secondary_slc | Secondary unpack |
| average_baseline | Baseline |
| extract_burst_overlaps | Burst overlap |
| overlap_geo2rdr | Overlap mapping |
| overlap_resample | Overlap resampling |
| pairs_misreg | Pair ESD/range misregistration |
| timeseries_misreg | Date misregistration |
| fullBurst_geo2rdr | Full burst mapping |
| fullBurst_resample | Full burst resampling |
| extract_stack_valid_region | Common valid region |
| merge_reference_secondary_slc | Merge SLC and geometry |
| generate_burst_igram | Burst interferograms |
| merge_burst_igram | Merge burst interferograms |
| filter_coherence | Filtering and coherence |
| unwrap | Unwrap |

Versioned semantic IDs use labels, not permanent stage numbers. Official generated
order/commands are retained. Unknown stages are explicit compatibility failures.
The GUI may group steps, but must preserve all individual histories.

Numerical invariant: burst interferograms then merge. Merged SLC multiplication
cannot replace this path. Never silently modify generated merge parameters.
The verified plan ends at unwrap; do not invent a geocode stage. GIS derivatives
are separately labeled. CPU/Auto/GPU-when-supported resolve against actual ISCE2
modules and official options, with requested and effective modes recorded.
