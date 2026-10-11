# 灾后图策略迁移与小规模对比

本目录是独立的 v2 source identity，包含灾后巡查与运输仿真环境、确定性 C0/C1 基线、L0/L1 图 PPO、登记场景、训练评价驱动和资源监督器。v1 的 Linux admission 子进程已通过运行时探针，但外层 guardian 因退出时 RSS 采样竞态将结算记为失败；v2 修复该竞态，仍须在目标 Linux runtime 重新完成 admission 与 engineering smoke。六路训练尚未开始。

`PRIOR_RESOURCE_COST.json` 是 v2 source identity 的必需文件。它绑定 v1 的 ledger、driver/guardian receipts、systemd 记录和部署身份，并在 admission 阶段计入 5.357756602210641 秒 wall / 2.771441418 秒 CPU，在 shutdown 阶段计入 0.3769723977893591 秒 wall / 0.143187582 秒 CPU。合计 5.734729 秒 wall / 2.914629 秒 CPU；这些成本不会作为旧 ledger 行进入 v2 的 admission/smoke 成功行门禁。缺失或证据 hash 不符时，v2 会拒绝继续。

## 运行与测试

所有阶段必须使用同一 `package-root` 和全新 `work-root`。已用 work root 含有既有证据，不要重跑覆盖；另选唯一目录。以下 PowerShell 示例先执行运行时准入，再执行真实工程 smoke：

```powershell
$PackageRoot = (Get-Location).Path
$WorkRoot = Join-Path $PackageRoot "execution\relief-graph-20261011-a"

python driver.py --preflight --package-root $PackageRoot --work-root $WorkRoot
if ($LASTEXITCODE -ne 0) { throw "Target-runtime admission failed; stop here." }

python driver.py --engineering-smoke --package-root $PackageRoot --work-root $WorkRoot
if ($LASTEXITCODE -ne 0) { throw "Engineering smoke failed; preserve its evidence and stop here." }

python -m unittest discover -s tests -v
```

在目标 Linux 主机上，`--preflight` 会核对 Python、PyTorch、NumPy、CPU affinity 和单线程设置，并运行真实 CPU 梯度更新。`--engineering-smoke` 必须紧接在同一 work root 中执行；它完成 L0/L1 短训练、严格保存恢复、夹具评价和独立审计、受控失败结算与 smoke 导出，并冻结共同训练轮数。正式阶段由 driver 的 gate 检查 admission 与 smoke 的主资源账本、driver receipt 和 Linux outer guardian receipt 均已成功结算后才允许开始。

仅当 admission 和 engineering smoke 均成功，且 smoke 的 `target_runtime_acceptance` 为 `true` 时，才依次执行正式训练、评价、导出：

```powershell
python driver.py --run --package-root $PackageRoot --work-root $WorkRoot
if ($LASTEXITCODE -ne 0) { throw "Formal training failed or was refused by the runtime gate." }

python driver.py --evaluate --package-root $PackageRoot --work-root $WorkRoot
if ($LASTEXITCODE -ne 0) { throw "Formal evaluation failed." }

python driver.py --export --package-root $PackageRoot --work-root $WorkRoot
if ($LASTEXITCODE -ne 0) { throw "Export failed." }

python driver.py --resources --package-root $PackageRoot --work-root $WorkRoot
```

`--resources` 汇总当前 work root 与 `PRIOR_RESOURCE_COST.json` 中的 carry-forward 资源账。各阶段失败时返回非零状态并保留 receipt、账本和部分检查点；不要复用失败 work root，使用新 identity 继续工程排查。

正式比较入口使用共享的 `reset()` / `step(action_batch)` / `export_trajectory()` 分钟步进接口运行 C0/C1/L0/L1；`ReliefEnv.run()` 保留为旧 C0/C1 夹具兼容回归入口。七组夹具的两条基线路径逐字段比较事件、转移、终态和指标，要求完全一致。

## 基线与审计

- **C0** 严格沿用第一章合成快照中的初始队列，不主动改派；队头暂不可行时等待。
- **C1** 根据公开可见任务，以优先级、截止时间和预计完成时间选择可行动作；保留在途任务与块外承诺。它不是学习策略，也不读取环境真值。
- C0/C1 的分钟步进比较适配器按公开库存逐项预留物资，跳过超出批次剩余库存的候选；旧 `run()` / `choose_actions()` 路径保留原语义。
- `independent_audit.py` 从输入场景和公开事件重建任务指标、能耗与逐物资库存守恒，不使用仿真器的汇总指标作为审计来源。完整审计还核对状态转移、终态以及场景和策略身份。
- `fixtures/` 覆盖基础控制、故障、能量变化、库存损失、报告延迟、组合扰动和块外承诺。每个夹具均是为工程验收编写的有限样例，不代表真实灾情分布。

场景结构、事件顺序、单位、指标定义及审计合同见 [IMPLEMENTATION_CONTRACT.md](IMPLEMENTATION_CONTRACT.md)。Smoke 和正式阶段输出目录、stage receipt、资源账本、checkpoint 清单及 export manifest 均位于所选 work root；正式评价按登记的 56 个保留父场景输出逐任务轨迹和独立复算指标。

## 解释边界

距离按无障碍欧氏距离计算，地图、速度、能耗、服务时长、库存、平台能力和任务均为合成设定。当前结果只能检查实现是否符合已定义规则，不能支持 C1 一般优于 C0 的结论：两者共享公开信息和平台约束，但动作规则与任务分配权限不同；C0 只执行初始队列，C1 还可分配后续发现的任务。单个控制夹具中的差异应按场景机制解释，不是统计推断。

Graph PPO 策略、分钟步进接口、配对训练器、评价驱动、结算门禁和 v1 本机工程 smoke 已实现。当前本机为 Windows Python 3.14.4、PyTorch 2.13.0+cpu、NumPy 2.5.0，未满足目标 Linux runtime；该 smoke 仅作实现诊断，不能作为目标 runtime 验收、正式训练预算或训练证据。须先在指定 Linux runtime 对 v2 成功完成 admission 与 engineering smoke，再运行六路正式比较。合成场景结果不支持真实灾情泛化或平台校准结论。

## 时间记录

driver 的 stage ledger 记录 wall、CPU、RSS 与工作/导出存储；在目标 Linux 上 outer guardian 还记录子进程结算和进程组监测证据。Smoke 冻结使用两种方法的最慢观测训练轮作为预算基础并保留 50% 余量；本机运行记录仅用于工程诊断，不是服务器预算或吞吐量基准。
