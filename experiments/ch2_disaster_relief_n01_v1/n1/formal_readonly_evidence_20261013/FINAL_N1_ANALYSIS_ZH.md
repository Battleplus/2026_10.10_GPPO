# N1 完整本地分析与缺失覆盖补录

日期：2026-10-13（Asia/Shanghai）

## 完整性与复算

正式矩阵预期 2,800 个唯一键（heldout 2,240，development 560）。初始取证成功捕获并独立重放 2204 条轨迹；补取 ZIP 中另有 596 条。合计 2800/2,800 条完整轨迹均通过冻结包独立事件重放。补取归档 SHA-256 为 `93a3bcf316f9a71dd69e5f9570f6313dbad5ba7d1a74c3779f5c46a8709e1f31`，ZIP CRC 检查通过。

2,800 个 episode_metrics 键唯一且无缺失；2,800 个 episode row 与 stored audit 的 10 项核心指标逐项一致（差异 0）；episode_metrics canonical row hash 与 runner summary 匹配。初次捕获跳过的 596 个键与补取归档中成功重放的 596 个键完全对应。

2026-10-13 的唯一 N1 invocation 已完成 evaluation 阶段；identity 后缀 `20261012` 是冻结身份字符串，不是本次执行日期。状态、summary 和 stage receipt 报告 2,800 episodes / 2,800 audit pass。随后 shutdown 阶段因 admission receipt cardinality 检查失败；journal 首错为 `shutdown requires exactly one successful n01_full_admission receipt`。这是收尾工程失败，不是评价阶段 0 episodes，也不代表补跑理由。

## Heldout 主指标

边界：heldout 结果在前序工作中已被查看并用于探索性分析，因此这里不是未触碰测试集上的独立确认；其区间应按探索性证据解读。

每个对比先按同一 parent 和同一 learned seed 配对，再对三个固定 seed 的差值取平均。CI 为完整 56-parent row 表上的 10,000 次 paired parent bootstrap；这与 2,800 条轨迹均已独立重放的事实相互补充。正差表示 L1 的 priority-weighted on-time delivery rate 较高。

| Condition | L1-C1 mean [95% CI] | L1-L0 mean [95% CI] |
|---|---:|---:|
| original | -0.007391 [-0.024123, 0.009868] | -0.001829 [-0.022413, 0.017977] |
| scale_8x12 | -0.004415 [-0.023978, 0.017130] | 0.001147 [-0.016391, 0.019359] |
| scale_12x18 | -0.004415 [-0.023978, 0.017130] | 0.001147 [-0.016391, 0.019359] |
| carrier_competition | 0.010125 [-0.000689, 0.025571] | 0.006456 [0.000000, 0.015385] |
| stock_competition | -0.008326 [-0.018624, 0.001082] | 0.002202 [-0.008086, 0.012667] |

## 逐 Seed 与运行指标

以下 heldout 指标按 parent 宏平均。L0/L1 各行单独列出固定 seed；巡查按时率由独立 audit 的 on-time inspection count / inspection task count 汇总。成本列是 episode row 记录的决策耗时，不是主机总资源结算。

### original

| Method | Weighted on-time | On-time inspection (n/N) | Energy | Reassignments | Decision CPU ms/tick | Decision wall ms/tick |
|---|---:|---:|---:|---:|---:|---:|
| C0 | 0.472712 | 0.982143 (110/112) | 4.653548 | 0.000000 | 0.009270 | 0.014682 |
| C1 | 0.970105 | 1.000000 (112/112) | 6.701269 | 3.017857 | 0.021853 | 0.025507 |
| L0-8201 | 0.974105 | 1.000000 (112/112) | 7.074383 | 2.875000 | 2.600981 | 3.742345 |
| L0-8202 | 0.956708 | 1.000000 (112/112) | 6.870954 | 2.500000 | 2.605088 | 3.756405 |
| L0-8203 | 0.962817 | 1.000000 (112/112) | 6.942943 | 3.250000 | 2.544671 | 3.637537 |
| L1-8201 | 0.959581 | 1.000000 (112/112) | 7.295869 | 2.785714 | 3.480509 | 4.984141 |
| L1-8202 | 0.956685 | 1.000000 (112/112) | 6.812063 | 2.821429 | 3.391341 | 4.845183 |
| L1-8203 | 0.971876 | 1.000000 (112/112) | 6.863919 | 2.732143 | 3.363604 | 4.798758 |

### scale_8x12

| Method | Weighted on-time | On-time inspection (n/N) | Energy | Reassignments | Decision CPU ms/tick | Decision wall ms/tick |
|---|---:|---:|---:|---:|---:|---:|
| C0 | 0.472712 | 0.982143 (220/224) | 9.307095 | 0.000000 | 0.009497 | 0.009578 |
| C1 | 0.970105 | 1.000000 (224/224) | 13.402538 | 6.035714 | 0.010082 | 0.012533 |
| L0-8201 | 0.974105 | 1.000000 (224/224) | 14.148766 | 5.785714 | 5.824627 | 8.715011 |
| L0-8202 | 0.956708 | 1.000000 (224/224) | 13.741908 | 5.000000 | 5.540814 | 8.437775 |
| L0-8203 | 0.962817 | 1.000000 (224/224) | 13.885886 | 6.500000 | 5.862938 | 8.765702 |
| L1-8201 | 0.959581 | 1.000000 (224/224) | 14.527065 | 5.535714 | 6.369024 | 9.642224 |
| L1-8202 | 0.967399 | 1.000000 (224/224) | 13.692835 | 5.642857 | 6.759311 | 10.271898 |
| L1-8203 | 0.970090 | 1.000000 (224/224) | 13.683131 | 5.464286 | 6.161376 | 9.339822 |

