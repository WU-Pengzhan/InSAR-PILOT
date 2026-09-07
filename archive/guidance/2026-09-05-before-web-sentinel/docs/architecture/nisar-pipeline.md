# NisarInsarPipeline

Formal orchestration: validate RSLC dataset → prepare DEM → prepare RSLC inputs
(local full data or openSEPPO subset) → build version-matched runconfig →
official nisar.workflows.insar → validate and publish actual products.

One execution selects one compatible pair and frequency/polarization. Target product
is RIFG, RUNW or GUNW; do not assume three independent chained executions.
Only actual generated products are registered.

## Internal observability

Installed ISCE3 contains bandpass, rdr2geo, geo2rdr, HDF5 preparation, coarse
resampling, optional dense offsets/offsets product/rubbersheet/fine resampling,
crossmul/filter, unwrap, optional ionosphere, geocode, optional troposphere,
solid earth tides and baseline. Enabled stages come from the validated template
and actual events. They are not independent v1 restart boundaries.

Preserve template numerical settings and correction choices. Reuse current
plan/runner/validator, adapting their lifecycle rather than replacing algorithms.
Keep RSLC source read-only. Range-based AOI subset is supported without requiring
full-granule download; record source and terrain/window provenance.

NISAR CPU/CUDA/GPU ID comes from its runtime capability. Explicit unavailable CUDA
blocks; no silent fallback. Existing validation evidence is ISCE3 0.25.17 CPU and
does not establish CUDA parity.
