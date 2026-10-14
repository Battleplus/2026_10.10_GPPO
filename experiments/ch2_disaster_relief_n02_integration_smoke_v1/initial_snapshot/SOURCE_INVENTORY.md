# Initial Source Inventory

This is a static inventory for planning. It does not assert that any copied source has passed the new package's acceptance gates.

## Civilian environment and graph PPO

Source root: `development/ch2_disaster_relief_graph_v2/`.

- `relief_env.py`: deterministic public-observation simulator; one `step(action_batch)` executes simultaneous candidate IDs and advances one minute. It builds stable `dispatch:<platform>:<task>` candidates plus `NOOP`, and checks public stock, platform compatibility, task locality, capacity, energy, and duplicate platform/task use.
- `relief_env.py::_step_reward`: existing per-minute reward is `-0.01` per move/service energy unit, `+priority/5` for an on-time confirmed delivery, `+0.1` for a timely received inspection report, and `-0.05` for a task's first reassignment away from its original owner. N2 global utility deltas must sum this unchanged reward over the paired physical window.
- `graph_policy.py` / `ppo_trainer.py`: graph policy and the existing actor/PPO/critic/GAE path are the candidate base. The N2 contract still needs to bind a *complete environment action batch* to the autoregressive policy's exact masked joint probability; a single dispatch-edge probability is not a complete-action probability.
- `baselines.py`: C1 rule baseline and action selection from public observations/candidates.
- `stable_identity.py`: stable observation/catalog identity binding.
- `chapter1_adapter.py`: only normalizes the versioned initial synthetic Chapter 1 assignment; it does not accept arbitrary in-progress state.
- `scenario_schema.py`: declares time in minutes and quantities in kg; validate actual compatible inventories before using any task stratum.

## N2 world model and integration

Source root: `development/ch2_disaster_relief_n2_v1/engineering/`.

- `world_model.py`: multi-head binary/continuous and per-task output, validity masks, ranking/consequence loss, critic-only detached features, and strict checkpoint identity/restore logic are candidates for reuse after the dynamic public task/candidate layout is bound.
- `branching.py`: snapshot/restore, fixed-window branch and paired C1 continuation/label helpers are candidate logic only. Existing helper currently labels itself synthetic engineering data; it cannot be passed off as new real server collection.
- `ppo_integration.py`: integrates the critic-only adapter with the civilian `PPOTrainer` restore contract. Exact full-action probability, five global channels, GAE/value consistency, and freeze/no-WM-update conditions require new-package acceptance.
- `n2_linux_runner.py` and `package_n2_linux_acceptance.py`: historical r2 engineering acceptance is not the new experiment service/authorization submission path and does not satisfy new Request identity or target-runtime measurement.

## Explicit exclusions and audit items

- No N1 held-out data or N1/model checkpoints are training inputs.
- No old military data or world-model weights are inputs.
- The N1 16 kg carrier-task feasibility finding rules out copying the old 16 kg variation. The prior 126-row carrier registry (train/dev/heldout) is negative exclusion evidence only: all 16 kg targets were inventory-infeasible despite at least one nominal locality/capability/capacity-compatible platform. None of those targets, labels, or heldout records may be reused as new N2 candidates or feasibility evidence. New parent scenes must be regenerated/selected from publicly documented scenario fields and pass feasibility checks; inventory, locality, capability, capacity, stock, deadlines, and shared-carrier competition all need checking.
- A hand-authored causal case must show one allocation changing another order's later delivery outcome.
- Verify snapshot public-prefix equality, hidden-state exclusion, exogenous event tape identity, label masks, full-action mapping, dynamic candidates, and final stage names against new-source hashes.

## Physical-time and workload ledger to freeze after runtime measurement

The base environment is one minute per transition. If retained, a 60-minute episode is at most 60 transitions and branch start at minute 8/16/24/32 with a 30-minute tail is at most 38/46/54/60 transitions per candidate before episode termination. The task book's 13,680 environment-step bound must be reconciled against the exact collection, branch, policy-training, and evaluation schedule before Request freeze.

The task-book caps remain ceilings, not measured costs: server wall 3,600 s, CPU 1,800 s, RSS 4 GiB, work/export storage 1 GiB each, 384 branches, 8 WM updates, 64 PPO updates, 16/8 training/development episodes, WM forward 2,048 batches/16,384 candidates, transport 600 s wall/120 s client CPU/2 GiB, with at least 120 s wall and 90 s CPU reserved for settlement/export. Target-runtime measurements are pending.
