# Target-server execution

The user approved this bounded pilot on 2026-10-11. This document does not reuse historical authorizations. The v1 admission runtime probe was accepted, but its outer guardian settlement failed on a child-exit RSS race; engineering smoke and formal training did not run. The v2 package fixes that race and carries all v1 server costs through `PRIOR_RESOURCE_COST.json`. Re-run target runtime admission and full real smoke against v2 before the six-run stage. Keep the v1 package and work root unchanged.

Existing runtime: Python3.11.16 / Torch2.7.0+cu128 / NumPy1.26.0. CPU0 only, all numerical thread pools1, CUDA disabled and never initialized. Do not install or rebuild this runtime. The initial connection was checked separately; it is not a model/runtime acceptance result.

Every command uses the same immutable package and work root:

```bash
relief_python=/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python
relief_package=/home/user1/w1-pilot/packages/ch2-disaster-relief-graph-v2-20261011
relief_work=/home/user1/w1-pilot/runs/ch2-disaster-relief-graph-v2-20261011-once
export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
"$relief_python" -B "$relief_package/driver.py" --preflight --package-root "$relief_package" --work-root "$relief_work"
"$relief_python" -B "$relief_package/driver.py" --engineering-smoke --package-root "$relief_package" --work-root "$relief_work"
```

Run sequentially under a fail-fast wrapper: stop if either exit is nonzero. Each Linux command internally starts the independent process guardian. Both stages accumulate in the same resource ledger; the admission and smoke allocation is600+900 wall seconds and300+600 CPU seconds. Do not execute unmetered extra model tests on the server.

After the main agent and independent reviewer check the actual target receipts and measured common round count, use the same fail-fast wrapper for:

```bash
"$relief_python" -B "$relief_package/driver.py" --run --package-root "$relief_package" --work-root "$relief_work"
"$relief_python" -B "$relief_package/driver.py" --evaluate --package-root "$relief_package" --work-root "$relief_work"
"$relief_python" -B "$relief_package/driver.py" --export --package-root "$relief_package" --work-root "$relief_work"
"$relief_python" -B "$relief_package/driver.py" --resources --package-root "$relief_package" --work-root "$relief_work"
```

Use a new systemd user service per wrapper, Restart=no, KillMode=control-group, CPUAffinity=0, CPUQuota=100%, MemoryMax=4G. Outer service timeout is an additional ceiling, not permission to expand any phase. Read the same unit's InvocationID/status/journal after reconnect; never infer success from a disappeared process or blindly resubmit after observation failure.

The server admission+smoke and subsequent training/evaluation/export share the approved14400 wall /12000 CPU seconds, RSS4GiB and combined work/export8GiB contract. `PRIOR_RESOURCE_COST.json` is mandatory and source-hashed; its evidence is hash-checked before runtime identity is accepted. It carries 5.734729 wall / 2.914629 CPU seconds from the v1 admission and shutdown, with wrapper overhead assigned to the admission stage. Keep the new work root empty so its admission and smoke rows remain the only current-identity prerequisite rows. Separate wrapper invocations do not reset these budgets. Transfer is measured separately. Guards report sampled disk/RSS and final accounting-tail limitations; do not call them complete system-wide accounting.

The local Windows diagnostics are development evidence only. They deliberately fail target admission and cannot authorize the six-run gate. The preserved v1 failure evidence is included read-only under `diagnostics/prior-v1/` solely to verify the carry-forward receipt; it is not a successful runtime or smoke result. No v2 target-runtime revalidation has been run yet.
