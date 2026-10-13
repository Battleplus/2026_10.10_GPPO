# Experiment Audit Report

Date: 2026-10-14 (Asia/Shanghai; evidence snapshot 2026-10-13T16:34:04Z)
Auditor: GPT-6 Codex subagent, same-family review; provisional acceptance
Project: Open-source RL + world-model civilian migration v1
Audit ID: rlwm-stage01-20261014-codex-luna-review

## Overall Verdict: WARN

Integrity status: warn. No evidence of fabricated ground truth, output-based score normalization, or nonexistent result artifacts was found in the bounded engineering evidence. The evidence supports local engineering smoke checks only; it does not support a formal training, evaluation, or algorithm-performance claim.

## Scope and conclusion

Reviewed the r3 regression and failure artifacts, the fixed-batch precision diagnostic, civilian r4 and upstream CartPole r5 smoke receipts, the scenario registry and scoped historical-data scan, the implementation and smoke harnesses, and the draft pilot plan. The current tested runtime is Python 3.11.5 with Torch 2.5.0+cpu. The successful r4/r5 smokes explicitly use a CPU float32 project overlay and mark exact_upstream_reproduction=false. Target Torch 2.8 was not tested.

The r3 test receipt reports 26 tests passed. The civilian r4 engineering smoke reports 128 adapter calls, 120 simulated physical minutes, 8 dispatch microsteps, 129 replay frames, 3 completed learner updates, 0 illegal actions, and successful strict checkpoint and metadata restoration. The upstream CartPole r5 smoke reports 31 environment steps, 3 learner updates, matching pre-save and restored model hashes, and optimizer restoration. Both receipts mark formal_updates=0. CartPole checkpoint scope is model/optimizer/scheduler/scaler and is explicitly not exact training continuation; the civilian checkpoint excludes replay and simulator state. The civilian RSS reading is null.

The fixed-batch diagnostic on Torch 2.5.0+cpu used the same batch, initial model and RNG state. CPU float16 stopped on the first backward with RsqrtBackward0 NaN and made no optimizer step. CPU float32 completed two diagnostic updates with finite losses, gradients and parameters. This supports a precision-path diagnosis only for this compatibility runtime; it does not establish behavior on Torch 2.8.

The upstream P0 r3 smoke failure (NaN RSSM logits), civilian r3 failure (non-finite RSSM gradients), and upstream r4-fp32 restore failure (OmegaConf actor.dist.disc KeyError) remain preserved as historical failures. Later r5 and civilian r4 receipts pass their engineering-smoke checks; these successes do not erase or broaden the earlier evidence.

The upstream provenance file declares NM512/r2dreamer commit 546e4fab8146ea4b14e1d7726bbc1a8a1d50322f. The extracted buffer.py SHA-256 is 3299fe6a9548000769a4ff9605dcf371e3e75758f2b62f0c7542415030756bf3 and matches the buffer.py entry in the local source ZIP. This establishes local snapshot/archive consistency, not external Git or remote commit identity; the project checkout has no verified Git/remote evidence.

The old-data receipt covers only its three explicit roots. It inventories 4,771 JSON/CSV files, all parsed, with no skipped entries; it reports 483 unique IDs and 6,513 unique structural semantic hashes and zero intersections with the current 126-row registry. The scanner only processes JSON/CSV and does not follow symlink directories. The 6,513 hashes are not a count of independent scenarios or episodes; semantic hashing removes scenario_id but otherwise hashes each recursively found object with tasks and depots.

Formal training and heldout evaluation remain unstarted. The pilot plan is draft, has no authorization, and requires a 56-parent heldout set only after six final checkpoints and strict restore checks. Target Linux admission and resource measurement remain blocked by unavailable SSH authentication; RSS is not measured. These are scope and readiness limits, not evidence of fraud.

## Checks

### A. Ground Truth Provenance: PASS

No performance evaluation or ground-truth claim was made. Both learning smokes consume simulator transitions (CartPole or the civilian adapter); they report training/update and restoration diagnostics, not agreement with model-generated references. The future weighted on-time outcome is defined from task priorities in the scenario, but the draft plan has not evaluated it. Evidence: protocols/PILOT_AND_COMPARISON_PLAN.md:3,51; upstream_smoke/upstream_dreamer_smoke.py:225,238; integration/civilian_dreamer_smoke.py:293,322; both r4/r5 receipts mark formal evaluation/updates as zero.

