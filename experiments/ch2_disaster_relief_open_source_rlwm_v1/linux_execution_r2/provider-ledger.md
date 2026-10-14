# Linux Provider Ledger

## ru-server-MS-1

- Shape: direct SSH host with a dedicated venv.
- Host identity: `user1@172.17.27.173` (`ru-server-MS-1`).
- Source root: `/home/user1/w1-pilot/rlwm-engineering-20261014/source-r2`.
- Run venv: `/home/user1/w1-pilot/rlwm-engineering-20261014/runtime/venv-r2`.
- Read-only base Python: `/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python`.
- Read-only base packages are referenced from the new venv by `read_only_original_runtime.pth`; the base runtime is not modified.
- Environment spec: `environment-spec.json`.
- Canonical spec hash (sorted JSON, no whitespace, SHA-256): `e3a397648bcecf7f8fa556cf6d20df21b54c82fe6b3c5b7f5fa1076026f60230`.
- Observed base versions: Python 3.11.16, Torch 2.7.0+cu128, NumPy 1.26.0. CUDA was not initialized during the probe.
- Upstream `pyproject.toml` declares Torch 2.8.0. This provider environment is a compatibility runtime and is not an exact upstream Torch 2.8 reproduction.
- The first environment installation passed pip check but the first run stopped on missing TensorBoard and an external fixture path. The separate r2 environment adds the fixed TensorBoard dependency closure; its build and witness are pending. The existing base venv was not changed.
- Resource shape: CPU affinity 0, CPU quota 100%, memory maximum 4 GiB, runtime maximum 600 seconds, one Torch thread, CUDA hidden.
- Evidence location: `reports/linux-engineering-20261014/`.

## Readiness

The environment is built but the seeded CPU witness and execution sequence are still pending. Do not call it ready until the documented transient service completes with `run-receipt.json` status `pass`, systemd accounting checks complete, and artifact hashes are present. Any changed spec hash requires rebuilding or recording a new ledger entry. Do not retry a failed run id; inspect its first error and logs before considering a newly named run.

The receipt's process and cgroup counters cover the bounded service and its child commands. They exclude SSH, source deployment, package installation, and unrelated user-session work.
