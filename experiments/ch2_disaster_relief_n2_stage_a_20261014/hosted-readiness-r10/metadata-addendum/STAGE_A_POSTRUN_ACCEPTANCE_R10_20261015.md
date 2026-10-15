# Stage A Post-Run Acceptance Checklist (R10)

**Purpose.** Record post-run acceptance from the controller's collected receipts and raw exported evidence. This checklist does not authorize or initiate a run. Fill in evidence paths, hashes, measured values, and dispositions after execution; do not infer missing values.

**Current state (2026-10-15).** `RUN NOT STARTED; POST-RUN ACCEPTANCE PENDING`. The recorded `READ_ONLY_PREFLIGHT_MATCH` is preparation evidence only. The proposed configuration remains `NOT_APPROVED`. A preflight result is not a worker run, a completed ledger, an archive, or scientific-budget calibration.

For every row below, record `PASS`, `FAIL`, or `UNKNOWN`, with the evidence path and SHA-256. `UNKNOWN` means the evidence is absent, incomplete, or not comparable; it is not a pass and must not be converted to zero. A failed required row rejects run acceptance until explained and resolved.

## 1. Run Identity and Controller Acceptance

| Check | Required evidence and acceptance condition | Disposition / evidence |
|---|---|---|
| Controller bundle identity | Controller receipt identifies the exact R10 bundle; its SHA-256 matches the reviewed input snapshot used for that run. Record the run ID, bundle hash, config hash, and receipt hashes together. Do not substitute a later metadata snapshot for the run input identity. | `UNKNOWN` / |
| Controller outcome | Controller reports successful completion and collection of both `managed-worker-receipt.json` and `managed-supervisor-receipt.json`; remote command/worker return codes are zero; no `first_error`; cleanup succeeds; `automatic_retry` is false. | `UNKNOWN` / |
| Receipt schemas and linkage | Worker schema is `n2-managed-worker-receipt/1`; supervisor schema is `n2-managed-stage-supervisor/1`. The controller, worker, and supervisor refer to the same bundle and run; supervisor `systemd_invocation_id` is present and equals the controller-observed invocation ID. | `UNKNOWN` / |
| Controller acceptance result | Preserve the controller's final acceptance result and rejection reasons. Confirm the result was computed from the collected receipts for this run, rather than copied from a prior attempt. | `UNKNOWN` / |

Relevant source contract: `n2-development/controller-password-r10/n2_controller.py` (`collect_managed_receipts` and final same-invocation resource checks), `managed_runtime.py`, and `managed_stage_supervisor.py`.

## 2. Worker, StageServer, and Ledger

| Check | Required evidence and acceptance condition | Disposition / evidence |
|---|---|---|
| Worker receipt completeness | Preserve the full worker receipt, including `status`, `worker_result`, `ledger`, `operation_results`, `exports`, `export_status`, `stage_server_socket_present`, and `settlement`. `settlement` is complete and successful; `export_status` is successful; the verified export is linked to the worker result and export list. | `UNKNOWN` / |
| StageServer transitions | Preserve the ordered `stage_server_rows` with stage names, sequence/order, timestamps, and result fields. Reconcile the observed path to `vendor/stage_contract.py`: `input_admission` → `paired_collection` → `world_training_and_restore` → `offline_prediction` → `conditional_policy_training` → `conditional_task_confirmation` → `analysis_and_settlement` → `settlement_and_verified_export`. Require the final stage to be `settlement_and_verified_export`; explain any absent, repeated, failed, or out-of-order transition. | `UNKNOWN` / |
| SQLite ledger settled | Archive the SQLite database and capture a read-only query/export of all `calls` rows (`id`, `stage`, `name`, `amounts`, `status`, `started`, `finished`, `error`). Every call is terminal (`complete` or explicitly explained `failed`); there are no `pending` rows. Receipt snapshot has `pending_calls == 0` and `failed_calls == 0`. Reconcile row totals by operation against receipt `ledger.totals` and `operation_results`. | `UNKNOWN` / |
| Reservations and caps | Record `assert_settled`/equivalent settlement result. The durable reservations projection must equal the sum of `calls.amounts` by stage/resource, preserving charges for every call status; it is not expected to be zero. For `PASS`, require `pending_calls == 0`, `failed_calls == 0`, and per-operation plus aggregate totals within configured caps. Preserve cap configuration and calculation evidence; do not rely solely on the aggregate success flag. | `UNKNOWN` / |
| World-model learning acceptance | Resolve `LOCAL_ENGINEERING_RECEIPT.json` via `worker_result.receipt_path` and verify `worker_result.receipt_sha256`. In that engineering report, require 10-20 inclusive actual WM optimizer updates across the measured comparison paths. Reconcile `world_model.optimizer_steps_across_both_paths` with ledger calls and raw checkpoint evidence. Require `world_model.next_update_equivalent` to be true. | `UNKNOWN` / |
| PPO learning acceptance | In the same hash-verified engineering report, require 2-64 inclusive actual PPO optimizer updates across the measured comparison paths. Reconcile `ppo.combined_optimizer_updates_across_comparison_paths` with ledger calls and raw checkpoint/rollout evidence. Require `ppo.restore_equivalence.equivalent` to be true and evidence that the frozen WM stayed unchanged during PPO. | `UNKNOWN` / |
| Saved prediction integrity | Require saved predictions to be finite and identity-aligned to their source windows/candidates; reconcile prediction counts and identities to the engineering receipt and archived raw evidence. Local or mocked tests do not establish any of these real-run learning gates. | `UNKNOWN` / |
| Error and interruption audit | Search controller, worker, supervisor, StageServer, and ledger evidence for exceptions, nonzero return codes, interrupted calls, and recovery. Any exception or failed row is a failure unless the acceptance contract explicitly permits it and the reason is documented. | `UNKNOWN` / |

