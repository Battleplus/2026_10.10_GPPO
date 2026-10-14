# N2 local run independent review R6

Date: 2026-10-14. Reviewer: independent GPT-6.1 Sol high. Run: `E:/10.14/n2-development/runs/local-1791969402746190800/`. This report is separate from the executor's node packet. No environment, model forward, optimizer, SSH or formal training was rerun by the reviewer.

## Finding

**LOCAL engineering learning chain VERIFIED WITH LIMITS.** The saved evidence supports real candidate/NOOP branch collection, WM optimizer learning, a learned frozen WM entering the real civilian critic-augmented PPO trainer, real PPO updates, and exact continuous/restored next-round equivalence. The worker exited 0, watchdog violation is null, and the local no-descendant cleanup receipt is consistent. This is not hosted acceptance, formal research evidence, scientific benefit, complete contract acceptance, or Stage A PASS.

Independent audit: `audit_local_run_r6.py` exited 0. Its reproducible JSON evidence is `audit_local_run_r6_output.json`; stdout is `audit_local_run_r6_stdout.txt`, all in this review directory. Checkpoints were inspected with `weights_only=True` and explicit standard NumPy safe types; no pickle execution or model execution was needed.

## Actual evidence

The 13 source files and budget pinned in R5 still match both worker and watchdog receipts and current file hashes. The raw-record data identity independently recomputes to `F7A97A131FB6BC9BDB461C63F774FF0B0C042D80750CA00CC04833310A87A68C`, exactly the WM checkpoint's training data identity. This verifies the listed manifest, not every transitive dependency: `stable_identity.py` and `chapter1_adapter.py`, among called helper imports, are not separately in the supervisor's frozen list. A final research identity should cover all called code.

Seven unique candidates comprise six dispatches and NOOP, from the full t8 catalog. Every branch has a common t8–38 horizon and 30 candidate plus 30 reference transitions: **420 saved paired steps**. Observation/catalog digests independently recompute across every raw transition; first candidate actions match their candidate identities, reference first actions are NOOP, and all seven reference traces are identical. The NOOP candidate equals its reference in every transition and event; its global deltas are exactly zero and its nonexistent target-task head is invalid. Actual instrumented branch-phase work is 596 steps, correctly larger than saved paired steps because restore/prefix replay work is included. Source scan work is 68 (60 base plus 8 prefix); real PPO work is 720, totaling **1384 actual environment steps**.

Raw cumulative rewards and move/service event energy independently reproduce all seven reward/energy targets. There are nonzero differences: heli-1/inspection has reward −0.0094, energy +0.94 and a changed latent-water elapsed outcome; uav-1/inspection has reward −0.005 and energy +0.5; uav-1/water has reward about −0.00687107 and energy +0.68710678; uav-3/water changes both inspection and water elapsed labels. This is actual branch diversity, but limited diversity. Every `reward_improved`/`energy_saved` binary target is 0, every other-task on-time/report-count delta is 0, and the heli-1/water reward difference is floating noise (−2.22e−16). These data cannot demonstrate positive reward decisions, classification of positive cases, useful externality/report heads, overdue/failed/censored outcome performance, or scientific PPO gains. All branch windows stop at the engineering horizon, with `terminal=false`/window `right_censored=true`; the resolved per-task labels are distinct from episode-level censoring.

WM receipts count **12 actual Adam calls**: ten initial updates plus one continuous and one restored comparison update. Checkpoints prove update/Adam indices 10 and 11; all 16 WM tensors change between those checkpoints. The final frozen checkpoint SHA256 is `27BA7C52BAAC1B1C17BA88815B9E0B17D8296DEC8F4BD8C2023321228D5C2D23`, with tensor-state digest `E9D87972FE4BA323647256ABA63A4D925E00127ECE911D7E67D0BB110C25AE88`. The initial ten-step checkpoint is not the PPO source. All 16 WM tensors in each of the three PPO checkpoints precisely equal the frozen update-11 WM and remain unchanged throughout PPO. WM next-update equality is supported by the executed comparison receipt; the separately restored WM branch checkpoint was not retained, so that particular equality is not independently recomputed from two saved WM endpoints.

Three real civilian learning-curve records each contain 16 optimizer updates, four episodes and 240 transitions: **48 PPO optimizer calls / 12 episodes / 720 transitions**. Saved Adam counters are 16, 32 and restored 32. Forty-five policy/critic/adapter tensors change from round 1 to round 2. The two round-2 rollout files are byte-identical; continuous/restored model and optimizer states compare exactly tensor by tensor. Every episode contributes 60 steps; each saved rollout has four true terminal transitions, zero truncations and zero rollout cuts. This supports this local restore path; it does not exercise truncation or establish scientific evaluation results.

