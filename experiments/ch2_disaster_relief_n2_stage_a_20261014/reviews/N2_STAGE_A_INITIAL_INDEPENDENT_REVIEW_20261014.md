# N2 阶段 A 独立审核：初始依据与验收框架

审核日期：2026-10-14（Asia/Shanghai）。角色：GPT-6.1 Sol high 独立审核器；独立上下文，不参与工程实现。范围仅为阶段 A 的有限历史核验与工程验收框架。本报告不是实施通过收据、研究准入、预算批准或原主模型决定。未启动训练、远程运行或修改历史冻结包。

## 当前判定

**NOT VERIFIED / 阶段 A 未通过。** 执行器正在定位和实现；当前没有新 N2 源码冻结身份、工程测试收据、真实托管学习运行及资源结算可供实质审核。允许在独立工程范围继续实现和取证；不能启动阶段 B/C/D 的正式研究，不能复用旧授权。

## 已核验的有限历史证据

1. 完整读取用户交接：`C:/Users/ASUS/.codex/attachments/c0318911-b518-4deb-8164-e09f9c856b8f/pasted-text-1.txt`，SHA-256 `4a967e619735b0c870aa868f9dea0eb8e11e4880fb227f26e4981db414e71dbe`。阶段 A 必須贯通公共观察到候选、恢复、标签、WM、critic、PPO、评价与结算；工程最少 10 次 WM 与 2 次 PPO 更新；真实唯一入口/systemd/StageServer/BudgetLedger/结算/导出不可省略。
2. 基础结果报告 `E:/Z博士/research-executions/ch2-disaster-relief-graph-v2-20261011/reports/RESULTS_ZH.md`，SHA-256 `90cebe8f8ca3b024c2058df3c218285f73e06be079f3b563f1f7866836ed77ed`，及同目录 `results_summary.json` 支持 C0=47.2712%、C1=97.0105%、L0=96.4543%、L1=96.2714%，六个模型共 3072 optimizer updates、56 个父场景/448 轨迹。两个图策略对比区间跨零，报告明确没有世界模型。此次仅核验报告与结构化摘要一致，未重新运行 448 轨迹审计。
3. N1 最终独立审核 `E:/Z博士/research-executions/N1_FORMAL_RESULT_FINAL_INDEPENDENT_REVIEW_20261013.md`，SHA-256 `17ecca148d883c18064744b77dbe1a7a7b357a37dee545be0ae3673ed87fbe0a`；结果报告 `E:/Z博士/research-executions/n01_analysis_parallel_20261013/FINAL_N1_ANALYSIS_ZH.md`，SHA-256 `69dc7f861e0da7ce21fb1863d326cf1616e15edd4795ee82426299bdb74bda55`。支持 2800 唯一评价键（2240 heldout、560 development），全部轨迹独立重放、核心指标复算完成；承运竞争 L1-L0=0.006456（约+0.65pp）属探索线索，不能作为确认结论。此次未再次重跑 2800 轨迹。
4. **N1 运行并非正式 PASS**：同一最终审核明确 evaluation/export complete，但 shutdown failed，结算 `FAILED_PRESERVE_FIRST_ERROR`，`formal_result_claimed=false`。冻结 evaluator 将 admission ledger 的 `complete` 错读为必须 `accepted`，导致 shutdown 在 cgroup 扫描前失败。`E:/Z博士/research-executions/N1_SHUTDOWN_PROCESS_CLEANUP_GAP_AUDIT_20261013.md` 表明整个 systemd cgroup cleanup 仍 UNKNOWN，不能用子进程组 cleanup 或 failed 状态代替空 cgroup 证据。
5. `E:/Z博士/research-executions/ch2-disaster-relief-n01-v1/N1_NODE_DELIVERY_STATUS_20261012.md` 是早期尚未完成状态，不能作为最终 N1 状态。基础报告还明确 Type=oneshot 的 RuntimeMaxSec 无效、watchdog 未覆盖当次运行，因此新 N2 的墙钟外层保护必须现场验证。

## 阻断项及解除所需证据

以下均为当前待验证项目，不代表已发现新 N2 缺陷。

