# N02 正式交付索引

索引基准目录：`development/n02_cost_chain_repair_engineering_release_20261016_r2_closed_db_fix_final/`。本包描述一项正式执行及其既有证据；不包括本次新增训练或远端操作。

| 路径（相对基准目录） | 内容 |
| --- | --- |
| `FINAL_RESULTS_ZH.md` | 中文正式结果报告。结论为正式运行闭环完成，但实际使用 L0、未启用图消息传递，图 GPPO 目标未完成。 |
| `FINAL_INDEPENDENT_REVIEW.md` | 独立工程、预测与决策链路审查；包含 L0/L1 架构偏差、辅助 adapter 更新、世界模型冻结、结果及资源范围判断。 |
| `FINAL_INDEPENDENT_HASH_AUDIT.json` | 机器可读 hash 审计；记录 package manifest、export payload、sources、prior evidence、snapshot 和 SQLite work-call 核验。 |
| `MEASURED_FINAL_INDEPENDENT_REVIEW.md` | 前序测量来源与正式授权绑定审查；明确先前测量只覆盖 input_admission。 |
| `FINAL_DELIVERABLE_INDEX.md` | 本索引。 |
| `FINAL_DELIVERABLE_SHA256SUMS.txt` | 本次交付 SHA-256 清单，基准目录为本索引首行所述目录；按设计不包含该清单自身。 |

## 正式运行证据

| 子目录 / 文件 | 用途 |
| --- | --- |
| `final-formal-run-evidence/authorization.json`、`authorization-validation.json`、`FINAL_FORMAL_AUTHORIZATION_CONTRACT.json` | 一次性授权 envelope、验证回执与冻结合同。 |
| `final-formal-run-evidence/preflight_receipt.json`、`diagnostics/n02-v5-cost-repair-engineering-20261016-r2-closed-db-fix-final/preflight_receipt.json` | 提交前静态身份/环境预检证据。 |
| `final-formal-run-evidence/handoff.json`、`submission.txt`、`systemd-terminal.json`、`journal.txt` | systemd 交接、正式提交及终态/journal 回读。 |
| `final-formal-run-evidence/run-once/systemd_context.json`、`systemd_handoff.json`、`systemd_submission.json`、`authorization_consumed.json` | attempt、InvocationID、授权消费与 unit 绑定。 |
| `final-formal-run-evidence/run-once/receipts/01-*.json` 至 `07-*.json` | 七阶段 driver 收据，含状态、错误字段、结果与分阶段资源记录。 |
| `final-formal-run-evidence/run-once/guardians/01-*.json` 至 `07-*.json` | 七阶段 guardian 收据及 worker exit/error 信息。 |
| `final-formal-run-evidence/run-once/resource-ledger.jsonl`、`work-calls.sqlite3`、`worker-phase-accounting.jsonl`、`worker-phase-protocol.jsonl`、`supervisor-phase-protocol.jsonl` | 外层资源账本、work-call 数据库及阶段协议/会计原件。 |
| `final-formal-run-evidence/run-once/runtime_admission.json`、`console.log` | 运行时绑定记录及 supervisor 输出。 |

## 导出内容

canonical export 为 `final-formal-run-evidence/run-once/export/n2_integration_smoke/`。`export_manifest.json` 声明 15 个 payload，payload 合计 5,221,026 bytes；另有 manifest 与 `resource_ledger_snapshot.json`。原件和 checkpoint 副本位于 `final-formal-run-evidence/run-once/n2_pipeline/`。

15 个声明 payload：

- `checkpoint_restore_receipt.json`、`collection_receipt.json`
- `development_evaluation_receipt.json`、`development_windows.json`、`graph_policy_training_receipt.json`
- `parents.json`、`training_branches.jsonl`、`training_windows.json`、`world_model_training_receipt.json`、`world_model.pt`、`strict_restore_subprocess.json`
- `checkpoints/G/round_01.pt`、`checkpoints/G_WM/round_01.pt`
- `rollouts/G/round_01.jsonl`、`rollouts/G_WM/round_01.jsonl`

## 绑定的代码与输入

- `package/civilian/n2_stage_pipeline.py:1461`、`:1462`、`:1596` 与 `package/civilian/graph_policy.py:416`、`:443`：核实训练和开发重建路径均选择 L0；L0 不执行 Literal message passing，L1 分支才调用 attention/task-update。它们是架构偏差结论的只读来源。
- `package/civilian/registered_data/input_registry.json`：注册输入主表，SHA-256 为 `e4e9046890c6e2935bdf1ed02e77cbf250ba074ddd4ffcb4ab8a0fad0eeefd55`。
- `package/civilian/registered_data/data/train/n02-train-base-00-f8f0f2ea820d8265.json`、`package/civilian/registered_data/data/train/n02-train-carrier_competition-01-f9079eaafa67c7d7.json`、`package/civilian/registered_data/data/development/n02-development-carrier_competition-00-f8c58727a4bffd36.json`：本次 2 个训练和 1 个开发场景。
- `package/civilian/registered_data/fixtures/causal_allocation_case.json`：双动作因果 fixture；静态构造和字节绑定已验证，正式运行未留下 replay 或实际标签差值回执。
- `package/civilian/PRIOR_RESOURCE_COST.json` 和 `package/civilian/resource_cost_evidence/n02-cost-measurement-20261016-r2-closed-db-fix/`：先前 input_admission bootstrap 成本证据。

## 完整 hash 审计

`FINAL_INDEPENDENT_HASH_AUDIT.json` 记录 53 项 package manifest、15 个 export payload、resource-ledger snapshot、40 个导出 source 引用、7 个 prior evidence 引用，以及 formal evidence 文件的实测 hash；独审结论为所有声明 hash 检查通过。SQLite 检查为 1,347 次 work-call 全部 complete。`FINAL_DELIVERABLE_SHA256SUMS.txt` 为此次报告、索引及主要运行证据的便捷校验清单；完整源文件覆盖以机器可读 hash audit 为准。

报告明确限制：unit 终态回读时已被 systemd GC，不能将日志区间当作精确 wall 总时长；独立审查确认开发集排序 pair_count=0、accuracy=null，G/G-WM 结果一致且无决策增益证据。