### scale_12x18

| Method | Weighted on-time | On-time inspection (n/N) | Energy | Reassignments | Decision CPU ms/tick | Decision wall ms/tick |
|---|---:|---:|---:|---:|---:|---:|
| C0 | 0.472712 | 0.982143 (330/336) | 13.960643 | 0.000000 | 0.013599 | 0.024410 |
| C1 | 0.970105 | 1.000000 (336/336) | 20.103807 | 9.053571 | 0.031463 | 0.049933 |
| L0-8201 | 0.974105 | 1.000000 (336/336) | 21.223149 | 8.732143 | 15.030201 | 23.230187 |
| L0-8202 | 0.956708 | 1.000000 (336/336) | 20.612862 | 7.607143 | 14.917938 | 23.410021 |
| L0-8203 | 0.962817 | 1.000000 (336/336) | 20.828828 | 9.964286 | 14.809319 | 23.306409 |
| L1-8201 | 0.959581 | 1.000000 (336/336) | 21.785464 | 8.535714 | 16.025281 | 25.468022 |
| L1-8202 | 0.967399 | 1.000000 (336/336) | 20.559872 | 8.142857 | 15.800170 | 24.987187 |
| L1-8203 | 0.970090 | 1.000000 (336/336) | 20.523465 | 8.232143 | 15.873934 | 24.887958 |

### carrier_competition

| Method | Weighted on-time | On-time inspection (n/N) | Energy | Reassignments | Decision CPU ms/tick | Decision wall ms/tick |
|---|---:|---:|---:|---:|---:|---:|
| C0 | 0.229130 | 0.982143 (110/112) | 3.455132 | 0.000000 | 0.009108 | 0.017554 |
| C1 | 0.470486 | 1.000000 (112/112) | 4.178483 | 2.267857 | 0.007540 | 0.013590 |
| L0-8201 | 0.466203 | 1.000000 (112/112) | 4.662679 | 2.375000 | 2.625447 | 4.511024 |
| L0-8202 | 0.474559 | 1.000000 (112/112) | 4.454068 | 2.125000 | 2.983144 | 5.102712 |
| L0-8203 | 0.481702 | 1.000000 (112/112) | 4.568413 | 2.250000 | 2.585273 | 4.493887 |
| L1-8201 | 0.473071 | 1.000000 (112/112) | 4.783447 | 2.392857 | 3.803804 | 6.654628 |
| L1-8202 | 0.485273 | 1.000000 (112/112) | 4.213795 | 2.357143 | 3.651234 | 6.063153 |
| L1-8203 | 0.483488 | 1.000000 (112/112) | 4.512609 | 2.267857 | 3.475593 | 6.161524 |

### stock_competition

| Method | Weighted on-time | On-time inspection (n/N) | Energy | Reassignments | Decision CPU ms/tick | Decision wall ms/tick |
|---|---:|---:|---:|---:|---:|---:|
| C0 | 0.392885 | 0.982143 (110/112) | 4.233518 | 0.000000 | 0.008570 | 0.011048 |
| C1 | 0.748136 | 1.000000 (112/112) | 5.515669 | 2.660714 | 0.007113 | 0.007782 |
| L0-8201 | 0.738895 | 1.000000 (112/112) | 5.849994 | 2.357143 | 2.163082 | 3.854589 |
| L0-8202 | 0.742184 | 1.000000 (112/112) | 5.703691 | 1.964286 | 2.448375 | 4.281352 |
| L0-8203 | 0.731745 | 1.000000 (112/112) | 5.678531 | 3.071429 | 2.434545 | 3.925819 |
| L1-8201 | 0.729375 | 1.000000 (112/112) | 6.068943 | 2.321429 | 3.388753 | 5.703208 |
| L1-8202 | 0.746746 | 1.000000 (112/112) | 5.595129 | 2.214286 | 3.006997 | 5.182478 |
| L1-8203 | 0.743309 | 1.000000 (112/112) | 5.637040 | 2.464286 | 3.141650 | 5.398467 |

## Development 描述性摘要

development 单独列示，不与 heldout 合并推断。L0/L1 为三个固定 seed 的宏均值；巡查率同时报告总按时数/巡查任务数。

