# Upstream RL + World Model Source Audit

Date: 2026-10-13

## Scope and provenance

This is a static source audit for the bounded upstream-engineering P0. It does not claim an experiment, a disaster-relief result, or a successful runtime smoke.

- Selected upstream: `NM512/r2dreamer`, pinned snapshot `546e4fab8146ea4b14e1d7726bbc1a8a1d50322f` at `upstream_r2/r2dreamer-546e4fab8146ea4b14e1d7726bbc1a8a1d50322f`.
- License: MIT, as declared by the pinned repository.
- Legacy comparison: `NM512/dreamerv3-torch`, pinned at `6ef8646d807cd10ce0c88e10a7e943211e7fc44c`. Its README describes the implementation as outdated and points readers to `r2dreamer`.
- Chosen experiment configuration: the upstream DreamerV3 baseline setting `rep_loss=dreamer`, not the R2 representation-loss extension.

## Reusable implementation

The pinned source has an upstream `Dreamer` learner in `dreamer.py`, a sequence replay implementation in `buffer.py`, and its training entry/configuration in `train.py` and `configs/`. The learner's `update(replay)` path samples sequences, computes the world-model and actor/value objectives, takes optimizer/scheduler/scaler steps, and writes recurrent latent state back through the replay update API. The source therefore provides a concrete RL + world-model baseline suitable for an isolated learner smoke and later component-level comparison.

Its configuration supports vector observations with an MLP encoder and discrete actions represented by one-hot categorical actions. The minimal smoke harness is prepared at [upstream_dreamer_smoke.py](../upstream_smoke/upstream_dreamer_smoke.py): it is intended to collect a small Gymnasium CartPole sequence into the upstream `Buffer`, call the real upstream `Dreamer.update` method, and check model and optimizer checkpoint restoration. The harness has **not run yet**.

## Integration limits for the disaster-relief dispatcher

The upstream baseline is not a drop-in implementation of the current dispatcher action contract:

- Its actor samples one categorical action per decision. The relief environment exposes a changing set of stable candidate keys and selects a jointly valid batch, with candidate-order and residual legality constraints. No source path was found that applies this dynamic legality mask to actor logits or imagined actions.
- Its imagination advances the learned RSSM using actor-sampled actions; it cannot query the live simulator for a candidate mask at each imagined state. A future integration must use only masks derived from information available to the policy and must not inject future simulator state.
- Its imagined return uses a fixed horizon discount (`1 - 1 / horizon`). The source does not expose a per-transition physical-duration discount such as `gamma ** dt`, so decisions that consume different simulated time need an explicit, separately tested adaptation.
- The upstream vector observation and discrete action primitives can support a small engineering smoke, but stable candidate identity, multi-assignment constraints, `PublicPrefix` hashing, unknown-label masks, and one-minute physical-time transitions remain project-specific contracts.

Consequently, a CartPole smoke can show that the pinned upstream learner trains and restores in the chosen runtime. It cannot show that the world model predicts relief-task consequences or that the algorithm improves task allocation.

## Current P0 state

- Static source/configuration audit: complete.
- Isolated Python runtime: Python `3.11.15` installed under the new `runtime` directory.
- CPU PyTorch `2.8.0` installation: first attempt failed before training because the 590.7 MiB wheel exceeded the default 30-second UV HTTP timeout. The original failure is retained. The parent run is making one bounded retry with an increased timeout and no automatic retry loop.
- Neural forward passes: `0`.
- `Dreamer.update` calls: `0`.
- Gymnasium smoke environment steps: `0`.
- Checkpoints or evaluation results: none.
- Formal research, authorization, token, attempt, or server job: not started.

The next evidence needed is a successful dependency install followed by the prepared smoke. If the smoke fails, preserve its first error and repair only this isolated harness/runtime. Do not infer algorithm performance from this P0.
