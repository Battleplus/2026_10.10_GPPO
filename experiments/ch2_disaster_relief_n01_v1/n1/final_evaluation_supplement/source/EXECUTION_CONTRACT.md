# Relief graph migration: accepted execution contract

Date: 2026-10-11 Asia/Shanghai. User explicitly approved implementation, six new CPU training runs, evaluation, and GitHub archival. No further generic execution approval is required within this contract. Historical identities, frozen packages, checkpoints and evidence remain unchanged. Independent new package only. No automatic research resubmission, added tuning or expanded budget.

## Scope and ownership

- Luna graph executor owns copied civilian environment/schema/baselines/adapter/audit/identity, graph representation and policy, graph/environment tests and source-reuse manifest. Source: development/ch2_disaster_relief_v1 and src/uav_assignment/paper_faithful_models.py. Exclude historical results and bytecode when copying. Retain 25 old tests as regression evidence. New files may be adapted; old files remain read-only.
- Luna training executor owns dataset generation/protocol, PPO/GAE/trainer/checkpoints, driver/resource supervisor, evaluation/report/export, corresponding tests and source-reuse records. Source optimizer: src/uav_assignment/ppo.py. Coordinate exact Python APIs directly with graph executor before coding consumers.
- GPT-6.1 Sol owns independent review and REVIEW.md. Reviewers may coordinate corrections directly with owners. Main coordinates only integration gate, budget freeze and final delivery. Do not revert others' work.

## Experiment

C0 fixed initial queue; C1 existing public rule; L0 entity-wise MLP without message passing; L1 graph GPPO with reused Literal platform attention/task update/shared pair scoring/NOOP. L1 hidden64, L0 active capacity within5%, deterministic static architecture search (not data-driven); common modules paired initialization per seed8201/8202/8203. No world model/PreCo/preference or cross-block borrowing. All six freshly initialized. Frozen final checkpoints only, no best-seed/model selection.

Expose reset/step(batch)/export preserving exact old C0/C1 events/results. One step=one minute; horizon60 terminal. Autoregressive batch of public candidate IDs, mask assigned platforms/tasks, NOOP stops, finite bound. Whole-batch logprob=sum conditional logprobs; PPO tick transitions, scalar initial value, logged residual masks and selections. No physical time for intra-batch selections. Public features only, dynamic node sizes/explicit masks, no hidden-order padding leakage. Preserve outside commitments and actual logistic lifecycle.

Reward: first confirmed on-time delivery priority/5; first received report of on-time inspection +0.1; motion/service energy -0.01 per synthetic unit; each initially assigned task's first change of carrier -0.05. No hidden denominator, duplicate rewards, or shaping added later. Independent metrics remain authoritative.

PPO Adam3e-4, gamma.99 lambda.95, clip.2, value.5, entropy.01, max gradnorm.5. Per rollout round4 full episodes=240ticks,4epochs,minibatch60=16 optimizer steps. Explicit termination/bootstrap/continuation masks, detached rollout, deterministic expected RReLU. Strict save/restore model+optimizer+Python/NumPy/Torch RNG+schedule/config/source/data identities; next update equals uninterrupted path.

## Data and comparison

Old7 fixtures only regressions. New train56/dev14/eval56 parents, equal allocation to7 strata: control/failure/energy/stock/report-delay/combined/external commitment. Fixed3UAV+1heli, horizon60. Preregister generator ranges before any new training; vary positions/priorities/service/quantities/deadlines/disturbance times within existing civilian schema. Initial queue capability/capacity/local contract valid. Generate/register all input hashes first; distinct parent IDs and scenario tapes, no outcome-based rejection or selection. Use dev only for engineering diagnosis; heldout outcomes accessed after six final checkpoint barrier. Evaluate C0/C1 once and each of six models on same56parents, deterministic actions. All inspected evaluation parents become future development material.

Report parent-macro weighted on-time delivery (primary); inspections ontime, unmet/late orders, outside commitment delay, energy, reassignment, decision CPU/wall. Per-seed L1-C1/L1-L0, paired-parent bootstrap on seed means, individual seed directions; no claims bootstrap includes all training uncertainty. Negative results retained, no added search. Learning curves and per-task traces with independent audit.

## Server and bounds

Target existing ru-server-MS-1 runtime /home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python (Python3.11.16 Torch2.7.0+cu128 NumPy1.26.0). CPU0, torch/BLAS single-thread, CUDA_VISIBLE_DEVICES empty, GPU never initialized. Local diagnostics distinct from server proof. Main owns SSH deployment/actual submission unless explicitly delegated after integration; do not independently launch jobs.

Whole server pilot bounds wall14400/CPU12000sec, RSS4GiB, work+export8GiB. Stages wall/CPU: admission600/300; real-smoke900/600; six-training9000/8400; evaluation-analysis2400/1800; export600/300; shutdown reserve900/600. Transfer separate. Supervisor must guard actual full process lifetime/resources, keep first error and partial checkpoints, no reserve borrowing. Record exact scope, unresolved measurement gaps honestly; prevent cumulative acceptance/tests consuming untracked server budget. Local development tests have separate evidence.

Smoke: independent engineering identity, L0/L1 two real rounds each plus strict recovery and tiny full driver success/failure acceptance, within smoke budget. No smoke weights reused. Measure full round wall/CPU including normal checkpoint writes; use slower observed costs across both architectures and smoke rounds. Freeze common rounds=min(32, floor(9000/(6*1.5*max_round_wall)), floor(8400/(6*1.5*max_round_cpu))). If rounds<8 stop as budget-insufficient before starting six runs. Include startup/final-save fixed overhead in guard and conservative round sample; no retrospective reduction to successful subset. Budget freeze recorded before six fresh runs.

## Acceptance and delivery

Real target-runtime full driver from admission through genuine update/recovery/evaluation/normal export, plus controlled failure receipt, before six-run phase. Exact source used in acceptance is deployed/frozen source. Semantic tests: old7 fixture identity regression; conservation; hidden information invariance; permutations/padding/NOOP/empty/variable size; hand GAE terminal/truncation; ratio1; gradients/updates; exact resume next-update equivalence; resources/failure settlement. Review actual test coverage, not just counts.

Deliver code, source and change inventory, resolved protocol, datasets, six checkpoints if budget admits and run succeeds, learning curves, paired/per-task results, independent metric audit, measured resources and Chinese report. Archive code/reports to https://github.com/Battleplus/2026_10.10_GPPO using existing gh auth; never store or echo supplied PAT. Old archive commit and evidence retained. No secrets/server credentials in public archive.
