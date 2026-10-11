# N1 full evaluation runner readiness

## Current target access update (2026-10-12)

The latest read-only SSH attempts from the local execution environment timed out while connecting to `172.17.27.173:22`. No remote command started. The target unit's active state and current effective systemd/cgroup settings therefore remain unverified. The authentication failure recorded for 2026-10-11 is historical and does not describe these later attempts. Target execution remains NOT READY; this update does not authorize evaluation or training.

Date: 2026-10-11  
Code status: refreshed local static preflight passed with final r11 plan; the 2026-10-11 target read-only systemd probe failed SSH authentication; the later 2026-10-12 attempts timed out during TCP connection as summarized above; historical evaluator-profile no-model probe preserved as non-current evidence; evaluation status: not authorized and not run

## Runner

`package/n01_full_evaluator.py` reuses `evaluator.py` for C0/C1 and the six checkpoint policies, `_episode_row` and `independent_audit.audit_run` for each trajectory, and the existing `process_guardian.py` for realtime process-tree supervision. It evaluates the five registered conditions over all 70 parents per condition. The 100-sample diagnostic and the heldout-only 448-row evaluator are unchanged.

The refreshed local static `--mode dry-run` passed with the final r11 plan SHA256 `84e37c9816ba27aa780d07ddf31b19fe4609977532825f19a8d7976918cfd78d`. The 2026-10-11 target read-only probe reached TCP/22 but failed SSH authentication with no remote command started; this historical attempt is recorded in `received/n01_target_readonly_probe_attempt_20261011.json`. Later 2026-10-12 attempts timed out during TCP connection, as recorded in the current access update above. No target static preflight or current target systemd verification is claimed. The check covers the 350 canonical scenario hashes and content identities, 56 heldout + 14 development per condition, all six checkpoint file/configuration/architecture/state/optimizer digests, and emits the 2,800 unique `(condition, parent, method, seed)` keys. It does not simulate a trajectory. The runner applies the existing `dataset_protocol._canonical_bytes` convention, matching the scenario manifest's sorted compact JSON plus trailing newline. A checkpoint barrier check showed that local Torch initialization evidence differs from the target build; static preflight verifies frozen checkpoint digests and saved architecture evidence, while fresh strict model loads run at target admission. The existing prior-cost summary is validated against its bound evidence hashes, including the known 173.079052 wall / 124.840999 CPU seconds. External-commitment scenarios are preserved and hash-checked; the preflight asserts 10 such parents per condition and the expected 14/12 task counts at 8x12 and 21/18 at 12x18.

The guarded execution modes are `admit`, `evaluate`, `export`, and `shutdown`. `resource_supervisor.py` and `process_guardian.py` enforce the proposed 120/60 admission, 5,400/4,500 evaluation, 300/180 export, and 120/60 shutdown caps. Early-stop thresholds reserve 5/2 seconds for admission, 20/15 for evaluation, 5/2 for export, and 10/2 for shutdown (wall/CPU); identity-wide thresholds are 5,870 wall and 4,760 CPU seconds, preserving 70/40 seconds inside the proposed 5,940/4,800 totals for kill, reap, receipt, and settlement. Before checkpoint loading or any episode, admission verifies the current systemd InvocationID, active unit, effective Type/KillMode/memory/CPU accounting settings, unit cgroup membership, `memory.max`, and readable cgroup CPU accounting. No hard CPU quota is claimed without a readable current `cpu.max`: the historical r3 receipt's inspected user slice exposed only `memory` and `pids` controllers, not `cpu`, and it captured an older effective profile including `CPUQuota=80.7%`. That receipt is retained only as historical invocation, accounting-readback, and settlement evidence, not as current package/profile or quota proof. `CPUAccounting=yes` plus cgroup-v2 `cpu.stat usage_usec` provides measurement, not throttling. The guardian samples that counter every 0.25 seconds across the service cgroup and descendant tree; it separately samples the isolated child process group for RSS, kills/reaps that group on a cap breach, and removes/verifies any new cgroup member that detached from the process group. Sampled limits can overshoot between samples and during kill/reap/settlement; receipts preserve observed excess and sampling interval. `RuntimeMaxSec=5900s` and `TimeoutStopSec=40s` provide the outer wall-time stop contract. No additional probe is planned. Shutdown checks all PIDs in the current unit cgroup subtree and permits only its verified caller chain; unreadable or missing cgroup evidence fails closed. Each stage is single-use in its identity; existing stage receipts, execution outputs, state markers, or export directories block restart.

