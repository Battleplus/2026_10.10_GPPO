# N02 成本链修复准备

## 当前结论

v5 的成本拒绝是正确的：`PRIOR_RESOURCE_COST.json` 明确为 pending，`_read_prior_resource_cost()` 返回 `execution_allowed=false`。正式 `driver.py --run` 当前是在 systemd handoff 后由 guardian 拒绝；候选 diff 把同一个既有判断前移到 systemd 提交之前，输出明确的 `blocked_pending_prior_resource_cost`，不将 pending 转成 measured。

v5 目前没有一条可由公开 CLI 启动的成本测量 bootstrap。`--preflight` 只验证 runtime/systemd 并写 admission 证据；`process_guardian.run_guarded_pipeline(preflight_only=True)` 已具备可复用的真实阶段计量，但现有 `driver.py` 没有把公开 preflight 路由到该 guardian。`_run_engineering_smoke()` 没有调用点，而 CLI 明确拒绝旧 `--engineering-smoke` 模式。候选 [engineering_cost_bootstrap.py](engineering_cost_bootstrap.py) 将这一小段现有 guardian 路径接入独立 systemd 工程单元；不增加训练或新调度框架。

## 候选改动

`patch-v5-minimal.diff` 只做三件事：把 `resource_supervisor.py` 和 pending 状态文件中的 stage protocol 统一到 manifest 已用的 `n02-integration-smoke-v4-100x100/seven-stage`；在正式 systemd handoff 前报告 pending 并退出；保留 pending 的 measurement/gate 值。新 helper 和 receipt writer 留在本候选目录，应用到后续新 release 前还须进入其发布清单。

## 工程测量入口

后续单独获准后，在修复候选 release 上部署 helper，以目标 Python 运行 `engineering_cost_bootstrap.py --launch`。helper 为新鲜 diagnostics work root 创建一个新的 systemd user unit，设置 `Restart=no`、`KillMode=control-group`、CPU/内存 accounting、`MemoryMax=4G`、`TasksMax=64`、270 秒 wall 上限及 36% CPU quota。随后由这个 systemd unit 调用已有 `run_guarded_pipeline(preflight_only=True)`；worker 只运行 `input_admission`，随后正常退出。36% quota × 270 秒给出约 97.2 CPU 秒的服务上界，留在拟申请的 100 CPU 秒以内。若 systemd 不接受该配置、超限、未成功退出或证据缺失，receipt writer 拒绝生成 measured 收据并保留首错材料。

receipt writer 只接受同一 unit 的 `InvocationID`、成功终态、`ExecMainStartTimestampMonotonic`、`ExecMainExitTimestampMonotonic`、`CPUUsageNSec`，以及 guardian 生成的真实 `resource-ledger.jsonl`、stage receipt、guardian receipt 和部署 receipt。它按 v5 `/2` 校验器要求把 systemd wall/CPU 与 ledger 差额记入 `input_admission`，然后调用原校验器复核生成的 `/2` receipt。当前校验器允许 ledger stage 子集；最终收据显式标注只覆盖 `input_admission` 和同一 systemd unit 的退出尾部，不能说成测得七阶段成本。

后续申请的 workload 上限建议为 wall 270 秒、CPU 100 秒、RSS 4 GiB；这是 preflight 工程测量申请值，不是已授权额度或已经消耗额度。该单元不做模型 forward、训练、checkpoint、正式 attempt 或授权创建。现有正式 attempt 已消费，不能复用；该测量需新的工程运行授权和独立预算核定。

## 哈希范围

`resource-cost-carry-forward/2` receipt 的 `source_identity_sha256` 和 `deployed_package_archive_sha256` 引用**实际部署用于测量的前序 package**，并和其 `deployment_receipt` 做字节级字段一致核验。receipt 另外 SHA-256 绑定 ledger、systemd show、deployment receipt、measurement context、stage receipt 和 guardian receipt。receipt 不嵌入最终 release 的完整 manifest：最终 release 将在测量后收录 receipt 与证据、重新计算 package manifest/hash bundle/Request/Attempt，因此不会形成自摘要循环。

前序部署身份不等同最终 release manifest。后续封版必须确认测量使用的代码、stage protocol、runtime 与准备发布的代码一致，并在 receipt/证据加入后重新生成所有静态身份。当前 `/2` validator 仅交叉核对 receipt 和 deployment receipt 中的 source/archive 值，不自行将其与最终 manifest 比较；本候选不声称它具备该额外校验。

## 验证与限制

源文件哈希见 [source-hashes.json](source-hashes.json)。候选 helper 仅做语法检查和 CLI help 检查；不连接服务器、不提交 systemd unit、不构造模拟 measured receipt、不创建 authorization/token、不启动训练。`v5`、`v4` 和既有正式 attempt 均未修改。
