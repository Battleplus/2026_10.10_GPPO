# N1 Formal Run: Final Independent Review

Review date: 2026-10-13 (Asia/Shanghai)  
Identity: `ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012`  
InvocationID: `fbdad1589e894466b62cf1785df0de47`

## Conclusion

The formal unit **failed at shutdown** (`ActiveState=failed`, `Result=exit-code`, `ExecMainStatus=1`). The evaluation and export stages themselves recorded `complete`; their receipts report 2,800 episodes and 2,800 passing artifact audits. The complete exported trajectories and metrics now support offline exploratory analysis, but the run remains failed: shutdown failed, settlement is `FAILED_PRESERVE_FIRST_ERROR`, and `formal_result_claimed=false`.

The shutdown failure is explained by a deterministic status-field mismatch in the frozen evaluator source. `_verify_shutdown` reads the resource ledger and requires the admission row's `status` to be `accepted`. The admission ledger row's `status` is `complete`; `accepted` is stored in the admission driver's nested `result.status`. The shutdown check therefore rejects the successful admission stage before it checks cgroup process membership. This matches the recorded PermissionError and is not evidence that evaluation or export raised an earlier error. Correcting this comparison offline can preserve and analyze the completed evaluation/export artifacts; it cannot rewrite this invocation's failed systemd settlement or make this run a formal PASS.

## Evidence Integrity and Binding

The one-shot capture identifies the frozen identity and expected InvocationID above. The captured systemd readback reports that same InvocationID both before and after the journal capture, and the final state is stable and failed. `session-record.json` reports one SSH invocation, exit code 0 for the read-only capture, no local capture errors, and no remote writes.

Local SHA-256 recomputation matched the capture's `SHA256SUMS.txt` and manifest values:

| Evidence | SHA-256 | Finding |
|---|---|---|
| `stdout.raw` (2,152,599,871 bytes) | `d0125d85d79ef111195898a2aa0a00578f78120ae6c6ca407aeb96531c1349b5` | Match |
| `stderr.raw` (0 bytes) | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | Match |
| `session-record.json` | `4d4ff986dedf719e76afe2c8b395dac86dcccb582fa53c60847a92bacb250092` | Match |
| `decoded/manifest.json` | `6a4dd9760f72a9756888732600f6b39a2d8378229c1a1cea203c433f4d871dbd` | Match |
| `diag/final-status.txt` | `d564f98abb8f65c2a19d450f82fa8d33927f6eea465acc12170ebdd37998bc6a` | Match |
| `diag/journal.txt` | `a01d9bfab843393cfa0171baf814ada80e4aa19e7bc1d5c6d0100e21c78b2587` | Match |
| `diag/run-files.tsv` | `7cfc3b60e288a9c2967d7079e6e4f1734a4ee3d0a392259f005307b5a1099014` | Match |
| `diag/settlement.json` | `d96be27cc78135ee8d56832f0e1b8857831cc2f3d16f541cf34f6f1d4e5c57f0` | Match |

The remote admission receipt binds `n01_full_evaluator.py` to SHA-256 `18cfd467df9d39b99fcf54b00732c56fe89c221d026615e2adc9a0fc130531e5`, matching the local frozen release copy. That copy's `_verify_shutdown` at lines 686-696 contains the mismatched requirement described above. The local source is used here only because its SHA-256 matches the source hash reported in this invocation's admission record.

## Stage and Result Findings