| 编号 | 阻断项 | 最低证据 |
|---|---|---|
| A01 | 公共/隐藏边界未验证 | 观察、候选、合法 mask、actor/critic/WM 输入各自字段白名单和数据流；仅改变隐藏需求、未来故障、未报告库存而公共状态相同的成对测试，证明以上公开输出相同；内部快照不得透传模型/replay 特征。 |
| A02 | 动态候选身份与顺序动作未验证 | candidate_key 构成和唯一性；parent/repeat/window/time/PublicPrefix/pre-action snapshot/source digest 绑定；动态数量/顺序动作/库存预留实例；重复、缺失、跨窗候选身份必须拒绝。不可沿用旧六任务/25候选布局。 |
| A03 | prefix 与 pre-action 恢复未验证 | flatten 前逐候选 PublicPrefix 一致性拒绝；pre/post-action 标记混用负例；同窗候选和 NOOP 从同一快照恢复；状态、库存、载荷、承诺、事件队列/RNG 恢复等价与配对外生过程；执行顺序不能改变标签。 |
| A04 | 标签语义与未知值未验证 | 实际分支轨迹复算当前运输/巡查按时、报告及时、其他订单新增过期、未满足、能耗/改派/全局效用及相对 NOOP 增量；C1 固定延续身份；无机会、NOOP、unknown 分别记录。30 分钟结束尚未决出的标签为 unknown，不能补零。 |
| A05 | event_signal 与 unknown 梯度未验证 | 0/1 合法值及 unknown 独立有效位/原因；有效数和排序非平局 pair 数；unknown 目标替换为极端/非有限占位不影响有效 loss/梯度的测试；unknown 标签不能参与监督 loss 或排序 pair；合法候选不能因未来标签 unknown 被过滤，critic 聚合合法性必须只来自公共合同。 |
| A06 | 排序置换一致性未验证 | 相同权重对候选置换，按身份对齐逐头预测；loss 和模型参数梯度按预设数值容差一致；排序 pair 按候选身份生成；预测/replay/策略整条链不能靠列表索引隐式对齐。 |
| A07 | 守恒、承诺及指标分母未验证 | 实际 pickup/load/move/unload/confirm 轨迹；库存损失、失败、载荷、预留的数量守恒；区域外承诺不被擅自重分配；失败/未报告运输需求仍在已冻结主指标分母的实例。 |
| A08 | PPO bootstrap 未验证 | terminal 与 truncation 各有可复算数值例；真实终止不给 bootstrap，时间截断应基于最后状态 value 按定义 bootstrap；episode 边界不能串联 GAE；环境 60 分钟若是任务真实终点须明确与采集截断区别。 |
| A09 | checkpoint 严格身份未验证 | 保存并恢复模型、优化器、布局、数据摘要、归一化及来源身份；恢复前后相同候选预测/下一步更新等价；布局、数据身份、归一化、头定义、缺失/额外张量不匹配的独立拒绝收据；禁止 strict=False 或仅比较张量形状。 |
| A10 | critic-first 接线未验证 | WM 冻结，actor 概率 detached，合法候选后果按身份聚合/归一化，仅进入辅助 value 分支，末层零初始化；G 同结构零输入；冻结 actor 不能被宣称即时获益；actor logits 不直接接 WM、无虚构 rollout/在线搜索。 |
| A11 | 真实工程学习路径未完成 | 独立工程场景 manifest 和新工程身份；实际至少 10 WM/2 PPO optimizer steps、逐步计数/有限 loss/梯度、checkpoint 保存恢复预测、评价轨迹审计；必须由同一实际工程调用贯通，而非独立 synthetic worker。工程消耗单列、不作研究效果证据。 |
| A12 | 托管、结算与导出未完成 | 新目标准入（Python/Torch/NumPy、CPU 单线程、GPU 禁用、部署 hash）；唯一入口和 unit readback、InvocationID、systemd 外层墙钟保护；StageServer 状态/receipts、BudgetLedger 调用与资源、导出 hash；shutdown 状态字段正确，MainPID/ControlPID 和 cgroup.events populated/procs/threads 或明确 cgroup 不存在；evaluation 完成不等于 invocation PASS。 |
| A13 | 额度和失败状态未冻结 | 工程预先额度及采集/分支步/WM 更新/预测/PPO/checkpoint/export 各项上限、CPU/wall/RSS/disk；前置预算保留+实际消费+剩余+failed/pending 完整对账，额度拒绝、失败、首错保留及安全停止证据。不得使用历史 N1/W1 授权；正式预算只能依据实测新冻结且等待节点决定。 |

## 后续审核材料要求

执行器应提交新包绝对路径、源码/差异与复用清单、数据合同、测试命令和原始 stdout/stderr/退出码、工程额度与运行 identity、原始托管和结算/导出收据、checkpoint 和输入 hashes、未验证项清单。每个断言须指向可直接复算的具体文件；生产者报告中的 passed 字段不是独立审核结论。

阶段 B/C/D 只在节点决定后启动。后续 56/14/24 父场景划分必须新冻结，已查看 N1/基础父场景不得成为独立确认集；确认集结果封存。预测门固定为三个新 seed checkpoint 严格恢复、全合法候选有限且身份正确、至少两个 seed 同时满足固定三指标、主要目标有开发有效标签、信息/恢复/账本通过。不能因未知或困难样本删除目标、调门槛、追加训练；无法计算即未通过。

已读取 `E:/10.14/n2-governance/RESEARCH_BUDGET_STRUCTURE_UNFROZEN.md`，其明确未冻结、未授权；PPO 768/3072 和最终 168 轨迹数量与用户协议相符。WM `ceil(训练候选记录数/8)` 公式仍需确认既有损失所用 batch 单位（候选记录或同窗组），不能据此预先认证更新额度；其余实测资源项空缺，因此不是可消费预算。

此审核器没有联系原对话，也没有主模型批准证据。新实现提交后再进行源码和实际证据的实质审核；本框架只能约束验收，不能预先认证。


