# N01 R2 部署与静态回读收据

执行时间：2026-10-12 11:55 UTC。静态准备状态：**PASS / DEPLOYED_STATIC_ONLY**；研究状态仍为 **NOT_READY / NOT_APPROVED**。静态准备通过不构成正式 admission 或 authorization。

一次 SSH 会话成功完成 8 个捕获步骤，所有步骤 exit=0。归档冻结包验证通过：594 个 tar 成员（560 文件、34 目录），28 个 source hash、9 项 prior evidence、350 个 scenarios、6 个固定 checkpoint。冻结 tar SHA-256 为 `36f4fb3b72eba0dcbf82c16a3bfe062901e6d6590cd3271099cdf6941ab3b860`；identity SHA-256 为 `0b56977312a3c926e6595b97fbcbbe379f54f69e69a1d07935c7136310716800`；stage budget SHA-256 为 `38dea8cef35f1f7b3fb428bf302afd812b05958e0c520859935615b5745129d1`。

部署后 `prior-cost-dry-run` 通过；完整 `dry-run` 通过，校验 350 scenarios、2,800 episodes 和 2,800 个唯一 run keys，并生成 6-checkpoint barrier。完整 dry-run 按源码路径对 6 个 checkpoint 执行 payload `torch.load`；`strict_model_load=False`，strict model loads 为 0，模型构造、forward、训练、正式评价及 admission 均为 0。计划 SHA-256 为 `f14ce0f4cfc271febf0753bf202253c2a5b9db92a02e2c8ce7d70c7121edc383`，run keys SHA-256 为 `54e72e67110976e1f3ad7ecb67e581749e42b1e68866d80819e7e7bf7caa170a`。

目标 runtime 契约为 Python 3.11.16、PyTorch 2.7.0+cu128、NumPy 1.26.0，CPU device。实际 unit `n01-full-evaluation-r2-prior-evidence-20261012.service` 已安装并回读为 loaded/inactive/dead、InvocationID 为空；CPU affinity 为 0、MemoryMax 为 4 GiB、Restart=no、KillMode=control-group、RuntimeMax=5900 秒、TimeoutStop=40 秒、无 drop-in。R1 既有 failed 状态未改变；R2 run、admission、state 和 guardian token 均不存在。

GNU `time -v` 对完整 dry-run 记录 wall 1.47 秒、user 1.29 秒、system 0.14 秒、峰值进程 RSS 600,160 KiB。这是该进程的测量，不是整机资源基线。目标机总内存、可用内存、CPU 拓扑、GPU 利用率和逐 checkpoint 耗时没有测量。历史已知成本 173.079 秒 wall / 124.841 秒 CPU 单独结转；更早历史消耗未知，不视为零。

预算仍为 `proposed` 且无批准引用：本 identity wall 5,940 秒、CPU 4,800 秒；unit 内存上限 4 GiB。后续 start 必须获得独立明确授权与预算批准。供用户审阅的唯一 systemd 命令为：

```sh
systemctl --user start n01-full-evaluation-r2-prior-evidence-20261012.service
```

该命令本次没有执行。没有创建授权 token、准入或 run，也没有启动 R2 服务。本收据只证明静态部署和回读完成，不代表预算批准或正式评价通过。独立本地审核已复核完整 transcript 与现场摘要一致。
