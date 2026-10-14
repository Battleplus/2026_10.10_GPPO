# N2 新合同与工程预算 v2 初审 R1

日期：2026-10-14。被审查：`E:/10.14/n2-development/n2_contracts.py`、`test_n2_contracts.py`、`ENGINEERING_BUDGET_DRAFT_v2.json`，以及只读追踪 `references/civil/relief_env.py`。文件仍由执行器修改，审核是当时读到的开发版本，不是冻结hash的最终验收。本审核未修改实现、未执行测试或模型代码。

结论：**阶段 A 未通过；局部真实接口已出现，合同和预算仍待修订。** `preaction_snapshot()` 真正调用民用 `ReliefEnv.public_observation()`/`candidates()` 并deepcopy环境，因此并非纯字典假接口。但测试在reset初始time0取得snapshot，尚无C1到8分钟、实际恢复→候选分支→标签→WM/PPO学习及托管证据。以下是可纠正的源码问题，不把尚未实现的链路当作完成。

| 优先级 | 发现 | 影响与修正 |
|---|---|---|
| 阻断 | `verify_preaction()` 只比较candidate_keys中的candidate_id集合，不验证key每个context字段 | key的parent/repeat/window/time/prefix/catalog可以被改成其他窗口而仍通过。逐key完整比较context、拒绝重复key/缺失/跨窗/来源错配；消费方必须用同一校验，不能只生成key后从不验证。 |
| 阻断 | snapshot中的PublicPrefix不与context摘要互验，internal_snapshot没有完整恢复摘要、phase或source绑定 | 活观察可能匹配context，但保存的prefix或内部恢复对象被替换仍未被检测。绑定source scenario/event/RNG、完整恢复状态、pre-action阶段及快照引用身份；恢复后检查时间、状态、公共prefix和catalog一致。避免把完整内部快照传模型/replay。 |
| 阻断 | pre/post拒绝只测试NOOP step后time变化 | 只能证明不同时间的prefix被拒绝。补充真实顺序动作/预留后快照不得冒充原pre-action，以及snapshot phase/context被篡改负例；不以观察恰好相同证明内部恢复位置正确。 |
| 阻断 | 隐藏任务差分测试构造env后append `changed.scenario.tasks` | 民用env在`__init__`第54行建立 `_task_spec`，reset再由其创建 `_tasks`；append未进入有效隐藏任务集合。测试可能通过却没有探测hidden entity数/ID边界。用合法成对scenario在构造前改变隐藏任务，并确认内部有效状态确实不同；再测公开观察/candidates/mask/actor及WM特征shape、后续未报告故障/库存边界。disturbance tape变化须合法、可生效，不能仅添加不完整字典。 |
| 待闭合 | `LabelLeaf` valid分支只排除None与unknown_reason | NaN/Inf可成为valid，valid类型非bool也被truthiness接受。冻结通用数值有限约束，binary/event_signal头另外限制0/1；unknown独立有效位和原因。当前不存在unknown mask loss/gradient证据。 |
| 待闭合 | 置换只比较feature字典，NOOP与其他候选feature字典shape也不同 | 字典比较说明映射按id，但不证明模型预测、loss、参数梯度、replay或critic对齐。冻结特征字段/缺省/单位/归一化规则，保留动态catalog；实际模型置换及unknown梯度测试仍必需。 |
| 阻断 | v2 catalog cap17只是初始目录，不是选中8min窗口或完整rollout | full base episode scan与base步骤8冲突。先定义工程输入和C1 prefix/选窗，扫描本身必须有预算/计量；观测该窗完整catalog N，再推导N×最多30 branch步，所有候选+NOOP，无截断。 |
| 阻断 | v2 episodes仍branch25、total27，但candidate_branches_max17 | 若一base+17branch+一PPO则19，不是27。构造/reset/episode是否按每个fork计必须明确，且包括scan/审计额外环境副本。宽松上限可更高，但须解释其来源和总step关系。 |
| 待闭合 | `source_fixture_episodes_used_for_model_fit=0` 与工程copy拟用于fit矛盾 | 应明确历史轨迹/旧权重复用0，新工程副本及其分支标签用于拟合的实际量；复制fixture并改身份不代表其内容未用于fit。工程拟合不等于研究训练，不要用字段掩去实际来源。 |
| 待闭合 | 初始化与验证forward口径 | world_model_initializations1/policy_initializations1与strict restore所需新实例须一致定义；checkpoint加载/恢复/负例加载实际计入。v2 WM总forward24算术一致（10+1+1+12），但PPO采集value、PPO训练、policy checkpoint等价验证前向尚无定义。计量须覆盖实际操作，不能以WM额度代替所有forward。 |

v2相对R0已改善：结算reserve明确包含总1200wall/900CPU，工作分别1155/870；区分RSS与cgroup内存；Type=exec；工作384MiB+export128MiB联合512MiB；训练/预测/恢复/audit WM forward分项。以上是草案设计改善，不代表守护/CPU计量/存储峰值已经实现或测试。写操作64须由实际ledger/receipt/checkpoint/临时文件数量验证，不能先认定足够。

已把具体问题发执行器及协调者。既有两次已消费N2 STOP保持不变；本地真实学习工程的后续证据仅覆盖本地部分，真实托管不因预算草案或局部合同测试而通过。controller成功路径mock应逐条检查传给远程执行器的command text与label及transfer/submit顺序，避免再次出现create_roots参数颠倒；这类mock依然不能替代真实托管收据。
