# N1 R2 正式评价技术停止记录（去标识版）

日期：2026-10-13（UTC）

## 可核验范围

本地 session record 与手工保存的 Codex 工具转录摘录报告：冻结身份 `ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012` 通过 source、reader 和 approval binding；固定 unit 只 start 一次，reported InvocationID 为 `fbdad1589e894466b62cf1785df0de47`，retry 数为 0。摘录中的轮询 1、14、44、73、84、93、102、121、140、161、172、183 报告 `active/running/result=success`；poll 184 报告 `failed/exit-code`。本地 settlement 摘录报告 `FAILED_PRESERVE_FIRST_ERROR`、`start_count=1`、`retry_count=0`、`formal_result_claimed=false`，transport 进程退出码为 1。

以上是本地保存材料所报告的状态，不是远端原始 systemd 或 journal 记录的独立证明。原 PTY/session buffer 已不可读取；保存的输出只是手工摘录，省略了中间轮询，没有原始 stderr，也没有收到远端 settlement、journal、final-status 或 run-files 文件。对应独立审核详见 `INDEPENDENT_REVIEW_ADDENDUM_20261013.md`。

## 结果边界

计划范围为 2,800 episodes；实际完成数和 trajectory 数均为 **UNKNOWN**。首错正文及发生阶段、模型或 checkpoint 加载状态、资源测量、export 文件和正式指标均为 **UNKNOWN / NOT VERIFIED**。本归档不报告 N1 PASS 或算法性能结论，也不表示 2,800 episodes 已运行完成。

较早的一次 SSH 失败是 Windows text-mode 将 LF 转为 CRLF，导致远端 Bash 在 package preflight 前退出。字节传输修复及其 5/5 离线验证记录在 `TRANSPORT_REPAIR_REPORT.md`。本次 session 在同一 transport 下进入绑定与单次 start，随后报告失败终态；没有重连、重试、第二次 start、training、N2 或 N3。
