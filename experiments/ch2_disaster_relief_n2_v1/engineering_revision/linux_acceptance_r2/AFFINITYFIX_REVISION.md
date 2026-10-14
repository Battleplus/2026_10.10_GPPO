# Affinity Capture Revision

This is a separate candidate derived from the statically reviewed r2 one-shot launcher. The reviewed original remains unchanged at r2_once_launcher.py.

The original CLI required a caller-supplied ordinary SSH affinity before connecting. That did not fit a single-connection execution. This revision reads taskset output from the ordinary SSH shell during the existing preflight command on the same Paramiko transport, expands CPU ranges such as 0-3 to 0,1,2,3, and passes that observed value to the frozen runner. A missing or malformed observation stops before package transfer and systemd submission. It does not assert the ordinary shell is pinned to CPU 0.

No package bytes, target, run identity, resource caps, or acceptance scope changed. The exact candidate was independently reviewed before use; see AFFINITYFIX_REVIEW.md and AFFINITYFIX_EXECUTION_RECORD.md. It was used for the one authorized connection attempt and stopped before transfer when localized taskset output was not recognized. The one-time authorization is consumed; no retry or resubmission is authorized.
