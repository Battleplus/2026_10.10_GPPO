# Linux Engineering Acceptance

**Status:** Environment installed; engineering run pending. No formal learning, evaluation, or heldout confirmation was started.

## Scope

The bounded service runs these stages in order and stops at the first failure:

1. Seeded CPU tensor witness and imports with CUDA disabled.
2. Exactly 26 tests via standard-library `unittest` discovery.
3. Pinned upstream CartPole smoke with exactly three updates.
4. Civilian adapter smoke with exactly three updates.
5. Fixed-batch precision diagnosis with at most two FP16 updates and exactly two finite FP32 updates. The separate `execution-plan.json` caps all engineering optimizer steps at ten. A CPU FP16 technical stop is diagnostic evidence; the FP32 control must complete both updates.

The source pin is `NM512/r2dreamer@546e4fab8146ea4b14e1d7726bbc1a8a1d50322f`. The civilian smoke reads a registered train scenario. The service does not evaluate heldout policies or generate confirmation outcomes, create study identities, or start the six formal learner paths. Integrity tests and manifests may inspect heldout file bytes, schema and metadata hashes.

## Runtime

The dedicated venv uses the read-only Python 3.11.16 / Torch 2.7.0+cu128 / NumPy 1.26.0 runtime through `read_only_original_runtime.pth`. Overlay packages are installed into the new venv in the ordered phases in [environment-spec.json](../../linux_execution/environment-spec.json), using `--no-deps` so pip cannot replace the shared Torch or NumPy. The declared upstream Torch version is 2.8.0, so this run must be reported as a Linux compatibility run, not an exact upstream reproduction.

## Invocation

Run this once with a new run id and output directory. The command contains only absolute paths without spaces, so it can be passed as an argv list through SSH without additional shell quoting:

```text
/bin/bash /home/user1/w1-pilot/rlwm-engineering-20261014/source/linux_execution/launch_systemd_run.sh
--repo-root /home/user1/w1-pilot/rlwm-engineering-20261014/source
--venv-path /home/user1/w1-pilot/rlwm-engineering-20261014/runtime/venv
--output-dir /home/user1/w1-pilot/rlwm-engineering-20261014/source/reports/linux-engineering-20261014/run-01
--unit rlwm-engineering-20261014-01
--run-id linux-eng-20261014-01
--source-identity c8b705e
```

Pass those lines as the following argument vector to `/bin/bash` (the line breaks above are for readability):

```text
[
  "/bin/bash",
  "/home/user1/w1-pilot/rlwm-engineering-20261014/source/linux_execution/launch_systemd_run.sh",
  "--repo-root", "/home/user1/w1-pilot/rlwm-engineering-20261014/source",
  "--venv-path", "/home/user1/w1-pilot/rlwm-engineering-20261014/runtime/venv",
  "--output-dir", "/home/user1/w1-pilot/rlwm-engineering-20261014/source/reports/linux-engineering-20261014/run-01",
  "--unit", "rlwm-engineering-20261014-01",
  "--run-id", "linux-eng-20261014-01",
  "--source-identity", "c8b705e"
]
```

The launcher creates one transient **user service** with `Restart=no`, `KillMode=control-group`, `CPUAffinity=0`, `CPUQuota=100%`, `MemoryMax=4G`, and `RuntimeMaxSec=600s`. It uses `RemainAfterExit=yes` and polls for `active/exited` or failure. The retained unit is read before one explicit cleanup stop; it does not use `--collect`. The runner also verifies that CPU 0 is allowed and applies affinity to its process.

## Pass Conditions

- Python is 3.11.16; Torch is 2.7.0+cu128; NumPy is 1.26.0; pinned overlay versions match the spec.
- Imports succeed, `CUDA_VISIBLE_DEVICES` is empty, Torch CUDA is unavailable and uninitialized, and the seeded CPU matrix witness is finite.
- The unittest log reports `Ran 26 tests` and `OK`.
- Both smoke receipts pass, record exactly three updates, show one Torch thread and CUDA uninitialized, and include a changed parameter hash plus a matching restored-model hash.
- Civilian receipt reports 128 adapter steps, 120 physical minutes, zero illegal actions, zero formal updates, and a train-split scenario.
- FP32 precision control records two finite optimizer steps. FP16 may pass or stop; either result remains recorded.
- `run-receipt.json` status is `pass`; systemd checks confirm exit success, no restart, control-group killing, CPU affinity/quota, memory limit, runtime limit and CPU usage counter.
- `artifact-hashes.json` includes the source manifest, stage logs, smoke receipts, checkpoints, precision diagnostic, systemd logs/status, and the final receipt hash.

## Failure Handling

The runner never retries. It persists the first error, stage argv, traceback, log tail, stage resource sample, and hashes, then exits nonzero. The launcher still collects systemd status and cgroup counters. Do not rerun the same `run-id` or output directory. Review the saved receipt and logs first; any separately authorized retry must use a new run id and output directory.

Systemd checks are bounded service checks, not full system accounting. MemoryPeak can be unavailable on systemd 249; single-child getrusage RSS and sampled process-tree RSS are separately labelled.

Resource values cover the transient systemd service and its child processes only. They do not include source transfer, environment installation, SSH overhead, or unrelated work in the user session. RSS samples are sampled process-tree measurements; systemd cgroup CPU/memory fields are recorded separately. These measurements do not freeze the full pilot budget or authorize study training.
