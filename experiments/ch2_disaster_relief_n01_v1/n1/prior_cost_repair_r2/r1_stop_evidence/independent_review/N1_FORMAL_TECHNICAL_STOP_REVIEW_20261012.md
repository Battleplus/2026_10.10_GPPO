# N1 正式技术停止独立审核（2026-10-12）

## 审核结论

**技术停止判定：通过。研究结果判定：不适用。不得重提本次身份。**

本审核为只读证据审核，没有运行、修复、重新部署或重试。现有证据支持：本次唯一 systemd invocation 在正式评价准入阶段因绑定 prior-cost 证据路径无法解析而失败，未进入 checkpoint 加载、轨迹生成、评价或训练。因此本次不能产生算法正负结论，也不能作为 N1 完成或失败的性能结果。

## 绑定证据与完整性

审核目录：`research-executions/ch2-disaster-relief-n01-v1/n1/formal-run-20261012`。

| 文件 | SHA-256（独立计算） | 审核结果 |
|---|---|---|
| `systemd-settlement.json` | `95c5b18b454c04e3db51d5831f0c3b2e0f535e499ee19451628f7f68e27c0c42` | 匹配提交值 |
| `journal.txt` | `7a6678807de343ec25598fc0c807758441f0130cc2251633964dbb51f0ff5b00` | 匹配提交值（大小写不影响 SHA 比较） |
| `N1_TECHNICAL_STOP_REPORT_CN.md` | `e524ba49926c827b4b0cae4a7ee4b677c48df2a734ed9d632486fe11c688ebb4` | 匹配提交值 |

结算记录和状态清单共同绑定 `InvocationID=7b65d35b5b4c464b810ecac918978166`，服务为 `n01-full-evaluation-r1-20261011.service`，主进程退出状态为 `1`，`Result=exit-code`。`contract_status=complete` 和 `settlement_status=failed` 的组合表示结算合同完成记录、被审计的服务运行失败；不能解释为评价合同完成。

## 首错核对

`journal.txt` 中最早的 Python 异常是：

```text
FileNotFoundError: [Errno 2] No such file or directory: '/home/user1/w1-pilot/packages/received'
```

调用链为 `_guarded_dispatch` -> `_read_bound_prior_cost`，失败点是对绑定 prior-cost evidence 路径执行 `resolve(strict=True)`。这与停止报告的首错、阶段位置和部署/证据路径接线解释一致。该异常发生在 `admit` 调度前；日志中没有 checkpoint load、trajectory、evaluation 或 training 调用的后续证据。故应分类为部署/证据路径工程故障，而非算法结果、模型质量或场景机制结果。

## 资源与生命周期核对

- systemd `CPUUsageNSec=123739000`，约 `0.123739` CPU 秒；结算时 cgroup `cpu.stat usage_usec=127108`，约 `0.127108` CPU 秒。
- cgroup `memory.peak=12222464` 字节（约 11.65 MiB），与停止报告的 `12,222,464` 字节一致；`memory.events` 的 OOM 和限制事件均为 `0`。
- 服务配置和回读显示 `MemoryMax=4294967296`、`CPUAccounting=yes`、`CPUAffinity=0`、`KillMode=control-group`、`RuntimeMaxUSec=1h 38min 20s`、`TimeoutStopUSec=40s`；`CPUQuotaPerSecUSec=infinity`，且 `kernel_cpu_quota_status=unavailable`，因此没有被错误宣称为硬 CPU quota。
- `resource_ledger_sha256=null`、`resource_receipts=[]`、`guardian_receipts=[]`。本次只能使用结算阶段保存的 systemd/cgroup 抽样资源，不能推导完整评价阶段资源或预算消耗。

报告将 `systemd CPU 0.123739 秒` 和 cgroup `usage_usec=127108` 并列列出，属于不同采样来源的轻微差异，不构成矛盾。结算记录明确说明 cgroup 值是在 `ExecStopPost` 抽样，故应按抽样证据解释。

## 产物和研究边界

本地审核目录包含结算、journal、状态清单和停止报告四个审计文件；服务器正式 run 目录被报告为仅有 `systemd-settlement.json`，没有 trajectory、checkpoint 输出或分析文件。现有证据不显示任何研究轨迹、checkpoint 加载产物、评价表、训练更新、N2/N3 运行或新增 checkpoint。

因此：

1. 正式 N1 固定矩阵的有效 episode 数为 `0`，不能报告 C0/C1、L0/L1、图 GPPO、规模扩展、承运竞争或库存竞争的性能差异。
2. 不能把 exit 1、空轨迹或未生成结果解释为算法负结果；也不能把静态准入、预算或历史 N0 证据充当本次 N1 运行结果。
3. 不能追加预算、恢复、复用本次 invocation 或以同一冻结 research identity 再次提交。
4. 若继续工作，必须新建修复身份，修正 prior-cost 证据部署路径，重新执行独立审核、部署和 preflight，并在新身份中记录本次已消耗的结算资源；修复身份也必须重新获得相应授权。
5. N2/N3 不得由本次停止自动触发。

## 审核限制

本审核没有登录目标主机、执行命令、读取包外 `received/` 的真实部署状态或重算远端目录清单。关于缺失研究产物的判断限于提供的 settlement、journal、status-and-files 和停止报告；服务器目录“仅有 settlement”的表述应按停止报告所述服务器 run 目录理解，不与本地审计目录文件数混淆。

