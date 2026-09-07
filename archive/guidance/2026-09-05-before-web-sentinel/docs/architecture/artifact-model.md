# Artifact model

Artifacts are immutable logical scientific outputs, not arbitrary folders.
Types include Sentinel1SLC, NisarRSLC, OrbitEOF, DEM, ReferenceGeometry,
CoregisteredSLC, MergedSLC, Interferogram, Coherence, UnwrappedPhase,
GeocodedProduct and BaselineNetwork.

Each stores ID/type/mission/processor, AssetRefs, creating Run or import provenance,
input lineage, metadata, spatial/temporal/quality metadata, validity and creation time.
HDF5 datasets may share one physical file. ISCE sidecar references must form a complete
resolvable asset closure. Changing content creates a new identity.

## Publication

Write to a temporary artifact directory, copy/reflink outputs, resolve closure,
validate checksums/metadata, write manifest, atomically publish. Record the artifact
and run result transactionally. Recover orphan publications only from validated
manifest plus execution evidence, never from existence alone. Frozen scientific
outputs are never overwritten by later stages or reruns.

## Spatial and postprocessing contract

Distinguish map grid and radar grid. Record CRS/axes/geolocation references,
dimensions, nodata, units, temporal pair, wavelength, phase/reference convention,
look direction, coherence/mask relationships and source lineage when available.
Unknowns are explicit. Radar grids must not be assigned a fabricated geographic CRS.
Display reprojection/tiles are derivatives, not replacement science products.

Layer registration is metadata-only and automatic after publication. Heavy reads
are demand-driven and cached. Postprocessing consumes standard artifact contracts,
with explicit mission extensions where science differs.
