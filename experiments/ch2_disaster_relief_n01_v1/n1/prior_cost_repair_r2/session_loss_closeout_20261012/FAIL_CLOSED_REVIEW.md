# Fail-closed helper 验证记录

## 审核对象

公开归档的 fail-closed-mux-check.sh 是本地 helper 的最小化测试副本。原 helper 位于本地候选目录 received/target_preparation_20261012/n01-r2-fail-closed-mux.sh，其原件包含本机密钥路径和目标端操作值，未复制到公开归档。

## 本地验证

- bash -n 对原 helper 通过。
- 原 helper 的 verify-fail-closed 分支通过。
- SSH verbose 输出确认 ControlPath 不存在，执行了 ProxyCommand: exec /bin/false，没有出现 Connecting to 127.0.0.1 直连尝试。
- OpenSSH 在 proxy 被调用前打印了本地版本字符串，随后 proxy 失败；这不是目标端连接成功。
- 本目录中的最小副本保留同一验证行为，不含目标地址、真实用户名或密钥路径。它可在 POSIX bash、OpenSSH 环境重跑。

## 能力边界

此测试只证明指定的 mux SSH/SCP 调用在 ControlPath 缺失时，由 ProxyCommand=/bin/false 阻断自动新连接回退。原始操作 helper 还包含显式建立 ControlMaster 的 connect 子命令和接受任意远端命令的 ssh 子命令；它不是通用的禁止连接或只读安全门。公开的最小副本只测试失败关闭行为，不执行目标端动作。

原 helper 的本地 SHA-256：c44d4d60a18745da279668711ff16ce09c2cdccca4ff0769ad02112da9ee72d0。

该验证记录不能替代对 helper 完整命令面或目标端状态的审核。
