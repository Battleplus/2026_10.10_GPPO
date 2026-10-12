# Independent review: deploy-only preparation

Reviewed against frozen identity `ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012` and the local preparation report.

- The archive contains 560 release files plus one manifest member; its deterministic archive SHA256 is recorded in `HASH_INDEX.json`.
- The expanded dry-run plan is the output of the frozen evaluator's static dry-run. Its canonical SHA256 is pinned separately from the frozen reader JSON's plan SHA256.
- Local substitutes executed the generated remote entry on success, a self-consistent expanded-plan SHA mismatch, and evaluator child return code 7. The mismatch and failure paths retained staging/diagnostics; the failure path retained child stdout/stderr and original return code.
- The report records six checkpoint payload deserializations with strict model loading disabled, zero model forward, no start, admission, approval/token creation, run creation, SSH, or formal evaluation.

This is a local deploy-only preparation record. No research server connection or formal runner execution was performed.
