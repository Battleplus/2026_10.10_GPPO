# 本地来源与迁移清单

核查日期：2026-10-11。所列路径均相对原始工作区根目录；行号仅用于本次定位。静态检查和旧报告不等于新场景验收通过。

`source-snapshot.json` 是本次发布之前盘点得到的历史来源快照，不是本仓库当前发布文件的校验清单。其中旧研究计划的摘要对应盘点时内容；本次发布更新了该计划，不能用历史摘要校验新版。来源源码仍位于原研究工作区，本次仅公开路径与摘要。

路径缩写：

- `ROOT`：工作区根目录。
- `W7`：`research-plans/w1-drone-consequence-ranking-window-balanced-ablation-v7-input-reuse-stage-schedule-repair/package/`。
- `R3`：`research-plans/w1-drone-consequence-ranking-window-balanced-ablation-v7-evaluation-recovery-v3-config-contract-repair/package/`。
- `RESULT`：`research-plans/w1-drone-consequence-ranking-window-balanced-ablation-v7-evaluation-recovery-v3-config-contract-repair/formal-run-20261011/`。

## 1. 应当复用的具体实现

| 来源与位置 | 已有逻辑 | 迁移处置 | 必须补的验收 |
|---|---|---|---|
| ROOT `src/uav_assignment/paper_faithful_models.py:30,170,207` | LiteralUAVAttention、LiteralTaskUpdate、PaperFaithfulActorCritic；共享pair评分、NOOP、mask | 图算子作为首选底座；新增平台能力/载荷/任务阶段的特征映射 | 旧输入数值回归；新active/type mask、候选置换、动态维度 |
| ROOT `src/uav_assignment/paper_models.py:61,195,259` | Adaptive注意力与任务更新、PaperHeteroActorCritic | 历史机制参考与可选对照；首版不同时维护第二套主图骨架 | 如启用，明确公式差异及公平控制 |
| ROOT `train_paper_faithful.py:85,97`；`src/uav_assignment/ppo.py:59,191` | GAE、采样、PPO更新流程 | 提取优化逻辑；环境构造、episode边界、reward重接 | truncation bootstrap、时间折扣、采样/更新logprob一致 |
| ROOT `src/uav_assignment/preco.py:7,31,56,64` | simplex、min-norm、cosine和相似性系数 | 保留通用数学函数；偏好验证时再启用 | 目标尺度、偏好输入、梯度方向；不直接沿用旧目标语义 |
| ROOT `src/uav_assignment/pcrl_training.py:149,620`；`pcrl_models.py:64` | 向量GAE与偏好PPO更新、偏好条件模型 | 后续扩展参考；当前N_OBJECTIVES固定，不能当任意多目标接口 | 新目标数、归一化与向量critic一致性 |
| W7 `native/gppo_world/joint_gppo.py:74,369`；`joint_training.py:601` | JointGraphPreferencePolicy、PreCo方向与PPO/PreCo更新 | 复用训练/审计思想；不整套替代根目录图策略 | 旧两目标、4/6/25合同和base API重新映射 |
| W7 `consequence_model.py:43,66,113` | masked BCE/Huber、两种ranking reduction、复合loss | 通用loss优先复用；默认pair_weighted | mask、平局、空窗口、三元分组、梯度和日志 |
| W7 `consequence_model.py:17,134`；`vendor/w1_graph_jepa.py:44` | ConsequenceJEPA、FrozenEnsemble、分类型池化世界编码器 | 后果模型结构候选；新维度和任务头重新初始化 | 后果标签、模型输入、反事实窗口及新特征语义 |
| W7 `consequence_training.py:20,93,180` | optimizer严格恢复、训练循环、checkpoint准入 | 复用身份和恢复框架；移除固定58窗/40epoch假设 | 参数/optimizer一一恢复，数据和模型schema匹配 |
| W7 `consequence_policy.py:10`；`consequence_replay.py:70,101` | critic-only辅助值、replay封存与更新核验 | 复用critic-first思想及一致性检查，适配标量图critic | rollout/bootstrap/GAE/update同一value语义；WM特征detach |
| W7 `public_prefix.py:103,144,237` | PublicPrefix、类型/来源校验、统一flatten | 合同模式复用，库存/载荷/报告/阶段字段及layout重建 | 0合法、unknown、篡改、pre/post混用均覆盖 |
| W7 `candidate_keys.py:56,85,177,222` | window context、候选catalog、输入绑定、replay键校验 | 保留parent/repeat/window与摘要；动作改用稳定ID映射 | 数量变化、候选重排、非法动作、跨窗混配拒绝 |
| W7 `consequence_collection.py:35,50,139` | 一次snapshot、多候选恢复与配对采集 | 采集模式复用；环境/适配器深恢复加入物流状态 | 时间/RNG/库存/载荷/报告一致；审计不修改分支 |
| R3 `evaluation_config_contract.py:99`；`evaluation_tape_contract.py` | 完整配置解析、场景tape与登记交叉核验 | 采用先准入完整resolved config的做法，重建新schema | scenario/parent_ids/重复和排序错误启动前拒绝 |
| R3 `evaluation_recovery_worker.py:116`；`production_driver.py:728` | 模型屏障、恢复后评价、首错和pending保留 | 复用完整模型集合准入和失败结算；不照搬固定六模型数量 | 按新实验矩阵判定完整集合，正常/无机会/失败导出 |
| R3 `budget_ledger.py:204`、`phase_handshake.py`、`launch_pilot.py`、`supervise.py` | 调用预留/结算、阶段socket、托管交接与监督 | 复用基础设施；新stage表与额度独立生成 | 最终版本真实driver全路径、systemd、所有调用计量 |

