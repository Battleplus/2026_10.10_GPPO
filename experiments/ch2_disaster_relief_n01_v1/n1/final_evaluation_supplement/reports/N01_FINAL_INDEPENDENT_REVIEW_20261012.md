# N01 final independent review (local package)

Review date: 2026-10-12 (Asia/Shanghai)

## Decision

**Local frozen package: PASS. Target execution readiness: NOT READY.** This is an independent static package review only. No trajectories, model evaluation, training, or full run were started. It does not certify any published archive or GitHub release that was not present in the reviewed workspace.

## Bound inputs

- Evaluation identity: `ch2-disaster-relief-n01-full-evaluation-r1-20261011`
- Local package identity manifest SHA-256: `3667872dc04bcabbc6c5bbe77cabf169e8344c5e8cb337376c164a24c5d9bdb6`
- Reproduced plan canonical SHA-256: `84e37c9816ba27aa780d07ddf31b19fe4609977532825f19a8d7976918cfd78d`
- Plan's bound identity manifest SHA-256: `3667872dc04bcabbc6c5bbe77cabf169e8344c5e8cb337376c164a24c5d9bdb6`
- Plan file: `received/n01_full_evaluation_preflight_plan_final_r11.json`; r12 has the same content and canonical plan SHA.
- Independent dry-run copy: `%TEMP%/n01_independent_static_review_20261012.json` (outside the package).

The plan's `plan_sha256` is the SHA-256 of canonical JSON after removing the `plan_sha256` field. It is therefore expected to differ from a byte-for-byte SHA-256 of the pretty-printed plan file. The canonical digest reproduced independently and equals the digest embedded in the plan; this is not a mismatch.

## Findings

The package's `--mode dry-run` completed successfully on 2026-10-12 and regenerated canonical plan SHA `84e37c...8fd78`. The plan contains 350 hashed scenarios across five conditions, six checkpoint records, 28 current source/input hashes, and 2,800 unique `(condition, parent, method, seed)` keys. It reports 2,240 heldout and 560 development episodes. The six checkpoint file hashes, manifest hash, architecture evidence, and saved state/optimizer digests are represented in the plan barrier. This is static verification; fresh strict model loads are a target-admission gate and were not performed here.

The source identity inventory covers the full evaluator, reused evaluator and policy/environment/audit code, dataset protocol, runtime and preregistration, scenario and input manifests, checkpoint manifest, prior-cost records, resource supervisor and guardian, and systemd runner/settler/service files. `n01_full_evaluator.py` validates the complete inventory before execution. Stage dispatch and the child each derive limits from the proposed identity budget and replace legacy 1,140/720-second defaults with the 5,940/4,800-second identity caps. Early-stop thresholds preserve the configured 70 wall / 40 CPU seconds for settlement and teardown. The budget is still `proposed`; the required external `N1_FULL_EVALUATION_BUDGET_APPROVAL.json` is absent.

The settlement code checks the effective user unit, invocation ID, systemd properties and cgroup readback. It records `cpu.stat` sampling and only reports a kernel CPU quota when `cpu.max` supports that claim. The service template specifies `Type=exec`, `KillMode=control-group`, `MemoryMax=4G`, CPU accounting and affinity, `RuntimeMaxSec=5900s`, and `TimeoutStopSec=40s`. These are local template facts, not evidence of the installed target unit.

No private key material was found in the reviewed `package/` or `received/` files. The historical failed-probe record contains an old key path as text, not key contents. The reviewed workspace does not contain a current target static-preflight receipt or current installed-unit/systemd readback. Historical no-model probe evidence is not current proof. Accordingly, the target remains NOT READY until a current, identity-matching target receipt confirms static preflight and effective systemd/cgroup settings. The explicit budget approval must also exist before any guarded stage can start.

## Scope limits

This review does not approve the budget, authorize the run, or certify result quality. It does not review an archive or GitHub package created after this local review. The static plan and package identity are bound below so an eventual 2,800-row result can be independently checked against the exact reviewed inputs. Resource accounting uses sampled `cpu.stat`; the package documents the sampling interval and possible overshoot, which is an acceptable measurement limitation for this readiness review.