| Condition | Method | Weighted on-time | On-time inspection (n/N) | Energy |
|---|---|---:|---:|---:|
| original | C0 | 0.476394 | 1.000000 (28/28) | 4.293863 |
| original | C1 | 0.942262 | 1.000000 (28/28) | 6.579526 |
| original | L0 (3-seed mean) | 0.950198 | 1.000000 (84/84) | 6.805559 |
| original | L1 (3-seed mean) | 0.950198 | 1.000000 (84/84) | 6.803725 |
| scale_8x12 | C0 | 0.476394 | 1.000000 (56/56) | 8.587725 |
| scale_8x12 | C1 | 0.942262 | 1.000000 (56/56) | 13.159052 |
| scale_8x12 | L0 (3-seed mean) | 0.950198 | 1.000000 (168/168) | 13.611118 |
| scale_8x12 | L1 (3-seed mean) | 0.950198 | 1.000000 (168/168) | 13.623303 |
| scale_12x18 | C0 | 0.476394 | 1.000000 (84/84) | 12.881588 |
| scale_12x18 | C1 | 0.942262 | 1.000000 (84/84) | 19.738578 |
| scale_12x18 | L0 (3-seed mean) | 0.950198 | 1.000000 (252/252) | 20.416677 |
| scale_12x18 | L1 (3-seed mean) | 0.950198 | 1.000000 (252/252) | 20.441516 |
| carrier_competition | C0 | 0.276686 | 1.000000 (28/28) | 3.122862 |
| carrier_competition | C1 | 0.546948 | 1.000000 (28/28) | 4.176111 |
| carrier_competition | L0 (3-seed mean) | 0.539011 | 1.000000 (84/84) | 4.389460 |
| carrier_competition | L1 (3-seed mean) | 0.539011 | 1.000000 (84/84) | 4.404721 |
| stock_competition | C0 | 0.350250 | 1.000000 (28/28) | 3.930476 |
| stock_competition | C1 | 0.736881 | 1.000000 (28/28) | 5.468722 |
| stock_competition | L0 (3-seed mean) | 0.730532 | 1.000000 (84/84) | 5.690065 |
| stock_competition | L1 (3-seed mean) | 0.717833 | 1.000000 (84/84) | 5.704530 |

## Scale 配对核验

Scenario manifest 将 scale_8x12 和 scale_12x18 中的 70 个输入逐一绑定到相同 `source_parent_id`。冻结生成器对同一 base scenario 分别做 2 份和 3 份独立复制；审计确认 70/70 对的共享 map、8 个共享 platform 记录及全部共享 task 记录完全一致，规模分别为 8/12 platforms 与 12/18 tasks（外部承诺场景 14/21 tasks）。

虽然两个规模的全部 row-level primary rates 对每个 parent、每个 method 和每个 seed 都逐项相等（development 14/14、heldout 56/56），能耗、reassignment 和决策成本会随额外副本变化。依据已审阅的生成器克隆规则，这种比率相等符合复制构造本身，当前证据不支持将其判为错误；因此规模结论应表述为复制压力测试下的行为/成本结果，不把相同比率写成规模扩展带来的性能增益。

## 最差父场景与机制证据

下表按 parent 汇总三个固定 seed 的 L1 减比较策略差值后排序，因此每个 parent 只出现一次。support 仅表示 audit task rows/conservation 中存在可观察模式；unknown 表示轨迹审计不能判定。`policy_choice_error` 一律为 unknown，因为独立 audit 未提供可用于判断替代动作优劣的反事实证据。

### original heldout

**L1-C1**

| Parent (unique) | Seed-mean difference | Registered stratum | Audit evidence: carrier / resource / delay / choice |
|---|---:|---|---|
| `n01-original-graph-v1-heldout-stock_loss-00` | -0.233333 | stock_loss | unknown / support / unknown / unknown |
| `n01-original-graph-v1-heldout-failure-05` | -0.153846 | failure | unknown / unknown / unknown / unknown |
| `n01-original-graph-v1-heldout-external_commitment-00` | -0.133333 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-original-graph-v1-heldout-failure-00` | -0.121212 | failure | unknown / unknown / unknown / unknown |
| `n01-original-graph-v1-heldout-external_commitment-04` | -0.092593 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-original-graph-v1-heldout-external_commitment-05` | -0.074074 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-original-graph-v1-heldout-stock_loss-02` | -0.055556 | stock_loss | unknown / support / unknown / unknown |
| `n01-original-graph-v1-heldout-combined-00` | -0.047619 | combined | unknown / support / unknown / unknown |
| `n01-original-graph-v1-heldout-combined-03` | -0.033333 | combined | unknown / support / unknown / unknown |
| `n01-original-graph-v1-heldout-failure-01` | -0.027778 | failure | unknown / unknown / unknown / unknown |

Seed-level examples for L1-C1 are retained in the JSON field `worst_10_cases_by_condition_with_registered_mechanism_and_audit_evidence`; they can repeat a parent across seeds and are not a unique-parent ranking.

**L1-L0**

| Parent (unique) | Seed-mean difference | Registered stratum | Audit evidence: carrier / resource / delay / choice |
|---|---:|---|---|
| `n01-original-graph-v1-heldout-combined-05` | -0.333333 | combined | unknown / support / unknown / unknown |
| `n01-original-graph-v1-heldout-stock_loss-00` | -0.200000 | stock_loss | unknown / support / unknown / unknown |
| `n01-original-graph-v1-heldout-failure-05` | -0.153846 | failure | unknown / unknown / unknown / unknown |
| `n01-original-graph-v1-heldout-combined-01` | -0.083333 | combined | unknown / support / support / unknown |
| `n01-original-graph-v1-heldout-external_commitment-00` | -0.066667 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-original-graph-v1-heldout-combined-00` | -0.047619 | combined | unknown / support / unknown / unknown |
| `n01-original-graph-v1-heldout-stock_loss-02` | -0.027778 | stock_loss | unknown / support / unknown / unknown |
| `n01-original-graph-v1-heldout-combined-03` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-original-graph-v1-heldout-combined-04` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-original-graph-v1-heldout-combined-06` | 0.000000 | combined | unknown / support / unknown / unknown |

