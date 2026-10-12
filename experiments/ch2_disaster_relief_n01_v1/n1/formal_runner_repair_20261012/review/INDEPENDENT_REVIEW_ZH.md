# N01 R2 Formal Runner 修复包独立审核

审核对象：`formal_runner_repair_v1`，状态 `NOT_APPROVED`。审核仅在本地进行，没有 SSH、服务器连接、训练、模型 forward、正式评价或部署。六个离线场景只执行包内 `remote_script()`，并以临时 fake `systemctl`/`journalctl`/`sleep` 替代外部命令。

## 结论

针对本地 runner 合同，审核通过。旧 R2 首错记录保持为历史证据：旧脚本把 Python 字典键和 identity 字符串放进嵌套 `bash -c`，导致 reader preflight 的 SyntaxError；transcript 中 preflight exit=1，审批未上传且 start 不可达。修复包建立独立的新身份 `ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012`，release 内 identity、budget、reader、source hash 清单及 unit 均绑定到该身份；旧身份未被改写或作为新 run 身份使用。

runner 通过单一 `bash -s` stdin 传脚本，Python 参数使用 argv/heredoc，静态确认没有 `bash -c`；其中恰有一个 `systemctl --user start`，位于身份、reader、source、unit、运行状态、审批字段和原子 lock 门禁之后。审批内容逐项绑定新身份、预算哈希、四阶段 cap、reader/plan 哈希、unit、内存限制、审批来源和排除项。审批校验是字段内容绑定，不是数字签名验证；本包只有 `NOT_APPROVED` request，没有 approval 文件或生成/上传 approval 的路径。

## 本地模拟

在 WSL 中运行 `python3 -m unittest -v test_offline_runner.py`：6 项通过。覆盖引号/空格路径下的一次启动、错身份和非批准状态拒绝、reader mismatch、unit active/已有 run 拒绝、原子 lock 拒绝重复提交，以及 start 非零后写失败结算和 pending timeout。模拟验证的是本地 runner 分支行为，不证明服务器状态、部署、审批或研究结果。

## 剩余限制

该包目前不能启动正式任务：budget 仍为 `proposed`，审批 request 为 `NOT_APPROVED`。approval 的 `approved_by` 与 `approval_reference` 只按字段存在性检查，授权真实性由包外审批流程提供；本地审核不把合成 fixture 当作批准。任何服务器执行都不在本审核结论内。

哈希明细见同目录 `INDEPENDENT_HASH_INDEX.json`。本审核报告与索引是审核产物，不属于待批准的研究授权。
