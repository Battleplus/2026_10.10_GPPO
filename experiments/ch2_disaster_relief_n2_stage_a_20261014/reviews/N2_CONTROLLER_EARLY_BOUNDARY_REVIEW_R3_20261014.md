# N2 controller 早期独立审核 R3（未冻结）

日期：2026-10-14。范围仅只读 `E:/10.14/n2-development/controller/n2_controller.py` 与 `test_n2_controller.py`，文件仍变动。未执行controller、测试或SSH；没有实现修改。具体问题已直发独立目录执行器 n2_controller_executor 并抄送协调者。

结论：**NOT READY / 开发中，不能作为托管通过或新授权依据。** `command()`使用keyword-only label/text，create_remote_roots以正确方向调用；mock检验命令文本和顺序，比旧仅计connect/submission site有所改善。但以下重大边界尚未闭合。

| 编号 | 重大问题 | 所需证据/修订 |
|---|---|---|
| C01 | 最终systemctl输出未解析，返回invocation不要求ActiveState/Result/ExecMainStatus成功 | failed服务或仅InvocationID输出也能走“结果”返回。定义submitted/observed/complete/failed/UNKNOWN；绑定同invocation的runner、StageServer、BudgetLedger、shutdown和export收据。缺字段保持UNKNOWN，失败入口退出1，不把观察成功当worker成功。 |
| C02 | authorization只比package/run/target等，不绑定budget摘要、worker entry/args/remote-root | 仅budget status字符串APPROVED不足已冻结额度。exact frozen budget hash与身份/入口/参数/路径绑定授权；不可用额外args覆盖package/work-root或identity等受控参数。 |
| C03 | 只有两个硬编码已消费run禁止项与evidence目录exists检查，没有通用持久消费锁 | 同授权/同run更换evidence路径，特别preflight stop尚未创建remote root时可再次connect。connect前原子claim exact authorization/run，独立于evidence目录，失败后保留消费；并发/重入/新evidence路径必须零连接拒绝。不得测试真实已消费私有授权。 |
| C04 | 本地wall工作deadline与remoteRuntimeMaxSec起点不同，超时只closechannel | preflight/transfer耗时后remote仍可从提交起运行完整总限；本地1155 cutoff不会证明unit停止，45sec reserve也未形成单独结算路径。定义总体monotonic deadline、剩余remote运行预算、停止和settlement deadline；若连接断开或无法核验，保留remote running/cleanup UNKNOWN。不能声称安全停止。 |
| C05 | connect/SFTP put/collect阻塞操作没有deadline/计量约束 | 前后检查时钟不能限制阻塞中的超时。connect与通道/SFTP/collect须有有界超时和完整计量，失败保留首错与partial/pending不重连；输出写入/下载字节同样封顶。 |
| C06 | 只设CPUQuota/MemoryMax，未执行累计CPU总限、工作计数、storage或reserve预算 | worker必须消费新身份绑定完整budget并产出counter trace；完整unit/descendants/shutdown/export CPU不能用quota冒充累计CPU秒。预算hash、环境步/WM forward与optimizer/PPO真实optimizer/checkpoint/导出写入均须核对。controller不能只传任意stage-adapter/ledger-adapter字符串声称真实托管。 |
| C07 | preflight读取cgroup根cpuset而非实际unit cgroup；final缺whole cgroup cleanup证据 | 入口服务实际ControlGroup的cpuset/CPU/memory可用性要在worker start前验证；末尾MainPID/ControlPID、cgroup.events populated、procs/threads或明确cgroup absent。父进程组结束不等于unit为空。 |
| C08 | shell依赖SECONDS，未规定远端shell为bash | 默认远程shell可能dash，set-u与SECONDS引用可直接首错；需可移植或明确并校验解释器的deadline机制。外部monotonic守护不能用shell字符串中的deadline替代。 |
| C09 | manifest_rel/worker_entry/本地symlink边界尚未验证 | manifest必须包内受限相对路径，worker_entry必须manifest列内可执行入口，拒绝abs/..及symlink逸出；pin实际入口来源。传输仅mkdir直接parent，对深层目录也需验证完整创建成功。 |
| C10 | final collect回调没有要求验收返回值，mock仅记录collection调用 | 必须验证完整收集清单/字节与hash、收据status和export绑定，不能空collect也走观察成功并误解为验收。remote首错下不得清理或再提交未授权动作；保留partial evidence和unknown。 |

当前读取测试仅成功路径mock与budget/auth/hash三类prevalidation负例。最终至少补各phase首错（connect/preflight/mkdir/transfer/verify/submit/observe/result/collect）、拒绝前零文件写/零连接、持久one-shot重入、bad/missing/duplicate InvocationID、failed/unknown final、超时及结算不可证状态。成功mock必须逐条核对远端实际text语义，包含同invocation验证、exact pinned worker和budget传递；mock通过仍不替代真实目标托管收据。

本轮LOCAL开发profile由协调者另行提供，不能把Windows无cgroup的本地运行称远端通过。新controller最终审核仅在执行器宣布冻结hash后进行；本报告针对早期读取版本的边界，不推断后续修订仍有同一缺陷。
