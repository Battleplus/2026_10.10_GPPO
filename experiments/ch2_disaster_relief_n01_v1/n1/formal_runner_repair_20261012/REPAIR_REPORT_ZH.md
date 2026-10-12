# N1 R2 formal runner repair v1

状态：`NOT_APPROVED`。本目录只包含包外 runner 修复、来源摘要、diff、请求和
离线验证；未连接服务器，未部署修复，未获服务器验收，未上传 approval，未调用准入、训练或评价。
场景、checkpoint、prior evidence 等研究数据与权重字节沿用已跟踪基线，未被改写；仅显式列出的身份绑定 overlay 有变化。

旧首错是 shell quoting：外层 `bash -c` 消耗了 Python 字典键和字符串的引号，
远端执行 `x[evaluation_identity]` 并在 identity 字符串处报 SyntaxError。旧会话
在 preflight 结束，`systemctl start` 不可达。

新 runner 通过 `bash -s` 传输单一脚本。冻结 reader、identity、stage budget 和
plan SHA 在启动前逐项检查；JSON 检查采用 Python heredoc，字段通过 argv 传入。
approval 必须是目标机预先存在的外部批准记录，采用 evaluator 要求的 schema，并逐项
匹配新 identity、预算 SHA、四阶段 caps、reader SHA、plan SHA、unit、4 GiB、批准来源
及排除项。这里验证的是记录内容绑定，不声称存在独立签名。修复包只有
`NOT_APPROVED` request，不含 approval，也不会生成/上传批准文件。active 或已有
InvocationID 的 unit、已有 run、错身份、错 approval 和已有原子 launch lock 均拒绝。
唯一 `systemctl --user start` 位于全部门禁之后，无 retry。

start 后同一进程记录 InvocationID、终态、systemd resource fields、journal 和 run 文件
索引。非零 start、失败、InvocationID unknown、证据缺失或超时均写 settlement；超时
保留为 pending。即使 settlement 显示终态成功，也不宣称正式结果成立，仍需独立审计。

离线测试使用本地 fake `systemctl` 和临时 fixture，执行同一份 runner 脚本，覆盖正确
绑定、含空格和引号路径、身份错误、NOT_APPROVED、reader 错配、active/已有 run、
原子锁重复拒绝、start 非零后的失败留痕和 pending 超时。mock 不执行 release evaluator。

new identity: `ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012`。
它与旧 identity 隔离；request 当前状态为 `NOT_APPROVED`，本目录尚无可启动授权。
