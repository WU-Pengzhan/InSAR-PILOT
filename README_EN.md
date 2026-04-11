# ISCE2 Sentinel-1 TOPS GUI (English Manual)

## 1. Overview

This GUI is a workflow orchestrator for local ISCE2 `topsStack` processing on Ubuntu/WSL.
It helps you prepare inputs, generate official `run_files`, execute them safely, and inspect results.

Core design rules:

- Use official ISCE2 `stackSentinel.py` and generated `run_files`.
- Keep native ISCE output layout and names.
- Keep failures explicit with per-step and per-subcommand logs.

## 2. What You Can Do

- Validate local runtime (`python`, ISCE scripts, GDAL helpers, `snaphu`).
- Prepare inputs in two phases:
1. Data precheck: SLC/Orbit/DEM and optional ZIP extraction.
2. Processing plan: bbox, workflow, coreg mode, looks, `num_proc`, etc.
- Import GeoTIFF DEM (`.tif/.tiff`) into ISCE DEM format under `.iscegui/dem_import/`.
- Choose vertical reference explicitly for GeoTIFF DEM:
  - `EGM96 geoid -> convert to WGS84`
  - `Already WGS84 ellipsoid`
- Generate workflow and run by:
  - `Run Next Step`
  - `Run Selected Step`
  - `Run Remaining Steps`
- Preview/export quicklooks:
  - SLC grayscale
  - Interferogram phase color
  - SLC background + INT phase overlay

## 3. Environment Requirements

- Ubuntu (WSL preferred).
- Conda environment with ISCE2 dependencies (default env name: `insar`).
- Local ISCE2 root (default: `/home/griffin/tools/isce2`).

The app exports ISCE paths automatically when running commands.

## 4. Install and Launch

```bash
source ~/.bashrc
conda activate insar
pip install -e .[dev]
isce2-gui
```

Alternative:

```bash
python -m isce2_gui
```

## 5. Project and Metadata Layout

Given a work directory `<work_dir>`, GUI metadata lives in:

- `<work_dir>/.iscegui/project.json`
- `<work_dir>/.iscegui/logs/`
- `<work_dir>/.iscegui/inputs/safe_inputs.txt`
- `<work_dir>/.iscegui/dem_import/`
- `<work_dir>/.iscegui/visualize/`

ISCE native outputs remain in standard folders such as `run_files/`, `configs/`, `reference/`, `coreg_secondarys/`, `merged/`, etc.

## 6. Recommended User Flow

### 6.1 First-time run (new project)

1. Open `1. Environment`, confirm shell/conda/ISCE root, then click `Validate Environment`.
2. Open `2. Inputs -> Data Precheck`, set:
   - Sentinel-1 input directory (ZIP/SAFE)
   - orbit directory
   - DEM path
   - GeoTIFF vertical reference (if DEM is `.tif/.tiff`)
   - optional AUX directory
   - work directory
3. Click `Validate & Prepare Data`.
4. In `2. Inputs -> Processing Plan`, set bbox (SNWE) or leave all empty.
5. Click `Generate Workflow` in `3. Execute`.
6. Run steps (`Run Next` or `Run Remaining`).
7. Open `4. Visualize` for quicklook preview/export.

### 6.2 Recovery after failure (existing project)

1. Click `Open Project` and select `project.json` (or its parent work dir).
2. Inspect failed step/subcommand in `Steps` and `Logs`.
3. Select the target step and click `Run Selected Step` for focused rerun.
4. Continue with `Run Next` or `Run Remaining`.

## 7. Inputs and Processing Notes

- BBox is SNWE rectangle only.
- Empty bbox means “use stack common overlap”; this is not a final hard crop.
- `num_proc` is an ISCE parallel parameter and run-file subcommand concurrency cap.
- GeoTIFF DEM must be geographic WGS84 grid (`EPSG:4326` style).
- The app does not auto-detect vertical datum reliability; user choice is authoritative.

## 8. ISCE Run Steps (Typical `interferogram + NESD`)

Actual run files can vary by workflow/options. The table below describes the common 16-step path.

