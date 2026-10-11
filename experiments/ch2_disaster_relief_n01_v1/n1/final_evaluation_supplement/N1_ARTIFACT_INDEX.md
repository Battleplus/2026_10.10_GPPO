# N01 GitHub Archive Supplement Candidate

Status: prepared release payload; not published. Candidate archive review status is bound by the companion `N01_GITHUB_ARCHIVE_CANDIDATE_MANIFEST.json`.

This supplement binds to evaluation identity `ch2-disaster-relief-n01-full-evaluation-r1-20261011` with package identity SHA-256 `3667872dc04bcabbc6c5bbe77cabf169e8344c5e8cb337376c164a24c5d9bdb6`. Its frozen static plan has canonical SHA-256 `84e37c9816ba27aa780d07ddf31b19fe4609977532825f19a8d7976918cfd78d`. The self-contained deployment archive is `evidence/n01_full_evaluation_r1_identity_3667872d.tar.gz`, SHA-256 `329c30853c380290d13710236809ab085af85b7bc8f697e300febaaa56c831a1`; its 540-file content manifest is beside it.

## Contents

- `source/`: executable evaluator, reused implementation, preregistered protocol, all 350 scenario inputs, registry, six fixed checkpoints, runtime specification, stage budget, guardian, systemd templates, and carry-forward cost evidence. It excludes Python bytecode caches, historical diagnostics, and the obsolete deployment manifest. No secrets are included.
- `reports/N1_DEVELOPMENT_AND_ACCEPTANCE_REPORT.md`: records completed N0 and 100-sample engineering acceptance, and states the 2,800-episode evaluation was not run.
- `reports/N1_FULL_RUNNER_READINESS.md` and `reports/N1_FULL_EVALUATION_BUDGET_PROPOSAL.md`: local static readiness and proposed resource envelope.
- `reports/N01_FINAL_INDEPENDENT_REVIEW_20261012.md` and its binding JSON: independent review decision is local package PASS, target execution NOT READY. That report reviews the frozen local package; it does not itself certify this assembled GitHub candidate. The separate archive review outcome is recorded by the companion manifest.
- `reports/n0_mechanism_source_review_20261011.md`, `n0_replay_20261011.json`, and `sample_replay_20261011.json`: existing N0 mechanism and sample replay evidence.
- `evidence/n01_full_evaluation_preflight_plan_final_r12.json`: regenerated local static plan; its byte-level hash is recorded in the deployment archive manifest.
- `evidence/n01_review_independent_plan.json` and `n01_reviewer_final_plan.json`: plan artifacts, not evaluation results.
- `evidence/N1_BUDGET_ADDENDUM_MANIFEST.json`: frozen identity and scope record.

## Verified State

- Local static preflight: passed; 350 scenarios, 6 checkpoints, 2,800 unique run keys (2,240 heldout and 560 development).
- Full 2,800-episode evaluation and training: not executed. No N1 results, analysis, or result exports are claimed.
- Target deployment and current systemd/cgroup readback: not verified. The independent review records target readiness as NOT READY.
- Latest read-only SSH attempts on 2026-10-12 timed out at TCP connect to `172.17.27.173:22`; no remote command started. The 2026-10-11 authentication failure is historical, as clarified in the candidate readiness report.
- Budget approval: absent; the package budget remains proposed. This supplement does not authorize a run.
- Archive integrity: the deployment tarball's full 540-file set and SHA-256 values match its sidecar manifest and the local frozen identity. The assembled candidate archive's hash and independent review outcome are recorded in its companion manifest.

## Review Gate

Before publication, confirm that the companion manifest binds the exact archive hash and an independent archive review report, verify the report's scope statements, and preserve the GitHub repository's existing staged work. A publication decision is separate from target execution approval. The candidate must continue to state that the 2,800-episode evaluation is pending.
