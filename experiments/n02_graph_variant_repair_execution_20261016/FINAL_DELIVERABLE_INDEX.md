# N02 L1 最终交付索引

本索引对应本地 execution 目录 `development/n02_graph_variant_repair_execution_20261016`。完整原始证据仍保留在本地；公开归档只收录报告、索引和必要的非敏感结果制品。

## 四份最终报告

| 文件 | 用途 |
|---|---|
| `FINAL_RESULTS_ZH.md` | 中文正式结果、身份、L1 图参数、WM frozen、strict restore、评价、资源与边界 |
| `FINAL_INDEPENDENT_REVIEW.md` | Sol 静态审核和本地正式证据的独立复核结论 |
| `FINAL_DELIVERABLE_INDEX.md` | 本索引、保留/排除边界和复核路径 |
| `HASHES.sha256` | 必要制品与回执的 SHA-256 清单；不包含自身摘要 |

## 归档建议保留的必要制品

以下文件不含授权正文、密钥或 SQLite，足以复核主要结果：

- `measured-final-deployment-evidence/deployment_receipt.json`
- `measured-final-deployment-evidence/identity.txt`
- `final-formal-run-evidence/run-once/n2_pipeline/world_model_training_receipt.json`
- `final-formal-run-evidence/run-once/n2_pipeline/graph_policy_training_receipt.json`
- `final-formal-run-evidence/run-once/n2_pipeline/checkpoint_restore_receipt.json`
- `final-formal-run-evidence/run-once/n2_pipeline/development_evaluation_receipt.json`
- `final-formal-run-evidence/run-once/n2_pipeline/strict_restore_subprocess.json`
- `final-formal-run-evidence/run-once/export/n2_integration_smoke/export_manifest.json`
- `final-formal-run-evidence/run-once/export/n2_integration_smoke/resource_ledger_snapshot.json`
- `final-formal-run-evidence/run-once/resource-ledger.jsonl`
- `final-formal-run-evidence/run-once/n2_pipeline/checkpoints/G/round_01.pt`
- `final-formal-run-evidence/run-once/n2_pipeline/checkpoints/G_WM/round_01.pt`
- `final-formal-run-evidence/run-once/n2_pipeline/world_model.pt`

checkpoint 与 world-model 文件是必要结果制品，不包含授权内容；其身份见 `HASHES.sha256`。如果公开仓库策略禁止二进制模型，则保留其 hash 和报告，模型仍留在本地证据目录。

## 明确排除

- `FINAL_FORMAL_AUTHORIZATION_CONTRACT.json`、`authorization.json`、`authorization-validation.json`、`authorization_consumed.json` 及任何授权正文；
- `deployment-package.zip`、临时 zip、锁文件、密钥、凭据、主机/用户运行路径和未脱敏远程日志；
- `work-calls.sqlite3`、`__pycache__`、`*.pyc`；
- 原始 `journal*.txt`、`console.log`、systemd handoff/submission/context 和 worker/supervisor protocol 日志；
- 完整巨型阶段 receipt、rollout JSONL、训练分支/窗口原始轨迹，除非后续公开审核明确批准。

排除项仍在本地正式证据目录中，不从本地删除，也不改变其 SHA-256。

## 复核入口

- 工程与执行结果：`FINAL_RESULTS_ZH.md`；
- 独立审查：`FINAL_INDEPENDENT_REVIEW.md` 与 `REVIEW.md`；
- checkpoint/WM 结构：两个 `.pt` 与 `graph_policy_training_receipt.json`；
- strict restore：`strict_restore_subprocess.json` 与 `checkpoint_restore_receipt.json`；
- 配对开发评价：`development_evaluation_receipt.json`；
- 资源结算：`resource-ledger.jsonl` 与 `resource_ledger_snapshot.json`；
- 导出完整性：`export_manifest.json`。

## 归档协议

目标仓库为 `Battleplus/2026_10.10_GPPO` 的归档分支 `archive/n02-v5-preflight-20261016`。归档提交只应包含本索引列出的报告和必要制品；提交前应逐文件重算 SHA-256、运行仓库既有公开检查，并在推送后核对远端 commit/ref。冻结 release、旧证据和本地敏感文件不得被重写。
