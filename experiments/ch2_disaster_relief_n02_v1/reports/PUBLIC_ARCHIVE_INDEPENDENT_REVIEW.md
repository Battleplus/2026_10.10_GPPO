# N2 Public Archive Independent Review

Date: 2026-10-13

## Decision

Approved for N2-only commit and push as a public archive, subject to staging only `experiments/ch2_disaster_relief_n02_v1/`. This approval covers the archive contents and evidence descriptions only. It does not approve Linux target execution, research collection, model training, prediction, or policy comparison. No SSH, model, training, or smoke command was run during this review. M0/M1 are already defined by the user; this review does not reopen those definitions.

## Scope And Evidence Boundary

The public copy contains N2 engineering source, tests, and reports for local synthetic work. The recorded Linux attempt was a one-session admission preflight only: authentication succeeded, the target identity and absent destination root were printed/checked, then a Python runtime probe exited 1 with `AssertionError`. Its individual chained assertion is not identified. The stop record reports zero remote root creation, upload, systemd submission, research processing, training, prediction, and PPO smoke, with no reconnect or retry. This is a failed preflight, not Linux runtime acceptance or an N2 research result. No private key material, SSH transcript bytes, target address/user, key path, or authorization text should be included in the public tree.

The N2 local engineering report describes a synthetic PPO integration smoke on Python 3.14.4 and PyTorch 2.13.0+cpu, including 720 comparison-path transitions, 48 optimizer updates, strict restore equivalence, and normal/injected-failure export checks. These are local engineering results only. The 40-epoch research fit, prediction gate, data collection, and formal policy comparison remain unrun. The separate M0/M1 local result report records its own 27 inherited regressions and 4 snapshot probes; it is not evidence of N2 research execution.

## Findings

The executor added clean-checkout layout, runtime versions, test commands, source index, public preflight stop evidence, and an archive rebuild record. The chronology now correctly records one authenticated SSH preflight followed by a failed Python assertion; it does not imply package transfer, service submission, or research work. The public smoke receipts use relative fixture/export/checkpoint paths. The local and target connection locator, private key, authorization body, raw transcript, and one-session private script are excluded. Historical resource-cost paths are identified as source references, not current N2 target instructions.

The archive distinguishes the original independently reviewed package digest `47C6ED5B74027E157A4F259AF63D778E1B3B905885CED7EF771FE3036DB524BA` from the archive-corrected manifest digest `4BBA81400B575F6D6C928DE2D6FB4CC7AFB5136DB993BD29A24A1793B9285051`; the reason is the corrected Linux README chronology and updated manifest file hash. It does not claim these are the same package identity. Rebuild verification is accurately split: the reconstructed workspace passes 29/29 with `PRIOR_RESOURCE_COST.json`, while the exact 23-file package remains 28/29 because that identity input is absent from the manifest. This is a documented limitation for any future Linux run, not a blocker to archiving the code and failure record. Do not describe the package as test-complete or Linux accepted.

## Checks Performed

Read the final N2 subtree, rebuild instructions, source/artifact index, public stop settlement, smoke receipt, engineering imports, and Git status. Scanned all subtree files for private-key material, SSH endpoint/account, key/config locator, private evidence filenames, workstation paths, caches, and large binaries. The final scan found none of those sensitive or generated artifacts; the two receipt copies have identical SHA-256 `45A22441EAA563E99DA7D0BCCBF7C860EE47C9BBC58E7659D77C2063700A8CC8`, with fixture paths relative to the archive. The public stop counters match the private-evidence review: one authenticated connection, no root creation/upload/systemd/InvocationID, zero research/training/prediction/PPO, and no retry. The public root worktree contains unrelated untracked N1 files outside this N2 subtree; the approved commit scope is only `experiments/ch2_disaster_relief_n02_v1/`. No test, smoke, package, SSH, or model command was executed in this public-copy audit.
