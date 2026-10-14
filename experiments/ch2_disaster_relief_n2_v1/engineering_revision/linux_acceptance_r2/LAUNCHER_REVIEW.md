# N2 r2 One-Shot Launcher Review

Review date: 2026-10-13

## Scope and conclusion

Static review of `preparation/r2_once_launcher.py` against the execution checklist and frozen package manifest. The reviewed candidate is suitable for consideration after a separate, valid user authorization is supplied. This review does not authorize execution. The authorization template remains `NOT_APPROVED`.

The launcher pins frozen package manifest SHA-256 `C90FA16A70158E77FBF1EF56C35D9E511F4579F8CE926F35B9458963AAF5ACCA`. Static checks recorded for this review passed: Python AST parsing; exact manifest pin; one SSH `connect` site and one `systemd-run` site; strict rejection of unknown host keys; required observed-affinity input; and exclusive creation of the evidence directory and transcript. Authorization validation binds the identity, target, connect host, digest, run identity, unit, one-time status, permitted scope, and excluded scope.

The launcher sets CPU affinity and CPU quota, a 4 GiB memory limit, and an 1,800-second outer service timeout. It relies on the frozen runner for the 1,740-second wall, 1,200-second CPU, 4 GiB RSS, and 8 GiB package/work storage limits, and checks the corresponding receipt values. It records the service invocation ID while streaming output and validates the matching service result and receipt fields. No retry or reconnect path was found.

## Residual execution precondition

The checklist requires the evidence directory to be outside version control. The launcher creates it exclusively but does not detect whether the selected path is inside a Git worktree. Before any separately authorized execution, the operator must select and verify an evidence path outside all version-controlled worktrees.

## Verification boundary

No SSH connection, remote action, launcher execution, model test, or frozen-package modification was performed. This is a static review only; authorization and the operator's checklist preconditions remain mandatory.
