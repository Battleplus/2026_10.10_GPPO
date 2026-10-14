# N2 节点①交付包 R1 更正

日期：2026-10-14。本文更正 [NODE_A_DELIVERY_ZH.md](E:/10.14/n2-governance/NODE_A_DELIVERY_ZH.md) 中的源码身份和证据表述；旧稿已标记 `SUPERSEDED_INCORRECT_DRAFT`，仅保留修订轨迹，不是有效节点证据。

**阶段A仍为 NOT PASSED；正式研究预算未冻结；托管执行未通过，且未获本包授权。** R6 独立审核只确认本地 learning chain `VERIFIED WITH LIMITS`。它不是托管或 Stage A PASS，也不授权远端/正式研究运行。

## 正确源码与模型合同

阶段A实际民用实现是 `E:/10.14/n2-development/references/existing_n2/` 中的 `branching.py`、`world_model.py`、`ppo_integration.py` 及其 tests，结合 `references/civil` 的动态民用环境、图策略、PPO trainer。`run_local_engineering.py` 实际导入 `references/existing_n2/world_model.py` 的 `DynamicConsequenceModel`、`CriticOnlyGppoAdapter`、`CriticAugmentedGraphPolicy`；不是旁边同名 `references/world_model/consequence_model.py` / `consequence_policy.py` 的固定槽模型。

原本地模型头为动态候选轴和动态 public-task 轴：2 global binary (`reward_improved`, `energy_saved`)，4 global continuous (`cumulative_reward_delta`, `energy_use_delta`, `other_task_on_time_count_delta`, `inspection_report_count_delta`)，4 per-task binary，2 per-task continuous。R6 确认阶段A需要新增 unmet demand、reassignment delta 和 other-order newly-overdue 目标；这些不在首轮收据中，不能追认为已测。

原 `CriticOnlyGppoAdapter.value_adapter` 的末层为随机初始化，原实现没有 auxiliary normalization；不存在另一个 `actor_adapter`。critic-only 的 actor logits 直接原样返回、WM candidate values 与 policy probabilities detach、按合法候选 ID 对齐、WM 冻结，这些是已实现代码路径；等容量 G/G-WM 的小测试已存在，但首轮只实测 L1 actor + trained frozen WM critic 路径，没有正式双臂公平训练。`G`/G+WM 同辅助结构、zero WM input 与 zero-last initialization 仍需新 revision 及测试绑定。

## 已核实的本地运行证据

- First-run archive：`E:/10.14/archives/n2-local-engineering-20261014-first-run.zip`，SHA-256 `459C1403F1ACC995138E48C739B147C5090610ECCA93832385D29B89E3E4E912`；30 files，13 frozen source hashes 与收据一致，包含 raw records、checkpoints、profile、R5 review。
- Worker/watchdog/profile/source 首轮 identities 及 raw receipts 见该归档和 `E:/10.14/n2-development/runs/local-1791969402746190800/`。首轮 run immutable；不得重跑相同身份/profile或用首轮收据证明新 revision。
- 独立 R6 审核：`E:/10.14/n2-governance/reviews/N2_LOCAL_RUN_FINAL_INDEPENDENT_REVIEW_R6_20261014.md`，SHA-256 `947EE9683CE1EF60D71D9AEA46E591BA132B85EAD533DA70AE155F99D0C7E215`。核实本地分支 raw-label、reward/energy、PPO 48 次更新、WM 冻结来源、PPO model/optimizer 严格恢复；结论为 `VERIFIED WITH LIMITS`。
- 收据显示 7 candidate/branches（包括 NOOP），t=8 单 window，candidate 对同窗 NOOP，后续冻结 C1 continuation，30 分钟上限；WM 更新 12、PPO 更新 48、PPO 12 episodes、720 PPO transitions。工程 fixture 不构成研究数据。
- Watchdog exit 0、无 violation；外部 wall 105.786 s，process-tree CPU 108.90625 s，采样 RSS peak 406,495,232 bytes，settlement output tree 13,123,773 bytes，Windows cgroup CPU/memory unavailable。

## 计量限制与缺口

- Worker receipt 的 `checkpoint_reads=2` 是被审查的 restore 入口计数；PPO override 与 `super()` 均物理 `torch.load`，实际至少 3 次底层读取。不能称读取计量精确。
- Worker 15 audited output writes 不含最终 watchdog receipt 与 supervisor 2 次写入；按调用入口至少 18 次。该字段不是全进程每个 kernel write 数。
- 首轮 source hash 清单遗漏传递依赖 `stable_identity.py`、`chapter1_adapter.py` 等。归档保留了原 manifest/hash，不补改旧 identity；新 revision 必须用完整 self-contained source manifest。
- Watchdog 规划 receipt 3722 bytes、实为 3769 bytes；规划 tree 为 13,127,436 bytes，receipt final tree 为 13,123,773 bytes；R6 对 artifact tree 重算为 13,127,542 bytes，较规划多 106 bytes。口径差异需用不可循环的 accounting rule 修复；当前无资源 PASS 声明。
- 研究目标 head 不完整、正式 checkpoint/layout/data identity 未冻结，G/G+WM 未做正式配对训练。真实托管 worker、StageServer、BudgetLedger、systemd invocation、unit cgroup CPU/memory/process settlement、production signature verifier 和目标节点身份均未通过真实执行验证。
- 正式研究预算必须由阶段A合格的目标 Linux 托管实测形成；不得从一次 Windows 采样、单个 7-candidate fixture、本地 profile 或其比例外推。正式 56/14/24 父场景、四采集窗口、WM/ PPO/预测/检查点/导出/settlement 预算仍未冻结。

## R1 实现进度

新 revision 工作目录：`E:/10.14/n2-development/revisions/stage-a-followup-r1/`。首轮 run、归档和 historical references 均保持不变。R1 目标是补足民用动态 head、training-only critic normalization、G/G-WM 初值公平性、wrapper strict restore rollback，以及完整 source/counter evidence。R1 代码与测试尚不是托管/研究证据；以 revision 内冻结 hash 和靶向测试收据另行审核。

## 节点决定

保持 hosted/正式训练暂停。先完成 R1 靶向测试、独立审核、self-contained controller package 和 mock success/failure/stage cap 验证；然后由节点决策者基于新 revision hashes、目标节点证据和完整新预算另行决策。不得复用旧 consumed identity、授权、样本或权重。
