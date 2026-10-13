# N2 Linux Acceptance r2 Archive

Status: prepared and independently reviewed for consideration of one bounded engineering attempt. This archive does not authorize target execution.

## Frozen package

- Identity: `n2-local-synthetic-engineering-linux-acceptance-r2`
- Manifest SHA-256: `C90FA16A70158E77FBF1EF56C35D9E511F4579F8CE926F35B9458963AAF5ACCA`
- Package: `package/` contains the exact reviewed staged inventory: 25 manifest-listed files and the manifest (26 files total).
- Required prior-cost input: `package/development/ch2_disaster_relief_graph_v2/PRIOR_RESOURCE_COST.json`, SHA-256 `B577B88138699DCEFC8286314B64D0C41D7278F36ED3DB38ECCDAE962A5ED263`.
- Proposed limits: 120/60 seconds for runtime admission, 600/480 for unit tests, 900/600 for synthetic smoke, 120/60 for shutdown (wall/CPU); 1,740 seconds total wall, 1,200 seconds total CPU, 4 GiB RSS, and 8 GiB package/work/export storage.

## Local evidence

- `evidence/unit-tests.log` records the full staged-package suite: 32 tests passed, comprising the unchanged 29-test baseline plus 3 runtime-contract regressions.
- `evidence/N2_ENGINEERING_NODE_REPORT.json` records the synthetic smoke: 720 combined transitions, 48 combined optimizer updates, strict restore equivalence, and local Windows accounting of 55.8357 seconds wall / 53.78125 seconds process CPU.
- `evidence/normal_export.json` records the completed normal export.
- `evidence/failed_export.json.failure.json` records the injected failure path, retained checkpoint, and successful pending-file cleanup.
- `evidence/INDEPENDENT_REVIEW.md` records review of the exact manifest and package inventory.

These are local engineering results, not target-Linux measurements. No SSH, package transfer, target command, formal research-data processing, training, or prediction gate was run. The earlier SSH preflight failure remains unknown. Use only the exact staged package; the mutable source candidate contains unlisted files.
