# N02-v5 正式运行结果

## 结论

本轮一次性授权已通过 v5 gate 校验，并由远端 systemd 接收。服务在训练 worker 启动前失败退出；没有采集或训练更新，也没有形成资源账本、SQLite 或结算。首错为运行时资源成本门禁拒绝执行。该 attempt 已消费，未重提。

## 授权与交接

远端无授权 preflight 收据为 `accepted`，运行时为 Python 3.11.16、PyTorch 2.7.0+cu128、NumPy 1.26.0；CPU affinity 为 `[0]`，CUDA 未初始化，systemd user manager 与规定的资源属性检查通过，且 `training_started=false`。

正式授权使用 `n02-v5-formal-run-authorization/1`，绑定请求摘要 `bf81982f...cd7ca79`、attempt `n02-v5-formal-auth-binding-once`、preflight 收据摘要 `b607e3c0...ec9600`，范围为 `n02-v5-full-pipeline-once`。本地调用实际 `validate_authorization_document` 返回 `authorized=true`。唯一服务的 InvocationID 为 `d26c70718c2d4cbaaa67f87269a291df`；授权消费和 systemd submission 收据均为 `submitted`。

## 首错与更新数

`process_guardian.py:1028` 抛出：

```text
PermissionError: N2 pipeline execution requires a measured prior resource-cost receipt
```

冻结包内 [PRIOR_RESOURCE_COST.json](../package/civilian/PRIOR_RESOURCE_COST.json) 标记 `status=no_current_engineering_runs`、`measurement.status=pending`、没有有效的 `validated_receipt`，并明确 `pipeline_execution_allowed=false`。因此正式服务在建立正式 pipeline run ledger 之前停止。

实际世界模型更新数为 **0**，PPO 更新数为 **0**。没有证据表明训练 worker 已启动。环境步数未形成账本，记为未计量，不能从本次运行结算。

## 终态与资源口径

同一 unit 的终态为 `ActiveState=failed`、`SubState=failed`、`Result=exit-code`、`ExecMainStatus=1`。systemd 记录该 unit CPU 使用 **1.706205 秒**。journal 从服务启动到退出约 **1.740294 秒**。这些只覆盖 systemd unit；没有 worker 账本或结算来覆盖完整 CPU、环境步、存储和其他资源，因此本轮资源结算不完整。

取回的 run 目录只有 `authorization_consumed.json`、`systemd_submission.json`、`systemd_handoff.json` 和 `console.log` 四个文件。没有 SQLite、训练 checkpoint、阶段收据、pending 文件或 settlement/export 文件。终态、完整 journal 与关键文件摘要记录在同目录 `first-error-evidence.json` 中。

## 交付状态

本轮到达的最后阶段是正式 systemd handoff；后果采集、世界模型训练与恢复、G/G-WM 训练、开发评价以及结算/导出均未开始或未完成。因为授权是一次性的且已经消费，本报告只记录该次失败，不创建第二个 attempt、不重提服务。

正式授权文件 SHA-256：`14fa69cf64d51c1f5aa1631af9a4da926126107378dbd97e6ae9a7491d701837`。机器可读首错证据 SHA-256：`0f4c1bc673d2dbe5e1212bcbe40e9a7abd3d7de4abbc05c4b0e7ed983ab17766`；本报告 SHA-256 随交付消息提供。
