# N01 R2 deploy-only 静态回读记录

## 结果

2026-10-12 22:27（Asia/Shanghai）完成一次 deploy-only 接入，命令总墙钟耗时 16.800768 秒，进程退出码为 0。该时长包含本地准备、静态 dry-run、归档和唯一一次 SSH 调用；SSH 网络段耗时与服务器 CPU 时间没有单独测量。服务器返回 `DEPLOY_ONLY_STATIC_ACCEPTANCE`。新包已发布，user unit 已安装并回读为 inactive；unit 未启动，admission 未调用，run 未创建。

本次只验证 prior-cost dry-run、完整静态 dry-run、包发布和 unit 安装/回读。静态 dry-run 反序列化了 6 个 checkpoint payload，`strict_model_load` 为 false；没有 model forward、训练或正式 evaluation。未创建 approval 或 token。

## 冻结绑定

- Evaluation identity：`ch2-disaster-relief-n01-full-evaluation-r2-formal-repair-v1-20261012`
- Identity manifest SHA256：`e01f2444bfb75d765f9522934a581a535055990445ec0356e6dd13b6fdc6e5fe`
- Stage budget SHA256：`49f2736a53e6428b3893a1ae0c81500b0e48ca766300352fb464715627ebeb5c`
- Reader file SHA256：`3eb535aa7390c0056044ba4ee5356fc3e2cea6ca9ce8e2e6d4ad5064d919aa3d`
- Reader 内嵌 plan SHA256：`7e5334cd8c9691df59a63501e5ed8bbb8ad31e466ecffdb535ae45bed832fb45`
- Expanded full dry-run plan canonical SHA256：`1c1563508730ed6b2cf63e9a4a3aec39e77401aecb17d920af883967d1e390e8`
- Expanded plan scope：350 scenarios、6 checkpoints、2,800 run keys
- Published release：560 files；561 archive members；archive SHA256 `d1aa7b5e03e8bf7c4f90f4a2f3c6f5085ad4df4f097e30647c49ed5ab098b7b1`

Reader file 的内嵌 plan hash 与 expanded full dry-run plan hash 对应不同 canonical 对象，分别绑定并校验。

## Unit 回读

`n01-full-evaluation-r2-formal-repair-v1-20261012.service` 的回读断言通过：`Type=exec`、`CPUAffinity=0`、`MemoryMax=4294967296`、`Restart=no`、`KillMode=control-group`、`LoadState=loaded`、`ActiveState=inactive`、`SubState=dead`、空 `InvocationID` 和空 `DropInPaths`。`systemctl cat` 内容绑定了本次 identity 与 package。run 路径不存在。

本次未执行启动该 unit 的命令：`systemctl --user start n01-full-evaluation-r2-formal-repair-v1-20261012.service`。

## 预算与资源边界

冻结预算仍为 `proposed`，approval request 为 `NOT_APPROVED`。新 identity 的预算上限是 5,940 wall seconds、4,800 CPU seconds；其中 evaluation 阶段 proposed cap 为 5,400 wall seconds、4,500 CPU seconds。它们是未批准预算上限，不是本次消耗量。历史未知用量仍未量化。

unit 回读证实静态 `MemoryMax=4 GiB` 与 `CPUAffinity=0`。没有采集 live CPU、内存、I/O、GPU 利用率、主机可用内存、CPU 拓扑或进程清单；不能据此推断服务器实际使用量或总资源容量。

## 审核与证据

独立 reviewer 对本地执行收据 PASS：核对了唯一调用及退出码、输出摘要、完整 560 项 release hash inventory、identity/source/checkpoint/archive/reader/expanded-plan 绑定、unit 回读断言和资源未测边界。原始合并 SSH 输出、执行 metadata、详细内部收据和完整 hash inventory保存在本地受控证据目录；本公开记录不包含主机地址、账户、私钥或原始输出。对应 SHA256 见 `DEPLOY_ONLY_EVIDENCE_HASHES.json`。

结论仅为 deploy-only 静态接受，不代表 formal admission、预算批准或正式 evaluation 获准。
