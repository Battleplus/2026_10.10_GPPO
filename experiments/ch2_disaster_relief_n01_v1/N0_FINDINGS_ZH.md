# N0 证据与机制审计

身份：`ch2-disaster-relief-n01-v1`。N0 只读既有民用证据；本阶段研究模型前向推理 0 次、优化更新 0 次。

## 已复核证据

输入为旧执行包提取后的完整轨迹、训练曲线、最终 checkpoint 和旧报告。`n01_evidence_audit.py` 对 56 个父场景 × 8 种方法共 448 条原始 trajectory 逐条调用事件重播审计：由 raw events 重建 task outcomes、报告时点、能耗、改派和库存守恒，并验证每分钟 transition 与公开候选身份。再独立按场景 delivery priority 和重播 task outcome 求优先级加权按时率，并逐项对比归档 audit 的 task rows、metrics 与 conservation。448 条均为 60 个分钟决策，独立重播和指标复算全部通过；脚本不读取旧 summary 聚合均值来计算主率。

6 个 checkpoint 均为 round 32、`training_complete=true`、`target_rounds=32`，元数据含 optimizer state；六份实际 SHA-256 与 checkpoint index 一致，source hash 数均为 26，data hash 一致绑定旧注册输入。N0 未载入模型做前向推理，也未写回权重。

独立轨迹宏平均主指标：C0 47.2712%，C1 97.0105%；L0-8201/8202/8203 分别 97.4105%、95.6708%、96.2817%，三 seed 宏均值 96.4543%；L1-8201/8202/8203 分别 95.9581%、95.6685%、97.1876%，三 seed 宏均值 96.2714%。这些是已查看的旧 evaluation 开发证据，不能作为 N1 独立确认集或算法泛化证据。

32-round 曲线和逐 seed 原始 JSONL 哈希见 `n0/training_curve_inventory.json`；旧交付图见 `research-executions/ch2-disaster-relief-graph-v2-20261011/plots/training_curves.png`。没有以曲线挑 checkpoint，所有 N1 使用六个冻结 final。

## 公开关系输入覆盖

| 关系/机制 | 输入编码或运行时状态 | N0 判定 |
| --- | --- | --- |
| 平台与任务实体及动态节点数 | platform/task node features、显式类型 mask；节点按公开 ID 排序 | 已表达；旧模型只验证旧小场景，N1 另验 4/6、8/12、12/18 动态尺寸 |
| 平台可达任务关系 | `UAV_TASK_EDGE`，候选 ID 与 (platform, task) entity pair 显式绑定 | 已编码，表示局限由消息传递结构表达 |
| 平台自关系 | `SELF_EDGE` | 已编码 |
| 任务先后/依赖边 | 环境 task 记录有 `discovered_by` truth，但图构造没有 task predecessor/successor edges；对应关系权重结构零并从有效容量计数排除 | 未编码；不能声称模型学会因果任务依赖 |
| 潜在订单及报告延迟 | 内部 truth 中存在；policy 只收到当前 public tasks；inspection report 收到后任务才进入 public set | 运行时边界已实现；延迟会改变任务公开时点 |
| 未来故障、库存损失、能量变化 | 环境 event tape，按公开报告时间更新 public mirror | 未来 tape 不暴露给 policy；只在事件报告后可见 |
| 公开 depot 库存及同批次竞争 | depot stock features、显式候选及 autoregressive remaining-stock mask | 已表达；旧生成器通常将初始 stock 补足声明需求，不能由旧结果推出库存竞争能力 |
| 原 Chapter-1 初始队列/外部承诺 | policy-facing snapshot queues；外区任务要求保持 snapshot owner | 已表达；不能混称为可全局自由调度 |
| 聚合多订单承运需求 | 独立候选的载重可行性；没有显式全局“运力分配”关系/背包边 | 部分表达；任务瓶颈或能力需由 N1 竞争压力测试区分 |

## 机制、表示和工程缺陷的区分

| 观察/待测风险 | 分类 | 证据边界 |
| --- | --- | --- |
| C0 在旧登记场景 unmet 明显高于 C1/学习策略 | 已观察任务规则瓶颈 | C0 固定初始队列、不接纳新发现订单；与 C1 可主动分配权限不同，不能解释成网络能力比较 |
| 大载荷任务可能无兼容 UAV，或外区 helicopter 受 locality/commitment 限制 | 可证物理/合同瓶颈，N1 逐任务复核 | capacity/locality 是仿真合同；candidate absent 的任务留在 demand denominator，不要求环境产生 dispatch rejection |
| 任务 predecessor/successor 关系没有图边 | 表示不足 | 代码显式不构造；不是训练轮次不足 |
| 原生成器逐商品把初始库存抬到声明总需求 | 场景覆盖不足 | 旧数据缺少初始库存竞争；N1 单独固定水库存为声明需求的 0.6 |
| 外区任务被 owner 锁定且不能借调 helicopter | 任务合同约束 | 该行为是已编码的 locality 规则，不归因于策略学不会 |
| N1 新尺寸造成 ID 引用不一致、重复或隐藏字段泄露 | 工程风险，待前置验证 | 若出现即拒绝评价并保留首错；不是结果性算法发现 |
| L1 在旧 56 parents 主指标未超过 C1/L0 | 已观察结果 | 三 seed、有限开发场景；不证明等价或图消息传递普遍无效 |

尚未观察到可在 N0 中归因于具体工程 bug 的证据。被独立审核指出的首要 N1 风险为扩规模 ID/ref remap 与 carrier capacity intervention；在 N1 前置验证失败时按工程缺陷记录，不把失败场景静默剔除。

## 输入哈希

见 `n0/input_hashes.json`、`n0/trajectory_recomputation.csv`、`n0/checkpoint_metadata.json`、`n0/training_curve_inventory.json`。旧正式轨迹归档原包 SHA-256：`9259d39d8c8ec1950b2f6b27376c30068594f8e39ac6e0e4b055a065d296e3c3`。
