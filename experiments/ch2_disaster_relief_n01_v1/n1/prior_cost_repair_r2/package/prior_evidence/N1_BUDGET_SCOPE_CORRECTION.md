# N1 budget scope correction addendum

Date: 2026-10-11  
Status: clarification for independent review; no evaluation execution authorized by this note

## Corrected interpretation

The 1,140 wall-second / 720 CPU-second limit is the upper bound for the engineering acceptance phase. It is not a user-specified lifetime budget for the complete N1 evaluation. The earlier `received/n01_evaluation_budget_freeze.json` treated this phase limit as the whole-pilot cap and used that interpretation to stop the 2,800-episode evaluation. Preserve that freeze and its receipts as historical evidence; this addendum corrects the scope interpretation without rewriting them.

The final evaluation scope remains 5 conditions x 70 registered parent scenarios x 8 policies = 2,800 episodes. Each condition has 56 heldout and 14 development parents. Report the two splits separately; do not label all 70 as heldout. The eight policies are C0, C1, L0-8201/8202/8203, and L1-8201/8202/8203. The 100-episode diagnostic is only L1-8201 (20 parents per condition), is excluded from the 2,800 final episodes, and is not evidence for all eight policies.

Historical known use is 173.079052 wall seconds and 124.840999 CPU seconds, including carry-forward and engineering probes. Continue to include it in project cumulative accounting. That charge does not convert the engineering-phase cap into a cap on all future authorized work.

## Estimate and decision

The directly observed 100-sample process used 53.983695 wall seconds and 49.039534 CPU seconds. A conservative 28x scale gives 1,511.543472 wall and 1,373.106959 CPU seconds, before adding historical known use. A separate observed maximum single episode (1.160301 wall / 0.943577 CPU seconds) multiplied by 2,800 is 3,248.844 wall / 2,642.015 CPU seconds. These are planning estimates, not a validated cost bound. They differ because one is a measured whole-process scaling and the other is a per-episode worst-observed extrapolation.

This addendum does not authorize a run. The proposed new evaluation identity and stage budgets in `N1_FULL_EVALUATION_BUDGET_PROPOSAL.md` require independent review and explicit authorization before admission or execution. Do not charge future evaluation to, or alter receipts for, the completed engineering identity.

## Guardian receipt clarification

The original guardian receipt is immutable. Its message `engineering_smoke wall 107.745>108s` formats a precise threshold with zero decimal places. The underlying wall base was 104.536380 seconds and the configured headroom was 3 seconds, so the threshold was 107.536380 seconds; 107.745 exceeded it. This explains the displayed rounded `108`, while preserving the original receipt and the earlier correction note. The receipt supports a wall-overrun kill; its rounded display should not be treated as an exact threshold.

Known cleanup status is limited: the temporary SSH key was removed and the disconnect probe had no residual process. The remote probe evidence directory remains; this addendum does not claim all remote temporary files were removed.

## Bound evidence

The SHA-256 bindings for this addendum are recorded in `N1_BUDGET_ADDENDUM_MANIFEST.json`. They identify the evaluator and manifests examined when preparing this correction. Any changed input requires re-review.
