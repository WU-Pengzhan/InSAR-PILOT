# Data Explorer and Library

One SearchApplicationService and Download Service serve global Explore, embedded
Project search, Create from Selection, Add to Project and Download Only.

Common filters: AOI, dates and Mission. Mission-specific capability descriptors own
their specialized fields. All fans out to providers and returns separate summaries,
pagination and errors; one failure does not erase another provider's results.
SDK objects never cross the API. A search result is not a processing dataset.

## Shared Library

DataLibrary contains Sentinel1, NISAR, Orbit, DEM, partial and library.sqlite.
Projects reference exact versions; they do not copy large inputs by default.
Physical locations, logical product identity and content version are distinct.

Path reference is default; external paths are supported. Symlinks may stage
read-only processor inputs. Hard links cannot isolate mutable inputs or outputs.
Use reflink or copy on demand if the processor writes, paths are incompatible, or
portable export is requested.

Downloads lock by identity, resume partial files, verify, then publish atomically.
Partial files are never processable. Different content for one provider identity
does not overwrite the previous version. Removing projects never deletes library
data; no automatic raw-data garbage collection in v1.

Size/mtime is only a quick change detector. Strong fingerprints are separately
recorded. Verify external references around execution; changed input prevents active
promotion. Mutable external inputs needing stability are materialized first.

DEM versions include source, AOI, vertical datum, conversion grids and tool versions.
NISAR subset versions include source granules, window, frequency/polarization,
terrain bounds and openSEPPO version. Preserve verified Range-based subsets;
full download remains an explicit option. Freeze terrain bounds from prepared DEM
where possible instead of depending on an unaudited online response.

Credentials stay in local credential providers, outside manifests/provenance.
