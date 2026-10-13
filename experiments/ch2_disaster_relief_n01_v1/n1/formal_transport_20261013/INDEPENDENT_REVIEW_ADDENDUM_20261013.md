# N1 正式运行独立审核补充

审核日期：2026-10-13（Asia/Shanghai）  
对应初审：`N1_FORMAL_RESULT_INDEPENDENT_REVIEW_20261013.md`  
范围：只读复核新落盘的 `formal_transport_v1/attempts/formal-run-20261013-ssh1/`。未连接或重连目标机，未运行评价，未改动既有记录。

## 更新结论

新收据补足了本地工具记录层面的运行身份和失败终态信息。`session-record.json` 与保存的 transcript 摘录都报告 identity 为 `ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012`，InvocationID 为 `fbdad1589e894466b62cf1785df0de47`；该 identity 与冻结 `FROZEN_BINDINGS.json` 一致。两份本地记录报告单次 SSH invocation、单次 unit start、retry 0，且终态为 `failed / exit-code`，settlement 标签为 `FAILED_PRESERVE_FIRST_ERROR`，`formal_result_claimed=false`。据此，以上内容可归档为**工具摘录及本地 session record 所报告的状态**。

本报告不把这些 reported 状态提升为远端原始事实或正式结果 PASS。保存的 stdout 明确是手工摘录，不是完整、逐字节原始缓冲区；原始会话 buffer 已不可读取，stderr 原始捕获不存在，远端 `final-status.txt`、`journal.txt`、`run-files.tsv`、`settlement.json` 没有回传。因此 InvocationID 和终态没有原始 systemd/journal/远端 settlement 收据可独立核验，轮询过程也因摘录省略中间输出而不完整。

初审中“未找到该 InvocationID 或本次 session record”的结论由新增记录修正；初审对轨迹、首错文本、模型加载、资源和导出均为 UNKNOWN 的判断仍然成立。正式评价结果仍为 **UNKNOWN / NOT VERIFIED，且未被声明为正式结果**。

## 收据核对

对照 `SHA256SUMS.txt` 重新计算的三个文件哈希全部相符：

| 文件 | SHA-256 核对 |
|---|---|
| `session.stdout.tool-transcript-excerpts.txt` | `27881B85C4AF65751B741C03B19569C097515E26152AE1A990BA0832460C4990`，匹配 |
| `session-record.json` | `D9C01B357A38D13E85C1161843ADEEE48965D7486FA9697A69FBAC030E6EED22`，匹配 |
| `TECHNICAL_STOP_REPORT.md` | `77F51467B8B5555D58F0C52F5E9D191B18CA2DFD1E602350AA5A4BB7B3134AF4`，匹配 |

这只证明当前文件字节与同目录清单一致；清单本身不是外部签名或远端来源证明。冻结绑定中的 identity SHA-256 为 `e01f2444bfb75d765f9522934a581a535055990445ec0356e6dd13b6fdc6e5fe`，reader SHA-256 为 `3eb535aa7390c0056044ba4ee5356fc3e2cea6ca9ce8e2e6d4ad5064d919aa3d`，plan SHA-256 为 `7e5334cd8c9691df59a63501e5ed8bbb8ad31e466ecffdb535ae45bed832fb45`，stage-budget SHA-256 为 `49f2736a53e6428b3893a1ae0c81500b0e48ca766300352fb464715627ebeb5c`。手工摘录报告 source/reader/approval bound；本地 session record 也将相应字段置为 true。缺少远端原始部署清单及审批字节回读，故这仍是**本地材料报告绑定成功**，不构成我对目标端字节的独立重算。

## 逐项状态

| 项目 | 可归档结论 | 证据边界 |
|---|---|---|
| 冻结身份 | **Reported 且与本地冻结 identity 一致** | session record、摘录 identity 和 `FROZEN_BINDINGS.json` 一致；目标端 identity 文件原件/哈希回读未收到。 |
| 单次 SSH / 单次 start / retry 0 | **Reported** | transcript 摘录显示一次 `formal_start`；session record 和 settlement 摘录报告 `ssh_invocation_count=1`、`start_count=1`、`retry_count=0`。无完整原始 SSH/PTy transcript 作独立确认。 |
| InvocationID | **Reported** | 本地记录及摘录为 `fbdad1589e894466b62cf1785df0de47`；没有原始 `systemctl show` 回读或 journal InvocationID 字段可交叉核验。 |
| 终态及 settlement | **Reported failure** | 第 184 次摘录轮询报告 `failed / exit-code`；记录报告 `FAILED_PRESERVE_FIRST_ERROR`、remote script exit 1。远端 `settlement.json` 未返回，不能独立确认实际远端 settlement 字节。 |
| 首错文本 / 首错是否被完整保留 | **UNKNOWN** | record 明确 `first_error_text` 不在收到的 stdout/stderr；标签宣称 preserve-first-error 不能替代首错正文及阶段 receipt。 |
| 2,800 轨迹及完成数 | **UNKNOWN** | `episodes_completed` 和 `trajectory_count` 均为 null；冻结范围 2,800 只是目标计划。 |
| 模型 / checkpoint 加载 | **UNKNOWN** | record 将 `model_load_status` 标为 unknown；无本次六 checkpoint load barrier 或模型事件。 |
| 资源使用 / 预算结算 | **UNKNOWN** | record 称资源文件未返回；无 final-status、cgroup/systemd 数值、阶段账本或 shutdown 收据。不能据此推定零资源。 |
| 导出及正式结果 | **无可核验导出；未宣称正式结果** | `formal_result_claimed=false` 是本地 record 和摘录报告值；无 export manifest、产物哈希或独立评价重算输入。 |

## 可归档准确结论

N1 冻结 formal-repair-v1 identity 的本地 session record 和手工工具转录摘录报告：2026-10-13 UTC 00:57:51 开始一次 SSH session，报告 source/reader/approval bound；随后报告对固定 unit 执行一次 start，取得 InvocationID `fbdad1589e894466b62cf1785df0de47`。摘录实际保留的 poll 1、14、44、73、84、93、102、121、140、161、172、183 均报告 active/running；poll 184（2026-10-13 UTC 01:43:45）报告 failed/exit-code。摘录省略了其他中间 poll。settlement 摘录报告 `FAILED_PRESERVE_FIRST_ERROR`、`start_count=1`、`retry_count=0`、`formal_result_claimed=false`，本地 transport 进程退出码为 1。摘录、记录和技术停止报告的本地 SHA-256 均匹配同目录 `SHA256SUMS.txt`。

以上为**本地保存材料所报告的执行状态**。当前无法独立确认远端原始终态/结算字节、首错及其阶段、轨迹数或完成数、模型加载、资源数值、文件导出和结果指标；这些字段保持 UNKNOWN。正式结果未获本地证据支持，不可标为 PASS。没有再次连接或自动重提。

## 后续归档所需材料

如需把 reported 状态提升为远端可核验事实，应由已授权的证据交付渠道提供原始完整 stdout/stderr 或 SSH transcript、目标端 `systemctl show` 与匹配 InvocationID 的 journal、远端 `settlement.json` 和 `final-status.txt`、run-files 索引及其文件哈希。若要审计研究结果，还需轨迹/唯一 run keys、完成计数、六 checkpoint 加载记录、分阶段资源账本和导出 manifest。无法取得的项目继续保留 UNKNOWN；本补充不提出自动重提或恢复运行。