Seed-level examples for L1-L0 are retained in the JSON field `worst_10_cases_by_condition_with_registered_mechanism_and_audit_evidence`; they can repeat a parent across seeds and are not a unique-parent ranking.

### scale_8x12 heldout

**L1-C1**

| Parent (unique) | Seed-mean difference | Registered stratum | Audit evidence: carrier / resource / delay / choice |
|---|---:|---|---|
| `n01-scale_8x12-graph-v1-heldout-stock_loss-00` | -0.266667 | stock_loss | unknown / support / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-failure-05` | -0.153846 | failure | unknown / unknown / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-00` | -0.133333 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-failure-00` | -0.121212 | failure | unknown / unknown / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-04` | -0.092593 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-05` | -0.074074 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-stock_loss-02` | -0.055556 | stock_loss | unknown / support / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-combined-00` | -0.047619 | combined | unknown / support / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-failure-01` | -0.027778 | failure | unknown / unknown / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-combined-02` | 0.000000 | combined | unknown / support / unknown / unknown |

Seed-level examples for L1-C1 are retained in the JSON field `worst_10_cases_by_condition_with_registered_mechanism_and_audit_evidence`; they can repeat a parent across seeds and are not a unique-parent ranking.

**L1-L0**

| Parent (unique) | Seed-mean difference | Registered stratum | Audit evidence: carrier / resource / delay / choice |
|---|---:|---|---|
| `n01-scale_8x12-graph-v1-heldout-stock_loss-00` | -0.233333 | stock_loss | unknown / support / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-combined-05` | -0.166667 | combined | unknown / support / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-failure-05` | -0.153846 | failure | unknown / unknown / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-combined-01` | -0.083333 | combined | unknown / support / support / unknown |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-00` | -0.066667 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-combined-00` | -0.047619 | combined | unknown / support / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-stock_loss-02` | -0.027778 | stock_loss | unknown / support / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-combined-04` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-combined-06` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-scale_8x12-graph-v1-heldout-combined-07` | 0.000000 | combined | unknown / support / unknown / unknown |

Seed-level examples for L1-L0 are retained in the JSON field `worst_10_cases_by_condition_with_registered_mechanism_and_audit_evidence`; they can repeat a parent across seeds and are not a unique-parent ranking.

### scale_12x18 heldout

**L1-C1**

| Parent (unique) | Seed-mean difference | Registered stratum | Audit evidence: carrier / resource / delay / choice |
|---|---:|---|---|
| `n01-scale_12x18-graph-v1-heldout-stock_loss-00` | -0.266667 | stock_loss | unknown / support / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-failure-05` | -0.153846 | failure | unknown / unknown / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-00` | -0.133333 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-failure-00` | -0.121212 | failure | unknown / unknown / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-04` | -0.092593 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-05` | -0.074074 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-stock_loss-02` | -0.055556 | stock_loss | unknown / support / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-combined-00` | -0.047619 | combined | unknown / support / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-failure-01` | -0.027778 | failure | unknown / unknown / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-combined-02` | 0.000000 | combined | unknown / support / unknown / unknown |

Seed-level examples for L1-C1 are retained in the JSON field `worst_10_cases_by_condition_with_registered_mechanism_and_audit_evidence`; they can repeat a parent across seeds and are not a unique-parent ranking.

**L1-L0**

| Parent (unique) | Seed-mean difference | Registered stratum | Audit evidence: carrier / resource / delay / choice |
|---|---:|---|---|
| `n01-scale_12x18-graph-v1-heldout-stock_loss-00` | -0.233333 | stock_loss | unknown / support / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-combined-05` | -0.166667 | combined | unknown / support / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-failure-05` | -0.153846 | failure | unknown / unknown / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-combined-01` | -0.083333 | combined | unknown / support / support / unknown |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-00` | -0.066667 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-combined-00` | -0.047619 | combined | unknown / support / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-stock_loss-02` | -0.027778 | stock_loss | unknown / support / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-combined-04` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-combined-06` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-scale_12x18-graph-v1-heldout-combined-07` | 0.000000 | combined | unknown / support / unknown / unknown |

Seed-level examples for L1-L0 are retained in the JSON field `worst_10_cases_by_condition_with_registered_mechanism_and_audit_evidence`; they can repeat a parent across seeds and are not a unique-parent ranking.

### carrier_competition heldout

**L1-C1**

| Parent (unique) | Seed-mean difference | Registered stratum | Audit evidence: carrier / resource / delay / choice |
|---|---:|---|---|
| `n01-carrier-graph-v1-heldout-stock_loss-00` | -0.066667 | stock_loss | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-stock_loss-02` | -0.027778 | stock_loss | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-00` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-01` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-02` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-03` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-04` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-06` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-07` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-control-00` | 0.000000 | control | unknown / unknown / unknown / unknown |

Seed-level examples for L1-C1 are retained in the JSON field `worst_10_cases_by_condition_with_registered_mechanism_and_audit_evidence`; they can repeat a parent across seeds and are not a unique-parent ranking.

**L1-L0**

| Parent (unique) | Seed-mean difference | Registered stratum | Audit evidence: carrier / resource / delay / choice |
|---|---:|---|---|
| `n01-carrier-graph-v1-heldout-combined-00` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-01` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-02` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-03` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-04` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-06` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-combined-07` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-carrier-graph-v1-heldout-control-00` | 0.000000 | control | unknown / unknown / unknown / unknown |
| `n01-carrier-graph-v1-heldout-control-01` | 0.000000 | control | unknown / unknown / unknown / unknown |
| `n01-carrier-graph-v1-heldout-control-02` | 0.000000 | control | unknown / unknown / unknown / unknown |