### B. Score Normalization: PASS

No evaluation score was produced and no metric was normalized by the learner's own output. The precision receipt reports raw fixed-batch losses and finite-value checks. The planned primary outcome denominator is the total priority of delivery orders in the episode, not a prediction statistic. Evidence: reports/cpu-precision-diagnostic-20261014.json:28, protocols/PILOT_AND_COMPARISON_PLAN.md:51.

### C. Result File Existence: PASS

The cited test log, failure logs, diagnostic receipt, civilian r4 receipt/checkpoint, and upstream r5 receipt/checkpoint exist. The success receipts agree with their stored checkpoint paths and hashes/restoration flags. Failure receipts remain separately identifiable and were not rewritten as passes. Evidence: reports/all-tests-compat-r3-20261014.log:35,37; reports/upstream-smoke-compat-r3-20261014.log:61; reports/upstream-smoke-compat-r4-fp32-20261014.log:71; reports/civilian-dreamer-smoke-20261014-r4-fp32/civilian-dreamer-smoke-receipt.json:2,305-310; upstream_smoke/results-r5-fp32/smoke-receipt.json:2,25-26,158.

### D. Dead Code Detection: WARN

The engineering smoke paths call the learner update methods and persist their returned metrics. No evaluation metric pipeline ran, so planned outcome evaluators and their outputs cannot be audited for call-site coverage from this evidence. This is an unverified evaluation implementation, not an observed dead metric function. Evidence: integration/civilian_dreamer_smoke.py:322, upstream_smoke/upstream_dreamer_smoke.py:238; protocols/PILOT_AND_COMPARISON_PLAN.md:51.

### E. Scope Assessment: WARN

Coverage is 26 engineering tests, one 31-step CartPole smoke with 3 updates, and one civilian smoke with 128 adapter calls and 3 updates. The two successful smokes use one fixed seed/runtime path; no formal learner updates or confirmation episodes were run. The registry has 56 heldout parents, but they remain unevaluated. Scope does not support words such as comprehensive, robust, or improved. Evidence: reports/ENGINEERING_NODE_20261014.md:11,15-18; upstream_smoke/results-r5-fp32/smoke-receipt.json:10,19; reports/civilian-dreamer-smoke-20261014-r4-fp32/civilian-dreamer-smoke-receipt.json:7,333-338; protocols/PILOT_AND_COMPARISON_PLAN.md:3,47.

### F. Evaluation Type: PASS

Both learner smokes and adapter behavior checks are simulation_only. The fixed-batch precision diagnostic is a self_supervised_proxy technical diagnostic based on simulated transitions and the learner objective; it is not a performance evaluation. No real_gt or human_eval result is present. Evidence: upstream_smoke/results-r5-fp32/smoke-receipt.json:10; reports/civilian-dreamer-smoke-20261014-r4-fp32/civilian-dreamer-smoke-receipt.json:2,11-12; reports/cpu-precision-diagnostic-20261014.json:2,28.

## Action items

- Run the smoke path in the intended target Linux/Torch 2.8 environment before claiming target-runtime compatibility.
- Keep the float32 overlay and checkpoint scope explicit; validate any future full training-continuation requirements separately.
- Restore authorized SSH access, measure CPU/RSS/storage and evaluation costs, then freeze the pilot budget before formal training.
- Do not open heldout confirmation results until all six final learner checkpoints pass the plan's identity and strict-restore barrier.
- Preserve the three-root and JSON/CSV limitations when citing the historical-overlap scan.

## Claim impact

- Local engineering path: supported with qualification to the observed Torch 2.5 CPU environment and float32 overlay.
- FP16 failure / FP32 finite diagnostic: supported only for the fixed batch on Torch 2.5 CPU; not generalized to Torch 2.8.
- Civilian performance improvement, world-model predictive validity, method superiority, scale generalization, or component synergy: unsupported; no formal evaluation exists.

## Audited input hashes

Complete SHA-256 manifest: reports/EXPERIMENT_AUDIT.json, audited_input_hashes. The hash of the extracted upstream buffer.py matches the same-path ZIP entry; the ZIP archive hash is recorded separately.