| Run step | Main operation | Typical outputs | Common failure signal | Rerun advice |
|---|---|---|---|---|
| `run_01_unpack_topo_reference` | Unpack reference SLC and build geometry/topo | `reference/`, `geom_reference/` | DEM warnings, missing orbit, parse errors | Fix DEM/orbit/inputs, rerun step |
| `run_02_unpack_secondary_slc` | Unpack secondary SLCs | `secondarys/` | SAFE/ZIP missing or parse failures | Fix input catalog, rerun |
| `run_03_average_baseline` | Compute baseline metadata | `baselines/` | Missing reference/secondary products | Ensure run_01/02 valid |
| `run_04_extract_burst_overlaps` | Extract overlap bursts for ESD | `reference/overlap/` | Burst mismatch | Check swaths/bbox consistency |
| `run_05_overlap_geo2rdr` | Geo2rdr on overlap regions | overlap geometry files | Geometry errors | Check DEM and prior geometry |
| `run_06_overlap_resample` | Resample overlap bursts | overlap coreg products | Missing geo2rdr products | Rerun 05 then 06 |
| `run_07_pairs_misreg` | Pair-wise azimuth misregistration estimation | `misreg/azimuth/pairs/` | Missing overlap XML or ESD artifacts | Usually due to earlier overlap/coreg issues |
| `run_08_timeseries_misreg` | Invert pair-wise misregistration | misreg time-series files | Empty pair list / index errors | Fix run_07 outputs first |
| `run_09_fullBurst_geo2rdr` | Full-burst geo2rdr | full-burst geometry products | DEM/geometry limits | Check DEM coverage margin |
| `run_10_fullBurst_resample` | Full-burst resampling/coreg | `coreg_secondarys/` | Missing geo2rdr input | Rerun 09 then 10 |
| `run_11_extract_stack_valid_region` | Determine common valid burst region | `stack/IW*.xml` | Burst count mismatch across dates | Check secondary consistency |
| `run_12_merge_reference_secondary_slc` | Merge reference and secondaries | `merged/SLC/` | Missing coreg secondary products | Validate run_10 success |
| `run_13_generate_burst_igram` | Generate burst interferograms | burst-level interferograms | Missing merged/coreg artifacts | Check run_10-12 chain |
| `run_14_merge_burst_igram` | Merge burst interferograms | `merged/interferograms/*/fine.int*` | Merge dimensions mismatch | Check valid-region extraction |
| `run_15_filter_coherence` | Filter and coherence estimation | `filt_fine.int`, `fine.cor` | Filter command failure | Verify upstream `fine.int` |
| `run_16_unwrap` | Phase unwrapping (`snaphu`) | `filt_fine.unw*` | snaphu missing/config failure | Install/check snaphu and rerun |

## 9. What Users Usually Need Most

For quick quality checks:

- `merged/interferograms/*/fine.int*`
- `merged/interferograms/*/fine.cor*`
- `merged/interferograms/*/filt_fine.unw*`
- quicklook BMPs from `4. Visualize`

For downstream analysis:

- unwrapped phase (`filt_fine.unw`)
- connected components (`filt_fine.unw.conncomp`)
- coherence (`fine.cor` or filtered coherence products)

For troubleshooting:

- `.iscegui/logs/run_*.batch_*.log`
- `.iscegui/logs/run_*.cmd_*.log`
- `.iscegui/logs/stack_generate.log`

## 10. Visualization Guidance

- `Preview` renders to cache and displays result in the Preview tab.
- If export parameters and input snapshot are unchanged, `Export BMP` reuses cached preview (no recompute).
- Large images are shown with scrollbars (full image access).
- Right/left black edge bars can appear from valid-data masks and zero-filled margins; they are common display artifacts, not always processing failures.

## 11. Troubleshooting

### DEM coverage seems insufficient but workflow still runs

- ISCE topo may warn that DEM limits are insufficient and continue using available overlap.
- This can degrade edges while center area remains usable.
- Recommendation: provide DEM with margin beyond full stack envelope for robust geometry.

### Why `Run Next` skips a previously successful step

- `Run Next` only picks `pending/failed/cancelled`.
- Use `Run Selected Step` to rerun a specific `success` step.

### Terminal message about `libtinfo.so.6`

- This is often an environment library warning from mixed shell/conda contexts.
- If processing results are correct and commands complete, treat as environment warning.

## 12. Useful Commands

Run tests:

```bash
PYTHONPATH=src pytest -q
```

Launch app:

```bash
isce2-gui
```

Inspect logs quickly:

```bash
ls -lah <work_dir>/.iscegui/logs
```

## 13. Current Limits (Stage 1)

- No remote data download.
- Sentinel-1 TOPS only.
- No polygon AOI editor (SNWE bbox only).
- Quicklooks are for usability/QA, not radiometric publication products.