Seed-level examples for L1-L0 are retained in the JSON field `worst_10_cases_by_condition_with_registered_mechanism_and_audit_evidence`; they can repeat a parent across seeds and are not a unique-parent ranking.

### stock_competition heldout

**L1-C1**

| Parent (unique) | Seed-mean difference | Registered stratum | Audit evidence: carrier / resource / delay / choice |
|---|---:|---|---|
| `n01-stock-graph-v1-heldout-stock_loss-00` | -0.166667 | stock_loss | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-01` | -0.145833 | combined | unknown / support / support / unknown |
| `n01-stock-graph-v1-heldout-failure-05` | -0.076923 | failure | unknown / unknown / unknown / unknown |
| `n01-stock-graph-v1-heldout-external_commitment-05` | -0.074074 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-02` | -0.055556 | combined | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-00` | -0.047619 | combined | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-failure-01` | -0.027778 | failure | unknown / unknown / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-03` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-04` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-05` | 0.000000 | combined | unknown / support / unknown / unknown |

Seed-level examples for L1-C1 are retained in the JSON field `worst_10_cases_by_condition_with_registered_mechanism_and_audit_evidence`; they can repeat a parent across seeds and are not a unique-parent ranking.

**L1-L0**

| Parent (unique) | Seed-mean difference | Registered stratum | Audit evidence: carrier / resource / delay / choice |
|---|---:|---|---|
| `n01-stock-graph-v1-heldout-stock_loss-00` | -0.166667 | stock_loss | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-02` | -0.055556 | combined | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-00` | -0.047619 | combined | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-external_commitment-00` | -0.044444 | external_commitment | unknown / unknown / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-01` | -0.041667 | combined | unknown / support / support / unknown |
| `n01-stock-graph-v1-heldout-combined-03` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-04` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-05` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-06` | 0.000000 | combined | unknown / support / unknown / unknown |
| `n01-stock-graph-v1-heldout-combined-07` | 0.000000 | combined | unknown / unknown / unknown / unknown |

Seed-level examples for L1-L0 are retained in the JSON field `worst_10_cases_by_condition_with_registered_mechanism_and_audit_evidence`; they can repeat a parent across seeds and are not a unique-parent ranking.

## 相对 Original 的同源场景差异

按 `source_parent_id` 对齐各 condition 与 original；每个 parent 先平均三个 L1 seed 的 primary-rate 差值，再对 heldout parents 做 10,000 次 paired bootstrap。该差值描述 condition 输入变化下 L1 的相对变化，不单独解释为因果效应。

| Condition vs original | Matched heldout parents | L1 weighted on-time delta [95% bootstrap interval] |
|---|---:|---:|
| original | 56 | 0.000000 [0.000000, 0.000000] |
| scale_8x12 | 56 | 0.002976 [-0.001190, 0.010119] |
| scale_12x18 | 56 | 0.002976 [-0.001190, 0.009524] |
| carrier_competition | 56 | -0.482103 [-0.516016, -0.447101] |
| stock_competition | 56 | -0.222904 [-0.263934, -0.183529] |

## 逐 Seed 最差案例补充

此处保留原逐 seed 排序案例，可能同一 parent 因不同 seed 多次出现；唯一父场景排序见上一节。

### original heldout

**L1-C1**

| Parent / seed | Difference | Registered stratum | Scheduled disturbance(s) | L1 outcomes (unmet/late/reassigned) |
|---|---:|---|---|---:|
| `n01-original-graph-v1-heldout-stock_loss-00` / 8201 | -0.600000 | stock_loss | stock_loss@t7 delay=0 | 1/1/3 |
| `n01-original-graph-v1-heldout-external_commitment-04` / 8203 | -0.277778 | external_commitment | none | 0/1/2 |
| `n01-original-graph-v1-heldout-failure-05` / 8201 | -0.230769 | failure | failure@t18 delay=0 | 0/1/2 |
| `n01-original-graph-v1-heldout-failure-05` / 8202 | -0.230769 | failure | failure@t18 delay=0 | 0/1/3 |
| `n01-original-graph-v1-heldout-external_commitment-05` / 8203 | -0.222222 | external_commitment | none | 0/1/2 |
| `n01-original-graph-v1-heldout-external_commitment-00` / 8202 | -0.200000 | external_commitment | none | 0/1/2 |
| `n01-original-graph-v1-heldout-external_commitment-00` / 8203 | -0.200000 | external_commitment | none | 0/1/4 |
| `n01-original-graph-v1-heldout-failure-00` / 8201 | -0.181818 | failure | failure@t9 delay=0 | 1/0/1 |
| `n01-original-graph-v1-heldout-failure-00` / 8202 | -0.181818 | failure | failure@t9 delay=0 | 1/0/3 |
| `n01-original-graph-v1-heldout-combined-03` / 8202 | -0.100000 | combined | failure@t13 delay=8; energy_change@t17 delay=8; stock_loss@t11 delay=9 | 1/0/3 |

**L1-L0**

