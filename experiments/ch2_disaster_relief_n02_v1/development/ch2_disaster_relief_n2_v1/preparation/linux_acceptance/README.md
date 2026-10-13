# N2 Linux Acceptance Preparation

Status: preparation packet; one later authenticated SSH preflight and Python runtime probe were performed, then stopped on an `AssertionError`. No package transfer/upload, remote package verification, systemd submission, dependency installation, research data processing, model training, prediction gate, or G/G-WM comparison was performed. The public stop summary is in `reports/N2_LINUX_PREFLIGHT_STOP_SUMMARY_ZH.md`. This packet covers target-runtime acceptance and resource measurement for the local synthetic engineering suite and PPO integration smoke; it does not authorize future research stages.

## Runtime and package identity

The target owner must provide the absolute path to the already-installed interpreter as `N2_PYTHON`; the runner has no baked target path. It admits only Python 3.11.16, PyTorch 2.7.0+cu128, NumPy 1.26.0, CPU execution, CUDA disabled, and one intra-op/inter-op thread. Do not install or rebuild packages.

The staged package root contains exactly the manifest-listed repository-relative files plus `preparation/linux_acceptance/package-manifest.json`. Copy the checked-in manifest to that staged path without alteration. Pass its SHA-256 out of band as `--expected-manifest-sha256`; the runner rejects a manifest mismatch, a listed-file mismatch, symlinks, and extra files. The exact manifest digest is supplied with the reviewed execution entry after final freeze.

The candidate wrapper is `development/ch2_disaster_relief_n2_v1/engineering/n2_linux_runner.py`. It is Linux-only. The reviewed manifest identity was used for one preflight connection, but the runtime probe failed before package transfer or runner execution. This packet is not target-runtime acceptance.

## Minimal package closure

Transfer only these source inputs after the package is frozen and hashed. Preserve the repository-relative `development/` paths in the package root so the existing test path resolver and smoke runner see the expected tree:

- `development/ch2_disaster_relief_n2_v1/engineering/branching.py`
- `development/ch2_disaster_relief_n2_v1/engineering/world_model.py`
- `development/ch2_disaster_relief_n2_v1/engineering/ppo_integration.py`
- `development/ch2_disaster_relief_n2_v1/engineering/failure_export.py`
- `development/ch2_disaster_relief_n2_v1/engineering/run_ppo_integration_smoke.py`
- `development/ch2_disaster_relief_n2_v1/engineering/n2_linux_runner.py`
- `development/ch2_disaster_relief_n2_v1/engineering/package_n2_linux_acceptance.py`
- `development/ch2_disaster_relief_n2_v1/engineering/tests/test_branching.py`
- `development/ch2_disaster_relief_n2_v1/engineering/tests/test_world_model.py`
- `development/ch2_disaster_relief_n2_v1/engineering/tests/test_failure_export.py`
- `development/ch2_disaster_relief_n2_v1/engineering/tests/test_ppo_integration.py`
- `development/ch2_disaster_relief_graph_v2/relief_env.py`
- `development/ch2_disaster_relief_graph_v2/baselines.py`
- `development/ch2_disaster_relief_graph_v2/scenario_schema.py`
- `development/ch2_disaster_relief_graph_v2/graph_policy.py`
- `development/ch2_disaster_relief_graph_v2/ppo_trainer.py`
- `development/ch2_disaster_relief_graph_v2/chapter1_adapter.py`
- `development/ch2_disaster_relief_graph_v2/stable_identity.py`
- `development/ch2_disaster_relief_graph_v2/literal_graph_ops.py`
- `development/ch2_disaster_relief_graph_v2/dataset_protocol.py`
- `development/ch2_disaster_relief_graph_v2/fixtures/control.json`
- `development/ch2_disaster_relief_n2_v1/preparation/linux_acceptance/README.md`

Also copy `development/ch2_disaster_relief_n2_v1/preparation/linux_acceptance/package-manifest.json` to `preparation/linux_acceptance/package-manifest.json` under the package root. The manifest pins every listed file; it is pinned out of band to avoid a self-referential hash.

Build the target packet from a frozen source tree with the listed builder. The output directory must be empty and separate from the source tree; retain the printed manifest digest with the reviewed invocation record:

