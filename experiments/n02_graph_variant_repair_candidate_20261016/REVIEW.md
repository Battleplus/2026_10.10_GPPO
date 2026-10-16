# 最小图变体修复独立审查

结论：**PASS，限于候选补丁的静态闭合性与改动范围。** 该结论不代表已执行 L1 或已验证 L1 的运行成本、训练结果、预测收益与决策收益。

审查输入：

| 文件 | SHA-256 |
|---|---|
| REPAIR.diff | `7911e9d44b7b96166762767b1ffb4c743e82b430f33bab882e3098d6f4ae4f98` |
| REPAIR.md | `51fd5c5d9aa50563e314c4e5ae892710b3ec8556b37cce73550c11499ae8d28c` |
| 原 final 的 n2_stage_pipeline.py | `5063b540d72ad5df145089e6a890c2db0bd72c939bc58f6e0c5906363cb91ebd` |

独立 `git apply --check --no-index` 对原 final 基线通过，未应用补丁。补丁仅改一个文件的四行语义：训练 G 与 G-WM 的两个构造由 L0 改 L1；actor_pairing 元数据同步改 L1；开发评价从 checkpoint 重建的构造同步改 L1。原文件全部三个 build_policy 调用及唯一 actor_pairing 字符串均已覆盖，没有遗漏的该管线 L0 构造。训练两组继续使用同一 WM_SEED=8201，`assert_paired_actor_initialization` 保留；保存与开发严格 load_state_dict 的目标架构一致。

现有 `package/civilian/graph_policy.py` 的 L1 构造（约416行）注册 literal_attention、task_update；`_graph_outputs` 的非 L0 分支（约446行）调用这两个图消息传递模块。原 L0 分支仅用 entity_mlp。因此此次选择 L1 对应的是实际图消息传递实现，而不是只改结果标签。REPAIR.md 记录的双 L1 构造、43项状态一致属于执行者已完成的无 forward 构造证据；本独立审核没有重复运行模型。

diff 不改 PPO_BUDGET、WM训练预算、阶段协议、数据/场景/候选构造、随机种子、episode/update计数、world-model冻结/cache、critic adapter、actor配对断言、资源上限、授权门、driver、acceptance harness 或 synthetic test。架构改动可能改变实际成本，现阶段没有 L1 成本实测，不能沿用旧 L0 成本作为 L1 实测值；这不改变本候选的静态范围结论。

本次仅增加本 REVIEW.md。原 final 的53项清单、身份、正式结果及旧 L0 checkpoint均未改；不应将此补丁解释为已修正历史运行。未 SSH、未 forward、未训练、未部署、未加载 checkpoint、未发起新研究或新授权条件。