| Parent / seed | Difference | Registered stratum | Scheduled disturbance(s) | L1 outcomes (unmet/late/reassigned) |
|---|---:|---|---|---:|
| `n01-original-graph-v1-heldout-stock_loss-00` / 8201 | -0.600000 | stock_loss | stock_loss@t7 delay=0 | 1/1/3 |
| `n01-original-graph-v1-heldout-combined-05` / 8201 | -0.500000 | combined | failure@t2 delay=3; energy_change@t10 delay=10; stock_loss@t15 delay=9 | 1/0/4 |
| `n01-original-graph-v1-heldout-combined-05` / 8202 | -0.500000 | combined | failure@t2 delay=3; energy_change@t10 delay=10; stock_loss@t15 delay=9 | 1/0/4 |
| `n01-original-graph-v1-heldout-external_commitment-04` / 8203 | -0.277778 | external_commitment | none | 0/1/2 |
| `n01-original-graph-v1-heldout-failure-05` / 8201 | -0.230769 | failure | failure@t18 delay=0 | 0/1/2 |
| `n01-original-graph-v1-heldout-failure-05` / 8202 | -0.230769 | failure | failure@t18 delay=0 | 0/1/3 |
| `n01-original-graph-v1-heldout-external_commitment-00` / 8202 | -0.200000 | external_commitment | none | 0/1/2 |
| `n01-original-graph-v1-heldout-external_commitment-00` / 8203 | -0.200000 | external_commitment | none | 0/1/4 |
| `n01-original-graph-v1-heldout-combined-01` / 8202 | -0.125000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 1/0/2 |
| `n01-original-graph-v1-heldout-combined-01` / 8203 | -0.125000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 1/0/2 |

### scale_8x12 heldout

**L1-C1**

| Parent / seed | Difference | Registered stratum | Scheduled disturbance(s) | L1 outcomes (unmet/late/reassigned) |
|---|---:|---|---|---:|
| `n01-scale_8x12-graph-v1-heldout-stock_loss-00` / 8201 | -0.600000 | stock_loss | stock_loss@t7 delay=0; stock_loss@t7 delay=0 | 2/2/8 |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-04` / 8203 | -0.277778 | external_commitment | none | 0/2/4 |
| `n01-scale_8x12-graph-v1-heldout-failure-05` / 8201 | -0.230769 | failure | failure@t18 delay=0; failure@t18 delay=0 | 0/2/4 |
| `n01-scale_8x12-graph-v1-heldout-failure-05` / 8202 | -0.230769 | failure | failure@t18 delay=0; failure@t18 delay=0 | 0/2/6 |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-05` / 8203 | -0.222222 | external_commitment | none | 0/2/4 |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-00` / 8202 | -0.200000 | external_commitment | none | 0/2/4 |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-00` / 8203 | -0.200000 | external_commitment | none | 0/2/8 |
| `n01-scale_8x12-graph-v1-heldout-failure-00` / 8201 | -0.181818 | failure | failure@t9 delay=0; failure@t9 delay=0 | 2/0/2 |
| `n01-scale_8x12-graph-v1-heldout-failure-00` / 8202 | -0.181818 | failure | failure@t9 delay=0; failure@t9 delay=0 | 2/0/6 |
| `n01-scale_8x12-graph-v1-heldout-stock_loss-00` / 8202 | -0.100000 | stock_loss | stock_loss@t7 delay=0; stock_loss@t7 delay=0 | 2/0/4 |

**L1-L0**

| Parent / seed | Difference | Registered stratum | Scheduled disturbance(s) | L1 outcomes (unmet/late/reassigned) |
|---|---:|---|---|---:|
| `n01-scale_8x12-graph-v1-heldout-stock_loss-00` / 8201 | -0.600000 | stock_loss | stock_loss@t7 delay=0; stock_loss@t7 delay=0 | 2/2/8 |
| `n01-scale_8x12-graph-v1-heldout-combined-05` / 8201 | -0.500000 | combined | failure@t2 delay=3; energy_change@t10 delay=10; stock_loss@t15 delay=9; failure@t2 delay=3; energy_change@t10 delay=10; stock_loss@t15 delay=9 | 2/0/8 |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-04` / 8203 | -0.277778 | external_commitment | none | 0/2/4 |
| `n01-scale_8x12-graph-v1-heldout-failure-05` / 8201 | -0.230769 | failure | failure@t18 delay=0; failure@t18 delay=0 | 0/2/4 |
| `n01-scale_8x12-graph-v1-heldout-failure-05` / 8202 | -0.230769 | failure | failure@t18 delay=0; failure@t18 delay=0 | 0/2/6 |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-00` / 8202 | -0.200000 | external_commitment | none | 0/2/4 |
| `n01-scale_8x12-graph-v1-heldout-external_commitment-00` / 8203 | -0.200000 | external_commitment | none | 0/2/8 |
| `n01-scale_8x12-graph-v1-heldout-combined-01` / 8202 | -0.125000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6; failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 0/2/4 |
| `n01-scale_8x12-graph-v1-heldout-combined-01` / 8203 | -0.125000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6; failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 2/0/4 |
| `n01-scale_8x12-graph-v1-heldout-stock_loss-00` / 8203 | -0.100000 | stock_loss | stock_loss@t7 delay=0; stock_loss@t7 delay=0 | 2/0/4 |

### scale_12x18 heldout

**L1-C1**