```bash
python -B development/ch2_disaster_relief_n2_v1/engineering/package_n2_linux_acceptance.py \
  --source-root /absolute/path/to/source-tree --output-root /absolute/path/to/empty/n2-package
```

The required runtime packages are the already-installed Python standard library, PyTorch, and NumPy. No network dependency installation is expected. Set `CUDA_VISIBLE_DEVICES=''`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1`, and `PYTHONDONTWRITEBYTECODE=1`; set Torch intra-op and inter-op threads to one in the process.

## Acceptance entry

Use a fresh immutable package directory and an empty work directory outside the source checkout. The target invocation is explicit and sequential:

```bash
N2_PYTHON=/absolute/path/to/approved/python
N2_PACKAGE=/absolute/path/to/frozen/n2-package
N2_WORK=/absolute/path/to/empty/n2-run-identity
N2_MANIFEST_SHA256=<reviewed-manifest-sha256>
N2_UNIT=n2-engineering-acceptance.service
export CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
"$N2_PYTHON" -B "$N2_PACKAGE/development/ch2_disaster_relief_n2_v1/engineering/n2_linux_runner.py" \
  --package-root "$N2_PACKAGE" --work-root "$N2_WORK" --python "$N2_PYTHON" \
  --cpu 0 --expected-manifest-sha256 "$N2_MANIFEST_SHA256" --expected-unit "$N2_UNIT"
```

For detached execution, place that exact command in one named systemd user service with `Restart=no`, `KillMode=control-group`, `CPUAffinity=0`, `CPUQuota=100%`, `MemoryMax=4G`, and `RuntimeMaxSec=1800`. Capture its `InvocationID`. The outer 1,800-second service deadline is cleanup reserve only; the runner enforces 1,740 seconds combined wall and 1,200 seconds CPU.

The runner verifies the smoke report has 480 transitions/32 updates per continuous-or-resumed path and 720 transitions/48 updates counted across the comparison execution, strict next-round restore equivalence, and normal plus injected-failure export receipts. Smoke output is written beneath the work root; package inputs must remain unchanged.

The stage caps are runtime admission 120s wall/60s CPU; unit suite 600s/480s; PPO smoke 900s/600s; shutdown 120s/60s. Total RSS is capped at 4 GiB and package+work+export storage at 8 GiB. The wrapper enforces cgroup service CPU while running and records process-group sampled RSS plus package/work size samples. Receipt wall time includes command shutdown and receipt preparation but excludes the final atomic-write tail; the same systemd invocation's final `Result`, `ExecMainStatus`, `InvocationID`, journal stop time, and cgroup accounting bound that unknown tail.

After a disconnect, reconnect read-only and inspect the same unit's `InvocationID`, final status, journal, cgroup counters, and `final-receipt.json`. Do not restart or resubmit. A vanished client session is not evidence of success. Keep observation and transfer costs separate from measured process costs.

## Measurement protocol

Retain runner UTC start/end, per-stage wall and child CPU, sampled process-group RSS, cgroup CPU/memory counters, package/work storage samples, exit status, log sizes/hashes, source hashes, and final receipt. Record target CPU model, kernel, affinity, memory cgroup, filesystem/free space, runtime versions/thread counts, and CUDA initialization separately from the same systemd invocation. Do not describe sampled process RSS or directory size as complete host accounting.

Run each stage once on a fresh work root for acceptance. A repeat is only for diagnosing a failed measurement, must get a distinct run identity, and must not erase the first failure. The local Windows PPO smoke measured 56.04 seconds wall and 53.91 seconds process CPU on its latest receipt; it is a workload reference only and must not be linearly scaled into Linux limits. Compare target measurements to the frozen caps and report per-stage reserve.

After the measurement, compare observed wall/CPU/RSS/storage with the frozen caps and record per-stage reserve. Include accumulated process and transfer costs in the ledger. Require process-tree settlement and first-error/pending-file receipts. Stop on a cap breach or any source/runtime/hash mismatch; do not enlarge caps after observing results.

## Not covered

This packet does not run or authorize research-data processing, registered-parent label generation, a 40-epoch world-model fit, prediction-gate analysis, G/G-WM policy comparison, or server training. The local receipt records only the PPO synthetic smoke. Before one Linux engineering acceptance, independently review the package and runner, create a new immutable package/work identity, verify the N2-specific execution decision and target, then retain read-only evidence from the same systemd invocation. Formal research stages remain outside this acceptance.
