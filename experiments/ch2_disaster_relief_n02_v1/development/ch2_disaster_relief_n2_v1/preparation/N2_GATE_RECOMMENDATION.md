# N2 Development Prediction Gate Recommendation

## Purpose and limit

This is a development-only signal screen for deciding whether to proceed to a small synthetic G/G-WM engineering smoke. It is not a policy efficacy test, protected-task risk certification, research claim, or authorization for formal collection, training, prediction evaluation, or server work. A failed or indeterminate screen means this development packet does not support advancing to that smoke; it does not establish that a world model is generally ineffective.

## Parent grouping and fixed inputs

Use the existing civilian registered parent split: 56 training parents and 14 development parents, stratified across the seven existing mechanisms: control, failure, energy change, stock loss, report delay, combined disturbances, and external commitment. The allocation is eight training parents and two development parents per mechanism. Fit the WM and any normalizers or constant baselines on the 56 training parents only. Use the 14 development parents once for this gate.

The seven checked-in fixture JSON files remain regression stimuli, not seven independent development parents. They share the fixture design, and the combined fixture overlaps the single-mechanism cases. The existing 56 heldout parents have already been viewed in the earlier civilian study. Keep them closed for this N2 stage and identify them as historically inspected exploratory data; do not relabel them as a fresh independent confirmation set.

The parent scenario ID is the split and inference cluster. All decision windows, candidate branches, candidate pairs, event variants, and repeated records from a parent remain together. Use one training example as `(parent_id, window_time)` with its complete dynamic candidate catalog, public task axis, targets, and validity/censor masks. Batch size is eight such parent-window examples. Keep the full window together when forming pairwise comparisons. Retain the approved windows 8, 16, 24, and 32 minutes, the 30-minute continuation, seeds 8201/8202/8203, 40 WM epochs, and batch size 8 as fixed settings. With four windows for each of 56 training parents, this is 224 window examples, 28 optimizer batches per epoch, and 1,120 batches per seed; report actual counts if any window is unavailable, without changing the epoch or batch settings.

## Prediction measures

The primary target for this gate is the valid global candidate-minus-C1 consequence increment. Join predictions and outcomes by stable candidate IDs and compare only candidates from the same decision window. Exclude equal-outcome pairs from ranking metrics as ties; retain their count in the report. Keep NOOP in global comparisons when its global label is valid. Do not use unknown, right-censored, or invalid outcomes as zero or failure.

For each seed, calculate the pair-weighted logistic ranking loss over valid unequal-outcome candidate pairs. Its no-signal baseline is `ln(2)`, from predicting zero score difference for every pair. First calculate each development parent's mean loss over its supported windows and pairs, keeping all valid pairs equally weighted within that parent; then calculate the parent-macro improvement `ln(2) - loss` across the fixed 14-parent denominator. This gives each parent equal inference weight while preserving pair-weighting inside each parent.

For parents with no valid unequal-outcome pair, the ranking loss is undefined. Mark them `no_pair_support`, report them in the denominator and coverage table, and assign zero improvement only in the gate aggregate. This is a conservative no-evidence contribution, not an imputed target or a claim that the parent has zero prediction error. Do not remove these parents from the gate denominator.

As descriptive error measures, report pairwise increment MAE against a zero-increment predictor and candidate-level global increment MAE against a constant mean fitted from training parents only. Report counts and coverage for every target family, mechanism stratum, decision window, NOOP status, and censor/unknown reason. These error and coverage summaries do not introduce additional tuned thresholds.

## Trigger rule

The gate is eligible for a decision only if at least seven of the 14 development parents have one or more valid unequal-outcome global candidate pairs, with at least one such parent in each of the seven mechanism strata. Report the full 14-parent denominator and the per-stratum supported-parent counts. If this coverage condition fails, classify the gate as `insufficient_pair_support`; do not search alternate windows or remove difficult cases.

When coverage is sufficient, trigger the next synthetic engineering smoke only if all three seed-specific parent-macro ranking improvements are positive and the lower bound of the two-sided 95% parent-cluster bootstrap interval for the equal-seed mean improvement is greater than zero. Use 10,000 bootstrap resamples of the 14 parent IDs; each draw carries all windows, candidates, and pair records for a sampled parent, including its zero contribution when it has no pair support. Keep the same resampled parent draw aligned across all three seeds, average seeds equally, and publish the seed-specific estimates and directions alongside the interval. Candidate pairs are not independent resampling units.

The trigger uses only development global ranking evidence and the declared coverage rule. Publish the error and coverage summaries even when the trigger passes. The screen says only that the current fixed development sample supports testing the critic-only path in a bounded synthetic smoke; it says nothing about disaster-relief performance, policy safety, external validity, or research readiness. Do not tune targets, thresholds, denominators, splits, or training settings after seeing these results.

## Limitations

There are only 14 development parent clusters, two per mechanism. Bootstrap intervals will be coarse and may have low power; the trigger is a conservative stage screen, not confirmatory inference. The zero contribution for unsupported parents prevents missing-pair parents from disappearing from the aggregate but does not make their ranking estimable. Report the supported-parent count next to every estimate and preserve an `insufficient_pair_support` outcome when the predeclared coverage rule is not met.
