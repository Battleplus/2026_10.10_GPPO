# Source summary

Source artifacts were read locally and left unchanged:

- `.codex-tmp/n01-r2-formal-single-session-20261012.py` (old formal runner).
- `.codex-tmp/n01-r2-formal-single-session-20261012-1216.transcript.txt` (first-error transcript).
- `development/ch2_disaster_relief_n01_v1/n1/prior_cost_repair_r2/package/static_plan_r2.json` (frozen reader).
- `development/ch2_disaster_relief_n01_v1/n1/prior_cost_repair_r2/package/N01_FULL_EVALUATION_IDENTITY.json` and `n01_full_evaluation_stage_budget.json`.
- `development/ch2_disaster_relief_n01_v1/n1/prior_cost_repair_r2/research-executions/N01_R2_TARFIX_DEPLOYMENT_INDEPENDENT_REVIEW_20261012_ZH.md` (stable report and first-error conclusion).

The old transcript stops during preflight. Approval was not uploaded, no
`systemctl start` occurred, and no formal run or result exists. The repair
copies the frozen research payload into `release/` and binds it to a distinct
repair identity. Scenario bytes, six checkpoint bytes, and evaluation logic
are preserved; the evaluator identity constant, unit names/paths, stage-budget
identity, and reader identity/hash are reissued together. The prior identity
and approval are not resumed or reused.
