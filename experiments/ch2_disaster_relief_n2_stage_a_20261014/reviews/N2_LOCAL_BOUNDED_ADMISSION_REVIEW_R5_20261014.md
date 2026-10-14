# N2 bounded LOCAL admission R5

Date: 2026-10-14. Independent reviewer: GPT-6.1 Sol, high. Review scope: frozen local worker, watchdog, budget, and called reference sources. No smoke, optimizer, SSH, remote test, or formal training was executed by this reviewer.

## Decision

**LIMITED LOCAL ADMISSION: the executor may start the first bounded local engineering learning run now under the existing user/coordinator authorization.** This is an engineering admissibility finding, not a new authorization, hosted acceptance, research evidence, or Stage A PASS. Missing research heads and hosted cgroup settlement remain separate Stage A blockers and do not block this run.

The R4 practical startup failures and omitted before-effect work counters have been repaired. The latest watchdog bounds log reading to 48 KiB, samples total supervisor plus retained-worker CPU after log/hash inspection, resamples tail RSS and output size, and checks 1200 s wall / 900 CPU s / 4 GiB sampled RSS / 512 MiB output. The coordinator explicitly accepted the remaining small tail-accounting limitations for local engineering; admission does not certify perfect hard resource enforcement.

## Frozen SHA256 identities

Paths are relative to `E:/10.14/n2-development/`. Independently read and hashed; the watchdog hash was confirmed after its final tail changes.

| File | SHA256 |
|---|---|
| LOCAL_ENGINEERING_BUDGET.json | E868BF157118116FCCBA0DE1BCDE5A1D56CBAF38FFD9A96228F10246271EDC98 |
| run_local_engineering.py | 9073DF6FADE8DBBB4675A1AB934819CC3AE5E787A5ACF458C89654C99FCC7DAF |
| run_local_engineering_watchdog.py | 95C7F57E21DB4D611CDE00DE1A8183C861FBDC832689B7B918AB30EA5EB4330F |
| n2_contracts.py | 270F4C94F2A063E841A1891A34D79C9B7BEE61C82F383F39B5AF1F0750E809ED |
| references/existing_n2/branching.py | 56ACCA9AFC744FB4E0F3D4F112EA84C234E6679F36776E804391984F3E5223FC |
| references/existing_n2/world_model.py | CEE1B2083383213CB50272A49CA819F4EA523E9D9E80D6073C96DBBFDBABE9FF |
| references/existing_n2/ppo_integration.py | BF4305AE8D775A6B706C36C849C6AF0CA165A527F83E2826BAEA0A0E2D04AAEA |
| references/existing_n2/tests/test_branching.py | DAA03ADEBE3210B7FD752E3038F6962F20A93EE63AFD680DC3C21F97224119FF |
| references/civil/relief_env.py | EA9B2605CF529E5331F9479B62F7E5504005177AF902343743E6FE7D0838955D |
| references/civil/baselines.py | 13B2A84662022B7ED6A56A19629AD3ABE2AD954C46926EB1A72CAA326039115A |
| references/civil/scenario_schema.py | 5E18A62D251D2D4A9CCF1CA429E2CA41B8CE6430D6571A0F3897079C3E7D08C0 |
| references/civil/fixtures/control.json | EB4946623237FD88C8464D54D974EB027335F2EAD1370B9D9AD0F8B37CECF4C0 |
| references/civil/graph_policy.py | E1A8E56DA7F6BE9B75F2C48AFAE54ABECF71445BCE3AF94724F50713A005D142 |
| references/civil/ppo_trainer.py | C0AC1C57AE1A06D8DADF94DE80CA4E35F5B136F0879064AAC0E0618ABB2FC891 |

## Work and expected evidence

The profile admits at most 4 base episodes / 240 base steps; 1024 environment constructions; complete candidate catalog and branch count at most 128; combined actual environment steps at most 8000; PPO episodes at most 12; WM optimizer steps 10–20; real PPO optimizer steps 2–64; WM forwards at most 10000 and candidate-row evaluations at most 1280000; output operations at most 1000; checkpoint read/write calls at most 32; exports at most 1. Worker hooks reserve work before environment, optimizer, checkpoint, and model effects; the restored WM is included. The worker forbids subprocess spawn; unexpected watchdog descendants invalidate cleanup.

The real opportunity fixture has a non-NOOP catalog at t8. The called path collects public C1 observation, restores the pre-action state, compares each candidate against same-window NOOP with frozen C1 continuation, learns the WM, saves/restores and compares its next update, then feeds a frozen learned WM to the real civilian critic-augmented PPO trainer. The three real PPO rounds are expected to produce 48 optimizer updates / 12 episodes; the WM path includes training plus continuous/restored next updates, with the final PPO source frozen at update 11. These are source-path expectations pending receipts, not claims that execution succeeded. Full branch records are saved for independent checking.

## Retained limits and follow-up

- Windows cgroup metrics are unavailable. CPU, RSS and disk monitoring are sampled, with between-sample peaks not established. Supervisor work before its monotonic start and the final receipt write/stdout emission are not fully wall-accounted; final write/print CPU and RSS are explicitly unmeasured. Settlement reserves are headroom, not measured proof of consumption.
- Final receipt serialization has a small self-sizing discrepancy: its planned total is computed before adding the planned-total field and final size changes. The receipt-size failure changes `receipt["violation"]` without changing the outer `violation` used for the process return code, and still writes the receipt. This edge must be repaired before claiming exact disk-limit/failure-exit enforcement. It is recorded as a non-blocking local limitation under the coordinator's explicit bounded-tail decision; a near-cap or discrepant receipt cannot receive resource PASS.
- Output operation accounting describes audited operations/entry calls, not every kernel write. Unexpected descendant termination is conservative and cannot establish whole-tree cleanup PASS. A normal no-descendant exited worker is locally reviewable.
- Research targets remain incomplete: unmet demand, reassignment, explicit newly-overdue outcomes and complete absolute outcomes are not implemented. Critic zero initialization, training-only normalization and the full frozen data/layout contract require further final review. Local success does not resolve these limitations.

After execution, independently inspect worker/watchdog first-error and exit agreement, hashes, real optimizer traces, environment/episode counts, strict restore evidence, checkpoint provenance, resource samples, receipt size and cleanup. No remote or hosted authority is admitted by this report.
