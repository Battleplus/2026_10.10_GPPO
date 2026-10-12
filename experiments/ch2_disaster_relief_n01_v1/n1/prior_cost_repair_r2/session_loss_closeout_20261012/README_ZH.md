# N01 r2 接入中断归档

本目录记录 2026-10-12 的有限目标端准备尝试。它是 `prior_cost_repair_r2` 冻结包之外的新增归档，不修改冻结 package、580 文件发布清单或既有发布提交 `ca1dd73bfded1ffe39dd5953865a2ad00cd5e9c1`。

## 结果

- 一次较早的错误密钥 SSH 尝试返回 exit code 1，结果为 `Permission denied (publickey,password)`，没有启动远端命令，也没有后续重试；该摘要来源于本地尝试记录。
- 使用专用 key 建立 ControlMaster 的命令返回 exit code 0。只读检查读到 r1 InvocationID `7b65d35b5b4c464b810ecac918978166` 为 failed，r2 package、run 和 unit 均不存在；共享 approval 仍绑定 r1 身份。
- SCP 上传归档返回 exit code 0，持续 7.814 秒，记录大小为 6,568,593 bytes，预期 SHA-256 为 `36f4fb3b72eba0dcbf82c16a3bfe062901e6d6590cd3271099cdf6941ab3b860`。目标端 SHA 未回读，因此不能确认目标字节完整性。
- 精确目标暂存文件路径为 `/home/user1/w1-pilot/packages/.n01-r2-prior-evidence-20261012.stage/archive.tar.gz`。
- 后续 preparation-script SCP 返回 exit code 1，持续 1.641 秒；ControlMaster 报 broken pipe，SCP 自动尝试了新的认证并被拒绝。脚本未上传。之后只检查本地 mux socket，未再次连接目标端。
- 断连后的远端 staging 状态未知。没有解包/发布、dry-run、unit 安装、approval/token/run 创建、start、admit、训练或正式评价。2800 个计划 episode 不是已完成评价。

## 证据位置与时间

原始本地记录位于工作站候选目录 E:/Z博士/.codex-tmp/n01-github-release-20261012-a/experiments/ch2_disaster_relief_n01_v1/n1/prior_cost_repair_r2/received/target_preparation_20261012/：

- `received/target_preparation_20261012/session-record.json`：命令 exit code、可用耗时、嵌入的 stdout/stderr 文本，以及明确为 null 的 `event_time_utc`。
- `received/target_preparation_20261012/raw-observations.log`：可读的观察汇总，不是命令执行器生成的逐条原始日志文件。
- `E:/Z博士/.codex-tmp/n01-r2-target-access-attempt-20261012.json`：较早错误密钥尝试的本地摘要；没有原始 stdout/stderr 文件或事件时间戳。
- `received/target_preparation_20261012/n01-r2-fail-closed-mux.sh`：本地实际使用的接入 helper。helper 原件含本机密钥位置和操作目标信息，因此本公开归档只附去除这些值的最小 fail-closed 测试版本。

`session-record.json` 记载的证据汇总时间为 `2026-10-12 06:52:03 UTC`。原始 exec 输出未提供事件时间戳；本归档不推断或补造时间。具体 stdout/stderr 和退出码以本地 `session-record.json` 中逐项字段为准，不将整理后的汇总文本称为原始终端日志。

逐项输出字段映射见 `target-preparation-observations.json` 的 `original_output_field_map`。目前没有单独保存的逐命令原始 stdout/stderr 文件；可用文本嵌在上述 JSON 记录中，错误密钥尝试仅保存了错误摘要和退出码。

## 文件

- `target-preparation-observations.json`：字段化事实、精确 staging 路径和来源位置。
- `fail-closed-mux-check.sh`：无主机、用户或密钥路径的 fail-closed 验证 helper。
- `FAIL_CLOSED_REVIEW.md`：本地语法/行为验证记录及本次独立审核状态。
- `NOT_READY_REVIEW.md`：结合既有独立候选包审核与本次会话记录的启动就绪性结论。