WM call counters total **405 forwards / 2270 candidate rows**: training20/140, restore comparison4/28, standalone inference1/7, PPO critic380/2095. The architecture receipt says public policy input only, detached WM and probability expectation, actor reads WM false, WM absent from trainable optimizer. The implementation remains `CriticOnlyGppoAdapter` with a random last layer and no training-only normalization. This is a functioning engineering adapter, not the final requested zero-init/normalization contract.

## Resource settlement

| Quantity | Observed | Local cap |
|---|---:|---:|
| Supervisor timed wall | 105.7861509 s | 1200 s |
| Final supervisor + retained-worker CPU | 108.90625 s | 900 s |
| RSS peak sampled | 406,495,232 bytes | 4,294,967,296 |
| Final independently counted output including watchdog receipt | 13,127,542 bytes / 14 files | 536,870,912 bytes |
| Actual environment steps | 1384 | 8000 |
| Episode constructions / PPO episodes | 57 / 12 | 1024 / 12 |
| WM / PPO Adam calls | 12 / 48 | 20 / 64 |
| WM forward calls / candidate rows | 405 / 2270 | 10000 / 1280000 |
| Reported checkpoint entry reads / writes | 2 / 5 | 32 combined |

The independently measured watchdog receipt is 3769 bytes; its `receipt_write_bytes_planned` is 3722 and its planned final total undercounts by 106 bytes. Actual output remains far below the cap. R5's receipt-edge failure-return defect was not triggered. Do not label the planned-total field exact.

The reported audited output operations are 15 before the worker's final receipt write; adding that write and two supervisor open/write operations gives 18 entry/audit operations, well below 1000. This is entry/audit semantics, not every low-level write. Similarly, reported checkpoint reads are restore entry calls: the N2 PPO override loads once and its superclass loads again, so physical deserializations include an extra read (at least three physical checkpoint reads in the whole run). That remains below 32 but must not be described as exactly two physical I/O reads.

The watchdog has 371 samples, no observed unexpected descendants, and exited-worker cleanup true. Python process inspection after completion found no running Python process. This is local exited-worker evidence; Windows cgroup CPU/memory and hosted service cleanup are unavailable. Between-sample RSS/disk peaks, a transient descendant between samples, pre-timer supervisor wall, and final receipt-write/stdout CPU/RSS remain unmeasured. The receipt explicitly discloses the latter. No failure/pending output or traceback appears in the observed log; failure-path return/first-error preservation was not dynamically tested by this successful run.

## What this can inform in a research budget

The run gives a concrete engineering footprint for this CPU, tiny model, one synthetic parent/window, seven candidates, four repeated fixture scenarios, 60-minute horizon and three PPO comparison rounds. The PPO rounds consumed about 86.984 CPU seconds and 93.784 wall seconds in aggregate, about 1.812 CPU / 1.954 wall seconds per PPO optimizer update for this exact workload. The overall run additionally includes startup, branching, WM and settlement. Retaining the raw evidence requires about 13.13 MB for this path. These observations can seed a provisional engineering estimate with separate allowances for startup, catalog growth, branch replay, WM passes, PPO episodes, checkpoints and cleanup.

A single local CPU sample does not give a worst-case cap, Linux/remote performance, scaling law, full dataset cost, formal sample size, scientific power, cgroup settlement budget or tolerance for large candidate/task graphs. Do not multiply per-update timing into a research authorization without bounding scenario count/horizon/catalog sizes, complete targets, unknown masks, evaluator workloads, saved artifacts and reserve/cleanup costs. The 12 PPO episode cap was exactly consumed; there is no episode headroom in this admitted run.

## Packet and Stage A boundary

The coordinator reported that the then-current `NODE_A_DELIVERY` draft mixed in military/W7 claims (six tasks/25 slots, physical-arrival/damaged/collision/host-confirmation heads, seven continuous targets and a frozen-zero actor adapter). **That draft is not independently approved and must be corrected before being archived as accepted delivery.** This R6 certifies only the actual saved local run and reviewed civilian source path. The real model has dynamic candidate/task axes, 2 global binary heads, 4 global continuous heads, 4 task binary heads and 2 task continuous heads; the four global continuous targets are reward/energy/other-on-time/report-count deltas.

Unmet demand, reassignment, explicit newly-overdue outcomes and full required absolute outcomes remain incomplete. Zero-init/training-only normalization, strict final layout/data contract, broader unknown/permutation/terminal/truncation acceptance, hosted controller execution and whole-cgroup settlement need their own evidence. The two old consumed remote authorizations remain consumed. LOCAL learning completion changes none of these boundaries.
