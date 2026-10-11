# 资源结算

批准的整轮预算为 14,400 秒 wall、12,000 秒 CPU；RSS 上限 4 GiB，工作与导出存储上限 8 GiB。下表为阶段记录，单位为秒。

| 阶段 | Wall | CPU | 结果 |
|---|---:|---:|---|
| Runtime 准入 | 3.248 | 3.214 | 通过；目标端 CPU 单线程 |
| 工程短测 | 50.760 | 50.500 | 真实更新、严格恢复和评价入口通过；短测权重未进入正式训练 |
| 六路训练 | 948.640 | 945.695 | 六个运行各 32 轮，均完成 |
| 评价与独立分析 | 98.226 | 98.178 | 448 条评价轨迹，完整指标与配对分析完成 |
| 导出 | 5.485 | 5.464 | 1,850 个导出文件通过哈希清单 |

主资源 ledger（含先验成本）记为 1,112.093 秒 wall、1,105.966 秒 CPU。连同已知服务包络及先验成本，最终审计的已知合计为 1,112.453 秒 wall、1,106.352 秒 CPU。该合计不覆盖传输、辅助 watchdog 与整台机器的所有系统开销，不能解释为完整主机计量。

峰值 RSS 为 824,274,944 bytes；最大工作/导出目录采样为 964,447,677 bytes。存储按 250 ms 扫描目录，短时间峰值可能漏采。

墙钟监管存在限制：目标 service 为 `Type=oneshot`，配置的 `RuntimeMaxSec` 不生效；`TimeoutStartUSec=infinity`，动态修正被拒绝。校正后的 watchdog timer 在正式服务完成后才启用，因此没有监控本次运行；执行期间仍有先前 invocation-bound timer 与进程内阶段保护。报告不把外层 timer 说成全程有效的 4 小时硬截止。

计量证据位于 `../evidence/extracted/run/`、`../evidence/raw/extra_evidence/` 和完整原始包 `../evidence/raw/formal-run-evidence.tar.gz`。独立审计 JSON 对应 known-total 的计算口径。
