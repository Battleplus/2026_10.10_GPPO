# N0 execution report

Identity: `ch2-disaster-relief-n01-v1`.

N0 is a completed, frozen evidence node. It contains 448 raw trajectories over 56 parents, 2,752 tasks, 37,295 events, and 26,880 transitions. Six fixed checkpoints and six learning curves were verified against their manifests. Full raw-event replay reproduced the reported metrics with zero trajectory differences. N0 performed zero model forward passes and zero optimizer updates.

The primary parent-macro values are recorded in `n0_summary.json`; the checkpoint and input hash files are authoritative. The independent replay review is included under `n1/engineering_revision/independent_review/` and is cited by the N1 delivery manifest.
