# N2 M0/M1 Preparation Independent Review

Date: 2026-10-13 Asia/Shanghai

## Decision

Supports continuing the local M0/M1 engineering preparation against the 2026-10-11 plan baseline. This is not acceptance of a frozen N2 research contract, world-model interface, collection pipeline, training, prediction gate, G/G-WM smoke, or authorization to start any of those stages.

## Reviewed Evidence

- Read `M0_M1_ENGINEERING_NOTE.md`, `N2_INTERFACE_IMPLEMENTATION_CONTRACT.md`, `M0_M1_LOCAL_RESULTS.json`, `SOURCE_HASHES.json`, and `test_branch_snapshot_contract.py`.
- Independently recomputed all 24 digests in the final `SOURCE_HASHES.json`; all matched.
- Independently ran the final four-test probe from `development/ch2_disaster_relief_n2_v1/preparation` with `$env:PYTHONDONTWRITEBYTECODE='1'; python -B -m unittest -v`: 4 passed, 0 failed, 0.039 seconds.
- The test SHA-256 was `BE874A8600820A607B7CC56C367DC39D7F3A7DB48A0A44BF29F796B7A2A5851E`, matching `M0_M1_LOCAL_RESULTS.json`.
- Confirmed that the final source inventory parses as JSON and includes the probe itself.
- The 27 targeted inherited M0/M1 regressions are recorded as executor-run evidence in `M0_M1_LOCAL_RESULTS.json`; this reviewer did not repeat them.

## Supported Scope

The four new probes cover reset-time public observation, candidate catalog, graph-encoded actor input, and legality invariance under hidden task attribute/ID/count changes and unreported failure/stock-loss changes; dynamic candidate catalog with explicit NOOP; an authentic t=8 NOOP-only state; pending report state across whole-object Python pickle serialize/restore; and source/sibling branch isolation using a separately named synthetic opportunity fixture.

The pickle check is an in-memory simulator object serialization round trip only. It does not establish a durable collection snapshot API, model checkpoint format, replay identity, or training resume behavior. The current environment path is deterministic and has no RNG calls (`rng=none`); any future stochastic continuation must bind and restore the exact RNG state/key.

## Open Gates

- Civilian target definitions, right-censoring semantics, and dynamic task-keyed target joins are unresolved.
- Unknown/validity masks are not implemented or validated for world-model heads.
- NOOP global consequence targets are not defined or tested.
- Stable candidate-ID binding through prediction, actor-probability aggregation, critic input, and replay is not implemented or tested.
- C1 continuation windows at t=8/16/24/32 and the 30-minute/terminal boundary are not implemented or tested.
- Model/optimizer/scheduler/RNG checkpoint identity and next-update-equivalence recovery are not implemented or tested.
- Prediction-gate metrics, thresholds, budgets, and stop rule remain unfrozen.

The inherited 27/27 regression report supports the stated civilian handoff/schema, environment, C0/C1, NOOP, independent replay, and conservation subset only. It does not close these world-model gates. Existing graph-v2 research data and W7 military weights, labels, windows, and scenario tapes are excluded from N2 consequence training.

## Execution Boundary

No trajectory collection, model training, prediction evaluation, server work, SSH, or G/G-WM smoke was performed by this reviewer. No source implementation was changed. The N2 stage contract remains draft and requires a separate frozen identity and node decision before later collection or training.

## N2 Synthetic Acceptance Addendum

Date: 2026-10-13 Asia/Shanghai

The independent acceptance review of the local N2 synthetic engineering implementation passed. Command: `python -m unittest discover -s development/ch2_disaster_relief_n2_v1/engineering/tests -q`; result: 26 tests passed, 0 failed, 59.561 seconds. The source/test/protocol hashes below were captured before and after the suite and did not change during execution.

Reviewed semantics include ordered global and per-task head names, branch-record joins by stable IDs, completion-by-observed-horizon versus final on-time censoring, report deadline and horizon semantics, full-scenario scalar externality labels, public-only model task axes, and the distinction between global-ranking gate evidence and descriptive errors/coverage for other heads. The synthetic GPPO path exercises rollout/update and strict next-round restore. This is local synthetic engineering acceptance only; it is not an N2 data fit, prediction gate result, research acceptance, or Linux readiness.

Frozen source/test/protocol identities:

| File | SHA-256 |
|---|---|
| `engineering/world_model.py` | `EA90196934A77F2A09A3FD0F5EFDED8F96B65DECDED1F70DBC0BE7007120BCAF` |
| `engineering/branching.py` | `65711D9F1D9F86766339708148075F2A72FDBA1BB5D7227961B7D810BCBF975B` |
| `engineering/tests/test_world_model.py` | `0401F8F28316B64F8DBF323B1E3CC7EF030BF1DF70986F43A4B99821E39C5C38` |
| `engineering/tests/test_branching.py` | `9EEC0D32D35796EE4F6AAF4D1BF2AEEE836EB0E92A687150AE765376F1D05E78` |
| `preparation/N2_PROTOCOL_DRAFT.md` | `B61D86709E3527162D6767F2972DEDBBE6BA090716F77E96F8FF13CE5D65EF4E` |