Evaluation outputs contain 2,800 episode rows, trajectories and independent audits; summaries are separate for each condition and heldout/development split. Heldout summaries include paired same-parent contrasts, percentile intervals and direction for each learned seed. Development rows are descriptive only and cannot support a confirmatory claim. Worst-10 primary-metric cases are retained per condition/split/contrast.

## Identity And Budget

`package/N01_FULL_EVALUATION_IDENTITY.json` binds the current runner, process guardian, systemd runner/settler/units and transitive imported code, runtime specification, stage budget, historical checkpoint manifest, registry and all six fixed checkpoint file hashes. The refreshed static plan is saved at `received/n01_full_evaluation_preflight_plan_final_r11.json` with SHA256 `84e37c9816ba27aa780d07ddf31b19fe4609977532825f19a8d7976918cfd78d`; it binds the current source identity, 350 scenario content hashes and complete 2,800-key matrix. A changed dependency or input invalidates the identity/plan.

`package/n01_full_evaluation_stage_budget.json` remains `proposed` and hash-bound, with a new-identity total of 5,940 wall / 4,800 CPU seconds. The 173.079052 wall / 124.840999 CPU seconds of known historical use are separately charged through `N01_FULL_EVALUATION_PRIOR_COST.json`. The cumulative known ceiling at full use is 6,113.079052 wall / 4,924.840999 CPU seconds. Unquantified earlier use remains explicitly unknown, not zero. Guarded stages require a separate `N1_FULL_EVALUATION_BUDGET_APPROVAL.json` beside this package, binding the frozen budget hash, identity, stage caps, total, approval reference, and approver. This external record does not change the hash-bound package proposal.

## Verification And Invocation

Static preflight command (no trajectories executed):

```powershell
python package/n01_full_evaluator.py --mode dry-run --plan-output received/n01_full_evaluation_preflight_plan_final_r11.json --output-root received/n01_full_evaluation_once
```

After independent review and explicit budget approval, the unique installed user-service start command is used exactly once. Admission validates that this unit's live limits match the reviewed contract before loading checkpoints; its runner then invokes all four stages and ExecStopPost writes the final settlement receipt:

```bash
systemctl --user start n01-full-evaluation-r1-20261011.service
while systemctl --user is-active --quiet n01-full-evaluation-r1-20261011.service; do sleep 2; done
systemctl --user show n01-full-evaluation-r1-20261011.service --property=Result,InvocationID,CPUUsageNSec --no-pager
cat /home/user1/w1-pilot/runs/ch2-disaster-relief-n01-full-evaluation-r1-20261011-once/systemd-settlement.json
```

The external approval record is absent, so the evaluation service remains unstarted. The 2026-10-11 authentication failure and 2026-10-12 TCP connection timeouts are historical/current access attempts respectively; neither started a remote command. The historical `/usr/bin/true` no-model contract probe uses the evaluation service's exact systemd resource profile and validates its effective limits, cgroup readback, invocation ID, and settlement wiring; its successful receipt is `received/n01_systemd_contract_probe_r3_receipt.json`, and it is not current package/profile or quota proof. It does not perform model loading. No full evaluator, training, N2 or N3 work has started. Direct gate checks confirmed that guarded stages refuse a missing approval record and existing execution roots are rejected for restart.
