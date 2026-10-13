# N2 Engineering Archive

This archive contains local synthetic engineering work, its draft protocol, a Linux acceptance package candidate, and the outcome of one stopped target preflight. It contains no research trajectory collection, model fit, prediction gate result, or formal policy comparison.

## Rebuild Layout

The source closure is under `development/`. To reproduce the documented commands, copy that directory's contents into the root of a clean checkout or temporary workspace, preserving the paths below:

```text
development/
  ch2_disaster_relief_graph_v2/
  ch2_disaster_relief_n2_v1/
```

In a POSIX shell, from the extracted archive root:

```bash
mkdir -p /tmp/n2-workspace/development
cp -a development/. /tmp/n2-workspace/development/
cd /tmp/n2-workspace
```

Use Python 3.14.4, PyTorch 2.13.0+cpu, and NumPy 2.5.0 to reproduce the recorded local run environment. The tests and synthetic smoke also require the standard library. The Linux runner packet separately admits Python 3.11.16, PyTorch 2.7.0+cu128, and NumPy 1.26.0 on CPU; that runtime was not accepted by the stopped preflight.

Run the N2 engineering suite and smoke from the reconstructed workspace:

```bash
python -B -m unittest discover -s development/ch2_disaster_relief_n2_v1/engineering/tests -q
python -B development/ch2_disaster_relief_n2_v1/engineering/run_ppo_integration_smoke.py \
  --output-root /tmp/n2-workspace-smoke-output
```

The smoke defaults to seed 8201 and writes synthetic outputs only under the explicit output root. The Linux packet can be rebuilt locally with:

```bash
python -B development/ch2_disaster_relief_n2_v1/engineering/package_n2_linux_acceptance.py \
  --source-root /tmp/n2-workspace --output-root /tmp/n2-package
```

The source root must contain exactly the paths listed in `development/ch2_disaster_relief_n2_v1/preparation/linux_acceptance/package-manifest.json`. Package construction does not authorize target execution.

## Evidence Boundaries

The N2 archive reconstruction workspace ran 29 engineering tests successfully after adding the civilian source-identity file `development/ch2_disaster_relief_graph_v2/PRIOR_RESOURCE_COST.json` (SHA-256 `B577B88138699DCEFC8286314B64D0C41D7278F36ED3DB38ECCDAE962A5ED263`). This file is a local test runtime input and is not in the frozen Linux package manifest. Re-running the same 29-test suite inside a package rebuilt from the exact 23-file manifest produced 28 passes and one error because that file is absent. Therefore the current Linux package candidate is not test-complete and requires a separately reviewed package identity update before any future target run. The earlier report of 26 engineering tests plus 3 focused runner tests is retained as evidence for its recorded source identity; it does not override this package reproduction result.

The separate M0/M1 preparation records 27 inherited regressions and 4 snapshot probes. All historical counts are bound to their recorded files and environments; they do not apply to arbitrary modified source versions.

The archive reconstruction smoke was rerun locally on Python 3.14.4, PyTorch 2.13.0+cpu, and NumPy 2.5.0. Its sanitized receipt reports 57.329 seconds wall, 54.563 seconds process CPU, 720 combined transitions, 48 combined optimizer updates, and strict next-round restore equivalence. Checkpoints, rollout files, and exports from that run are not included. This synthetic run is not research training, a prediction gate, or Linux resource evidence.

The Linux preflight authenticated once and stopped at a Python `AssertionError`. Its exact failing assertion is unknown. No package was uploaded, no target directory was created, and no systemd unit was submitted. No retry occurred. See `reports/N2_LINUX_PREFLIGHT_STOP_SUMMARY_ZH.md` and `reports/N2_ARTIFACT_INDEX.md`.

M0 is the reuse baseline and M1 is local engineering preparation only. Formal data collection, training, prediction, policy comparison, and confirmation remain unstarted and require their own frozen contract and decision.