The corresponding local execution receipt, `preparation/N2_ENGINEERING_NODE_REPORT.json`, has SHA-256 `0C468E2B9F822F38F5815BB7ADBD26D40213CB178B6ABE8879ADBA7AB019F9A7`. It records synthetic-only scope, strict restore equivalence, 480 transitions and 32 optimizer updates per continuous or resumed path, and the Windows-local timing. It does not measure Linux costs.

## Linux Acceptance Packet Review

The target wrapper candidate is `engineering/n2_linux_runner.py`; its source parses successfully, and the package manifest lists it. The focused command `python -B -m unittest -v development.ch2_disaster_relief_n2_v1.engineering.tests.test_linux_runner` passed 3 tests in 0.019 seconds. These exercise a synthetic package identity pass, manifest/file/inventory tamper rejection, and the non-Linux refusal path. They do not execute the Linux runner's process orchestration or signal cleanup. The Linux-only runner was not run on a target, and the packet remains a candidate rather than target-run acceptance.

The reviewed ceilings are 1,740 seconds cumulative wall, 1,200 seconds cumulative CPU, 4 GiB peak RSS, and 8 GiB combined package/work/export storage, with stage wall/CPU caps of 120/60, 600/480, 900/600, and 120/60 seconds. The outer `RuntimeMaxSec=1800` is termination protection and does not extend the 1,740-second work budget. The runner samples cgroup memory peak and total cgroup CPU while child work runs, in addition to sampled process-group RSS. Its `/proc` process-group RSS can miss short peaks; cgroup `MemoryMax=4G` must remain enforced by the service. Storage sampling includes the staged package and work tree, but should be preserved with final filesystem evidence.

The runner starts unittest and smoke through per-process Torch thread bootstraps and writes smoke output under the work directory. It checks strict restore, normal export, failure receipt presence, and 480/32 per path plus 720/48 actual combined transitions/updates. The final source manifest contains SHA-256 values for all 23 listed files and has digest `47C6ED5B74027E157A4F259AF63D778E1B3B905885CED7EF771FE3036DB524BA`. Its file/hash mapping matches the independently generated temporary hash map from the earlier package check. The executor built the formal staged package at `the independently staged N2 package directory`; it contains 23 listed files plus the manifest (24 files total, 340,896 bytes). This reviewer independently compared source and staged digests for all 23 entries, confirmed the staged manifest is byte-identical to the source manifest, checked the exact file inventory and absence of symlinks, and called the staged runner's `_load_package` with the out-of-band digest; all checks passed. The README invocation supplies both `--expected-manifest-sha256` and `--expected-unit`. This closes the package identity and runner package-validation review for this exact digest.

The runner traps TERM/INT, kills and waits for the active process group, retries cleanup from `finally`, checks for a surviving process group, and records per-stage log sizes and hashes. The final receipt includes recursive pending-file discovery, the last completed stage, and active checkpoint paths; cgroup settlement-read failure becomes a recorded first error. The runner intentionally reports its final atomic receipt-write tail as unknown. The README requires same-invocation systemd result, status, journal-stop, and cgroup evidence to bound that tail; no such target evidence was available to this review, so it remains unknown pending the target run. This is an external evidence requirement, not a request for the runner to measure its own final write tail. No checked-in systemd unit template was reviewed; the README specifies the service settings and read-only reconnect evidence to retain.

The smoke report separates 480 transitions/32 updates per continuous or resumed path from the 720 transitions/48 updates actually executed across both comparison paths. It also injects an export serializer error, rather than a real model-update failure; retain the suite's update-failure rollback/receipt checks as separate evidence and do not label the serializer probe as a training failure.

At the time of the Linux packet review, no target connection or execution had occurred. That review closed the package/runner identity prerequisite for the exact manifest digest; it did not itself supply an execution decision. A later, separately authorized one-attempt preflight is recorded below. It stopped before transfer or service submission. The final receipt-write tail therefore remains unobserved.

## Linux Preflight Stop Review

The authorized one-attempt preflight stopped after one authenticated SSH session, before remote root creation, package transfer, manifest verification, or systemd submission. The private original transcript recorded the expected host/user and the absent remote root, then a Python probe exited 1 with only `AssertionError`; the exact failed assertion is unknown because the probe used chained assertions without per-condition output. It is therefore unsupported to attribute the failure specifically to CPU affinity, runtime version, Torch/NumPy, CUDA, or any other individual condition. The raw transcript and private session script are excluded from this public archive.

The public stop settlement records one authenticated connection, no remote-root creation, zero uploaded files/bytes, zero service submissions, no InvocationID, zero research/training/prediction/PPO operations, and no retry. The raw transcript SHA-256 is retained as an evidence digest in the public settlement JSON; transcript bytes and private scripts are excluded. This is a failed engineering preflight, not a Linux runtime acceptance, and provides no model, research, prediction, or PPO result.

## Archive Rebuild Check

The public source archive was reconstructed into a clean workspace. The 29-test N2 engineering suite passed there only after adding the required civilian `PRIOR_RESOURCE_COST.json` runtime input. The package builder produced the reviewed 23-file manifest digest unchanged. Running the same suite from that exact package produced 28 passes and one error because `PRIOR_RESOURCE_COST.json` is absent from the manifest inventory. Thus the archived Linux package candidate is not test-complete; it requires a separately reviewed manifest/package update before a future target attempt. No package or runner source was changed during this archive review.
