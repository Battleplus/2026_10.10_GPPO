# N2 合同修订与复用链路独立审核 R2（开发中）

日期：2026-10-14。读取 `E:/10.14/n2-development/n2_contracts.py`、`test_n2_contracts.py`、复制的 `references/existing_n2/{branching.py,world_model.py,ppo_integration.py,run_ppo_integration_smoke.py,tests/test_world_model.py}`，对照 `references/world_model/consequence_model.py` 和历史民用 N2 protocol。文件仍由执行器修订；没有冻结hash，不出最终PASS。

## 独立已验证

执行 `python -B -m unittest -v test_n2_contracts`，10/10通过（test报告0.036秒，命令进程3.33秒）。这确认局部新增context校验、LabelLeaf有效数值约束、构造前隐藏scenario变更、GAE terminal/truncation数学例和旧event_signal validator的局部行为。它不证明这些helper已接入训练/replay/critic。

独立探针 `E:/10.14/n2-governance/reviews/audit_contract_counterexamples_r2.py` 和输出 `audit_contract_counterexamples_r2_output.txt`：

- 重复candidate_key、清空保存candidate_catalog、将context与所有key的time改999（live observation仍time0）均被ACCEPT。set比较吞掉重复key；保存catalog未验digest；context.time未与prefix/live时间互验。执行器已收到修复要求。
- 真实控制fixture C1前缀走8步后snapshot恢复PASS，t8完整catalog为1（仅NOOP）。这是合法无机会窗，不可改写为有机会研究样本；工程机会fixture须单独命名并保留来源/非研究身份。
- 旧动态WM一次无optimizer前向/反向比较：所有无效target从0改NaN后loss完全相同，每个参数梯度严格相同且有限。这支持 `_masked_element_loss` 先valid索引再BCE/Huber、ranking先skip无效pair的局部安全。探针没有执行optimizer、训练或SSH；只运行8个工程环境步及两个loss/gradient计算，审核消耗不混作执行器学习验收。

## 尚未接通的主链

全文调用搜索显示新n2_contracts只由新test引用；复制旧branch/WM/PPO尚未调用它。旧event_signal validate仅旧世界模型参考与新helper测试使用，民用公开prefix白名单仍没有该字段，实际WM/replay/critic没有0/1/unknown边界收据。因此helper PASS不能解除整链阻断。

旧 `branching.run_synthetic_candidate_pair()` 的reference首步仍为 `_step_c1(reference_env)`，其后C1；当前用户要求同窗NOOP首步基线。旧标签为reward/energy/其他按时数/报告数delta，尚非当前合同所列绝对后果+NOOP增量、其他订单新增过期、未满足、改派等完整头定义。旧文档中的candidate-minus-C1与新NOOP合同必须显式版本迁移，不能沿用旧schema/head名掩盖变化。

旧 `branch_records_to_targets()` 只join candidate_id/task_ids与head顺序，不核验来源state/scenario/source_prefix/window_start/context。来自不同窗口但ID相同的记录可误join；flatten前一致性校验须在真实batch构建入口执行，并绑定expected可信窗口/恢复摘要。

旧scalar `GppoEngineeringTrainer` 用一个固定Categorical动作作PPO局部更新，不能替代民用动态顺序动作及库存预留真实采集路径。`CriticAugmentedPPOTrainer`/`CriticAugmentedGraphPolicy`存在接入真实PPOTrainer的可复用路线，但目前独立smoke构造一个新随机WM，并非训练后的实际WM checkpoint贯通链。最终必须由已训练/严格恢复WM提供同身份预测。

## 损失复用判断

当前旧民用N2 loss为：global binary masked BCE均值 + global continuous masked Huber(beta=1)均值 + task binary masked BCE均值 + task continuous masked Huber(beta=1)均值 + 同窗有效非平局pair的softplus排序均值。排序所有有效pair等权，未加入tail loss或window-balanced消融。

这与 `E:/Z博士/development/ch2_disaster_relief_n2_v1/preparation/N2_PROTOCOL_DRAFT.md:38` 明确的四family均值+原pair_weighted公式一致，可作为“保持既有民用N2损失”的可核验来源。W7 `references/world_model/consequence_model.py` 另有latent/public/anticollapse(.01)及不同per_task布局，所以只能说复用BCE/Huber/rank模式，不能声称完整W7 loss原样。新标签适配必须冻结head/单位/mask语义；不得借适配添加权重、tail或排序归一化。

## 其他当前源码风险

- `CriticOnlyGppoAdapter`读取版本仍为随机末层、没有训练集归一化stats。用户要求辅助末层零初始化、冻结WM、detached概率聚合后归一化、G同结构零输入，尚待新修订实证。旧测试还期望初始化后WM立即改变value，需与zero-last-layer合同同步。
- `EngineeringTrainer.update()` 每次probe与training各一次WM forward；10次update实际至少20次forward，预算v2训练forward10漏计。所有恢复/permutation/unknown测试也计入相应真实额度。
- `EngineeringTrainer.restore_checkpoint()` 在next/sampler校验之前赋self.update_index；异常回滚仅model/optimizer/RNG，未回滚counter。坏boundary checkpoint可能拒绝却污染状态；需先验证或完整回滚并负例验证。
- `CriticAugmentedGraphPolicy.load_state_dict(strict=True)`分三prefix，顶层其他prefix被忽略；WM来源检查在加载之后，wrapper无完整rollback。额外key应严格拒绝，身份失败不应污染原模型。
- 旧WM checkpoint身份含model_config/data_identity字符串/code hash，但没有冻结layout、head定义、数据manifest和normalizerstats，不能满足正式严格恢复要求。

上述具体问题已同步执行器和协调者。后续以修订冻结包、实际完整调用链和工程收据为准，不因局部通过提升阶段。无SSH、无正式研究、无实现修改。