## 3. Same-Invocation Resources and Storage

| Check | Required evidence and acceptance condition | Disposition / evidence |
|---|---|---|
| Invocation identity | Capture the systemd invocation ID, `ControlGroup`, `CPUUsageNSec`, and `MemoryPeak` for the exact R10 service invocation. Match its invocation ID and cgroup to the supervisor receipt; do not combine values from another invocation or a preflight service. | `UNKNOWN` / |
| CPU, memory, and wall time | Preserve supervisor `cgroup_baseline`, `cgroup_final`, `cgroup_cpu_seconds_total`, and `wall_seconds_total`, together with the matching systemd values. Reconcile units and deltas. Confirm all configured `guard_limits` were respected and record the measured values beside each limit. | `UNKNOWN` / |
| Storage limit | Record `peak_package_work_export_bytes`, the configured byte limit, `storage_sampling_scope`, sampling interval, and the final pre-receipt sample. Require the recorded high-water value to remain within the configured limit. | `UNKNOWN` / |
| Storage measurement limitation | Supervisor storage accounting is a sampled high-water mark plus a final sample before writing its receipt. It is not continuous and excludes the receipt-write tail; record it as a sampled peak, not an exact final peak. If the limit must cover the receipt tail, mark that coverage `UNKNOWN` unless independent evidence measures it. | `UNKNOWN` / |
| Same-run evidence association | Hash the controller, worker, supervisor receipts and systemd evidence after collection; record sizes and hashes in a run manifest. Verify all resource evidence names the same invocation and bundle. | `UNKNOWN` / |

## 4. Raw ZIP and Verified Export

| Check | Required evidence and acceptance condition | Disposition / evidence |
|---|---|---|
| Archive identity | Resolve the raw ZIP path from `worker_result.evidence_archive_path` / verified export. Record byte size and SHA-256 of the exact archive bytes. They must match `worker_result.evidence_archive_sha256`, the verified export SHA-256/size, and the corresponding `exports` entry. | `UNKNOWN` / |
| ZIP integrity and names | Open the raw archive and run CRC/integrity validation. Reject duplicate member names, absolute paths, drive-prefixed paths, `..` traversal components, or unexpected path forms. Record the complete sorted member inventory and per-entry uncompressed sizes. | `UNKNOWN` / |
| Evidence index | Require `evidence-index.json` with schema `n2-local-engineering-evidence-index/1`. Its `artifact_sha256` keys must equal the archive member inventory excluding `evidence-index.json`; each key must be a safe relative path. Hash every extracted member and compare it with the index digest. | `UNKNOWN` / |
| Required raw evidence | Confirm the index and inventory include the run receipt/report, raw branch/continuation records, rollout/trajectory evidence, and every checkpoint or other artifact claimed in the worker/engineering receipt. Compare archive contents to receipt claims; missing or extra files require explanation. | `UNKNOWN` / |
| Export verification chain | Confirm the controller's verified-export record, worker `verified_export`, `exports` entry, archive path, SHA-256, and byte size all identify the same raw ZIP. Preserve the post-export verification result. | `UNKNOWN` / |

Archive contract reference: `n2-development/hosted-engineering-package-r1-20261014/run_local_engineering.py` (`_write_evidence_archive`) and `test_n2_contracts.py` (inventory/index/export contract). The R10 run's archive itself must be checked; source tests do not prove that a produced archive is valid.

## 5. Scientific-Budget Calibration Readiness

