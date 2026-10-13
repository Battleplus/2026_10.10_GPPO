# N1 节点判断（2026-10-13）

## 判断

N1 的 350 个父场景（5 个条件各 70 个）分别运行 8 个固定策略臂，共 2,800 条唯一轨迹；最终独立复核确认 2,800/2,800 条通过冻结包 `full_artifact` 重放。六个固定 checkpoint 文件的 SHA-256 均与通过的 checkpoint barrier 逐项相符。评价键为 heldout 2,240、development 560。条件差异先按同一父场景和固定训练 seed 配对；heldout 指标区间使用 56 个父场景上的 10,000 次 paired-parent bootstrap。

这批结果不证明稳定的图结构优势。`carrier_competition` 的 heldout L1-L0 差为 +0.006456，95% 区间 [0.000000, 0.015385]；L1-C1 差为 +0.010125，95% 区间 [-0.000689, 0.025571]。两者都是探索性估计：结果条件于三个既定训练 seed，bootstrap 只反映父场景抽样，不估计训练 seed 间不确定性；预注册材料也将本批数据界定为 development/exploratory，不作确认性或泛化证据。

规模条件是复制输入压力测试：`scale_8x12` 和 `scale_12x18` 由相同 70 个源场景复制生成，主指标逐行相同，能耗、改派和决策成本随副本数变化；因此不能据此声称规模扩展提升了主指标。`carrier_competition` 同时提高已知食物与首个隐藏 `latent-medical` 任务的数量，保留源库存和其他输入；场景还包含候选载具不足及库存短缺可能。它是载具与库存混杂的联合压力条件，不是纯载重因果检验。

成本只照录最终独立审核报告：阶段 ledger 报 admission 2.64 CPU / 3.13 wall 秒、evaluation 2,506.53 / 2,682.88 秒、export 46.88 / 49.58 秒、shutdown 4.97 / 5.73 秒；最终 cgroup CPU 使用约 2,563.20 秒，memory peak 为 2,760,151,040 字节，OOM/OOM-kill 均为 0。该报告说明资源采样有区间/结算限制，kernel CPU quota 不可用；这些数值不代表完整主机开销。

正式 unit 仍按原记录判失败。shutdown 校验把 admission ledger 顶层 `status=complete` 当作应为 `accepted`，而 `accepted` 实际在嵌套 `result.status` 中；校验在 cgroup membership scan 前失败。独立 reviewer 核验了一次只读 closeout：2026-10-13T02:52:59Z–02:53:01Z，InvocationID 匹配，`MainPID=0`、`ControlPID=0`，systemd 的 `ControlGroup` 为空；按此前记录的精确 cgroup 路径检查，unit cgroup 目录不存在。因此在本次读取时该 unit cgroup 为空/已不存在。此读数不能证明原 shutdown 时或其间的进程状态；历史 shutdown 时 cleanup 状态仍为 **UNKNOWN**，settlement 仍为 failed，formal PASS 不变。当前时点的清理只读取证已补充；主模型可据此规划 N2 critic-first 接线与验收。本判断不授权 N2/N3 训练，不授权重跑 N1。

## 需求与证据状态

| 判断需求 | 证据 | 状态 / 限制 |
|---|---|---|
| 350 父场景 × 8 策略臂及完整轨迹重放 | `N1_FORMAL_RESULT_FINAL_INDEPENDENT_REVIEW_20261013.md`；`FINAL_N1_ANALYSIS_ZH.md` | 2,800/2,800 通过；350 是父场景数，不是轨迹重放数。 |
| 六个 checkpoint 与 2,240/560 split | `N1_FORMAL_RESULT_FINAL_INDEPENDENT_REVIEW_20261013.md` 的 Checkpoints/Evaluation 行 | 六个文件哈希均匹配 barrier；split 为 heldout 2,240、development 560。 |
| 配对设计、bootstrap 和 carrier 效应 | `FINAL_N1_ANALYSIS_ZH.md`；`experiments/ch2_disaster_relief_n01_v1/SCOPE_AND_PREREGISTRATION.md` | 56 个 heldout 父场景、10,000 次 paired-parent bootstrap；仅探索性，条件于 3 个固定 seed。 |
| 规模与 carrier 条件解释 | `FINAL_N1_ANALYSIS_ZH.md`；`experiments/ch2_disaster_relief_n01_v1/SCOPE_AND_PREREGISTRATION.md` | 复制压力测试；carrier/库存联合压力，纯载重因果效应未识别。 |
| 资源成本与采样限制 | `N1_FORMAL_RESULT_FINAL_INDEPENDENT_REVIEW_20261013.md` 的 Resources 行 | 仅报告已记录阶段和 cgroup 数值；完整主机开销及 kernel CPU quota 不可得。 |
| Shutdown 原因与清理状态 | `N1_FORMAL_RESULT_FINAL_INDEPENDENT_REVIEW_20261013.md`；`READ_ONLY_CAPTURE_REPORT_ZH.md`；`CLEANUP_READBACK_RECEIPT.json`、`CLEANUP_READBACK_STDOUT.txt`、`CLEANUP_READBACK_STDERR.txt` | 首错与状态字段错配已复核；此次读取时 MainPID/ControlPID 均为 0 且原 unit cgroup 路径不存在。仅证明读取时状态，不追溯证明原 shutdown 清理；历史运行仍失败。 |
| 后续节点边界 | 本节点判断及 `experiments/ch2_disaster_relief_n01_v1/SCOPE_AND_PREREGISTRATION.md` 的 stop boundary | 当前时点清理只读取证已补充；历史 shutdown 时状态仍 UNKNOWN。随后由主模型规划 N2 critic-first 接线和验收；N2/N3 训练与 N1 重跑均未授权。 |

本附录是决策整理，不替代独立审核或运行结算。正式结果仍为 shutdown 失败；不得将离线重放通过改写为正式 unit PASS。
