# N2 最新已消费授权与 STOP 独立核验补充

日期：2026-10-14。范围：只读既有非敏感报告、归档索引及 launcher 源码。没有 SSH、网络测试、源码执行、实现修改；没有读取 `.codex-private` 文件、令牌或认证记录内容。仅写本独立审核报告。

## 结论

**最新可核验 N2 托管状态仍为 STOP，未验收通过。** 2026-10-13 的 locale-parser 首错之后，2026-10-14 的 locale-json 新一次性身份也已尝试并消费授权，随后在 package transfer/systemd submission 前停止。不得把旧静态“可考虑另授权运行”的 review、未批准 template 或新的总交接说明视为这些已消费身份的重试授权。

新的用户交接支持本轮可逆实现与本地独立工程取证，但不会改写历史 STOP，也不提供复用已消费 exact-run authorization 的依据。准备新修订和具体可审结果不等于允许自行重提托管作业。后续任何新的托管执行必须有与新冻结包/身份和明确范围绑定的准入与授权证据；本审核没有授予该权限。

## 两次 STOP 的证据

| 项目 | 2026-10-13 r2 | 2026-10-14 locale-json |
|---|---|---|
| 身份 | `n2-engineering-acceptance-r2-20261013-once` | `n2-engineering-acceptance-r2-locale-json-20261014-once` |
| 首错 | `SSH_SHELL_AFFINITY_NOT_REPORTED`：taskset成功但输出中文，English-only parser拒绝 | `REMOTE_COMMAND_FAILED` / exit127：create_roots调用参数顺序颠倒 |
| 当前证据状态 | 一连接、零重连、零上传、零systemd提交；授权消费 | 一连接、预检JSON affinity成功；零上传、零systemd提交，无InvocationID/runner收据；授权消费 |
| 未完成项 | runner/test/smoke/export及资源上限未测 | runner/test/smoke/export及资源上限未测 |

第一行依据：

- `E:/Z博士/n2-r2-stop-archive-wt/experiments/ch2_disaster_relief_n2_v1/engineering_revision/linux_acceptance_r2/PREFLIGHT_STOP_REPORT.md`
- 同目录 `STOP_SETTLEMENT.json`、`AFFINITYFIX_EXECUTION_RECORD.md`、`INDEPENDENT_STOP_REVIEW.md`
- `E:/Z博士/development/ch2_disaster_relief_n2_linux_acceptance_r2/preparation/STOP_REVIEW_REPORT.md`

最新行依据：

- `E:/Z博士/development/ch2_disaster_relief_n2_v1/engineering/linux_acceptance_r2_locale_fix/EXECUTION_REVIEW_STATUS.md`（独立执行停止审核，文件最后写入 2026-10-14 11:50）
- 同目录 `N2_LOCALE_FIX_STOP_REPORT.md`
- `E:/Z博士/development/ch2_disaster_relief_n2_v1/engineering/linux_acceptance_r2_locale_json_stop_archive_candidate_20261014/N2_LOCALE_FIX_STOP_REPORT.md` 和 `ARCHIVE_INDEX.json`（本地归档候选，明确 not pushed）

最新 launcher `E:/Z博士/development/ch2_disaster_relief_n2_v1/engineering/linux_acceptance_r2_locale_fix/r2_once_launcher_locale_json.py` SHA-256 实算匹配报告 `2dabc35063c698f79e760a70a1bc327758d7a4b6e8e39464145bb900caf87b1b`。其第127行签名为 `command(client, evidence, label, text, ...)`；第239行以 `mkdir...` 为label、`create_roots`为text，与停止报告因果解释一致。第240行才执行transfer，第258行才到systemd-run，因此源码支持“该首错在上传/提交之前”的控制流解释。本轮未读原始私有transcript或settlement，故真实一连接/零上传等运行事实为既有独立报告和红acted结算所支持，未再次独立复核原始远端记录；不声称目标连接关闭之后的状态。

最新停证报告 SHA-256：`a418f1e549dd47e628c8464eefbd3e0bd8c1b777bdd43b4f4e0c441e4a8051ac`，工作目录与归档候选副本一致。执行停止独立审核 SHA-256：`dad4d2c90fb5be088e5888b74a6da501cccf63071a563f8b560606667f477c65`。冻结旧包manifest身份仍是 `n2-local-synthetic-engineering-linux-acceptance-r2`，不是本交接阶段A真实学习贯通已通过证据。

## 较早 PASS 的边界与旧合同冲突

`E:/Z博士/development/ch2_disaster_relief_n2_v1/preparation/M0_M1_ENGINEERING_NOTE.md` 记录本地27项回归、4项snapshot/public probe PASS，明确只是草案、局部工程检查，未完成N2研究采集/WM训练/预测/服务器或G/G-WM smoke。不能替代本交接要求的10次WM、2次PPO、checkpoint及托管运行。

`E:/Z博士/development/ch2_disaster_relief_n2_v1/engineering/linux_acceptance_r2_locale_fix/INDEPENDENT_REVIEW.md` 为较早的11:15静态review，只验证preflight failure paths和单connect/submission静态site；其“ready to be considered”没有运行授权和成功提交结论。后续11:50 STOP审核取代任何“尚未执行”的理解。可逆修复必须增加成功路径mock检查，尤其核对每条远程command的label与text语义，不能仅数connect/systemd字符串出现次数。

旧 `E:/Z博士/development/ch2_disaster_relief_n2_v1/preparation/N2_GATE_RECOMMENDATION.md` 明确batch8指8个完整parent-window示例/动态catalog组，排序pair不能跨窗；它的旧目标是candidate-minus-C1，旧门为三seed ranking bootstrap。当前用户交接指定同窗NOOP增量、固定Brier/MAE/pair门，故旧gate不能直接复用。batch单位与损失公式须依当前合同冻结，旧文档仅作复用风险参考。

`E:/Z博士/development/ch2_disaster_relief_n02_v1` 与 `E:/Z博士/research-executions/ch2-disaster-relief-n02-v1` 本轮只读清单计数均为0；没有从这两个目录找到新实现或PASS。限定N2文件名搜索也没有在research-executions发现其他N2结果收据。文件搜索不是对全部磁盘/远端状态的绝对证明。

## 阶段 A 状态修订

初始审核的历史部分须补充上述两次已消费N2 STOP；不能再写“尚无既有N2尝试”。本轮工程草案尚待纠正，真实学习和托管验收仍未通过。待执行器交付新本地工件和预算时可继续独立审查；本地真实WM/PPO证据可确认学习路径的本地部分，托管部分继续列未验证，禁止合成runner或本地结果代替。
