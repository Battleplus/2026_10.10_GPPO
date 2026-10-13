# N2 Collection and Critic-Only Protocol Draft

**Status:** Draft local engineering protocol. This document is not authorization for formal research collection, policy comparison, confirmation, or server execution. Local synthetic implementation and engineering smoke are in scope.

**Baseline:** `research-plans/ch2-disaster-relief-reuse-execution-v1/refine-logs/EXPERIMENT_PLAN-20261011.md`, especially sections 5-10. Current civilian source references supplied for this draft are `development/ch2_disaster_relief_graph_v2/scenario_schema.py`, `relief_env.py`, `baselines.py`, `independent_audit.py`, `stable_identity.py`, and `ppo_trainer.py`. Exact source revision and file digests must be recorded before execution.

## Scope and comparison

The proposed research question is whether a frozen action-consequence model adds value through the critic, beyond the same graph policy and critic capacity without usable model features. It is a proposal to test, not an expected positive result. The planned comparison is L2 (L1 plus the frozen model's critic-only features) against L1 (the same actor, policy-data rules, and update budget, with that feature lane masked). C0/C1 remain scenario and rule controls; they are not substitutes for L1.

Use the civilian ReliefEnv and source schemas only. Do not load or derive N2 targets, splits, normalizers, candidate layouts, thresholds, or budgets from W7 military weights, labels, tapes, or fixed layouts. The proposed 3-UAV/1-helicopter, 2-inspection/2-known-delivery/2-latent-task composition is a synthetic fixture proposal only; it is not a research scenario specification. This N2 stage is an exploratory prediction gate followed, only on a pass, by a bounded synthetic G/G-WM engineering smoke. It is not an N3 policy comparison, an independent confirmation study, or an L2 efficacy claim.

## Collection unit and paired branches

The parent scenario is the split and pairing unit. At each approved decision window, freeze one branch snapshot and record its identity, schema/source identity, scenario and event-tape identity, physical time, complete simulator state, pending reports, public observation bytes, and dynamic public candidate-catalog identity. Snapshot encoding must be versioned, JSON-compatible, and digestible; pickle round trips are not a collection format. Restore must reject mismatched source/schema, tape, snapshot digest, public observation, or candidate catalog.

Use decision windows at 8, 16, 24, and 32 physical minutes. These are fixed for this stage. At each window, enumerate the legal public candidate IDs in that snapshot, including NOOP where the public catalog exposes it. Run one paired reference branch using C1 from the snapshot. For each candidate, run one branch that forces that candidate for exactly the first action and then follows the same versioned public C1 rule. Candidate and reference branches use the same exogenous event tape and event identities; C1 sees only information available to it at each step and cannot inspect future events or hidden task state. Candidate results are joined by stable scenario, window, task, and candidate IDs, never by array position.

Continue each branch for at most 30 physical minutes from its snapshot time or until a true episode terminal, whichever occurs first. Record the actual stop time and whether it is a true terminal or a nonterminal horizon limit. A branch that reaches the 30-minute limit without termination is right-censored; do not convert that limit into success or failure, and do not consume events after the limit. For the paired global-return delta, stop both branches at the earlier of the first terminal time or the 30-minute limit; report each branch's duration and terminal/censor status separately.

The current deterministic environment path is recorded as `rng=none`. If any stochastic component is introduced, its keyed random stream/state must be captured and paired so candidate count or action order cannot change exogenous draws. The event tape, environment implementation, C1 implementation, snapshot version, and candidate catalog must be bound in the collection identity.

## Records and target semantics

Store branch source/config identity, parent and split IDs, window and snapshot digest, event-tape digest, candidate and C1 IDs, actions, transitions, reward series, raw event slices, public task specs and timestamps, terminal/censor reason, and resource counters. Keep private label-audit evidence separate from model inputs and public exports. Hidden task identities may be used only inside the fixed scalar externality label audit; they never enter public features, task axes, masks, or exported observation records.

The consequence model uses the following complete head contract. Candidate axes join by stable candidate ID; per-task axes use only task IDs present in the window's public observation. Head names and order are serialized and validated before target assembly.

| Family and ordered heads | Target and units | Validity/censor rule | Loss |
|---|---|---|---|
| Global binary: `reward_improved`, `energy_saved` | Indicators for candidate-minus-C1 cumulative reward `> 0` and energy-use delta `< 0` | Both are valid over the paired common horizon, including NOOP; zero-delta is a valid negative | Masked BCE-with-logits, element mean |
| Global continuous: `cumulative_reward_delta`, `energy_use_delta`, `other_task_on_time_count_delta`, `inspection_report_count_delta` | Undiscounted reward units; synthetic energy units; scenario-wide count differences | First two always valid; task/report count is valid only if every included outcome is known in both branches; otherwise mask and retain censor audit counts/reasons | Masked Huber, element mean |
| Per-task binary: `service_completed_by_horizon`, `service_on_time`, `deadline_missed`, `report_received_by_deadline` | Completion by observed branch end; final on-time service; final missed deadline; inspection report received by task deadline | Completion-by-horizon is always observable for snapshot-public tasks. Final on-time/missed is valid on completion, deadline passage, or true terminal; otherwise right-censored. Report head applies to inspections, valid when report arrives or deadline/true terminal resolves it. Non-inspection report head is masked. | Masked BCE-with-logits, element mean |
| Per-task continuous: `completion_elapsed_fraction`, `report_delay_fraction` | Elapsed minutes from window start to completion divided by 30; report receipt minus generation minutes divided by 30 | Valid only when the corresponding event is observed by branch end; otherwise masked | Masked Huber, element mean |

Task completion and report receipt are separate events. `service_completed_by_horizon` can be false and valid while final on-time status remains unknown. NOOP retains all global supervision and masks both per-task families because it has no target task. Other-task externality is the fixed scalar difference in on-time service count across the full scenario task population excluding the selected target; it is label-only and valid only when all included task outcomes are known in both branches. The audit records denominator and censor reasons without exposing hidden IDs to the model.

The implemented engineering loss sums the four masked family means and the original equal-weight `pair_weighted` ranking loss on cumulative reward within each `(parent_id, window_time)`. No family weighting, target standardization, or outcome-dependent filtering is applied. Ties are excluded from ranking only; global regression/binary supervision remains. These heads are the planned N2 training target, while the development gate below uses only global reward-increment ranking as its trigger metric and reports all other head errors and coverage descriptively.

## Splits and leakage controls

Use the current civilian registered parent split: 56 training parents and 14 development parents, with eight/two per each of the seven existing mechanism strata (control, failure, energy_change, stock_loss, report_delay, combined, external_commitment). The 56 heldout parents have already been viewed in the earlier civilian study; keep them closed and do not call them independent confirmation for N2. The seven checked-in fixtures are regression stimuli, not independent gate parents. All windows, candidates, pairs, repeats, and tape variants from a parent remain in that parent's split.

Within each partition, preserve all failures, delays, no-op-only windows, no-opportunities, unsolved cases, and censored outcomes under their validity masks. Do not filter cases based on observed model results. Report parent-scenario macro averages and window-weighted results separately, with seed-wise paired differences and parent-scenario uncertainty; three training seeds do not make scenarios independent.

## Training proposal

Use matched model-training seeds **8201, 8202, and 8203**, **40 world-model epochs per seed**, and **batch size 8 parent-window examples**. One example is `(parent_id, window_time)` with its complete dynamic candidate catalog, public task axis, labels, and validity/censor masks; pairwise comparisons remain within that window. With all four windows for each of 56 training parents, this gives 224 examples, 28 optimizer batches per epoch, and 1,120 updates per seed. Record any unavailable window; do not reassign its parent or change the epoch/batch setting. Optimizer implementation and runtime budget are reported from the measured target Linux run.

For the proposed critic-first path, train the consequence predictor only on the training split with approved targets and masks, then freeze it before policy learning. The policy actor must not consume model outputs or change its candidate-selection rule. Feed model features only to a scalar critic adapter, detached from predictor parameters, and use the same frozen prediction identity through rollout value, bootstrap, GAE, and replay. Aggregate candidate auxiliary values by stable candidate ID and legal mask using detached actor probabilities; never assume a fixed candidate count or array layout. Mask unsupported predictions and NOOP-only auxiliary effects while retaining the same-capacity public critic path. Do not add reward shaping or direct actor features in this protocol.

Match L1 and L2 actor architecture, data rules, policy update budget, and critic adapter capacity; use paired initialization for shared structure. Record total parameters and active feature paths. Any shared actor-critic parameters and their gradient paths must be reported; “critic-only” describes the model feature route, not an assertion that all shared critic gradients leave the actor representation unchanged. Exact L1/L2 update counts and allowable capacity differences are unresolved.

## Throughput and resource budget

Do not reuse historical wall-time, update-count, or hardware budgets. First measure the actual approved pipeline on a bounded engineering workload and record its exact source/config identity. This draft sets no numeric cap.

For planning, let `W` be the number of collected windows and `C_w` the number of public legal candidate IDs at window `w`, including NOOP when present. The proposed branch count is one C1 reference plus one forced-action branch per candidate per window. Measure actual simulator transitions and physical duration per branch rather than estimating from candidate count alone. Once the batch unit is frozen, the nominal update count implied by the candidate training setting is `3 seeds × 40 epochs × ceil(training examples / 8)` per model stage; the number of examples and stage mapping are unresolved, so this is not a budget estimate.

The preflight and every later run must record environment steps, candidate branches, valid windows/targets, model and policy forwards, optimizer updates, checkpoint reads/writes and bytes, prediction/gate calls, analysis/export writes, CPU time, wall time, peak RSS, peak disk, and failed/pending work. Report throughput for transitions/second, candidate branches/second, valid windows/second, updates/second, and prediction rows/second, with workload identity and timing boundaries. Use measured distributions and an explicit reserve to derive caps for collection, training, recovery, gate evaluation, and export.

All numeric resource ceilings, throughput acceptance rates, scenario and branch counts, memory/storage limits, and failure reserve remain **UNRESOLVED**. The source plan requires these to be frozen from measured M4 costs before formal execution. Stop on a cap or contract failure, preserve the first error and pending state, and settle actual work; do not enlarge a budget after seeing an unfavorable result.

## Offline prediction gate

Use the development-only rule in `N2_GATE_RECOMMENDATION.md`; heldout remains closed and no independent confirmation set is introduced. For each seed, compute pair-weighted logistic ranking loss over valid unequal-outcome global candidate pairs, with zero score difference baseline `ln(2)`. Macro-average within supported parent, then macro-average over the fixed 14-parent denominator; parents without pair support contribute zero improvement only to the aggregate and remain explicitly `no_pair_support`. Report pairwise increment MAE against zero and candidate-level increment MAE against a train-only mean, plus coverage, unknown, and censor counts by target family, stratum, window, and NOOP status.

- Within-window ordering of valid candidate consequences, joined by candidate ID.
- Prediction error for predeclared transparent candidate-pair increments against paired branch outcomes.
- Coverage and unknown/censor rates by target family, task class, window, and NOOP status.
- Descriptive error and coverage for every global and per-task head, including NOOP, censor reason, mechanism stratum, and decision window.
- Incremental environment, training, recovery, prediction, CPU/wall, memory, and storage accounting versus the measured workload baseline.

Gate eligibility requires at least 7/14 development parents with a valid unequal-outcome pair and at least one supported parent in every mechanism stratum. Trigger only if all three seed-specific parent-macro improvements over `ln(2)` are positive and the lower end of the two-sided 95% parent-cluster bootstrap interval for the equal-seed mean improvement exceeds zero (10,000 resamples, resampling parent IDs with all nested windows and pairs; same draw across seeds). A pass permits only the bounded synthetic G/G-WM engineering smoke. A failure or insufficient support ends this exploratory screen without threshold changes or sample deletion. The gate is not a policy-efficacy test or a research claim.

## Freeze and execution gates

Before collection, the owner and stage approver must freeze: source and schema identities; scenario distribution and counts; split manifest; decision windows; candidate and C1 identities; snapshot/restore contract; target heads, units, masks, NOOP semantics, and censoring; paired-return horizon; model and policy configs; seed values; batch and epoch semantics; optimizer/update budgets; prediction gate; resource caps; and failure/resume/export rules. Hash the frozen config, source files, split manifest, and event-tape generator. Any change creates a new run identity.

Proceed only after the relevant engineering acceptance cases pass, followed by measured end-to-end M4 recovery, prediction, accounting, and export checks on the approved runtime. Local synthetic probes are engineering evidence only. Passing them does not authorize research collection, training, prediction acceptance, server work, or stage advancement.

| Gate | Required decision/evidence | Current status |
|---|---|---|
| Contract freeze | Current registered parent split, target masks, windows, source identity, C1, common horizon, loss/reduction, seeds, epoch and batch semantics | Defined for the exploratory development gate; implementation evidence remains under review |
| Cost preflight | Actual call counts and CPU/wall/RSS/disk distributions on target Linux, followed by caps and reserve | Numeric budget remains open pending target-Linux measurement |
| Training freeze | 3 seeds × 40 WM epochs × batch-8 parent-window examples | Fixed as stated; actual run costs not yet measured |
| Prediction gate | Coverage, `ln(2)` ranking baseline, three-seed positive improvements, 14-parent bootstrap lower bound >0 | Defined in `N2_GATE_RECOMMENDATION.md`; run only after the declared 40-epoch models and eligible labels exist |
| Stage approval | Any later formal policy comparison or confirmation | Outside this N2 objective; no N3/N4 work authorized here |

## Open decisions

The measured target-Linux resource and failure-reserve caps remain open. The remaining evidence gap is actual cost measurement and independent review of the bounded local synthetic G/G-WM smoke. This draft does not require a new confirmation split, N3 policy comparison, or N4 independent study.
