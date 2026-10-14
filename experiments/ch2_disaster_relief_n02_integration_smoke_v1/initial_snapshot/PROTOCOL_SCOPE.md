# N2 Integration Smoke Scope Snapshot

This file records the task-book constraints used for the initial source snapshot. It is a planning record, not an authorization and not a research result.

## Required chain

`civilian scenario -> paired consequence collection -> real world-model training -> strict restore -> graph GPPO critic wiring -> real PPO updates -> paired development evaluation -> settlement/export`

All collection, branching, WM training, PPO training, and evaluation run only on `ru-server-MS-1`. Local work stops at source development, static inspection, package generation, and returned-evidence review.

## Frozen target matrix to implement and measure

- Eight training and four development parent scenarios; each split has four base-feasible and four carrier-competition parents where applicable.
- Three UAVs and one helicopter; 60 physical minutes per episode; distinct train/development identities and event seeds.
- Pre-action windows at minutes 8, 16, 24, and 32; at most 48 windows; at most eight public candidates per window; at most 384 branches.
- Candidates are a stable, deduplicated, truncated set of complete legal environment actions: NOOP/keep arrangement, full C1 action, and public-information local reassignment proposals. The source actor's complete autoregressive masked probability must be bound to the exact submitted action batch.
- Each branch restores one common pre-action snapshot, forces one candidate, then follows C1 for at most 30 physical minutes or true episode termination under the same exogenous event tape.
- Labels: current delivery on-time, current inspection on-time, current report timely, new lateness in other orders, unmet demand, energy, reassignment, and unchanged environment reward sum. Absolute values and applicable NOOP deltas carry explicit units, validity, and unknown reasons.
- World model: seed 8201, two epochs, batch size 8 windows, at most 32 training windows and 8 optimizer updates, existing pair-weighted ranking reduction, dynamic candidate/task axes, unknown masks, strict new-process restore.
- G and G-WM each reinitialize from matched seeds and run two rounds x four training episodes x sixteen PPO updates, followed by four shared development parents each. WM critic input uses detached five-global prediction features, a 5->32->1 auxiliary MLP with zero-initialized final layer. Actor logits, true future labels, synthetic rollouts, extra actor loss, and WM updates are forbidden.

## Phase and resource ceilings

Stages must be named identically in matrix, Request, driver, and StageServer:

`input_admission`, `paired_consequence_collection`, `world_model_training_and_restore`, `world_model_prediction_check`, `graph_policy_smoke`, `paired_development_evaluation`, `settlement_and_export`.

The cumulative ceilings are 3,600 s server wall, 1,800 s server CPU, 4 GiB RSS, 1 GiB each work/export storage, 2,048 WM forward batches, 16,384 candidate evaluations, 384 branches, 8 WM updates, 64 PPO updates, 16/8 policy train/development episodes, 600 s transport wall, 120 s client CPU, and 2 GiB transport. Reserve at least 120 s wall and 90 s CPU for settlement/export. Engineering, controlled acceptance, and real smoke costs are separately recorded and count toward the relevant ceilings.

## Stop rules

Stop before collection or training for runtime/affinity/dependency mismatch, missing public-prefix or snapshot contract, hidden-state leakage, action probability mismatch, invalid/empty supervision, NaN, restore mismatch, actor-logit dependence on WM, or a budget measurement that cannot leave the required settlement reserve. Preserve the first error, pending SQLite/WAL/journal, partial checkpoints, and failed calls. Do not restart or resubmit automatically.

## Current status

This snapshot is development-only. No new Request, Manifest, authorization, Attempt, server connection, training run, dynamic evidence, acceptance receipt, or result claim exists.
