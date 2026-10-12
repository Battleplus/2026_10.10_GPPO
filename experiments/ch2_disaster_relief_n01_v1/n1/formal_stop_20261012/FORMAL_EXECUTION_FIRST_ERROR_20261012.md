# R2 正式执行首错与技术停止

状态：**STOPPED_FIRST_ERROR**。本次只建立了一次 SSH 会话；远端 preflight 首错退出，未上传 approval、未执行 `systemctl start`，未创建 R2 run、InvocationID、admission、轨迹或评价结果。按一次性授权约束，不重连、不重提、不复用该 identity 继续运行。

- 脚本：`.codex-tmp/n01-r2-formal-single-session-20261012.py`
- 脚本 SHA-256：`9e5ccfaf1dbfc563cadd11c31e9cfb9ccd128095e6e8eab691e51bd2e661047f`
- transcript：`.codex-tmp/n01-r2-formal-single-session-20261012-1216.transcript.txt`
- transcript SHA-256：`fc25e4cb80d729cc5b5a4324ba0bc9ad51d477d8d08e464565b32005381e8e9f`
- SSH 连接时间：2026-10-12 12:31:19 UTC；会话 exit=1。
- 远端 diagnostics 路径已去敏，未归档。

首错为 reader JSON 断言的 shell quoting 错误：`python3 -c` 中的 Python 字典键引号被外层单引号 shell 消耗，导致远端解释为 `x[evaluation_identity]`，并在 identity 字符串处触发 `SyntaxError: invalid digit '5' in binary literal`。这是提交脚本错误，不是包、approval、预算或目标 runtime 结算错误。

首错发生在 preflight：冻结 reader SHA、identity、budget 和 R1 隔离检查在同一命令中，reader Python 断言失败后，后续检查尚未完成。由于 fail-closed 行为，approval 目标没有写入，唯一 start 没有执行，R1 未被修改。当前没有正式评价、原始轨迹、任务事件、resource settlement 或 export 证据；这些计量缺口必须明确保留。

候选 approval 仍为本地未上传文件：`N01_FULL_EVALUATION_BUDGET_APPROVAL.candidate.json`，SHA-256 `99b167e97651ea016f4e2d771de91955c35bc7705a8f5ee9bbe08457caba0828`。冻结 reader SHA `254b2c08553d6a3ee7eb398187e4937ff89c576a2a41578f59313b0d885739e0`、identity SHA `0b56977312a3c926e6595b97fbcbbe379f54f69e69a1d07935c7136310716800`、budget SHA `38dea8cef35f1f7b3fb428bf302afd812b05958e0c520859935615b5745129d1` 均未改变。