| Item | Evidence-backed finding | Limit |
|---|---|---|
| Admission | Stage receipt and ledger entry are complete, `first_error=null`; nested admission result is `accepted`. | The shutdown validator incorrectly tests the ledger status against `accepted`. |
| Evaluation | Receipt status `complete`; result and captured `episode_metrics.json` each report 2,800 episodes; `audit_count=2800`, `audit_pass_count=2800`, no partial checkpoints. Split counts are development 560 and heldout 2,240. The trajectory artifacts were independently replayed and reconciled below. | Receipt fields remain producer records; independent checks corroborate their trajectory and row-level data. |
| Offline consistency audit | All 2,800 trajectories passed frozen-package `independent_audit.audit_run` with `full_artifact`; the 2,204 initial objects and the 596 recovered ZIP members together cover all expected keys. All 2,800 episode-metric rows have full unique-key coverage; episode rows and stored audits match across 10 replay metrics for every row (0 mismatches); canonical episode-metrics hash matches the summary. | Offline artifact replay does not mean the systemd shutdown stage passed. |
| Checkpoints | Captured `checkpoint_barrier.json` says `passed=true`, `checkpoint_count=6`, and binds the fixed checkpoint manifest hash `1d73153df7f4498d03018eef26ce7e53034d26c2e4859398043460cabda21b9f`. All six local frozen-release checkpoint files independently hash to the per-file hashes in the barrier. The barrier also records model-state hashes and architecture evidence for L0-8201/8202/8203 and L1-8201/8202/8203. | Local byte identity plus a passed barrier supports checkpoint verification for this evaluation, but this review did not separately load the tensors or rerun policy forward passes. |
| Export | Export receipt status `complete`; it reports 2,800 episodes and audits, archive SHA-256 `93a3bcf316f9a71dd69e5f9570f6313dbad5ba7d1a74c3779f5c46a8709e1f31`, and summary/metrics hashes. The retrieved ZIP matches the expected byte size and SHA-256; all 8,403 members pass CRC with no absolute/traversal paths or symlink entries. The archive contains 2,800 each of trajectories, audits, and episode rows. | All 596 newly retrieved trajectories passed independent `full_artifact` event replay; across both batches, all 2,800 trajectories passed. This does not change the failed shutdown result. |
| Shutdown | Shutdown receipt and guardian status `failed`; first error is `PermissionError: shutdown requires exactly one successful n01_full_admission receipt`. The journal contains the same traceback after the runner emitted `{"episodes": 2800, "status": "complete"}`. No earlier stage receipt records an error. | The shutdown gate raised before its cgroup membership scan. Cleanup success / empty cgroup is therefore **UNKNOWN**; failed systemd status does not establish that the cgroup was empty. |
| Resources | Ledger: admission 2.64 CPU / 3.13 wall seconds; evaluation 2,506.53 / 2,682.88; export 46.88 / 49.58; shutdown 4.97 / 5.73. Final cgroup reports CPU usage about 2,563.20 seconds, memory peak 2,760,151,040 bytes against 4 GiB, and zero OOM/OOM-kill events. | Resource sampling includes documented interval/settlement limits; kernel CPU quota is reported unavailable. Process cleanup remains unknown as described above. |

## Supplemental Read-Only Retrieval and Full-Row Recalculation (2026-10-13)

After a separately authorized, one-time, two-path read-only capture, local SHA-256 recomputation confirmed:

| Retrieved object | Size | SHA-256 | Result |
|---|---:|---|---|
| `stdout.raw` | 66,857,282 bytes | `6821ff7463080f1e1bbd28d74c1c8398015aaa47548ed3d1887fd6fbf7758f8a` | Match |
| `stderr.raw` | 0 bytes | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | Match |
| `session-record.json` | 2,747 bytes | `53256965d1a76d032948dc99ae1b282b844c2dcac572084bfd9bfbbb73f30267` | Match |
| `run/export/n01-full-evaluation.zip` | 66,112,453 bytes | `93a3bcf316f9a71dd69e5f9570f6313dbad5ba7d1a74c3779f5c46a8709e1f31` | Matches export manifest |
| `run/preflight_plan.json` | 743,708 bytes | `b2adef5016c9e5b0e6b9b54420d8e1e2ecc09753232cf77c7c7bcfb216f44dd3` | Size and framed-stream hashes match |

The ZIP has 8,403 members, passes `ZipFile.testzip()`, has no unsafe member paths or symlink entries, and contains exactly 2,800 trajectories, 2,800 audits, and 2,800 episode rows. Its 2,204 trajectories already captured individually match the ZIP member byte-for-byte by size and SHA-256; the remaining 596 now have their contents available and all passed independent `full_artifact` replay. Across both batches, the capture-skip keys exactly equal the 596 recovered keys, with zero missing or failed replay outcomes. The ZIP and preflight file were retrieved read-only; the original run settlement remains unchanged.

