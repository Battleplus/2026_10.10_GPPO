# Independent research-budget formula review R1

Reviewer: GPT-6.1 Sol, high reasoning. Date: 2026-10-15.

Verdict: **PASS for the bounded deterministic formula and provenance review. The research budget remains UNFROZEN and unapproved.** These artifacts do not establish a formal civilian WM trainer, measured Linux resource costs, or Stage A completion.

## Exact final artifacts

All paths below are relative to `E:/10.14/n2-governance/research-budget-r1`.

| File | SHA-256 |
|---|---|
| `operation_budget_r1.json` | `946C7DA3BD8E5FDB3A4468C5A4FA0BFA848AC606FD9AC52FB00FCC7F0480B844` |
| `calculate_operation_budget.py` | `05927FDB851DAB8B120B53837926C69B10273C4B891B8024E020898F26F44533` |
| `REPORT.md` | `6D5E99815B15F5234700B1D25C8AD21B2DFE209E6D7B34A2EEFC91541457EA15` |

The independent script and machine result use this report's filename prefix, with `.py` and `.json` extensions, under `E:/10.14/n2-governance/reviews`. All nine supplied provenance source hashes match the actual local files.

The coordinator disclosed applying the final mechanical B-step scope/null correction after archiving the preceding three-file version, because the executor's helper failure persisted. The reviewer checked the corrected final hashes and source. The reviewer made no budget implementation edits. Original R9 source-review artifacts and original experiments remain untouched.

## Verified formulas and their limits

The user protocol governs: 56 training, 14 development and 24 confirmation parents, with nominal windows at minutes 8, 16, 24 and 32. This yields 224/56/96 nominal window slots. The older civilian 56/14/56 split is accurately identified as a conflicting historical reference, not silently substituted. The new split identities and window admission rule remain unfrozen; no-opportunity and unknown outcomes must retain their reasons rather than disappear from the record.

WM training uses the **planned** window-row interpretation: three seeds, 40 epochs, batch size eight unique admitted window rows. The formula is `120 * ceil(N_train_windows / 8)` updates across all seeds. If all 224 nominal train windows are admitted, this is 1,120 updates per seed and 3,360 total. With actual N omitted, the default total stays null. The independent probes at N=0,1,8,9,224 match integer-ceiling expectations. The explicit N=0 probe yields zero because the caller supplied zero; it does not fill an unknown default with zero.

The batch interpretation is source-referenced to `n2-development/references/world_model/consequence_training.py`, SHA-256 `54D79991FC5E3E6E1ACA65AEDA9EEBD52B1C308478E84003C84228C744A837DE`. Its loop slices training-window rows by `WINDOW_BATCH=8` and concatenates candidate tensors within those batches. That historical W1/N2 reference trainer is absent from the frozen hosted civilian manifest. The budget correctly labels adoption as planned; this review does not claim the formal civilian trainer or B/C/D integration exists.

`120 * sum(K_i)` is candidate sample visits under that planned training loop, not all model forward calls or ledger candidate evaluations. The separate formal model-evaluation and forward-call fields remain null even after supplying candidate catalogs. Conditional development prediction rows and reference-only target/checkpoint counts are distinctly labeled. Catalog counts must be positive and include the legal NOOP; zero-catalog and inconsistent window/count inputs reject.

For D, two methods × three seeds × eight smoke rounds × 16 PPO updates gives **768 smoke updates**; the 32-round total is **3,072 updates including smoke**, leaving **2,304** afterward. Four episodes per round gives **192 smoke episodes** and **768 total episodes**. These are PPO counts, not WM counts. Confirmation is `24 * (3 + 3 + 1) = 168` trajectories. Parent bootstrap uses 10,000 resamples and seed 20261014; 240,000 parent draws and 1,680,000 trajectory slots are arithmetic resampling units, not independent study samples.

Formal episode horizon remains null. The calculator's default formal PPO and confirmation minute-step totals remain null. Its separately named 60-minute reference values, 11,520/46,080 PPO steps and 10,080 confirmation steps, are conditional diagnostics. Supplying an explicit horizon calculates conditional products; it does not approve or freeze that input. The fixed 16-update PPO schedule is a protocol planning count; adopting a different formal rollout length still requires compatible formal trainer design.

For B, `sum_i K_i * min(30, max(0, H-t_i))` now explicitly bounds **candidate-continuation paths only**. It excludes paired NOOP-reference continuation and reconstruction/restore/prefix work. Complete B ledger environment steps and those overheads remain null, including when an explicit horizon and catalogs are supplied. No unsupported factor of two is assumed. With synthetic catalogs and H=60, the independent probe gives candidate-only split bounds 88/30/90 and keeps the complete B total unknown. The conditional 94 context scans are separately described and do not turn into an approved total execution cap.

Linux CPU/wall, RSS, checkpoint/export bytes and other empirical resource costs remain null. The cited local calibration is correctly marked `OBSERVATIONS_ONLY_NOT_RESEARCH_BUDGET`; no aggregate Windows observation is decomposed into unit costs or extrapolated into a formal authorization.

## Validation and remaining work

One bounded run of the independent pure calculator probes passed after final freeze. It checked exact artifact/source hashes, default unknowns, formula boundaries, positive NOOP-inclusive catalogs, fixed PPO/confirmation counts and conditional horizon examples. It imported no Torch or training code and performed no experiment, SSH action or authorization creation/consumption.

Formal approval still requires frozen split identities/admission rules and horizons, an implemented and reviewed civilian training/prediction schedule, complete candidate/reference/restore workload accounting, checkpoint/export work and target Linux whole-cgroup calibration. Those omissions are explicit outstanding budget inputs, not zeros or approved placeholders. Hosted acceptance and the wider Stage A gate remain incomplete.
