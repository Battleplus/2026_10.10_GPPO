# Pilot and Comparison Plan

**Status:** DRAFT. No authorization, token, attempt, deployment, training run, or confirmation evaluation has been created or started.

## Question

On the registered civilian disaster-relief allocation workload, which of three tested approaches gives the best priority-weighted on-time delivery performance, and what tradeoffs appear on inspection, unmet demand, energy, and reassignment outcomes?

The study is intended to find a useful approach for this workload. It is not a factorial test of Graph PPO and world-model components, so it cannot establish that the two components work synergistically.

## Comparison Arms

| Arm | Method | Training | Seeds / final checkpoints |
|---|---|---:|---:|
| C1 | Transparent rule-based reallocation baseline | None | No learner seed or checkpoint |
| GPPO | Existing Graph PPO learner | Yes | 8201, 8202, 8203 / 3 checkpoints |
| Dreamer | Pinned open-source model-based RL learner | Yes | 8201, 8202, 8203 / 3 checkpoints |

Dreamer source is [NM512/r2dreamer](https://github.com/NM512/r2dreamer), pinned to commit `546e4fab8146ea4b14e1d7726bbc1a8a1d50322f`, under the MIT license, with `rep_loss=dreamer`. Provenance is recorded in [UPSTREAM_SOURCE_AUDIT.md](../upstream_audit/UPSTREAM_SOURCE_AUDIT.md) and [UPSTREAM_PROVENANCE.json](../upstream_audit/UPSTREAM_PROVENANCE.json).

The upstream pin supplies the RSSM, reward and continuation prediction, vector-observation path, and actor/value components. Dynamic mask-head behavior, real/imagined action masking, and time-discount integration are project overlay work in `integration/dreamer_relief.py`, not native upstream capabilities. This plan does not attribute candidate-consequence multi-head prediction or candidate-ranking supervision to upstream Dreamer. Dreamer-versus-GPPO compares complete learning systems; it does not isolate the causal contribution of a world model.

## Scenarios and Splits

The frozen registry has 126 parent scenarios across two balanced mechanisms: carrier competition and stock constraint. Parent scenarios are split once and remain in only one partition:

| Split | Parents | Carrier competition | Stock constraint |
|---|---:|---:|---:|
| Train | 56 | 28 | 28 |
| Development | 14 | 7 | 7 |
| Heldout confirmation | 56 | 28 | 28 |

Training and development parents are not confirmation evidence. No old military-scene data or old world-model weights are confirmation inputs.

## Training Budget

The limit is **128 training episodes per learner seed**, not a cap over training and evaluation combined. There are six learning paths: two learners times three seeds, for a maximum of **768 training episodes** in total. The first **8 pilot training episodes per learner seed** count toward that seed's 128-episode limit. C1 has no training episodes.

Development-evaluation parents are fixed at 14, but the number of evaluation episodes and keys is not frozen. Freeze those keys before the learning runs after measuring the target Linux runtime and resource accounting. Do not infer a development evaluation count from the training cap.

## Heldout Release Barrier

The heldout set contains 56 parents. For each parent, run one C1 trajectory, one trajectory for each of the three GPPO seed checkpoints, and one for each of the three Dreamer seed checkpoints:

`56 * (1 + 3 + 3) = 392` confirmation trajectories.

Keep the confirmation data sealed until all six final learner checkpoints exist and pass hash verification, metadata identity checks, and strict restore validation. Metadata must bind method, seed, configuration, source pin, and training-data identity. Only then may the fixed 392 heldout keys be evaluated.

## Outcomes and Analysis

The primary outcome is `weighted_on_time_delivery_rate`: the sum of priorities for delivered orders completed on time divided by the sum of priorities for all delivery orders in the episode. The environment returns `null` when there are no delivery orders; do not impute a value.

The registered secondary fields are:

- `inspection_completion_rate`
- `inspection_on_time_rate`
- `delivered_orders`
- `late_orders`
- `unmet_orders`
- `undiscovered_orders`
- `energy_used`
- `reassignments` (number of tasks that were reassigned, not the total number of reassignment events)
- `new_assignments`

Score real task outcomes for evaluation and audit only; do not feed them to the actor or use hidden task outcomes as training-time information. Do not add report-timeliness or candidate-ranking outcomes that are not part of the verified civilian evaluation record.

Make three comparisons: GPPO versus C1, Dreamer versus C1, and Dreamer versus GPPO. Compute paired differences on the same heldout parents. The parent scenario is the sampling unit. For a method-level estimate, aggregate its three learner seeds within each parent; also report seed-specific results. Report raw parent-level values and parent-paired bootstrap 95% intervals. Keep empty-order primary values as null and document their handling.

The two learned methods are different complete systems. A higher Dreamer score than GPPO would be evidence only for this workload and implementation comparison, not a component-level world-model effect or Graph-GPPO/world-model synergy.

## Resource Freeze and Stop Conditions

The full resource request is **NOT FROZEN**. Wall-time, CPU-time, RSS, storage, and development-evaluation episode limits remain unset. First measure the target Linux runtime and systemd/cgroup accounting with a bounded pilot, then record training, evaluation, checkpoint I/O, and export costs separately. Freeze the full request before any authorized study run. Pilot training episodes remain included in the per-seed 128-episode caps.

If source identity, scenario split, checkpoint metadata, strict restore, or heldout sealing fails, stop before opening confirmation results. If target resource measurement does not support the proposed limits, revise the request before seeking authorization; do not silently expand the episode cap.

## Claim Boundary

This plan compares the three registered methods on one civilian workload. It can identify a useful tested method if the paired results support that conclusion. It cannot establish a general graph-learning advantage, a causal world-model contribution, or a Graph PPO plus world-model synergy effect. No result exists until the training, checkpoint barrier, and heldout evaluation have actually completed.