| Parent / seed | Difference | Registered stratum | Scheduled disturbance(s) | L1 outcomes (unmet/late/reassigned) |
|---|---:|---|---|---:|
| `n01-scale_12x18-graph-v1-heldout-stock_loss-00` / 8201 | -0.600000 | stock_loss | stock_loss@t7 delay=0; stock_loss@t7 delay=0; stock_loss@t7 delay=0 | 3/3/9 |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-04` / 8203 | -0.277778 | external_commitment | none | 0/3/6 |
| `n01-scale_12x18-graph-v1-heldout-failure-05` / 8201 | -0.230769 | failure | failure@t18 delay=0; failure@t18 delay=0; failure@t18 delay=0 | 0/3/6 |
| `n01-scale_12x18-graph-v1-heldout-failure-05` / 8202 | -0.230769 | failure | failure@t18 delay=0; failure@t18 delay=0; failure@t18 delay=0 | 0/3/9 |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-05` / 8203 | -0.222222 | external_commitment | none | 0/3/9 |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-00` / 8202 | -0.200000 | external_commitment | none | 0/3/6 |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-00` / 8203 | -0.200000 | external_commitment | none | 0/3/12 |
| `n01-scale_12x18-graph-v1-heldout-failure-00` / 8201 | -0.181818 | failure | failure@t9 delay=0; failure@t9 delay=0; failure@t9 delay=0 | 3/0/3 |
| `n01-scale_12x18-graph-v1-heldout-failure-00` / 8202 | -0.181818 | failure | failure@t9 delay=0; failure@t9 delay=0; failure@t9 delay=0 | 3/0/9 |
| `n01-scale_12x18-graph-v1-heldout-stock_loss-00` / 8202 | -0.100000 | stock_loss | stock_loss@t7 delay=0; stock_loss@t7 delay=0; stock_loss@t7 delay=0 | 3/0/8 |

**L1-L0**

| Parent / seed | Difference | Registered stratum | Scheduled disturbance(s) | L1 outcomes (unmet/late/reassigned) |
|---|---:|---|---|---:|
| `n01-scale_12x18-graph-v1-heldout-stock_loss-00` / 8201 | -0.600000 | stock_loss | stock_loss@t7 delay=0; stock_loss@t7 delay=0; stock_loss@t7 delay=0 | 3/3/9 |
| `n01-scale_12x18-graph-v1-heldout-combined-05` / 8201 | -0.500000 | combined | failure@t2 delay=3; energy_change@t10 delay=10; stock_loss@t15 delay=9; failure@t2 delay=3; energy_change@t10 delay=10; stock_loss@t15 delay=9; failure@t2 delay=3; energy_change@t10 delay=10; stock_loss@t15 delay=9 | 3/0/12 |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-04` / 8203 | -0.277778 | external_commitment | none | 0/3/6 |
| `n01-scale_12x18-graph-v1-heldout-failure-05` / 8201 | -0.230769 | failure | failure@t18 delay=0; failure@t18 delay=0; failure@t18 delay=0 | 0/3/6 |
| `n01-scale_12x18-graph-v1-heldout-failure-05` / 8202 | -0.230769 | failure | failure@t18 delay=0; failure@t18 delay=0; failure@t18 delay=0 | 0/3/9 |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-00` / 8202 | -0.200000 | external_commitment | none | 0/3/6 |
| `n01-scale_12x18-graph-v1-heldout-external_commitment-00` / 8203 | -0.200000 | external_commitment | none | 0/3/12 |
| `n01-scale_12x18-graph-v1-heldout-combined-01` / 8202 | -0.125000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6; failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6; failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 0/3/6 |
| `n01-scale_12x18-graph-v1-heldout-combined-01` / 8203 | -0.125000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6; failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6; failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 3/0/6 |
| `n01-scale_12x18-graph-v1-heldout-stock_loss-00` / 8203 | -0.100000 | stock_loss | stock_loss@t7 delay=0; stock_loss@t7 delay=0; stock_loss@t7 delay=0 | 3/0/6 |

### carrier_competition heldout

**L1-C1**

| Parent / seed | Difference | Registered stratum | Scheduled disturbance(s) | L1 outcomes (unmet/late/reassigned) |
|---|---:|---|---|---:|
| `n01-carrier-graph-v1-heldout-stock_loss-00` / 8201 | -0.100000 | stock_loss | stock_loss@t7 delay=0 | 3/0/3 |
| `n01-carrier-graph-v1-heldout-stock_loss-00` / 8203 | -0.100000 | stock_loss | stock_loss@t7 delay=0 | 3/0/3 |
| `n01-carrier-graph-v1-heldout-stock_loss-02` / 8201 | -0.083333 | stock_loss | stock_loss@t16 delay=0 | 2/1/2 |
| `n01-carrier-graph-v1-heldout-combined-00` / 8201 | 0.000000 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-00` / 8202 | 0.000000 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-00` / 8203 | 0.000000 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 2/0/1 |
| `n01-carrier-graph-v1-heldout-combined-01` / 8201 | 0.000000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-01` / 8202 | 0.000000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-01` / 8203 | 0.000000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-02` / 8201 | 0.000000 | combined | failure@t19 delay=10; energy_change@t18 delay=3; stock_loss@t3 delay=12 | 2/0/1 |

**L1-L0**

| Parent / seed | Difference | Registered stratum | Scheduled disturbance(s) | L1 outcomes (unmet/late/reassigned) |
|---|---:|---|---|---:|
| `n01-carrier-graph-v1-heldout-stock_loss-00` / 8203 | -0.100000 | stock_loss | stock_loss@t7 delay=0 | 3/0/3 |
| `n01-carrier-graph-v1-heldout-combined-00` / 8201 | 0.000000 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-00` / 8202 | 0.000000 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-00` / 8203 | 0.000000 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 2/0/1 |
| `n01-carrier-graph-v1-heldout-combined-01` / 8201 | 0.000000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-01` / 8202 | 0.000000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-01` / 8203 | 0.000000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-02` / 8201 | 0.000000 | combined | failure@t19 delay=10; energy_change@t18 delay=3; stock_loss@t3 delay=12 | 2/0/1 |
| `n01-carrier-graph-v1-heldout-combined-02` / 8202 | 0.000000 | combined | failure@t19 delay=10; energy_change@t18 delay=3; stock_loss@t3 delay=12 | 2/0/3 |
| `n01-carrier-graph-v1-heldout-combined-02` / 8203 | 0.000000 | combined | failure@t19 delay=10; energy_change@t18 delay=3; stock_loss@t3 delay=12 | 2/0/3 |

