# 灾后巡查与救援运输：开源 RL + 世界模型迁移

从原民用 ReliefEnv、图 GPPO、规则基线、公开观察和独立指标复算逻辑迁移；使用固定 MIT 开源 Dreamer 源码及明确的本项目适配层。

当前交付是工程节点，正式研究与确认评价未启动。最新 Linux 验收通过，26 项测试及 10 次工程优化器更新完成；见 [Linux 节点报告](reports/linux-engineering-20261014/LINUX_NODE_REPORT_ZH.md) 和 [Luna 独立审核](reports/linux-engineering-20261014/independent-review/REVIEW.md)。下一阶段比较设计见 [执行计划](protocols/PILOT_AND_COMPARISON_PLAN.md)。旧 Windows 工程报告、审核和全部失败日志保留。

最新通过的 Linux 兼容运行时为 Python 3.11.16 / Torch 2.7.0+cu128 / NumPy 1.26.0，GPU 禁用，CPU FP32 overlay；旧 Windows 烟测使用 Python 3.11.5 / Torch 2.5.0+cpu。两者均不等同上游精确 Torch 2.8 复现。`runtime/` 是本机环境，不纳入 GitHub 归档；实际 r2 发布快照的复建与权威摘要见 [RECONSTRUCTION.md](linux_execution_r2/RECONSTRUCTION.md)。上游来源和许可位于 `upstream_audit/` 及各源码目录的 LICENSE。

## 工程复验

在项目根目录、配置好兼容依赖的 Python 下运行：

```powershell
python -B -m unittest discover -s tests -v
python -B upstream_smoke/upstream_dreamer_smoke.py --repo-root upstream_r2/r2dreamer-546e4fab8146ea4b14e1d7726bbc1a8a1d50322f --output-dir upstream_smoke/new-smoke --updates 3 --length 8
python -B integration/civilian_dreamer_smoke.py --repo-root . --output-dir reports/new-civilian-smoke --updates 3
```

这些命令执行神经 forward 和少量工程更新；不能称为零训练操作，也不能作为正式算法比较。输出目录应新建，保留此前收据。确认场景在 `relief_adapter/data/heldout` 中，工程 smoke 只使用训练场景。
