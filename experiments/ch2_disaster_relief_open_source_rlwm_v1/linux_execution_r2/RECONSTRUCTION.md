# Reconstruct the executed r2 release

The authoritative release manifest is `LINUX_RELEASE_MANIFEST.json`, SHA-256 `62553282bd69a851c83f3db3a3463c9f64e70323dfb93b6820a3c6ea8f644340`.

1. Extract only `experiments/ch2_disaster_relief_open_source_rlwm_v1/` from Git commit `c8b705effe6c314d5740be89112e5dd5a0547a40` into a clean directory.
2. Copy the files listed under `linux_execution/` in the release manifest from this archived `linux_execution_r2/` directory into that clean directory's `linux_execution/`, preserving bytes.
3. Apply `test-path-portability.patch` to `tests/test_decision_repeat_adapter.py`. No assertion or algorithm changes are made.
4. Copy `LINUX_RELEASE_MANIFEST.json` to the release root; verify all 313 registered file sizes and SHA-256 values. Including the manifest itself, the deployment has 314 files. Documentation added after execution is not part of that executed snapshot.
5. Build a dedicated venv using `environment-spec.json` and `bootstrap_linux_r2.py`. The base Torch/NumPy runtime is read-only. The bootstrap uses the recorded dated paths and is retained as executed provenance; adapt paths only in a new independently documented build, never overwrite the old environment.

The parent `reports/DELIVERY_HASHES.json` describes the original c8b705e archive and is intentionally preserved in the release. It does not describe the patched r2 release.

The original Linux run-01 remains archived. Do not reuse either run id/output directory or submit the launcher again merely to reproduce counters. Any new engineering execution requires a new documented run identity and bounded plan.
