# N02 正式结果报告：闭环完成，但实际 L0 无图消息传递，图 GPPO 目标未完成

**结论：正式运行闭环完成，但本次实际使用的是 L0 策略，没有启用图消息传递，因此图 GPPO 目标未完成。** 本次证据支持 PPO 与世界模型辅助 critic 的正式集成烟测成功，不支持“图 GPPO 已跑通”或“世界模型带来决策收益”的结论。

## 正式运行

唯一正式 attempt 为 `n02-v5-formal-auth-binding-closed-db-fix-final-once`，systemd unit 为 `n02-v4-n02-v5-formal-auth-binding-closed-db-fix-final-once.service`，InvocationID 为 `932a9532c1da4c068127be4d066dbb02`。终态回执为 `Result=success`、`ExecMainStatus=0`、`submission_error=null`。七阶段按序完成：`input_admission` 为 `accepted`，其余六阶段均为 `complete`，各阶段 `first_error=null`。独立核对的 work-call SQLite 中 1,347 条记录全部为 `complete`，无 pending 或 failed calls。

运行绑定到注册的 2 个训练场景和 1 个开发场景，registry SHA-256 为 `e4e9046890c6e2935bdf1ed02e77cbf250ba074ddd4ffcb4ab8a0fad0eeefd55`。场景为合成民用救援数据，地图合同为 `relief-grid-100x100-v1`（100×100，1 km/cell），局部区域为 `[40, 40, 2, 2]`；初始分配来源为 `synthetic_initial_assignment`。因果 fixture 的构造和字节绑定已核验，但正式运行没有该双动作案例的 replay 或实际标签差值回执，因此不声称正式实测了两个动作的后果差异。

世界模型在 8 个训练窗口上完成 2 次 optimizer updates（预算上限 8），checkpoint 严格恢复子进程状态为 `complete`；checkpoint SHA-256 为 `1b9a9303af07a519f3e03302a54a4154063a196df93752715974de450fc13c0c`。G 与 G-WM 各训练 2 个 episode、各完成 8 次 PPO updates，合计 4 个训练 episode、16 次 updates。正式执行在 rollout 前检查两组 L0 actor 的候选 ID 和初始 logits 一致；训练回执中的 initial probability-ratio error 均为 0。没有单独保存初始 actor 全状态快照。

## 架构偏差

回执中的 `G`、`G-WM` 是运行标签，不能证明图消息传递实际启用。正式训练代码在 `package/civilian/n2_stage_pipeline.py:1461`、`:1462` 为两组都调用 `build_policy("L0", WM_SEED, device="cpu")`；开发评估的重建路径 `:1596` 也选择 L0。`package/civilian/graph_policy.py:443` 的 L0 分支执行 `entity_mlp` 残差，Literal attention 与 task update 只在 L1 分支执行。两个正式 policy checkpoint 均含 18 个 `base_policy.entity_mlp.*` tensor 键，均不含 `base_policy.literal_attention.*` 或 `base_policy.task_update.*`。因此本次比较是 L0 PPO 与 L0 + WM 辅助 critic，不是图消息传递开启的 G/G-WM 比较。该实现与任务书要求的“图消息传递开启”不一致。

独立 checkpoint 审核确认 G-WM 的 4 个辅助 adapter 参数均有 Adam step=8 且 `exp_avg_sq>0`，辅助输出层已离开零初始化；世界模型参数逐 tensor 与训练前状态严格一致。配对 actor 初始化断言通过。世界模型训练 rollout 使用 120 次 forward、139 次 candidate evaluations；PPO 阶段复用缓存 480 次、0 次未命中、0 次重复 forward。此证据支持辅助 critic 路径参与训练，但没有逐步预测到辅助 value 的数值分解或显式消融；同时基础策略为 L0，不能视作图策略验证。

下一节点应另建并独立验收新包，将训练和开发评估的两处 L0 构造切换到图消息传递实现 L1，检查导出 checkpoint 中的图参数，再以能产生有效多候选和非零排序对的场景验证外部性。随后按要求取得新的正式授权。本次不做代码改动、训练或重新提交。

## 开发集结果

同一个开发场景上，G 和 G-WM 各运行一个 60 步 episode。两组均完成 4 个订单，按时交付率和 inspection completion/on-time rate 均为 1.0；late、unmet、undiscovered 均为 0，新增分配 4、改派 1，能耗均为 11.551500870754841。三项配对差值（按时交付率、inspection on-time、能耗）均为 0。

| 运行标签 | 完成交付 | 按时交付率 | Inspection 完成率 | Inspection 按时率 | 能耗 | 迟交 / 未满足 / 未发现 | 新分配 / 改派 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| G | 4 | 1.0 | 1.0 | 1.0 | 11.5515008708 | 0 / 0 / 0 | 4 / 1 |
| G-WM | 4 | 1.0 | 1.0 | 1.0 | 11.5515008708 | 0 / 0 / 0 | 4 / 1 |

开发评价 receipt 明确标记为 `diagnostic-only`。世界模型全局头汇总 MAE 为 0.0793732250，global utility delta MAE 为 0.0636360887；utility 正向高估 4/4。排序有效配对数为 0，accuracy 为 `null`，所以没有候选排序有效性的证据。任务头 Brier 分数为 delivery 0.2497998066（16 个有效标签、覆盖率 2/3）、inspection 0.2164698429（8 个、覆盖率 1/3）、report 0.2610244751（8 个、覆盖率 1/3）。样本和候选数不足以支持泛化或预测可靠性结论。单场景、单次配对结果也没有显示 G-WM 决策增益。

## 资源账本

前序 `PRIOR_RESOURCE_COST.json` 只覆盖 `input_admission`，计入同一 unit 的 shutdown tail 后为 wall 3.653973 s、CPU 3.276935 s；它不是七阶段训练成本。当前正式阶段的 live ledger 七阶段合计 wall 29.859739188 s、CPU 22.839005178 s。加上前序 carry-forward 后，最终 pilot 累计为 wall 33.513712188 s、CPU 26.115940178 s。最终 guardian invocation 另记 wall 29.859739188 s、CPU 23.362832708 s，口径是 guardian 启动至 worker 退出，不含最终 receipt 写入；不要与阶段分配 CPU 相加或互换。

systemd journal 独立记载整个 unit 消耗 CPU 23.829 s；Started 到该日志记录的间隔约 30.362 s，只是日志时间间隔。终态回读时 unit 已被 systemd GC（`LoadState=not-found`、InvocationID 为空、`CPUUsageNSec=[not set]`），因此没有完整 unit 生命周期的精确 wall/peak-memory 计数，报告不据此声称硬限制全生命周期结算。阶段账本记录的峰值 RSS 为 1,645,547,520 B / 4 GiB，工作区峰值 8,425,355 B / 1 GiB，导出峰值 5,232,319 B / 1 GiB。console 总账和导出 snapshot 是较早截止点，不作为最终成本。另一次只读 OpenSSH 状态查询因 `Permission denied (publickey,password)` 失败且未重试；其资源成本未知，也不在上述正式账本内。

## 证据路径

正式控制与阶段原件位于 `final-formal-run-evidence/`；canonical 导出位于 `final-formal-run-evidence/run-once/export/n2_integration_smoke/`。独立工程与结果审查见 `FINAL_INDEPENDENT_REVIEW.md`，完整本地 hash 核对见 `FINAL_INDEPENDENT_HASH_AUDIT.json`。本文的交付索引与 SHA-256 文件说明在 `FINAL_DELIVERABLE_INDEX.md` 和 `FINAL_DELIVERABLE_SHA256SUMS.txt`。
