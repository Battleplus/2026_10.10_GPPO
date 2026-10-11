# N1 full evaluation budget proposal

Status: proposed for independent review; not approved; no execution authorization  
Proposed evaluation identity: `ch2-disaster-relief-n01-full-evaluation-r1-20261011`

## Scope

Run each of the five registered conditions over all 70 registered parents using eight fixed policies, for 2,800 total episodes. The conditions are `original`, `scale_8x12`, `scale_12x18`, `carrier_competition`, and `stock_competition`. Each condition contains 56 heldout and 14 development parents. The eight policies are C0, C1, and the six frozen learned checkpoints (L0/L1 x seeds 8201/8202/8203). No training or model updates are in scope. The 100-episode L1-8201 cost diagnostic remains excluded.

The proposed run must first verify all six checkpoint hashes, all 350 scenario files and their registry identities, the five-condition/70-parent counts, and the evaluator identity against the bound manifest. It must produce one result per (condition, parent, policy), plus an independent audit for each trajectory. Abort before evaluation if any identity, count, audit, or budget gate fails.

## Proposed resource ceilings

These are new-identity stage limits, in seconds, proposed for review. They are not current authorization.

| Stage | Wall cap | CPU cap |
| --- | ---: | ---: |
| Admission and input verification | 120 | 60 |
| Full 2,800-episode evaluation | 5,400 | 4,500 |
| Export and independent output verification | 300 | 180 |
| Shutdown and process-tree verification | 120 | 60 |
| Maximum sum of proposed stage caps | 5,940 | 4,800 |

The historical 173.079052 wall / 124.840999 CPU seconds remain charged to project cumulative use, but are not charged to this new identity's stage limits. The 5,400/4,500 evaluation allowance exceeds the present 28x estimate (1,511.543472/1,373.106959) and the maximum-single-episode extrapolation (3,248.844/2,642.015). These projections are planning evidence only. The guardian must enforce the proposed stage caps and the approved cumulative project budget; a cap breach terminates the run and preserves the failed receipt.

## Required outputs and analysis

- Episode-level results with condition, split, parent ID, policy, checkpoint/seed where applicable, metrics, timings, and audit status.
- Coverage assertions proving exactly 2,800 unique condition-parent-policy rows, split as 2,240 heldout and 560 development rows.
- Separate summaries by condition and by heldout/development split. Never pool development rows into a heldout claim.
- Paired comparisons on matched parent scenarios, with per-seed direction for learned policies, uncertainty intervals, and declared comparison scope.
- Worst-10 cases per primary metric/contrast, with IDs and auditable case-level evidence.
- Independent audit totals, checkpoint barrier, input/output hashes, resource receipts, and process-tree shutdown evidence.

## Approval gates

1. Independent reviewer accepts this proposal, the scope correction, the addendum manifest, and the runner implementation/readiness report.
2. A new evaluation identity is registered with these exact stage ceilings and immutable input hashes.
3. An authorized budget owner approves the new identity and any cumulative project budget required by the host.
4. The runner passes preflight, including full 350-scenario and six-checkpoint verification, before any evaluation episode starts.

Until all gates are satisfied, this proposal authorizes no server evaluation, training, N2, or N3 work.
