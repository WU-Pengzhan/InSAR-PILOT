# Project model

project.pilot is readable versioned JSON: identity, name, profile, lock, AOI,
dataset references, user settings and pipeline/recipe versions. Runtime history is
in .insar_pilot/state.sqlite. Application preferences are outside the project.

## Profile binding

Unassigned projects may search and define AOI without locking. First formal attach
of a processing dataset locks to sentinel1_tops or nisar in the same revision.
Orbit/DEM do not lock. Removing all datasets does not unlock. A different mission
requires another project. Mixed-mission search selection must be grouped before attach.

Sentinel datasets support stacks. NISAR datasets may contain many acquisitions,
but each first-version pipeline processes one compatible pair and one
frequency/polarization combination. Multiple pair pipelines are allowed.

## Revisions and consistency

All changes use optimistic revision checks and a project writer lock. The durable
pending revision stores the proposed manifest before atomic file replacement;
SQLite then commits the accepted revision and event. Recovery compares manifest
hashes before completing/aborting pending work. No jobs are submitted during recovery.
Manual edits are validated and imported as new revisions; they cannot bypass profile
locking or mutate historical input snapshots.

## Legacy import

Always create a new ID/directory. Preserve source project, input paths, recognized
configuration, catalog and historical evidence. Unknown parameters/environments stay
unknown. Old success flags alone produce imported/unverified artifacts, not fabricated
successful runs. Legacy code never writes the new schema.
