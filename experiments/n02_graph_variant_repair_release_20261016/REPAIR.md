# Graph Variant Repair Candidate

Status: NOT_APPROVED static L1 repair candidate. The patch is applied to this candidate package only. No target-runtime preflight, policy forward pass, training, checkpoint restoration, formal attempt, or rollout was performed.

Release: `ch2_disaster_relief_n02_graph_variant_repair_l1_20261016`  
Candidate run ID: `n02-l1-graph-variant-repair-run-20261016-01`

The patch targets `package/civilian/n2_stage_pipeline.py`, whose baseline SHA-256 was `5063b540d72ad5df145089e6a890c2db0bd72c939bc58f6e0c5906363cb91ebd`. It changes the two graph-policy training constructors from L0 to L1, updates paired-initialization metadata, and reconstructs L1 for strict development checkpoint loading. The candidate file SHA-256 is `9688491468f41d7e2a48878537ece8e8ff79a9766a5eab5e789cfcaaa7ad5cbf`. Training and reconstruction therefore use the same variant and seed.

The patch does not change `acceptance_harness.py`, `driver.py`, or the synthetic critic test. It does not change formal evidence or authorize execution.

Checks: `git apply --check` passed against the baseline package. Two in-memory `build_policy("L1", 8201)` constructions both contained `literal_attention` and `task_update`; all 43 state entries matched exactly. The package test suite passed (9 tests, including the hand-checked two-valid-allocation fixture). These checks did not run a policy forward pass or load a checkpoint.

Static identity chain:

- Manifest payload SHA-256: `3aaf0ddb966edbd64bf9da7cc6998774f30c0370fbf6ae8e1b5e4752eeed063f`
- Hash bundle payload SHA-256: `f05eb10cb758d0da2052d3c4b92a581001db0134a634942f8656387f0121d06d`
- Candidate request identity SHA-256: `76fa3f23191a46a19efa37f43dad657dfcbaa574822b790d06e92d322404146f` (`authorized=false`, `request_frozen=false`)
- Candidate attempt identity SHA-256: `21a213d2832cfd9fc77c482d4fd75455ee305354d77c16caede427886be9b90f` (`attempt_started=false`)

The existing `load_release_binding` check passed and verified these four identities plus all 53 package-file hashes. The deployment archive builder produced a local 58-member ZIP from those 53 package files and the five static identity sidecars (`V4_RELEASE_MANIFEST.json`, `V4_RELEASE_SHA256SUMS.txt`, `V4_HASH_BUNDLE.json`, `V4_STATIC_REQUEST_IDENTITY.json`, and `V4_STATIC_ATTEMPT_IDENTITY.json`). Its SHA-256 was `56645fbb6d047c9915b4327786b482529a0ae8bf4b40e40dcba5166c9cd04cc1`; the temporary ZIP was deleted after verification. This was a local archive check only; no deployment or SSH operation occurred.

The copied prior resource-cost receipt is `bc60410eb314e7882b9cf85237d8d3243209f27edb11ce242dc94c6bfe485824`. Its stage coverage is only `input_admission` for the earlier package (source identity `d9b369faa831ce9d92c05c2b131e977ec70ee60a93c2114b8624ad0096226fec`). It does not measure this repaired L1 package, L1 training cost, or any later stage.

Local independent review: PASS for static candidate completeness and repair closure only (see `FINAL_REPAIR_REVIEW.md`). The static identity sidecar remains `independent_review=pending`; this review does not authorize execution or change the candidate's NOT_APPROVED status. If execution is approved later, the sole formal pipeline entry is `package/civilian/driver.py --run --authorization <absolute-path>`. It requires target-runtime preflight and fresh package-external authorization bound to these static identities; the driver validates authorization and performs the managed handoff. No execution launcher is currently included or authorized.
