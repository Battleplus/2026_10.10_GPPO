# N2 Linux 预检停止摘要

日期：2026-10-13（UTC）

本次 N2 Linux 工程验收只建立了一次受控 SSH transport，并成功认证目标。远端返回的主机名和账户符合预期；新目标根目录在预检时不存在。随后 Python runtime 探针退出码为 1，stderr 只有 `AssertionError`。探针没有逐项打印 Python、PyTorch、NumPy、CUDA 或 CPU affinity 的值，因此无法确定具体失败条件。

根据一次接入失败停止规则，本次没有重连。没有创建目标目录、上传文件、验证远端 manifest、提交 systemd unit 或取得 InvocationID。研究数据处理、训练、预测门和 PPO smoke 均未在目标端执行，计数均为零。

公开记录仅保留状态、计数和证据摘要哈希。原始 SSH transcript、单次会话脚本、认证材料、主机地址、账户、密钥位置和授权正文均不属于本归档。

这是一项失败的 Linux 工程预检，不构成 Linux runtime 通过、研究结果、模型结果或预测结论。停止后的研究工作仍未完成；本报告不授权自动重试。
