# Archive Scope and De-identification

The archived runner contains no SSH key path or credentials. Its SSH defaults
retain the already-published target host and user only as operational
configuration; the repository does not include a private key. This archive
does not execute SSH or deploy the repair.

Not included:

- The untracked `prior_cost_repair_r2/received/` directory.
- Any approval candidate, approval record, token, key, or credential.
- The raw formal SSH transcript or deployment diagnostics.
- Duplicate scenario data, checkpoint binaries, or prior-evidence payloads.

The source package is reconstructed through the baseline path and the explicit
seven-file overlay list in `RELEASE_OVERLAY_INDEX.json`. Every mapped input is
bound to its SHA-256. The old stop evidence remains at its existing tracked
path and is referenced as history; this archive does not edit or replace it.
No server acceptance of this repair has been received.
