# Independent final hosted preparation review — R9

Reviewer: GPT-6.1 Sol, high reasoning. Date: 2026-10-14.

Verdict: the frozen concrete managed-worker package and R9 controller are ready for a bounded Linux engineering acceptance attempt **after** connectivity, key identity, budget approval and fresh exact one-time authorization are resolved. **Stage A is incomplete; hosted acceptance is NOT RUN.** This source review grants no execution authorization and establishes no research effectiveness.

## Exact reviewed identities

| Artifact | SHA-256 |
|---|---|
| Package manifest | `661C80171B56DA0C45A072AA6699EE9D21032C2B3BB63D639286894D5655B05E` |
| Package content, sorted path=hash records | `FC38A4F7F0CA042313E7679F2CB137D64DDAEA0BEC34ECF139B300DB03E82BDC` |
| External budget proposal | `41931A96B2186BA9E589ADA0FDA3A9859611E9F48AEDF43E1672464D10F5FEA3` |
| Concrete proposed controller configuration | `B20073B957BEDC9DD6D9F5A628710A1667B96CB528747E079FC40217B23C437A` |
| R9 controller snapshot, canonical 17-file mapping | `6243B63A531EDD25E8F51D3A6BB05183EDD7195B59A92DC532B0D6636337531B` |
| R9 n2_controller.py | `CD90E38CB20B09EDE123FA178E46875854828A4E185081064B7FF783C3A5973E` |
| R9 managed controller bundle | `10DA0133BD5511596AB3EFFF7BC9A053FE1B6872FA12F502BC9FB0CAF6CF71D1` |
| R9 focused mocked-test log | `A70496E0D8FAB4B9D3049939BFE6BD1944C0F8B21DC51D9BA29C1096DEF9FE90` |

Paths: `n2-development/hosted-engineering-package-r1-20261014`, `n2-development/controller-final-r9`, `n2-development/hosted-engineering-budget-proposal-r1-20261014.json`, and `n2-development/hosted-preparation-evidence/controller-config-proposed-r9-20261014.json`, all under `E:/10.14`.

The independent executable audit is `audit_hosted_final_r9_sol.py`; machine-readable observations and every reviewed Python source hash are in `audit_hosted_final_r9_sol_output.json`, beside this report. Original R6 experiment results and R7/R8 review artifacts were not modified or re-run.

## Findings resolved in the frozen artifacts

1. The manifest now includes `cpu_quota_percent: 100`, matching both controller validation and the proposed budget. The previous omission would have rejected the package before SSH.
2. The event/signal contract dependency is present and hash-bound at `references/world_model/event_signal_contract.py` (`BA7B154A9385B2285A3F7BBF5DC82911CC087E194B4B8D5338D4DB6D8C88D194`). Exact inventory is 54 files plus manifest; no missing/extra files or digest mismatches were observed.
3. R9 checks the terminal, same-invocation systemd `CPUUsageNSec` and `MemoryPeak` before collection can produce success. CPU comparison uses integer nanoseconds and Decimal budget conversion, avoiding a float rounding gap. Missing, empty, non-ASCII, nondecimal or negative counters reject; nonfinite/invalid guard values reject. An overrun enters the existing first-error and same-invocation stop/settlement path without retry or reconnect. Existing mocked coverage records one stop and one settlement for each CPU/memory tail overrun; its 20-test log and source hashes match the freeze.
4. The launch explicitly sets CUDA visibility empty, OMP/MKL/OpenBLAS/NumExpr threads to one and disables bytecode writes. The worker admits Linux, Python 3.11.16, Torch 2.7.0+cu128, NumPy 1.26.0, one Torch thread and interop thread, CUDA unavailable and uninitialized. Target admission has not yet been observed.

## Source and contract assessment

The concrete managed worker's imported modules are present. Static import scanning also reports missing `local_runtime` and `tail_reserve` in the copied legacy `references/infrastructure/supervise.py`; that helper belongs to `launch_pilot` and is outside the concrete managed-worker/controller-vendor path. This review does not assert that every copied reference entry point is independently runnable.

The eight requested stages match the managed worker order. Per-stage caps sum exactly to global totals and match the external proposal: 8,000 environment steps; 20 WM and 64 PPO optimizer steps; 32 checkpoint operations; 1,000 output write operations; one verified export. BudgetLedger.call accepts the adapter's *args/**kwargs interface, durably reserves before work and preserves failed/pending charges. Environment, optimizer, forward, checkpoint and output operations route through the real ledger API. The existing direct-vendor mapping receipt has eight settled calls and zero failed/pending calls, but explicitly bypasses select()/StageServer transitions. It is **not** a live stage-routing acceptance test.

The managed worker archives its output tree, which includes branch JSONL, WM checkpoints and original/restored PPO rollout/checkpoint artifacts; it adds a member digest index and exports the ZIP through the verified copy operation. An independent tiny synthetic-file invocation of the extracted archive helper confirmed the raw branch/checkpoint/rollout bytes and index hashes are inside the ZIP. It imported no Torch or training code. The stage-8 allowance of one output write matches ZIP creation; verified export is a separate ledger resource. Only the real target run can prove that the final actual archive contains the run's raw data and is collected intact.

PPO next-update verification compares uninterrupted and restored next-round behavior, model and optimizer digests. Strict restore includes the saved optimizer, random state, schedule/counter identity and augmented critic state. WM restore validates identity, model digest, Adam update coherence and update-boundary counters before the next real update; the worker compares next-update model states. No new public/hidden input leak was observed: WM feature tensors derive from validated public policy input; branch outcomes are joined as targets by public IDs; frozen WM critic inference consumes public tensors. Previous R8 label/normalization/init/Adam audits remain the evidence for those unchanged implementations.

Resource limits are 1,200 seconds total wall, 900 seconds total process CPU, 4 GiB cgroup memory, 1 GiB combined sampled storage, and 100% CPU quota, with 45-second wall and 30-second CPU settlement reserves. R9 truthfully labels storage as a sampled high-water mark with the last supervisor sample before receipt writing; storage is not a continuous quota and does not measure the receipt-write tail. The settled systemd CPU/memory guards cover the corresponding post-snapshot process tail. Keep this storage limitation in acceptance evidence.

## Exact remaining blockers

1. The concrete config budget is `NOT_APPROVED`; the external proposal is `PROPOSED_NOT_APPROVED`. Its private-key path is explicitly `REQUIRES_VERIFIED_PRIVATE_KEY_PATH`. Verified `user1` connectivity and key/known-host references remain necessary; no secret material was read or emitted in this review.
2. A legitimate fresh exact authorization must bind the final configuration, approved budget, package manifest, R9 controller/bundle/standalone sources, fresh run/unit/remote root, approver/timestamp and persistent consumption root. The two previously consumed failure identities must never be reused. Replacing the key reference or approving the budget changes the exact request and requires the corresponding new binding. This review created or consumed no authorization and did not fabricate an approved record.
3. Actual target Linux runtime admission, systemd Type=exec success, live StageServer socket/handshakes, actual worker BudgetLedger routing/settlement, terminal cgroup CPU/memory evidence, sampled storage evidence, nonempty verified raw ZIP collection and failure/pending records remain unobserved for this final package. Windows mapping checks cannot satisfy these requirements.
4. Research-budget readiness remains outstanding for the wider Stage A gate. This engineering proposal authorizes no formal research training and no B/C/D work.

Recommendation: complete those prerequisites, then perform one bounded Linux engineering acceptance under the legitimate fresh exact record. Treat failure as consumed once-only evidence and preserve first-error, pending and settlement records. Mark Stage A complete only when the target acceptance and required research-budget readiness actually pass.
