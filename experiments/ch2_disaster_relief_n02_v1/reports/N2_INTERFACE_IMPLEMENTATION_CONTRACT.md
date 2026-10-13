# N2 Interface Implementation Contract (Draft)

Status: engineering interface draft only. This document does not freeze the research protocol or authorize trajectory collection, training, prediction evaluation, or server work.

## Verified Base

The inherited civilian M0/M1 implementation and its targeted regression subset are verified locally: 27/27 passed. The local N2 preparation probe is 4/4 passed and independently rerun against the final source bytes. These checks establish only the listed simulator and preparation behavior; they do not constitute N2 model or collection acceptance.

## Required Interfaces Before Collection

1. **Public observation and schema.** Define a versioned, serialized public observation schema with stable units and explicit known/unknown fields. Public observations and graph inputs must not expose hidden entity attributes, IDs, counts, unrevealed failures, or stock changes. Test invariance at report boundaries as well as reset.
2. **Dynamic candidates and task targets.** At each public decision, emit a variable-length catalog with stable candidate IDs and explicit `NOOP`. Branch from the observation immediately before the chosen candidate at `t=8,16,24,32`, force that candidate for one step, then follow the same public C1 rule for at most 30 physical minutes or true episode termination. Pair each branch with the C1 reference under the same event tape and public continuation. Bind predictions/replay by candidate ID. Per-task heads bind only publicly known task IDs; hidden orders must not change head count, IDs or tensor shape. Keep target-task labels separate from other-task externality aggregates. Every head carries validity and censor masks. A `NOOP` target-task head is unknown while its global consequence label remains valid.
3. **Snapshot and branch identity.** Implement a versioned local snapshot API, separate from Python pickle. Bind source prefix, absolute time, public observation, private environment state, scenario/event-tape identity, pending reports and scheduled times, and candidate catalog identity. Current civilian C0/C1 has no RNG calls; if stochastic sampling is added, record exact RNG algorithm/state. Restore checks compare state, public bytes and catalog, then prove sibling isolation.
4. **World-model and critic boundary.** Specify dynamic task/candidate axes, prediction heads, masks, reductions and losses. Preserve original `pair_weighted` ranking reduction (each valid preference pair has equal weight; do not substitute equal-window weighting), including ties, empty support and grouped comparisons. For critic-only use, freeze/detach WM parameters and features; actor logits must be invariant to WM output, while the critic may consume a detached candidate-probability-weighted auxiliary value. Rollout, bootstrap, GAE and replay must use the same value semantics. Reject hidden-count leakage and fixed 4/6/25 legacy layouts.
5. **Collection and resume.** A local engineering branch record binds scenario and code hashes, pre-action window time, C1 prefix, candidate catalog, forced branch action, continuation rule, target horizon and terminal/censor status. A resumable training checkpoint binds model, optimizer, scheduler/config, RNG, data identity and next-update index; prove exact next-update equivalence before use.

## Acceptance Gates and Open Decisions

Before formal collection, freeze train/development/confirmation parent splits; target definitions and masks; model/loss/seed/update budget; resume identity; and prediction-gate metrics, thresholds and stop rule. The engineering branch semantics above are executable local test rules, not authorization to collect research labels. Exercise each interface with focused tests, including NOOP-only, pending-report restoration, dynamic public task counts, hidden-state invariance, critic-only detach and next-update resume equivalence. No old W7 weights, labels, datasets or fixed-layout assumptions are acceptable substitutes.

## Current Stage Boundary

M0/M1 reuse is locally verified as an engineering baseline. N2 contract and implementation remain draft/open. No N2 research trajectories, labels, trained model, predictions, server execution or G/G-WM smoke have been produced.
