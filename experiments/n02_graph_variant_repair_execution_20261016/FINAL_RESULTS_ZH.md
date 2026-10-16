# N02 L1 图变体修复正式结果

日期：2026-10-16。本文只报告已经完成的一次 CPU-only L1 正式 run；不把它扩展为算法优越性结论。

## 结论

工程闭环 **PASS**。冻结 L1 release 通过部署后 preflight，唯一正式 systemd unit 正常结束，七阶段回执均成功（第一阶段为 `accepted`，其余阶段为 `complete`），资源账本结算成功，导出 manifest 完整。训练、恢复、评价和导出均有本地证据。

算法结果只支持“本次最小配对开发评价中两 variant 相同”。G-WM 没有相对 G 的开发环境收益差异；本报告不声称图策略或世界模型已经改善救援效益，也不声称跨规模泛化。

## 运行与身份

| 项目 | 值 |
|---|---|
| release | `ch2_disaster_relief_n02_graph_variant_repair_l1_20261016` |
| release manifest | `3aaf0ddb966edbd64bf9da7cc6998774f30c0370fbf6ae8e1b5e4752eeed063f` |
| hash bundle | `f05eb10cb758d0da2052d3c4b92a581001db0134a634942f8656387f0121d06d` |
| request / attempt | `76fa3f23191a46a19efa37f43dad657dfcbaa574822b790d06e92d322404146f` / `21a213d2832cfd9fc77c482d4fd75455ee305354d77c16caede427886be9b90f` |
| deployed source / archive | `b9dbd9417a4fd6c7f797295133d357d80a2fbe6ea3fa4b4ecff76351c42fd3d6` / `56645fbb6d047c9915b4327786b482529a0ae8bf4b40e40dcba5166c9cd04cc1` |
| formal run | `n02-l1-graph-variant-repair-run-20261016-01` |
| systemd unit | `n02-v4-n02-l1-graph-variant-repair-run-20261016-01.service` |
| invocation ID | `66dd44280c67427faaddb196dc9a4b09` |
| terminal result | `success`, `ExecMainStatus=0` |

部署 preflight 记录 CPU affinity `[0]`、CUDA 未初始化、Torch threads/inter-op threads 为 `1/1`。formal run 的最终 systemd 摘要中 `CPUUsageNSec=[not set]`，因此不能用 systemd CPU 字段替代阶段账本。

## L1 图策略证据

两个 checkpoint 均为 round 1，G 和 G-WM 各有 8 次 PPO optimizer updates，共 16 次。policy state 各含 65 个条目，关键真实图结构参数包括：

- `base_policy.node_encoder.*`、`node_type_embedding.*`；
- `base_policy.literal_attention.attention`、`uav_transform`、`self_neighbor_transform`、`task_edge_transform` 和 `gate.*`；
- `base_policy.task_update.predecessor_mlp.*`、`successor_mlp.*`、`uav_mlp.*`、`self_mlp.*` 和 `fusion_mlp.*`；
- `base_policy.pair_actor.*`、`noop_actor.*` 和 `critic.0/2.*`。

两 variant 的 receipt 都写明 `world_model_frozen=true`。checkpoint 中的 WM 张量逐项相等，且与独立 `world_model.pt` 的 `model_state` 逐项相等，最大差为 0。

critic 的 optimizer state 可直接映射到四个 critic 参数（IDs 10--13）：G 和 G-WM 均为 `step=8`，`exp_avg` 与 `exp_avg_sq` 均非零。例如 `critic.0.weight` 的 `exp_avg` 绝对值和分别为 `2.3137302399` 与 `1.9642304182`，`critic.2.bias` 分别为 `0.0894559026` 与 `0.0725161135`。训练 receipt 同时记录了非零 gradient norm、actor loss 和 value loss：

| variant | gradient norm mean / max | actor loss | value loss |
|---|---:|---:|---:|
| G | `0.3210175205` / `0.4921717048` | `-0.0059864726` | `0.5736628473` |
| G-WM | `0.4477209002` / `0.8316887021` | `-0.0066581755` | `0.5704251304` |

G-WM PPO 阶段记录 480 次 prediction-cache hit、0 miss、0 次额外 WM forward；训练阶段总 WM candidate evaluation 为 139，WM forward 为 120。

## 严格恢复与世界模型诊断

strict restore 子进程为 `status=complete`，4 次 prediction forward 和 4 次 candidate evaluation 均完成，Torch threads/inter-op threads 为 `1/1`，CUDA 未初始化。正式代码对同一组 `training_windows` probe 做 parent/child 比较，4 组 prediction hashes 均 exact match；这就是本报告所称的 strict same-probe exact。development windows 的摘要不是这组 probe，不能把不同 probe 的 digest 交叉比较。

世界模型 checkpoint 的诊断结果为：全局 MAE `0.0793732250`，没有有效的非平局 ranking pair（`pair_count=0`，ranking accuracy 为 unknown）。各 global head MAE：energy `0.1481850371`、global utility delta `0.0636360887`、other-order lateness `0.0183906471`、reassignment `0.1345732138`、unmet demand `0.0320811383`。这些是小规模诊断指标，不是收益证明。

## 开发评价

development evaluation 为 2 episodes、120 environment steps、60 policy decisions per episode，匹配 variant 为 `G` 和 `G-WM`。配对的 energy、inspection-on-time rate、weighted-on-time-delivery-rate 差异均为 `0.0`。该评价是诊断性开发评价，不是多 seed 或大规模确认实验。

## 资源结算

导出的 `resource_ledger_snapshot.json` 标记 `all_successful=true`，总计 CPU `22.582237053 s`、wall `30.429306381 s`，上限分别为 900 s 和 1800 s。快照阶段 CPU/wall（settlement 自身尚未计入快照总账）为：

| stage | CPU s | wall s |
|---|---:|---:|
| input_admission | 4.261134729 | 4.922908401 |
| paired_consequence_collection | 2.558264697 | 4.430270092 |
| world_model_training | 0.848525589 | 0.929076093 |
| checkpoint_restore | 0.048108700 | 1.784405666 |
| graph_policy_training | 12.838491929 | 15.401793873 |
| development_evaluation | 2.027711409 | 2.960852256 |

worker stage snapshot 的 RSS 峰值为 `684748800` bytes；外层 guardian ledger 的 RSS high-water 为 `1646800896` bytes。原始 `resource-ledger.jsonl` 另有 settlement entry（CPU `0.234507667` s、wall `0.834763972` s）；它与导出快照的 cutoff 口径不同，不能重复相加到快照总计。systemd 没有提供可用 `CPUUsageNSec`，所以完整资源结算以阶段 receipt/ledger 为准。

work-call export 的 failed/pending 均为 0；导出 manifest 为 15 个文件，payload `5304625` bytes，manifest SHA-256 为 `4d33088208eec5b22b2f06b91cb25377e0224feedfb3ec31a71a8fe9d657e85a`。

## 边界

本次只有一个训练 seed、一个 round 和两个 development episodes。G-WM 与 G 的开发差异为零，只能说明本次配对窗口未观察到差异；不能说明世界模型无效，也不能说明图模型优于非图基线。严格恢复的 exact 结论限定于代码实际比较的同一组 `training_windows` parent/child probe；development windows 是另一组诊断 probe。部署与执行回执中的敏感授权正文、远程运行路径和主机信息不作为公开交付内容。
