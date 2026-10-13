# N2 M0/M1 Engineering Note (Draft)

Date: 2026-10-13 Asia/Shanghai

This note records local engineering preparation against M0/M1 in `research-plans/ch2-disaster-relief-reuse-execution-v1/refine-logs/EXPERIMENT_PLAN-20261011.md` section 8. It is a new N2 civilian world-model draft using the old stage names. It is not a frozen research contract, a stage promotion, or authorization for trajectory collection, model training, prediction evaluation, or server work.

## Inherited M0/M1 Baseline

The reviewed civilian graph-v2 implementation already supplies the M0 schema, explicit units, synthetic chapter-one handoff, input validation, M1 minute-stepped public/private environment, C0/C1 policies, event traces, and independent conservation/task recomputation. Its `REVIEW.md` records a completed prior engineering acceptance. For this preparation, only 27 targeted local regressions were rerun: chapter-one handoff (2), environment/schema (10), independent audit (10), and step/C0/C1/NOOP (5); all passed. The broader historical acceptance was not repeated.

The N2 runtime must start from new civilian trajectories and labels. The existing graph-v2 registered train/development/heldout scenarios are not used as new consequence-model training data. The W7 military action-consequence package is code reference only: no weights, checkpoints, cached windows, labels, scenario tapes, or evaluation rows are copied or treated as civilian evidence.

## Reuse Map

| Concern | Civilian source | N2 disposition |
|---|---|---|
| Scenario schema, units, field rejection | `development/ch2_disaster_relief_graph_v2/scenario_schema.py` | Reuse contract and validation implementation; N2 synthetic schema additions require explicit fields and units. |
| Initial assignment handoff | `chapter1_adapter.py`, `fixtures/control.json` | Reuse adapter and synthetic fixture as engineering input only; not a real chapter-one output. |
| Public state and internal truth | `relief_env.py` | Reuse `public_observation()`, step lifecycle, event tape, depot/cargo/task state, and delayed report behavior. |
| C1 prefix and dynamic dispatch catalog | `baselines.py`, `relief_env.py` | Reuse deterministic C1 and `candidates()` stable IDs plus explicit `NOOP`; each decision catalog is recomputed from current public state. |
| Independent labels and conservation | `independent_audit.py` | Reuse event replay and task/stock/energy accounting as the authoritative source for future civilian targets. Exact N2 target mapping remains open. |
| Snapshot/candidate identity | `stable_identity.py` | Reuse public observation and catalog digests; extend an N2 branch identity with source prefix, absolute time, disturbance tape/RNG identity, private state and pending reports. |
| Consequence feature/candidate patterns | W7 `candidate_keys.py`, `consequence_contract.py`, `consequence_model.py` | Reimplement/adapt only generic masked-loss, candidate identity and pair-weighted ranking patterns. W7 fixed 4-platform/6-task/25-action layouts and per-task reshape are incompatible with civilian dynamic counts. |
| Collection and strict resume patterns | W7 `consequence_collection.py`, `consequence_training.py` | Technical reference only. New collector/model/data identities and civilian state serialization are required; W7 native pickle is not a production format contract. |

Source digests for the reviewed contracts, simulator, fixture, regression tests, and W7 technical references are in `SOURCE_HASHES.json`.

## New N2 Contract Gaps

These are engineering requirements to close before any collection identity is frozen. They do not change M0/M1 definitions by themselves.

1. **Public-prefix isolation.** For two scenario copies differing only in undiscovered order attributes/IDs/count or an unreported failure/stock-loss event, public observation bytes, candidate order/IDs, graph actor-input tensor bytes, and candidate legality must be identical. Hidden entity count must not leak through padding, IDs, or shape. The probe covers reset state only, not every later report boundary or a downstream world-model mask.
2. **Snapshot completeness.** An N2 snapshot must bind absolute time, public prefix, scenario/event tape, internal task phase, platform energy/position, stock and cargo, and pending reports with scheduled arrival times. The current civilian environment/C0/C1 path has no RNG calls (`rng=none`); exogenous events are a deterministic scenario tape. If future sampling or continuation adds RNG, the exact stream state/key must join the snapshot identity and restoration checks. A restored branch must match the captured private/public state and candidate catalog, and candidate runs must not mutate their source or sibling snapshots.
3. **Dynamic action binding.** Candidate targets must join to the prediction and replay record through stable candidate IDs, never a fixed ordinal. The catalog is variable-size and ends with explicit `NOOP`. Every output needs an unknown/validity mask; NOOP receives global consequences even though it has no task ID. Empty support, NOOP-only windows, censored targets and invalid heads must remain explicit.
4. **Task-head mapping.** Civilian target heads must be keyed by current task identity, not an old fixed 6-task reshape. Exact binary/continuous targets, censoring rules, and cross-task externality definition remain to be resolved against the approved N2 contract before training.
5. **C1 branch continuation.** The planned checkpoints `t=8,16,24,32` and continuation through 30 minutes or true terminal are not implemented here. Existing graph-v2 terminal behavior follows the scenario horizon; a bounded continuation endpoint must be represented as censoring, not silently marked terminal. C1 continuation needs its own fixed, deterministic continuation identity.
6. **Recovery identity.** No N2 training recovery was run. A future checkpoint must include model and optimizer state, RNG state, scheduler/config, code and data hashes, and the exact next-update invariant; no old military weight or optimizer state is a substitute.

## Local Probe Evidence

`test_branch_snapshot_contract.py` uses the synthetic `control.json` fixture and existing civilian APIs. It is an engineering object-snapshot serialization probe, not a collection snapshot acceptance: it pickles and restores the whole in-memory `ReliefEnv`, but defines no production snapshot API/manifest and does not test model checkpoint, replay, RNG or resume behavior. It does not retain branch outcomes as research data.

The probe found the unmodified C1 control fixture is genuinely NOOP-only at `t=8`. That is a valid no-op window, not a test failure to be repaired by changing the fixture. A separately named synthetic opportunity fixture is held at NOOP for eight minutes, with a pending unreported failure, only to exercise divergent legal-dispatch and NOOP branches. It is not represented as a deterministic C1 prefix or research trajectory. Both cases are retained in the final probe.

The probe uses Python `pickle` only for a local whole-object pickle serialize/restore and branch-isolation check over the in-memory `ReliefEnv`; this does not approve pickle as a durable N2 snapshot format. Python pickle round trips may reserialize to different memoization bytes, so restoration is checked by environment state equality and original payload identity, not by re-pickled byte equality.

## Status

- M0/M1 legacy civilian regression subset: 27/27 passed locally.
- N2 public leakage, hidden entity count/ID, dynamic catalog, and branch snapshot engineering probe: 4/4 local checks passed; independently rerun by reviewer on 2026-10-13 (4/4).
- Stage contract status: draft, not frozen.
- Research trajectory collection, world-model training, prediction, server job, G/G-WM smoke: not started.
- No new N2 research data or checkpoint has been created.

Before any later research data collection, freeze and hash the train/development/confirmation parent split; the C1 prefix and `t=8,16,24,32` window rules; candidate-set and NOOP branch rules; the 30-minute continuation and terminal/censor semantics; every civilian target and validity mask; task-level dynamic target joins and cross-task externality; model/loss/reduction/seed/update settings (including whether the historical 40-epoch, batch-8 setting applies); recovery identity; measured stage budgets; and the prediction-gate metrics, thresholds and stop rule. Gate thresholds must be fixed before any confirmation outputs are read. None of these unresolved contracts is passed by the M0/M1 probes.
