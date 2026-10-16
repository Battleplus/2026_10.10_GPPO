# 最终真实交付独立审核

审核日期：2026-10-16。范围为本地 final 目录与 `final-formal-run-evidence`；没有 SSH、forward、训练、重跑、源代码或身份文件修改。

结论：**七阶段执行、授权与文件交付闭环 PASS；“复用有图消息传递 GPPO”的目标未完成，因为实际 G/G-WM 均为 L0 无消息传递；预测有效性证据不足；本次没有观察到决策增益。** 因此不能将本报告解释为全部工程目标验收通过。以下依据直接回执、数据库、checkpoint 和导出文件，不以 wrapper 返回成功替代验收。

## 工程

本报告中的产物路径均相对于本 final 目录。直接定位：`final-formal-run-evidence/run-once/receipts/01-input_admission.json` 至 `07-settlement_and_export.json`、`guardians/`、`resource-ledger.jsonl`、`work-calls.sqlite3`；模型原件为 `final-formal-run-evidence/run-once/n2_pipeline/world_model.pt`、`checkpoints/G/round_01.pt` 和 `checkpoints/G_WM/round_01.pt`。导出副本为 `final-formal-run-evidence/run-once/export/n2_integration_smoke/`；预测/策略/评价回执分别为 `n2_pipeline/checkpoint_restore_receipt.json`、`graph_policy_training_receipt.json`、`development_evaluation_receipt.json`。

**图策略目标缺口（源和正式 checkpoint 一致）**：`package/civilian/n2_stage_pipeline.py:1460`、`:1461` 实际均调用 `build_policy("L0", WM_SEED, device="cpu")`。`package/civilian/graph_policy.py:416` 仅为 L1 注册 literal_attention/task_update；`:443` 的 L0 分支仅做逐节点 entity_mlp，L1 才执行图消息传递。两个正式 policy checkpoint 均含18个 `base_policy.entity_mlp.*` tensor 键，均不含 `base_policy.literal_attention.*` 或 `base_policy.task_update.*` 键。这里没有 use_message_passing 标志；真正控制开关是构造 variant。命名 G/G-WM 和 graph_policy_training 不足以证明实际使用了图消息传递。因此本次仅验明 L0+WM critic 的执行闭环，不满足用户指定的图 GPPO 架构目标。审核未改模型、未改冻结身份，也未发起修复运行。

唯一正式 attempt 为 `n02-v5-formal-auth-binding-closed-db-fix-final-once`，unit 为 `n02-v4-n02-v5-formal-auth-binding-closed-db-fix-final-once.service`，运行时 InvocationID 为 `932a9532c1da4c068127be4d066dbb02`。七个 driver 回执依序为 input_admission accepted，其余六阶段 complete，first_error 均为空；七个 guardian 均 complete、child_returncode=0，且无 kill/error。console 的完整 JSON 为 status=complete、phase_protocol_sequence=7。terminal 中 Result=success、ExecMainStatus=0；unit 已被回收，LoadState=not-found，不能把其空 InvocationID 当作运行时缺失。

53 项 manifest 全部哈希一致，四个 canonical 静态身份通过 `load_release_binding`。正式授权 envelope 通过 `validate_authorization_document`，其文件 SHA-256 `7af32c4f19fb998027f07272792216ff73bacb5963712ad5fb399b6001b4b237` 与 authorization_consumed 完全相符；这是文件哈希，与 envelope 内 canonical payload 身份 `986fc17d4589008afdb622587f4b9ae17786bb2567b1059c00eccc18acc2c1f2` 的作用不同。冻结矩阵、2 train + 1 development、seed 8201 与正式预算未改。静态身份和测量回执详细审核见 `MEASURED_FINAL_INDEPENDENT_REVIEW.md`。

独立以 SQLite `mode=ro&immutable=1` 查询 work-calls：1347 行全部 complete，reserved=actual，无 pending/failed。实际 WM optimizer updates=2，PPO optimizer updates=16（G/G-WM 各8），training episodes=4，development episodes=2，environment steps=894/4000，candidate branches=12/128，WM forward batches=198/512，WM candidate evaluations=232/2048。checkpoint 自身也记录 WM updates=2、两组 policy updates=8；训练 rollout 各120条，共240条。

