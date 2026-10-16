# v5 实际正式尝试独立终态审核

审核日期：2026-10-16。审核对象为本目录 `v5-formal-run-evidence/` 中已经导出的本地证据，以及用于解释抛出位置的本地只读源码。审核者为独立子上下文 `/root/v5_result_audit`。本审核未连接服务器、未修改源码、未启动或重试研究，仅新增本报告。其他执行者可能同时写入材料；本报告不撤销其修改。

## 总体结论

本轮确实完成了单次 systemd 提交，并已进入失败终态。正式七阶段管线没有启动 worker，也没有得到训练、预测或决策结果。失败原因是冻结包中的既有资源成本状态仍为 pending，且明确禁止 pipeline execution。不能将这次提交、短暂 active 状态或 accepted preflight 报为全链成功。

提交前的检查未识别这一真实的成本收据接线阻断。正式授权绑定修复能够走到 systemd 提交，但该事实不足以证明运行资格链已经接通。

## 可追溯终态证据

| 核对项 | 本地证据及判断 |
| --- | --- |
| 唯一尝试 | `n02-v5-formal-auth-binding-once`；unit 为 `n02-v4-n02-v5-formal-auth-binding-once.service`。名称保留 v4 前缀，但 journal 命令指向 v5 package。 |
| InvocationID | `handoff.json`、`run-once/systemd_handoff.json`、`run-once/systemd_submission.json`、`run-once/authorization_consumed.json`、`systemd-terminal.json` 和 `latest-systemd-show.txt` 均为 `d26c70718c2d4cbaaa67f87269a291df`。 |
| 提交和短暂运行 | handoff 记录 PID `970045`、`active/running`；它是交接时快照。 |
| 最终状态 | terminal 和 latest show 均为 `ActiveState=failed`、`SubState=failed`、`Result=exit-code`、`ExecMainStatus=1`、`MainPID=0`、空 ControlGroup。`submission_error=null` 仅说明提交无报错。 |
| journal | 2026-10-16 12:14:38.257407 +08:00 Started；12:14:39.997038 主进程 `status=1/FAILURE`；随后记录 failed。与 terminal 同一 unit，CPU 记录吻合。 |
| console | `process_guardian.py:1028` 抛出 `PermissionError: N2 pipeline execution requires a measured prior resource-cost receipt`。 |
| 文件身份 | 本地 `authorization.json` 文件 SHA-256 为 `14fa69cf64d51c1f5aa1631af9a4da926126107378dbd97e6ae9a7491d701837`，与 handoff/submission/consumption 一致；preflight 文件 SHA-256 为 `b607e3c07b48c3647cb4fab0ace2607709dd4bdff080240bd06b85f9d7ec9600`，与引用一致。 |

`authorization-validation.json` 的 `authorization_sha256=a0bb4f…` 是授权文档去掉其自摘要字段后的正文摘要；submission 使用完整文件摘要 `14fa69…`。本地源码分别采用 `_body_digest` 和 `sha256_file`，因此这两个值不同不构成本次身份链矛盾。

`journal.stderr.txt` 为空。导出的 `run-once/` 只有以下四个文件：

```text
run-once/
  authorization_consumed.json
  console.log
  systemd_handoff.json
  systemd_submission.json
```

导出树中没有 `resource-ledger.jsonl`、`work-calls.sqlite3`、worker phase journals、阶段 receipts、checkpoint、模型或评估产物。单靠本地缺失不能排除未导出的任意服务器文件；但 traceback 对应的源码顺序进一步支持本次入口在 worker 启动前退出：资源成本拒绝位于 line 1028，ledger 路径初始化从 line 1031 开始，StageServer 和 `subprocess.Popen` 则更晚。因而“未进入训练”的结论不只依赖目录缺失。

## 四维结论

| 维度 | 独立审核结论 |
| --- | --- |
| 工程 | **提交与终态留证通过；正式全链执行失败。** 授权已记录为 submitted/consumed，同一 InvocationID 的终态可追溯。`PRIOR_RESOURCE_COST.json` 的 `measurement.status=pending`、`validated_receipt=null`、`pipeline_execution_allowed=false` 与实际拒绝完全吻合。preflight 的 accepted 验证了目标运行环境和 systemd 条件；其 `training_started=false`，且该检查未消除正式执行所需的 measured prior receipt。 |
| 预测 | **没有可评价的本轮预测结果。** 未进入 worker/世界模型阶段，没有预测指标、误差、缓存或候选评估证据，不能据此声称预测能力改善或退化。 |
| 决策 | **没有可评价的本轮决策或策略结果。** 无 PPO 更新、训练 episode、development evaluation、baseline 对比或灾害救援效益数据。此终态不支持方法有效性结论。 |
| 下一步 | **保持本次终态与一次性消费证据，先修正真实成本收据链。** 找到并验证真实目标运行工程成本的来源、范围和身份绑定，将其按既有协议接入可执行资格链。不能把已知零消耗、pending 或外部形式授权当作 measured resource receipt，也不能仅翻转许可布尔值。若该修正改变冻结包或既有身份，按既有身份和授权协议形成后续新尝试；本次不重放。 |

本报告建议只针对已经发生的成本收据链问题，不扩大为新的防御性增强或研究任务。

## 资源结论及边界

- systemd 的 `CPUUsageNSec=1706205000`，即 **1.706205 CPU 秒**；journal 四舍五入为 1.706 秒。它是该失败 unit 的 CPU 记账，不是完整研究成本。
- journal 的 Started 到主进程退出约 **1.740 秒**，仅为日志时间差；不能替代正式 wall receipt，也不覆盖前置 preflight、发布、授权生成、连接或导出工作。
- 授权预算列出了 wall 1800 秒、CPU 900 秒、RSS 4 GiB 和工作/导出各 1 GiB；这些都是上限。preflight 的 `MemoryMax=4G`、`TasksMax=64` 是配置证据，不是峰值测量。
- 本地终态未包含峰值 RSS、峰值/最终磁盘用量或统一资源 ledger；不能填报为零或给出完整累计实际成本。本轮 CPU 值也不能被冒充为允许正式研究启动的既有 measured prior receipt。
- 本审核依赖当前导出的本地材料，没有独立远程实时进程盘点，亦未重跑测试、模型或研究。

## 执行报告交叉核对

原始证据审核完成后，已读取执行者 `v5-formal-run-evidence/FORMAL_RUN_REPORT_ZH.md` 和 `first-error-evidence.json`。执行报告关于一次性提交、同一 InvocationID 失败终态、资源成本门禁首错、worker 前停止、世界模型/PPO 更新为零、无 ledger/SQLite/结算、资源计量不完整的结论与原始材料和源码顺序一致。世界模型/PPO 的零更新数是入口提前终止所支持的控制流结论；环境步数仍保留未计量，不能把缺失账本写成正式结算零值。

机器证据引用的 11 项文件摘要均已逐项复算一致，`first-error-evidence.json` 自身 SHA-256 为 `0f4c1bc673d2dbe5e1212bcbe40e9a7abd3d7de4abbc05c4b0e7ed983ab17766`，与执行报告一致。执行报告的 1.740294 秒以 journal 的 Starting 行至退出行计差；本报告约 1.740 秒不作为正式 wall receipt。交叉核对未发现改变上述四维结论的矛盾。
