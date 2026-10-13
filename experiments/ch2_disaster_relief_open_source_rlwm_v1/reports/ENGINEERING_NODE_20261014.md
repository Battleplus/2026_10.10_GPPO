# 开源世界模型迁移：工程节点交付

当前结论：本地兼容环境中的接口回归、开源小模型更新、民用场景小模型更新及相应恢复检查已取得通过收据。正式研究、确认评价和算法收益尚未产生；目标 Linux 准入与预算实测仍未完成。

执行实现与修复设计由 GPT-6 Luna 负责。子线程 shell 间歇失败后，主线程按其修复方案代为落盘最小接线补丁、运行验证及保存日志。另一位 fresh-context GPT-6 Luna 独立读取源码、收据并复跑 replay 用例；其语义审核属于同家族、provisional 审核。

## 实际证据

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 接口/公开边界/掩码/物理时间/replay 回归 | 26 项通过，退出码 0 | `all-tests-compat-r3-20261014.log` |
| 开源 Dreamer 小模型工程烟测 | 3 次更新；模型参数和优化器恢复核验通过 | `../upstream_smoke/results-r5-fp32/smoke-receipt.json` |
| 民用场景工程烟测 | 128 次 adapter 调用、120 个物理分钟、8 次 dispatch 微决策、129 replay 帧、3 次更新；非法动作 0 | `civilian-dreamer-smoke-20261014-r4-fp32/civilian-dreamer-smoke-receipt.json` |
| 民用 checkpoint | 模型、优化器、调度器、scaler、计数、Python/NumPy/Torch CPU 随机状态及接口元数据恢复通过 | 同上；checkpoint 不含 replay 和仿真器状态 |
| 新场景登记 | 56 训练、14 开发、56 确认；确认集未评价 | `../relief_adapter/data/registry.json` |
| 历史数据范围复查 | 三个显式根目录；4,771 个 JSON/CSV；483 个历史 ID、6,513 个语义摘要，与当前登记表交集均为 0 | `old-data-scan-receipt.json` |

6,513 是 JSON 内符合结构的唯一语义摘要数量，不是独立父场景或 episode 数。去重结论只覆盖收据列出的三个根目录和扫描规则。

## 修复与限制

上游固定为 MIT 项目 `NM512/r2dreamer@546e4fab8146ea4b14e1d7726bbc1a8a1d50322f`，显式 `rep_loss=dreamer`。公开输入适配、动态动作掩码、零时间微决策、时间折扣与 replay clone-before-shift 均为本项目 overlay，上游源码快照保持原样。

原 CPU FP16 路径在真实更新中出现 NaN。固定 batch、同初始模型及随机状态的诊断中，FP16 首次 backward 在 `RsqrtBackward0` 停止、未执行 optimizer step；FP32 两次诊断更新保持有限值，见 `cpu-precision-diagnostic-20261014.json`。通过的两个 smoke 明确使用 CPU FP32 overlay；它们不是精确上游 FP16 复现，不能推断目标 Torch 2.8 行为。历次失败日志和部分工程制品均保留。

实测运行时是 Python 3.11.5、Torch 2.5.0+cpu、NumPy 1.26.0、Gymnasium 1.2.0、TensorDict 0.9.1、TorchRL 0.9.2。TorchRL C++ 扩展有版本警告；本次验证仅覆盖实际调用的 replay 路径。两次 Torch 2.8 下载失败证据保留，未覆盖系统环境。

民用成功 smoke 记录 wall 约 10.07 秒、进程 CPU 约 9.95 秒。P0 成功 smoke 记录 wall 约 1.05 秒、进程 CPU 约 0.89 秒；该计时从模型构造前开始，未覆盖完整进程启动/导入生命周期。RSS 读取为 null，不能声称已测得峰值内存。失败试验、精度诊断和成功试验不能只用最后成功时长代表全部工程成本。

P0 只验证模型、优化器、调度器及 scaler 恢复，不宣称训练续跑状态完整。民用 checkpoint 虽恢复额外计数与随机状态，仍不含环境/replay，不能直接当作中途续跑包。

## 下一步

服务器现有 SSH 身份认证拒绝，未执行远程研究命令，见 `SERVER_AVAILABILITY.json`。需要可用 SSH 配置后，在新建 Linux 环境上核验源码、依赖、FP32 路径、托管与资源计量，并完成有界 pilot 的预算实测。

比较计划保留 C1、三个新图 GPPO、三个新 Dreamer；每个学习器/seed 最多 128 个训练 episode，前 8 个 pilot 包含在内。六个新模型严格恢复通过前不评价 56 个确认父场景；确认轨迹为 56×7=392。预算和开发评价次数尚未冻结，不能以本烟测收据直接启动六路研究。

本轮只支持“已跑通本地兼容环境的小模型工程路径”。尚不支持世界模型预测有效、救援收益提高、图模型优越、规模泛化或图与世界模型组合优势。
