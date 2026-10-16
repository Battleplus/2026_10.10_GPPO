# N02 Cost-Repair Engineering Release

This directory is an engineering-only copy of the v5 package. It preserves the reviewed three-file repair, regenerates the static package identity chain, and carries the bounded preflight-only cost-measurement helpers. The original v5 directory and its existing operational evidence are unchanged.

The canonical runtime package is:

`<release-root>/package/civilian`

The static builder completed on 2026-10-16 with `package_files=46`, `python_files=32`, `json_files=14`, and `registered_scenarios={"development": 1, "train": 2}`. Its output was:

- release manifest payload SHA-256: `a2b71d1b08b0e55ec38bce595c5a1fb9068340f277d734ebaec0048341e3a46e`
- release manifest file SHA-256: `d505881675d9146d2fc5b909fb55543ce4aca7e5cc6642d6a63fe1a575a23197`
- hash bundle payload SHA-256: `394abb2255db7bc28fd98ef149e7131fe26173589affe37485ad61df5eec9ba9`
- hash bundle file SHA-256: `5cba6f801db89bc59cd933e11031f85cd1fdd55055a21660fe56a33f7d6c7bd5`
- runtime dependency bundle SHA-256: `42ed1d0f066a8eceb32842d2299dfc755bc69143051b4bab134c983b39905b01`
- candidate request identity SHA-256: `9722b65a413e2b8efda51c0f56e4df45c64750c1482a92dbe8ed5760feff6361`
- candidate attempt identity SHA-256: `63d15c195ba769c185cb7bedc98759b402c8c4f928907cbf646fe0b73d16a678`

The identity state remains `authorized=false`, `request_frozen=false`, `attempt_started=false`, and `target_runtime_preflight=not_run`. The builder command is static-only:

```powershell
python -B "E:\Z博士\development\n02_cost_chain_repair_engineering_release_20261016\prepare_static_release.py"
```

The local deployment helper is `deploy_preflight_once.py`. It is a future command and has not been run in this assembly. After a separately authorized deployment, it freezes the built ZIP bytes, uploads those exact bytes to a remote staging object, and requires the remote verifier to recompute the same SHA-256 before publishing the file set. It then runs the existing target `driver.py --preflight`, computes the exact `source_identity_sha256` from the deployed package source map, and only after remote archive verification and successful preflight writes and synchronizes `deployment_receipt.json`. Its remote paths are:

- package publish: `/home/user1/w1-pilot/packages/ch2_disaster_relief_n02_cost_repair_engineering_20261016`
- uploaded archive verification object: `/home/user1/w1-pilot/staging/ch2_disaster_relief_n02_cost_repair_engineering_20261016.deployment-package.zip` (removed by the verifier after a successful hash check)
- preflight diagnostics and receipt: `/home/user1/w1-pilot/diagnostics/n02-v5-cost-repair-engineering-20261016`

The future deployment command, from this release root, is:

```powershell
python -B .\deploy_preflight_once.py
```

The target-side measurement remains a separate engineering authorization. Use the target interpreter and the canonical package root; choose a fresh direct child of `/home/user1/w1-pilot/diagnostics` for each run:

```bash
/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python -B \
  /home/user1/w1-pilot/packages/ch2_disaster_relief_n02_cost_repair_engineering_20261016/engineering_cost_bootstrap.py \
  --launch \
  --package-root /home/user1/w1-pilot/packages/ch2_disaster_relief_n02_cost_repair_engineering_20261016/package/civilian \
  --work-root /home/user1/w1-pilot/diagnostics/n02-cost-measurement-20261016-<run-id> \
  --unit-name n02-cost-repair-20261016-<run-id>.service \
  --deployment-receipt /home/user1/w1-pilot/diagnostics/n02-v5-cost-repair-engineering-20261016/deployment_receipt.json
```

Only after that unit is retained as `active/exited` with successful, hash-bound evidence may the receipt builder be run:

```bash
/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python -B \
  /home/user1/w1-pilot/packages/ch2_disaster_relief_n02_cost_repair_engineering_20261016/build_prior_resource_cost.py \
  --package-root /home/user1/w1-pilot/packages/ch2_disaster_relief_n02_cost_repair_engineering_20261016/package/civilian \
  --measurement-root /home/user1/w1-pilot/diagnostics/n02-cost-measurement-20261016-<run-id> \
  --run-id n02-cost-measurement-20261016-<run-id>
```

The proposed measurement limits are 270 seconds wall time, 100 CPU seconds, and 4 GiB RSS, covering `input_admission` only. No deployment, target preflight, systemd unit, measured receipt, authorization, token, formal attempt, training, or rollout was created by this assembly.

`REVIEW.md` is the independent review record for the helper pair and remains preserved. `engineering-file-hashes.json` lists the release files and helper hashes; it excludes itself and this document to avoid a self-hash cycle.