### stock_competition heldout

**L1-C1**

| Parent / seed | Difference | Registered stratum | Scheduled disturbance(s) | L1 outcomes (unmet/late/reassigned) |
|---|---:|---|---|---:|
| `n01-stock-graph-v1-heldout-stock_loss-00` / 8201 | -0.500000 | stock_loss | stock_loss@t7 delay=0 | 1/1/3 |
| `n01-stock-graph-v1-heldout-combined-01` / 8201 | -0.312500 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 2/0/2 |
| `n01-stock-graph-v1-heldout-failure-05` / 8201 | -0.230769 | failure | failure@t18 delay=0 | 1/1/2 |
| `n01-stock-graph-v1-heldout-external_commitment-05` / 8203 | -0.222222 | external_commitment | none | 1/1/2 |
| `n01-stock-graph-v1-heldout-combined-02` / 8201 | -0.166667 | combined | failure@t19 delay=10; energy_change@t18 delay=3; stock_loss@t3 delay=12 | 2/0/1 |
| `n01-stock-graph-v1-heldout-combined-01` / 8203 | -0.125000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 2/0/2 |
| `n01-stock-graph-v1-heldout-failure-01` / 8202 | -0.083333 | failure | failure@t4 delay=0 | 2/0/1 |
| `n01-stock-graph-v1-heldout-combined-00` / 8201 | -0.071429 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 2/0/2 |
| `n01-stock-graph-v1-heldout-combined-00` / 8202 | -0.071429 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 2/0/2 |
| `n01-stock-graph-v1-heldout-combined-00` / 8203 | 0.000000 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 1/0/1 |

**L1-L0**

| Parent / seed | Difference | Registered stratum | Scheduled disturbance(s) | L1 outcomes (unmet/late/reassigned) |
|---|---:|---|---|---:|
| `n01-stock-graph-v1-heldout-stock_loss-00` / 8201 | -0.500000 | stock_loss | stock_loss@t7 delay=0 | 1/1/3 |
| `n01-stock-graph-v1-heldout-combined-01` / 8201 | -0.312500 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 2/0/2 |
| `n01-stock-graph-v1-heldout-combined-02` / 8201 | -0.166667 | combined | failure@t19 delay=10; energy_change@t18 delay=3; stock_loss@t3 delay=12 | 2/0/1 |
| `n01-stock-graph-v1-heldout-external_commitment-00` / 8203 | -0.133333 | external_commitment | none | 1/0/4 |
| `n01-stock-graph-v1-heldout-combined-00` / 8201 | -0.071429 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 2/0/2 |
| `n01-stock-graph-v1-heldout-combined-00` / 8202 | -0.071429 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 2/0/2 |
| `n01-stock-graph-v1-heldout-combined-00` / 8203 | 0.000000 | combined | failure@t12 delay=8; energy_change@t6 delay=11; stock_loss@t19 delay=12 | 1/0/1 |
| `n01-stock-graph-v1-heldout-combined-01` / 8202 | 0.000000 | combined | failure@t17 delay=6; energy_change@t11 delay=8; stock_loss@t13 delay=6 | 1/0/2 |
| `n01-stock-graph-v1-heldout-combined-02` / 8202 | 0.000000 | combined | failure@t19 delay=10; energy_change@t18 delay=3; stock_loss@t3 delay=12 | 1/0/1 |
| `n01-stock-graph-v1-heldout-combined-02` / 8203 | 0.000000 | combined | failure@t19 delay=10; energy_change@t18 delay=3; stock_loss@t3 delay=12 | 1/0/3 |

## 判断与边界

正式 evaluation 矩阵完整，无需重新评价或训练。596 条初始只读取证跳过项已从预先存在的正式 ZIP 本地补取并全数独立复算；没有因捕获上限产生的正式评价键缺口。完整审计仍需由 `formal_eval_result_reviewer` 独立复核，本报告作者不自我认证。

Development 结果仅作描述。固定 checkpoint 的三个 training seed 已分别列示；bootstrap 区间只反映 parent 抽样，不估计更广泛的 training-seed 不确定性。episode row timing 是记录的策略决策耗时，平台/systemd 的资源结算应引用对应收据而非该表。
