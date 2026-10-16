# Measured final release independent review

Result: PASS for the local final release identity, measured-receipt provenance, and formal authorization binding. Reviewed 2026-10-16. This review performs no server action and makes no claim that the concurrent formal execution has completed successfully.

The authoritative release is `n02_cost_chain_repair_engineering_release_20261016_r2_closed_db_fix_final`. Its manifest contains 53 package files; all 53 file hashes match the manifest and complete hash bundle. `execution_gate.load_release_binding` independently accepted the four canonical identity digests:

| Identity | SHA-256 |
|---|---|
| Manifest payload | `27713671439cd34bc5100fb78025c0888ccaa5a678e90d44c1301476c64fce43` |
| Bundle payload | `74dacac7b13fda848630c4f4ec5045a27d16675d58a5570d95bc2933d519825d` |
| Static request | `928428d9daab671fb1703c528370918387b1aaad9e16f67a2c9105074e8feb71` |
| Static attempt | `070e24274b7204f41583596b511734a889240c945df049dd3e28186da7508b2d` |

Manifest and bundle file SHA-256 values are respectively `5f4912417236e5819870c230451b634945a3a163132e10f716c20d97116fe0d4` and `598a7035985d8f3b3f6f66f554ce5932d5f4824682866594fd4501fa0a045faa`. These identities belong to the 53-file measured final release; the earlier 46-file engineering candidate is a different package.

`PRIOR_RESOURCE_COST.json` hashes to `bc60410eb314e7882b9cf85237d8d3243209f27edb11ce242dc94c6bfe485824`. All seven referenced evidence files independently match their declared hashes. Evidence binds the predecessor measurement source `d9b369faa831ce9d92c05c2b131e977ec70ee60a93c2114b8624ad0096226fec`, deployed archive `09970585454444d13f415a4d136bf1eb5c87bdfb7bb022f496bf4839c8ffbf3d`, deployment receipt `f4100fd8f55c9e7e219c0a8579b4d00a88db3c7b3c70d27b117e0bda3db4b907`, and systemd InvocationID `5a66544808104f9ab4629e0f4a26e02a`. The retained unit evidence records successful completion and exit 0. Coverage is explicitly `input_admission` only: 3.653973 wall seconds and 3.276935 CPU seconds, including the same-unit shutdown tail. It is not a seven-stage training cost measurement.

The taskbook binding remains `4b544e39b5fffa89ef364095341412c807d4d609a11117191b6b981aa51bcf5c`; registered input and scenario matrix files match the manifest. The frozen protocol remains `n02-integration-smoke-v4-100x100/seven-stage`, map `relief-grid-100x100-v1`, seed 8201, with registered 2 training + 1 development scenarios and matched G/G-WM initialization. The formal contract budget equals `execution_gate.FORMAL_BUDGET`: 1800 wall seconds, 900 CPU seconds, 4 GiB RSS, 1 GiB work and export storage each, 4000 environment steps, 128 branches, 8 world-model updates, 16 PPO updates, 4 policy training episodes, 2 development episodes, 512 forward batches, and 2048 candidate evaluations.

Both `static_candidate` and `formal_upgrade` in `FINAL_FORMAL_AUTHORIZATION_CONTRACT.json` bind the exact four final digests above. Static sidecars remain candidate-only, unauthorized and unfrozen. The external one-time formal envelope supplies approved scope `n02-v5-full-pipeline-once` and the frozen budget. Read-only invocation of `validate_authorization_document` accepted the actual `final-formal-run-evidence/authorization.json`: authorization SHA-256 `986fc17d4589008afdb622587f4b9ae17786bb2567b1059c00eccc18acc2c1f2`, formal attempt identity `3f3bf1d0bab48867bd74b698dac2b98fae48bddc04fefad2aad442e295b65a5d`, preflight receipt SHA-256 `8aaf7f453ca38e263574febf45a6c1da9439a20dd37dc8512cae1205a5b6b950`. Gate validation enforces matching candidate digests, formal state, one-time flag, scope, and budget before submission.

Local generated `__pycache__` files exist outside the 53 manifest entries. The gate validates the explicit manifest payload; this review neither deletes those caches nor represents them as deployed manifest files. No source, identity sidecar, frozen matrix, budget, or authorization was modified by this review.
