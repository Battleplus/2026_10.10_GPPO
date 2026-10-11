# Chapter 2 N0/N1 Scope and Preregistration

Status: preregistered before any N1 scenario outcomes are generated or evaluated.
Date: 2026-10-11 (Asia/Shanghai).
Research identity: `ch2-disaster-relief-n01-v1`.

## Scope

This identity completes N0 evidence analysis and N1 fixed-checkpoint evaluation only. It does not train, fine-tune, select, or update any research model. N0 reads the existing civilian trajectory bundle, final checkpoint metadata, training logs, and metrics. N1 evaluates frozen L0/L1 checkpoints for seeds 8201, 8202, and 8203, plus C0 and C1, across five scenario conditions. The six final checkpoints are never modified. No N2/N3 execution is authorized by this plan.

The prior v2 experiment has already inspected its evaluation split. Those 56 parents, the 14 development scenarios, and any newly generated N1 scenarios are development material for later work. No result here will be called confirmatory evidence or generalization evidence.

## Sources and reuse

Primary implementation source is the civilian package at `research-executions/ch2-disaster-relief-graph-v2-20261011/source/package`; source release and result bundle are treated as read-only. N1 reuses its schema validator, environment state machine, public C0/C1 rules, L0/L1 policy implementation, and independent trajectory audit by an explicitly hash-bound copy or import. The final civilian checkpoints and their metadata are read only from `research-executions/ch2-disaster-relief-graph-v2-20261011/evidence/extracted/checkpoints` and `indexes/checkpoint_index.csv`.

`research-plans/w1-drone-consequence-ranking-window-balanced-ablation-v7-input-reuse-stage-schedule-repair/package` may be consulted only for generic graph-policy engineering patterns. No military scenario, trajectory, checkpoint, optimizer state, or weight is an input to N0 or N1.

## Conditions and fixed methods

Each of the 14 prior development parents and 56 previously inspected evaluation parents is evaluated under every condition, for 70 parents per condition and 2,800 episodes total. These are all exploratory/development materials. Each parent is evaluated with the same scenario tape under C0, C1, L0-8201, L0-8202, L0-8203, L1-8201, L1-8202, and L1-8203. All learned actions are deterministic. No model-specific tuning, checkpoint selection, or research training is permitted.

1. `original`: unchanged base scenario, 4 platforms and 6 tasks.
2. `scale_8x12`: two independent copies of a base scenario, 8 platforms and 12 tasks.
3. `scale_12x18`: three independent copies, 12 platforms and 18 tasks.
4. `carrier_competition`: base scenario with the known food delivery and first hidden delivery each set to 16 kg. The first hidden delivery is the stable first hidden task in source task order (`latent-medical`); its commodity remains medical. Only the task `quantity` field changes; stock, initial queues, locality, and all other fields remain as generated. The pre-intervention initial assignment is validated as legal. After the intervention, where the queued owner has only 8 kg capacity, record the initial-plan capacity conflict and leave the task in every method's denominator. Adaptive policies may reassign a publicly visible task only to a compatible platform within the existing locality/commitment rules. The initial-queue C0 rule is not changed. In external-commitment parents, local 16 kg tasks have no eligible carrier because the helicopter is outside the local block and UAV capacity is 8 kg; the 16 kg external known-food order can also exceed the queued UAV's capacity. Report these structural infeasibilities and candidate absence as a separate stratum, with no cross-block reassignment or silent repair. Dispatch rejection is not expected when the candidate is absent. Because source inventory remains fixed, this is a combined carrier-and-stock pressure condition: report task capacity-compatible platform counts separately from declared-demand versus available-stock shortfalls for each affected commodity. Do not attribute all missed demand to carrier capacity.
5. `stock_competition`: base scenario with depot water stock fixed at 60% of the sum of all declared water delivery quantities, before any stock-loss event. The target ratio is the unrounded product; actual delivered quantities and shortages are reported so partial allocation is not mistaken for a full order.

Scale copies receive unique scenario, platform, task, depot, and disturbance IDs. Every queue, discoverer, task/depot reference, platform/depot disturbance reference, and event reference is remapped. All declared tasks remain present. Depot inventory is summed across independent copies so total stock scales with declared demand. Resource constraints are expanded consistently with each independent copy, except for the explicit N1 competition interventions above. The `stock_competition` water stock is the unrounded 0.6 multiple of declared water demand; partial and unmet quantities stay visible in outcome denominators. The 16 kg carrier intervention changes order quantities but leaves stock at its original base-scenario value; it does not create a second inventory treatment. If schema, ID, locality, or baseline-scenario checks fail, reject before policy evaluation; the only allowed initial-queue compatibility exceptions are the preregistered post-intervention capacity conflicts above.

## Checks and measurements

Before evaluation: validate unique IDs and resolved references; verify original allocation coverage and each platform-task compatibility; record any carrier-intervention infeasibility without changing the snapshot; verify dynamic graph sizes; verify candidate IDs map to the same entities after input permutation; check policy-facing observations/candidates contain no hidden task fields before disclosure; compare permuted-input outputs by stable entity identity; and independently replay all exported trajectories.

For every condition and method, report parent-level weighted on-time delivery rate, on-time inspection rate, unmet and late demand, demand-weighted and task-count rates, energy, reassignments, outside-commitment delay, and the worst 10% of parent scores. State the numerator and denominator, parent count, task count, declared demand, and fulfilled demand for each rate. Report every seed direction and parent-level paired contrasts. Scale results are descriptive comparisons at different workload sizes; additional tasks are not evidence of a transfer advantage by themselves.

N0 classifies each observed issue as (a) an evidenced task bottleneck, (b) a feature/relation absent from the representation, (c) a demonstrated engineering defect, or (d) unresolved. Correlation in old trajectories is not a causal claim. A relation absent from code cannot be described as a learned capability.

## Runtime and resource gate

The target Linux Python/Torch/NumPy runtime must be measured before any server budget is frozen. The old four-hour allowance does not carry forward. Following runtime measurement, freeze a new identity-bound stage ledger with conservative bounds for runtime admission, N1 engineering acceptance, evaluation, export, and shutdown. Any material resource increase returns to the parent model for a node decision before it is consumed. CPU affinity is core 0, all thread pools are single-threaded, CUDA is disabled, and GPU initialization is forbidden.

Target: `user1@172.17.27.173`, runtime `/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python`. No runtime claim is made until receipts from that exact interpreter are verified. Engineering acceptance uses an isolated disposable identity and may perform the minimum real update needed to verify update/save/strict restore/evaluate/export and failure accounting; engineering updates are not research training and their weights are discarded.

## Stop and decision boundary

Preserve the first error and all partial evidence. Never relaunch the same frozen research identity after a technical failure. A code repair gets a new engineering identity and records prior consumption. Stop after N1 and return the complete node packet for parent decision. Do not start N2/N3.
