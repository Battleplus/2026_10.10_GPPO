# N1 正式运行只读取证报告

日期：2026-10-13（Asia/Shanghai）  
Identity：`ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012`  
InvocationID：`fbdad1589e894466b62cf1785df0de47`

## 结论

固定 systemd invocation 已结束且状态稳定，但结果为失败：`ActiveState=failed`、`Result=exit-code`、`ExecMainStatus=1`。结算收据为 `FAILED_PRESERVE_FIRST_ERROR`，没有宣称正式结果通过。

日志中的首个 Python 异常为 `PermissionError: shutdown requires exactly one successful n01_full_admission receipt`（2026-10-13 09:43:34 +0800）；systemd 在 09:43:35 记录主进程以状态 1 退出。该错误发生于 shutdown 校验阶段，不是评价阶段的首错。

评价摘要报告 2,800 episodes、2,800 audits 和 2,800 audit passes。导出清单绑定 ZIP SHA-256 `93a3bcf316f9a71dd69e5f9570f6313dbad5ba7d1a74c3779f5c46a8709e1f31`。补取的 ZIP 已本地核验：8,403 个成员，无绝对路径、父目录跳转或符号链接，CRC 全部通过；trajectories、audits、episode_rows 各有 2,800 个 JSON 文件，metrics 有 2,800 行。上述数据支持离线复核，不改变本次 invocation 的失败结算。

## 传输与完整性

第一次 SSH 只读采集成功退出，原始 stdout 为 2,152,599,871 字节，SHA-256 `d0125d85d79ef111195898a2aa0a00578f78120ae6c6ca407aeb96531c1349b5`；stderr 为空。帧解码无 payload 哈希不匹配，但 2 GiB 累计预算使 598 个 RUN 文件未复制，合计声明大小 417,334,992 字节，采集状态为 `partial`。

随后经明确授权执行了一次限定两路径的只读补取：ZIP（66,112,453 字节）和 `preflight_plan.json`（743,708 字节）。ZIP 实际 SHA 与导出清单相符；preflight 的 SHA-256 `b2adef5016c9e5b0e6b9b54420d8e1e2ecc09753232cf77c7c7bcfb216f44dd3` 为首次读取所得。该次传输状态为 `complete`。没有再次连接。

两次捕获的原始二进制流、逐文件解包内容和 session record 留存在本地取证目录，不包含在公开归档中。公开归档包括只读取证工具、离线测试、相对路径 hash/inventory 索引、传输结算和补取摘要；不含 key、审批记录原件或远端诊断文件原件。

首次采集本地目录：`E:\Z博士\research-executions\n01_formal_readonly_capture_20261013\capture-20261013-approved-once`  
补取本地目录：`E:\Z博士\research-executions\n01_minimal_recapture_plan_20261013\capture-20261013-approved-once`

评价结果的独立复算和 shutdown 源码根因审查见 `N1_FORMAL_RESULT_FINAL_INDEPENDENT_REVIEW_20261013.md`。正式运行仍须保持失败状态；后续可在离线修复 shutdown 状态比较逻辑后重新独立验证，但不得改写本次运行结算。