I independently paired rows from the full 2,800-row `episode_metrics.json` by condition, split, parent scenario, method, and training seed. All 2,100 required pair differences were present (no missing comparisons). For each of the 60 condition/split/seed/contrast estimates, the directly computed mean matches the corresponding `summary.json` `per_seed` value within `1e-12`. Means below are weighted-on-time-delivery differences, averaged over 14 development parents or 56 heldout parents:

| Condition | Split | Seed | L1-C1 | L1-L0 |
|---|---|---:|---:|---:|
| carrier_competition | development | 8201 | -0.011904762 | 0.000000000 |
| carrier_competition | development | 8202 | 0.000000000 | 0.011904762 |
| carrier_competition | development | 8203 | -0.011904762 | -0.011904762 |
| carrier_competition | heldout | 8201 | 0.002584915 | 0.006868132 |
| carrier_competition | heldout | 8202 | 0.014787296 | 0.010714286 |
| carrier_competition | heldout | 8203 | 0.013001582 | 0.001785714 |
| original | development | 8201 | 0.000000000 | 0.000000000 |
| original | development | 8202 | 0.011904762 | 0.000000000 |
| original | development | 8203 | 0.011904762 | 0.000000000 |
| original | heldout | 8201 | -0.010524248 | -0.014523373 |
| original | heldout | 8202 | -0.013420310 | -0.000022943 |
| original | heldout | 8203 | 0.001770452 | 0.009059343 |
| scale_12x18 | development | 8201 | 0.000000000 | 0.000000000 |
| scale_12x18 | development | 8202 | 0.011904762 | 0.000000000 |
| scale_12x18 | development | 8203 | 0.011904762 | 0.000000000 |
| scale_12x18 | heldout | 8201 | -0.010524248 | -0.014523373 |
| scale_12x18 | heldout | 8202 | -0.002706024 | 0.010691342 |
| scale_12x18 | heldout | 8203 | -0.000015263 | 0.007273629 |
| scale_8x12 | development | 8201 | 0.000000000 | 0.000000000 |
| scale_8x12 | development | 8202 | 0.011904762 | 0.000000000 |
| scale_8x12 | development | 8203 | 0.011904762 | 0.000000000 |
| scale_8x12 | heldout | 8201 | -0.010524248 | -0.014523373 |
| scale_8x12 | heldout | 8202 | -0.002706024 | 0.010691342 |
| scale_8x12 | heldout | 8203 | -0.000015263 | 0.007273629 |
| stock_competition | development | 8201 | -0.019047619 | -0.019047619 |
| stock_competition | development | 8202 | -0.019047619 | 0.000000000 |
| stock_competition | development | 8203 | -0.019047619 | -0.019047619 |
| stock_competition | heldout | 8201 | -0.018760629 | -0.009519870 |
| stock_competition | heldout | 8202 | -0.001389979 | 0.004562402 |
| stock_competition | heldout | 8203 | -0.004826770 | 0.011564304 |

The earlier `scale_8x12` trace-only subset estimate is not used here; these full-row values use all 56 heldout parent scenarios. The scale-condition input audit found that the same 70 source scenarios were cloned into two-copy and three-copy variants, with shared maps/platforms/tasks equal. Primary rates match row-by-row across those paired inputs, while energy, reassignment, and decision cost change with the added copies. Interpret these as replicated-input pressure tests, not independent evidence that scaling improved primary performance. All 2,800 trajectories have now passed independent replay.

## Capture Limits and Use

The first capture decoded successfully with zero payload hash mismatches and no local errors, but its inventory status is **partial** because the 2 GiB cumulative payload budget skipped 598 run files (417,334,992 declared bytes): 596 trajectories, `preflight_plan.json`, and the export ZIP. A later authorized retrieval recovered the ZIP and preflight plan and closed those file-availability gaps. The `run-files.tsv` index lists 2,800 trajectory-named paths; that path count alone is not treated as a completion count. Episode counts above come from the evaluation receipt and captured metrics artifact.

The authorized supplemental capture retrieved only the ZIP and preflight plan; no evaluation was rerun. Preserve the actual settlement as failed. All 2,800 trajectory artifacts and full-row metrics have been independently checked, so they support offline exploratory analysis. The shutdown validator must be corrected and validated independently before any future invocation can pass its shutdown gate. No new invocation is needed to analyze the already completed evaluation artifacts.
