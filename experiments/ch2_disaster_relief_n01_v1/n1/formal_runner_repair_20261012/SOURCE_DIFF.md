# Repair diff

Compared with the old runner:

1. Removed the outer `bash -c '...'` wrapper and all nested shell quoting.
2. Sends one direct `bash -s` program over SSH; Python reads JSON from argv in
   a quoted heredoc, so JSON keys and identity strings cannot be consumed by
   the shell.
3. Copies the frozen package and issues a distinct repair identity, then binds
   the identity manifest, stage budget, static reader, plan, 28 source hashes,
   unit name, scenario manifest, and checkpoint hashes in `FROZEN_BINDINGS.json`.
4. Requires an external approval document with the evaluator's
   `n01-stage-budget-approval/1` schema and exact identity, budget, caps,
   reader, plan, unit, memory, provenance, and exclusion fields. The repair
   package includes only a `NOT_APPROVED` request and never writes approval.
5. Rejects an active or previously invoked unit, an existing run directory,
   a pre-existing atomic launch lock, or any binding mismatch. It has one
   `systemctl start` and no retry path.
6. Records the same InvocationID, final systemd status, journal, resource
   fields, run-file index, and a failure/pending/unknown settlement after the
   start call, including when that call exits nonzero.
7. Adds an offline fixture that executes the actual remote script and mocks
   only `systemctl`, `journalctl`, and `sleep`.
