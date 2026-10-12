# N1 R2 Formal Runner Repair v1

This archive records the local repair for the R2 formal submission runner's
first preflight failure. It does not record a formal run. Status remains
`NOT_APPROVED`; no approval is included and no server was contacted for this
repair. The repair has not been deployed and has not received server
acceptance.

The old runner embedded Python source inside a nested `bash -c` string. Shell
quoting removed dictionary-key quotes, so the remote reader check stopped with
a `SyntaxError` before approval upload or `systemctl start`. The old identity,
transcript, and stop report remain unchanged in their earlier archive paths.

The repaired runner sends one shell program through `bash -s`, checks a new
identity and the exact reader, budget, source set, R1 isolation, approval
fields, and existing-run state before one start call. An atomic launch lock
rejects repeat submissions. After the start call it records the same
InvocationID, systemd state and resource fields, journal, run-file index, and
a failure, pending, or unknown settlement without retrying.

The full frozen release is represented without duplicating its scenarios,
checkpoints, or prior evidence. `RELEASE_OVERLAY_INDEX.json` maps every release
file and SHA-256 either to an existing tracked file under
`prior_cost_repair_r2/package/` or to one of the seven small identity-bound
overrides archived here. `ARTIFACT_HASHES.json` retains the complete local
release file hash inventory. Scenario, checkpoint, and prior-evidence bytes
are reused unchanged from the tracked baseline; only the listed identity-bound
overrides differ.
`review/INDEPENDENT_HASH_INDEX.json` is preserved as the reviewer's historical
index for the local frozen release. Its `release/...` paths refer to that local
release layout. `PUBLIC_ARCHIVE_HASH_INDEX.json` separately hashes this public
archive's files, excluding itself to avoid a self-reference.

Offline validation ran under WSL with:

```text
python3 -m unittest -v test_offline_runner.py
```

All six cases passed. The tests execute the runner's actual shell program and
replace only `systemctl`, `journalctl`, and `sleep`; they do not execute the
release evaluator or load checkpoints.