Run acceptance and research-budget readiness are separate decisions. Freeze planned work from a frozen protocol and source-derived counts/formulas, with a separately authorized Linux calibration for resource estimates. Do not require or initiate a formal C/D research run to freeze the budget; execution authorization remains separate. A successful engineering run does not establish the formal B/C/D workload or justify scaling local observations into the research budget. Keep unresolved inputs `null`/`UNKNOWN`; do not treat nominal counts, local Windows data, or a per-candidate bound as a measured total.

| Calibration input | Evidence to capture before freezing the research budget | Current status |
|---|---|---|
| Protocol and split identity | Freeze the requested 56/14/24 train/development/confirmation parent identities and split generator, and state how this differs from the older 56-confirmation protocol. Hash the protocol and admitted datasets. | `UNKNOWN` |
| Window admission | For each nominal train/development/confirmation window slot, record usable/admitted status and reason, including no-opportunity and unknown outcomes. Nominal slots (224/56/96) are not usable-window measurements. | `UNKNOWN` |
| B candidate catalogs | Per admitted opportunity window, record the exact legal candidate catalog and count, including NOOP whenever legal; retain catalog hashes and admission reasons. Candidate counts are unresolved until observed. | `UNKNOWN` |
| B steps and overhead | Measure candidate-continuation steps separately from complete B-ledger steps. Include paired NOOP-reference continuation and restore, reconstruction, and prefix work. Record the formal horizon `H`; the `sum(K_i * min(30, max(0, H - t_i)))` candidate-only bound is not the complete B cost. Do not assume a factor of two. | `UNKNOWN` |
| C world-model work | Freeze the planned admitted-row rule and derive updates, candidate sample visits, forward/prediction calls by split, normalization/target forwards, and development scoring from protocol and source. The planned formula `3 * 40 * ceil(N_train_window_rows / 8)` remains unresolved until its admitted-row input is fixed. Use actual counters only from an already-authorized bounded run; a formal C/D run is not a budget-freeze prerequisite. | `UNKNOWN` |
| Checkpoints | Derive planned checkpoint operations from the frozen methods/seeds/schedule and source. Where an already-authorized bounded run exists, measure actual save/load/restore counts and bytes, including failed or repeated attempts, and connect each to the archive inventory and receipt. | `UNKNOWN` |
| D PPO and confirmation | Freeze the planned methods/seeds, PPO episodes, updates, environment steps, rollout counts, confirmation trajectories, and outcomes from protocol/source. Planned schedule values (3,072 updates, 768 episodes, 168 confirmation trajectories) are not empirical measurements. Record formal training and confirmation horizons before deriving horizon-dependent work; do not execute the formal schedule to obtain these planned counts. | `UNKNOWN` |
| Dataset and export materialization | Derive planned row counts and artifact/export inventory from frozen source/data definitions. Where separately authorized calibration evidence exists, record materialized sizes, bytes read/written, archive/export counts and sizes, and elapsed time. Preserve dataset and export hashes. | `UNKNOWN` |
| Linux resource calibration | Capture Linux wall time, same-invocation CPU, RSS/MemoryPeak, sampled storage peak and scope, configured limits, and run identity for a separately authorized calibration workload. The read-only host preflight is not workload calibration; do not start a formal research run as a substitute for this separately authorized calibration. | `UNKNOWN` |
| Provenance and budget update | For every value, identify the source receipt/query/log, unit, population, aggregation rule, source hash, and whether it is observed, protocol-fixed, or derived. Update `operation_budget_r1.json` and its report only from evidenced inputs; retain nulls where evidence is absent. | `UNKNOWN` |

Budget source: `n2-governance/research-budget-r1/REPORT.md` and `operation_budget_r1.json`. That report marks the budget `UNFROZEN`, says the new formal W1/N2 source is omitted from the hosted civilian manifest, and labels local Windows calibration `OBSERVATIONS_ONLY_NOT_RESEARCH_BUDGET`. Thus this checklist cannot mark scientific-budget readiness `PASS` from R10 engineering receipts alone; it requires frozen planned work, source-backed derivations, and the separately authorized Linux calibration, but not execution of the formal C/D research schedule.

## Final Disposition

| Decision | Required result | Disposition / reviewer / date |
|---|---|---|
| R10 post-run acceptance | All required run identity, receipt, stage, ledger, resource, and archive rows pass; all exceptions and limitations are documented. | `PENDING` / |
| Scientific-budget readiness | Protocol identity, source-derived planned work, and separately authorized Linux calibration above are evidenced; remaining unknowns are explicitly bounded. This disposition does not require that the formal C/D research schedule has been run. | `NOT ESTABLISHED` / |
| Authorization state | Record separately from technical acceptance. This checklist does not change approval or authorization state. | `NOT APPROVED` / |