Luna盘点所比较的模型/采集/PublicPrefix/候选/账本核心文件在W7与R3之间摘要一致；配置恢复与driver的修复优先参考R3。实施时仍须以来源摘要清单核对，避免未列入盘点的文件被误当相同。

## 2. 不能原样照搬的内容

- W7 `native/gppo_world/graph5.py` 和 `joint_gppo.py` 绑定4平台、6任务、24候选+NOOP；`PublicPrefix`有固定节点数 `(4,3,4,6,4)`、关系 `[4,6,4]` 和25位mask。
- `ConsequenceJEPA` 的外部性头按6任务×2项reshape；`ConsequencePolicy.pack()`固定25候选，旧critic增量为2维。单改最终输出维度不足以迁移。
- 根目录 `src/uav_assignment/paper_faithful_models.py` 含可复用图算子；新场景仍需适配异构特征、实体/候选映射和动态mask。4平台、6任务、25动作只指旧W1接线，不是根目录图算子的尺寸描述。
- `paper_faithful_env.py` 移除了deadline和随机hazard触发，使用固定任务变化tape，不能直接代表带时限的救援运输。`paper_env.py` 的异步事件/通信思路可参考，运输生命周期和货物账本需新建。
- 历史模型权重、288窗口和旧场景标签不直接复用为新场景训练证据。旧论文数值不能代替新应用评价。
- 不将整份历史目录复制为新工程；只提取民用通用调度与学习依赖，领域无关之外的其他模块不进入本迁移。

## 3. 最新结果的本地证据

| 文件（相对RESULT） | 本轮核对SHA-256 |
|---|---|
| `run-once/ranking-ablation-results.json` | `d74e4bbbcc4dcf061ccb1d0f7420dd07f5c591fa4675d61aba1658a8e927826e` |
| `run-once/evaluation-six-model-restore-audit.json` | `4320b0db29b0c85d41b797a5cff488a51260d38a5078c9df70d0e8392b7974f2` |
| `run-once/resource-settlement.json` | `eb9b2ddc8816c2ec24cfdbcfe0e136c41c4762294635da48e90bcb517bdae33f` |

结果JSON为 `evaluated`，冻结分类为 `no_average_improvement_or_mixed_result`；本轮读取status显示 `completed_evaluation_recovery`、pending=0、failed=0。更全面的远端完整性和逐行复算结论来源于已保存RESULT_AUDIT报告，本轮未重复认证。

## 4. 第一批交付的复用证明

每个被迁移文件记录 source_path、source_sha256、destination、unchanged_or_adapted、reason、dependency_list、checks。未变的通用算子可以逐字节比对；发生变化的图/模型接口须给差异和测试证据。复用比例若要报告，应按这些文件记录计算，不先承诺百分比。

相关原有测试可迁移断言与构造方法：ROOT `tests/test_paper_faithful.py` 的手工图公式/梯度/同输入结构比较；`tests/test_paper_faithful_generalization.py` 的协议隔离；W7 `acceptance/ranking_reduction_acceptance.py` 的窗口对齐与梯度；R3 `acceptance/evaluation_recovery_driver_acceptance.py` 的真实driver接口。旧测试成功记录不视为新测试已运行。
