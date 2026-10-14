# Linux 工程节点结论（2026-10-14）

服务器 SSH 认证已恢复。本次独立 r2 工程验收通过：26 项回归、上游 CartPole 三次真实更新、灾后巡查与运输适配三次真实更新及学习器恢复检查全部完成。固定 batch 的 CPU FP16/FP32 对照各完成两次有限更新，共计 10 次工程优化器更新。六路研究训练与独立确认评价均未启动，尚无算法收益结论。

## 实际运行与证据

服务器为 `ru-server-MS-1`。专用 venv 使用 Python 3.11.16、只读基础 Torch 2.7.0+cu128、NumPy 1.26.0，并在自身目录安装固定 overlay 闭包。CUDA 隐藏且未初始化；CPU0、单线程。上游 pin 为 `NM512/r2dreamer@546e4fab8146ea4b14e1d7726bbc1a8a1d50322f`，显式 `rep_loss=dreamer`。上游声明 Torch 2.8.0；本次是兼容性验证，使用 CPU FP32 overlay，不能称为精确上游复现。

首次 `run-01` 因测试引用外部环境路径及缺少 TensorBoard 停止，没有执行神经更新，其日志和收据保留。经 Luna 二次意见后，独立 r2 增加固定 TensorBoard 依赖闭包，只改一处测试夹具路径，不改变算法或测试断言；使用新的环境、源码与 `run-02`，没有重提原 run。

`run-02` 的 systemd InvocationID 为 `8c332cc30ff748ab81b06bc7df1dba7d`，服务退出码 0，所有有界托管检查通过。配置为 `Restart=no`、`KillMode=control-group`、CPUQuota 100%、MemoryMax 4 GiB、RuntimeMax 600 秒。先读取保留的退出状态与计量，再显式清理；清理返回 0。后续只读回查 `MainPID=0`、inactive/dead。

民用烟测使用一个 train 父场景，128 次 adapter 调用推进 120 个物理分钟，包含 8 个零时间分配微步，129 个 replay frame，非法动作 0。模型参数确实改变，恢复模型哈希与训练后一致；优化器、调度器、计数、RNG 和适配元数据恢复通过。checkpoint 不包含 replay 和模拟器状态，因此不证明完整训练续跑。

三次民用更新中后两次想象动作只剩 COMMIT，actor loss 为 0。短跑证明真实更新与接线可运行，不证明策略已学到有效分配；后续 pilot 必须观察该现象是否持续。

## 资源与完整性

- runner wall：35.0467 秒；systemd cgroup CPU：30.636219 秒。
- 最大单个子进程 RSS：829,440,000 字节；各阶段采样进程树 RSS 最大值：840,663,040 字节（约 802 MiB）。两者口径不同；systemd MemoryPeak 不可用。
- 独立 r2 环境构建 wall：21.7755 秒，单独记录，未计入服务值。
- 资源仅覆盖有界服务及子命令，不含 SSH、源码传输、安装、finalizer 或其他系统开销，不能称完整系统资源结算。
- 部署 313 个 manifest 登记文件及 manifest 自身共 314 文件通过；运行时 224 个源码/输入哈希与该 r2 快照一致。
- 17 个导出制品及最终收据逐字节复核通过；原审核绑定的 27 个输入未变。

最终运行收据 SHA-256：`0449033931a122dbbf7f7cf2ea5298cd7cd326f6515bced9913a20d947cb66f7`。

原 r2 验收文档有一处相对环境链接错误，已作为非阻塞限制保留；实际环境规范在 [linux_execution_r2/environment-spec.json](../../linux_execution_r2/environment-spec.json)。r2 的权威发布身份为 [LINUX_RELEASE_MANIFEST.json](../../linux_execution_r2/LINUX_RELEASE_MANIFEST.json)，源码内旧 delivery manifest 仅是父提交溯源。

## 下一节点

下一步建立有界真实 pilot，测量 GPPO 和 Dreamer 的训练成本、合法动作、想象 COMMIT 比例、actor 梯度及开发集表现，再冻结完整研究预算。pilot 计入每路 128 episode 的训练上限；不能把本次三步小模型烟测当作八 episode 的正式训练预算实测。确认集保持封存，六个最终 checkpoint 屏障通过前不评价。

现有三方法方案比较 C1、GPPO 与 Dreamer 的完整系统表现，可以判断本场景中哪种方法更有用；它不直接证明图与世界模型组合的协同优势。

原始收据：[run-02/run-receipt.json](run-02/run-receipt.json)；制品索引：[run-02/artifact-hashes.json](run-02/artifact-hashes.json)；主线程复核：[PRIMARY_BYTE_VERIFICATION.json](PRIMARY_BYTE_VERIFICATION.json)。Luna 独立审核另存于 `independent-review/`，其独立性为同模型家族 provisional，由主线程代传 SSH 命令与原始制品。
