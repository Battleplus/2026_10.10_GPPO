# 最终 L1 修复发布独立审核

结论：**PASS，限于本地 NOT_APPROVED 候选发布的静态完整性与最小修复闭合性。** 这不是运行授权，也不表示 L1 已部署、训练、通过目标运行时 preflight，或具有已测成本/研究收益。审核日期：2026-10-16。

本次目标目录为 `E:\Z博士\development\n02_graph_variant_repair_release_20261016`；比较源为 `E:\Z博士\development\n02_cost_chain_repair_engineering_release_20261016_r2_closed_db_fix_final`，后者确为包含真实 measurement 和 L0 正式结果的53文件版本。其 manifest 的 package_release 字符串沿用 `ch2_disaster_relief_n02_formal_auth_binding_v5`，不应据此误认作同名旧46文件初始目录。

执行者确认身份与本地归档稳定后，独立只读核验如下四个 canonical payload 身份；现有 `execution_gate.load_release_binding` 接受其链路：

| 身份 | SHA-256 |
|---|---|
| Manifest | `3aaf0ddb966edbd64bf9da7cc6998774f30c0370fbf6ae8e1b5e4752eeed063f` |
| Bundle | `f05eb10cb758d0da2052d3c4b92a581001db0134a634942f8656387f0121d06d` |
| Request | `76fa3f23191a46a19efa37f43dad657dfcbaa574822b790d06e92d322404146f` |
| Attempt | `21a213d2832cfd9fc77c482d4fd75455ee305354d77c16caede427886be9b90f` |

包内实有53个文件，精确等于 manifest 文件集，无多余、缺失或哈希不符。独立读取执行者保留的临时 ZIP：58个成员、无重复，精确为53包文件+5静态侧车，每个成员字节均等于发布目录；归档 SHA-256=`56645fbb6d047c9915b4327786b482529a0ae8bf4b40e40dcba5166c9cd04cc1`。它是本地归档身份，不是部署或执行证据；临时 ZIP 可由执行者清理。

与旧 final 的53项包文件逐项比较，仅3个文件改变：`package/civilian/n2_stage_pipeline.py` 的两个训练构造、开发严格恢复构造和 actor_pairing 元数据由 L0 改 L1；`execution_gate.py` 和 `package_layout.py` 仅更新新 release 常量。新管线 SHA-256=`9688491468f41d7e2a48878537ece8e8ff79a9766a5eab5e789cfcaaa7ad5cbf`。三个构造覆盖该管线全部 build_policy 调用，训练/开发均为同 seed 8201 的 L1。现有未改 `graph_policy.py` 的 L1 构造注册 literal_attention/task_update，并在 L1 分支调用图消息传递；初始 actor 配对断言、WM 冻结、cache、critic adapter 与严格 checkpoint 恢复均保留。故静态修复确实选择图实现，不是仅改变 G/G-WM 标签。

以 AST 表达式逐项比较，COLLECTION_BUDGET、PPO_BUDGET、WM_SEED、WM_TRAIN_BATCH_SIZE、WM_TRAIN_EPOCHS、WM_MAX_UPDATES 与 FORMAL_BUDGET 均原样。TASKBOOK 逐字节相同（SHA-256=`4b544e39b5fffa89ef364095341412c807d4d609a11117191b6b981aa51bcf5c`）；registry、场景/因果fixture、protocol、100×100地图与2 train+1 development矩阵均未改变。该发布没有附加研究、扩大预算或修订旧实验结果。

`PRIOR_RESOURCE_COST.json` 与旧包逐字节相同，SHA-256=`bc60410eb314e7882b9cf85237d8d3243209f27edb11ce242dc94c6bfe485824`，其7个证据文件均与声明哈希一致。receipt 明确绑定前序 source=`d9b369faa831ce9d92c05c2b131e977ec70ee60a93c2114b8624ad0096226fec`，stage_coverage 只有 input_admission。新 REPAIR.md、静态准备说明和身份侧车均保留该范围；没有将前序 bootstrap 伪装为本 L1 包或 L1训练成本实测。新 L1 的目标运行时 preflight/训练成本仍未测。

新 release=`ch2_disaster_relief_n02_graph_variant_repair_l1_20261016`，candidate run ID=`n02-l1-graph-variant-repair-run-20261016-01`。Request 为 authorized=false、request_frozen=false、execution_started=false、server_submission=not_performed、budget=null；Attempt 为 attempt_started=false、execution_receipt=null、pipeline_execution/training_or_rollout=not_run。状态明确 NOT_APPROVED，未复制旧正式授权为新授权。静态侧车中的 independent_review=pending 是被冻结身份的一部分；本独立报告另存，不回写侧车改变身份。

旧权威 final 目录按既有 hash audit 复核：原53项包哈希全部保持，68个原正式证据文件的实测 SHA-256 全部保持。旧 L0 结果仍是旧 L0 结果。审核只新增本报告，没有改动身份/包/归档/旧证据，没有 SSH、forward、训练、部署或新研究，也没有引入额外审批步骤。