导出 manifest 声明的15个 payload 的 SHA-256、字节数和 n2_pipeline 原件副本全部匹配；额外 resource_ledger_snapshot 也匹配。manifest 为有意声明的15项，目录另有 snapshot 和 manifest 本身；payload=5,221,026 bytes，总包=5,232,319 bytes。40个导出源引用逐项与当前 package 原文件哈希一致；前序测量回执7个证据引用也全部一致。settlement 指向的5个阶段结果回执与导出一致。所有声明哈希核对和本地证据文件实测哈希保存在 `FINAL_INDEPENDENT_HASH_AUDIT.json`，该文件 SHA-256 为 `3fcffca0597f2324e0df145eb0abedf97d824aa83f444c480f4e989a090a6653`。

关键产物 SHA-256：

| 产物 | SHA-256 |
|---|---|
| runtime identity | `60326b6164a03d2fdee55cbbbd72c9294992dc8d3c5f7cb13047e329e0053d76` |
| export_manifest.json | `57589dd747014e33e61a15e63f142591e8aa33beb2eca916750ad31c3887b730` |
| resource_ledger_snapshot.json | `e6effe8a1a0eee53ad5cb43d001b03af999253ce063cc84cc2c80a985d252789` |
| world_model.pt | `1b9a9303af07a519f3e03302a54a4154063a196df93752715974de450fc13c0c` |
| G checkpoint | `86d167642aac1e4346939f364b5aef299b4c4fd4d9650a476270dae914a44319` |
| G-WM checkpoint | `0408bab1651acd3218e472fea4c25e8951b6228742a53668224b855ea1ef5b4c` |
| policy training receipt | `26dcecb42d930004c60faa54f88672cc199b7398e1bd0de6daa37527a8437235` |
| development evaluation receipt | `a82a757c44651afeeebce9a4a713d0f98ec67729862f7f061c9f0499acb88eda` |

资源口径必须区分：最终 live ledger 7项本次分配合计 wall=29.85973918804666s、CPU=22.839005178s；加已授权前序 measurement carry-forward 后最终 pilot 值为 wall=33.51371218804666s、CPU=26.115940178s，均低于1800s/900s。最终 guardian invocation measurement 为 wall=29.85973918804666s、CPU=23.362832708s，明确范围为 guardian 启动至 worker 退出、排除最终 receipt 写入；与阶段分配 ledger 的 CPU 不能混用。journal 独立记录 systemd `Consumed 23.829s CPU time`，Started 至该记录约30.362s，后者是日志时间间隔而非精确 unit 总墙钟。console 总账是更早的 worker 截止（含 prior wall=30.491310408971508s/CPU=20.842702846s），snapshot 截止 settlement 前，均不可作为最终成本。峰值 process-group RSS=1,645,547,520 bytes/4 GiB，work=8,425,355 bytes/1 GiB，export=5,232,319 bytes/1 GiB。以上证据支持记录范围内预算合规，不声称未记录的机器全局资源或任意写出尾部均被阶段账精确计入。

## 预测

WM 只在8个训练 windows 上做1 epoch、2次更新；训练数据 identity 与 training_branches 文件哈希一致。world_model.pt 的两条训练行有有限非零 gradient_norm（约1.73615、1.70226）。normalization 声明 fitted_on=training_samples_only。严格恢复子进程 receipt complete、CPU-only，4个 training probes 的预测哈希经源代码断言与父进程 reference 完全一致；strict-restore 总计8次 forward（父4+子4）。审核没有重新执行 forward，只读取该历史直接证据，并以 weights_only 加载现有 checkpoint、strict=True 恢复状态。

4个 development windows、20个 global 有效标签：global MAE=0.0793732250109315；global utility MAE=0.06363608874380589。utility positive-overestimate 4/4，mean=0.06363608874380589、max=0.07192879915237427。排序 valid pair_count=0、accuracy=null；采集每窗口仅1个候选，因此本次没有候选排序学习/验证证据。task Brier：delivery=0.24979980662465096、inspection=0.21646984294056892、report=0.26102447509765625；有效标签分别16/8/8，覆盖率2/3、1/3、1/3。它们是小开发集诊断，不能据此宣布预测模型可靠、排序有效或具有泛化能力。

