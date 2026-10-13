# 执行状态：开源 RL+WM 民用迁移 v1

最终更新（2026-10-14）：26项工程回归通过；CPU FP32 overlay 上游烟测完成3次更新及有限范围恢复，民用烟测完成3次更新及学习器状态恢复。实际证据分别在 reports/all-tests-compat-r3-20261014.log、upstream_smoke/results-r5-fp32/smoke-receipt.json、reports/civilian-dreamer-smoke-20261014-r4-fp32/civilian-dreamer-smoke-receipt.json。正式研究、确认评价仍未启动；目标Linux预检/预算实测未完成。下文为中间节点历史记录，最终范围和限制以 reports/ENGINEERING_NODE_20261014.md 为准。

更新：2026-10-14（Asia/Shanghai）。状态：P0/P1 正在实施；目前尚无神经烟测通过收据，正式训练和确认评价未开始。

## 分工

执行：GPT-6 Luna（上游核验与短跑、民用适配分开负责）。独立审核：另一个 fresh-context GPT-6 Luna。主模型：节点判断。

## 已执行

- 默认沙箱 exec 初始化故障已记录；同任务范围自动审核后的工作区 exec 可用。
- 读取现有 ReliefEnv、训练与评价入口；保留旧冻结包，只写独立 development 目录。
- 原候选 NM512/dreamerv3-torch 固定 commit 6ef8646d807cd10ce0c88e10a7e943211e7fc44c、MIT，README 标为 Outdated Implementation。当前选择 NM512/r2dreamer 固定 commit 546e4fab8146ea4b14e1d7726bbc1a8a1d50322f，显式 rep_loss=dreamer；来源记录见 upstream_audit/UPSTREAM_PROVENANCE.json。此选择不代表模型已成功运行。
- 参考论文 Desktop 副本已读取，身份及迁移边界见 reference/PAPER_TRANSFER_NOTES_ZH.md；最新 WeChat 临时路径缺失。
- 两次 Torch2.8.0 CPU下载均未成功，失败证据保留。项目兼容环境只读复用 Python3.11.5/Torch2.5.0+cpu，局部安装 NumPy1.26.0/Gymnasium1.2.0/TensorDict0.9.1/TorchRL0.9.2/Hydra1.3.2。TorchRL C++扩展有版本警告，不能将其当作精确上游运行时。
- 服务器 user1@172.17.27.173 的现有 SSH 身份认证被拒绝，未执行远程研究命令；证据见 reports/SERVER_AVAILABILITY.json。
- 新场景登记表126个父场景：56训练、14开发、56确认，仅覆盖承运竞争/库存竞争。历史ID/语义摘要重叠及内部重复均为0；确认集未评价。最终registry文件SHA-256为3f96d6ad8a421d9d2890c4df34d3bdba2a81999fa76976e68d33492958bd161a，见reports/registry-generation-final-20261013.log。
- 第一轮完整兼容验收25项：22通过、2失败、1错误；18项adapter/replay/registry通过。日志reports/all-tests-compat-20261013.log保留。Luna正在修复，尚不能报告整套验收通过。

## 接口决定

保持原环境每分钟联合分配：同一物理分钟内逐候选 microdecision 累积，COMMIT 一次调用原 step(batch)。microdecision dt=0/reward=0，commit dt=1。Dreamer 的时间折扣和想象合法性尚未验收；不能把每个微决策当作完整物理分钟。
本轮小规模默认 4 platform slots / 16 task slots / 65 actions。容量配置独立于实际隐藏任务清单；任务仅在首次公开后登记。候选不足/NOOP/unknown保持明确语义。

## 未产生

当前没有上游神经烟测通过收据、民用学习checkpoint或正式算法结果。首次上游smoke在动作空间整数类型/OmegaConf接线处失败，见reports/upstream-smoke-compat-first-20261013.log。没有复用历史授权或启动N3。

## 下一节点

待办：修复当前工程问题，重新运行上游与民用小模型烟测，取得实际更新和恢复收据，再交给fresh Luna审核。以上均是下一步要求，尚未完成。正式研究预算另需在选定Linux运行时实测和冻结。计划见protocols/PILOT_AND_COMPARISON_PLAN.md；六模型屏障通过前，确认场景保持未评价。