**外部性构造确实存在，不能由 pair_count=0 推断不存在**：已注册 `package/civilian/registered_data/fixtures/causal_allocation_case.json`（SHA-256 `23086b183ac88f3a4ac2efa8b9c082f893a3587192245c989a05fceae365f905`）在 decision_time=8 提供同一 heli 的 candidate_a/候选b，分别 dispatch delivery-a 或 delivery-b，加 NOOP；两单 deadline=15/19，共用 carrier，声明 same_public_prefix、same_event_tape 和必须记录 actual label delta。`scenario_matrix.py:306` 起的 manual_causal_case 构造该输入。另 `package/tests/test_100x100_contract.py:133` 的 `test_two_legal_global_choices_change_other_order_and_recompute_labels` 是另一手工场景的可执行测试定义，要求同一 snapshot 两种合法分配产生相反 on_time 结果，并断言 paired task 标签 -1/+1（`:226` 起）。这证明静态构造与验证逻辑已经准备，不能替代其历史运行回执。正式 runtime_admission 的 causal_fixture_verified=true 只来自 `dataset_protocol.py:223` 起的 fixture/生成器字节一致性检查；它不执行两种分配、不验证 actual delta。本次收集的正式产物未找到该注册 causal case 的双分配 replay/actual label-delta 回执，因此“存在构造”可确认，“本次已实测证明两合法分配外部性不同”证据不足。

## 决策

G/G-WM 从同一 **L0 无图消息传递** seed 8201 初始化；正式执行源在 rollout 前强制执行 `assert_paired_actor_initialization`，比较 candidate IDs 与精确相等的初始 logits；运行 complete 支持该断言通过。两组训练 receipt 均 initial probability-ratio error=0。没有独立保存初始 actor 全状态快照，因此本结论来自执行断言和绑定源，而不是初始文件逐字节比较。此处 actor 配对成立，不补足上述图 GPPO 目标缺口。

两组最终 checkpoint 可严格恢复；其 `world_model.*` 每个 tensor 与原训练 WM 逐项完全相同，WM state identity=`5c09193f7e538e1171220536422bffad276cdaeef49f8adf50e62808753ba8cb`。源码将 WM requires_grad=False/eval，并在 PPO 前后断言 identity 不变。实际 G-WM checkpoint 的4个辅助 adapter 参数均有 Adam step=8、非零 exp_avg_sq；其输出层 weight/bias 绝对值和分别0.05924889072775841/0.002088665496557951，已离开零初始化。G 的 adapter 无 optimizer 状态、输出层仍为零。这是实际更新证据，不只是 architecture 声明。

预测进入 critic 的证据链为：绑定源在 `_proposal_scores` 从冻结 WM/cache 取得五通道预测，CriticOnlyGppoAdapter 聚合 detached 预测并加到 base value；训练 rollout 发生120次 forward/139候选评估，PPO 重用480次 cache hit、0 miss/0重复forward；辅助 critic Adam 非零状态证明该参数路径参与实际反传。源码中 actor 仍读取 base policy 的 action probability，WM/候选概率聚合均 detach。没有保存每次原始五通道 tensor 与辅助 value 的独立数值分解，因此不声称逐步预测因果效果已被消融验证。

开发评价为同一个 development parent、G/G-WM 各1个60步 episode。两组均 delivered_orders=4、weighted_on_time_delivery_rate=1.0、inspection_completion_rate=1.0、inspection_on_time_rate=1.0、energy_used=11.551500870754841、reassignments=1、late/unmet/undiscovered=0。三项 paired differences 均0。G-WM 评价有60 forward/69候选评估，但本次没有观察到任务表现提升；单 seed、单 development parent 也不能支撑统计比较结论。

## 下一步

将本次交付记录为“已提交的一次 L0+WM critic 七阶段闭环完成；图 GPPO 架构目标未完成；外部性构造存在但正式 replay 标签差异证据不足；预测与决策收益尚未证实”。现有文件足够复核本次实际运行和梯度/冻结路径；不需要重跑来完成本审核。后续若修复图 GPPO 目标，必须按真实变更重新形成身份和实验记录，不能把现有 G 标签解释为已执行 L1。若未来另立实验验证研究主张，优先在已存在的双分配 causal case 上补可追溯 actual label delta，设计具有有效多候选/非零排序对的窗口、独立多场景多 seed 评价及预测/critic 明确消融，并记录初始 actor 快照和预测→辅助 value 数值分解。此处不增加本次授权条件或启动新运行。
