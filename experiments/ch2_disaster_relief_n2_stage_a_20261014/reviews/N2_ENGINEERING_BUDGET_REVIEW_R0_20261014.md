# N2 工程额度草案独立审核 R0

日期：2026-10-14。仅审核 `E:/10.14/n2-development/ENGINEERING_BUDGET_DRAFT.json` 当前草案。未参与实现，未授予运行授权。

结论：**NOT READY，必须纠正计量定义和工作量推导。** 草案明确 DRAFT、禁止正式研究；1200 wall / 900 complete-process CPU 秒、4 GiB 内存和各工作上限是拟议值，本审核不把它们解释成已冻结额度。

| 项目 | 问题 | 必要修订/证据 |
|---|---|---|
| 候选及构造 | 候选25、branch25、construct/reset27、branch750仍无现场目录推导，25与旧固定布局数字相同 | 工程场景冻结输入、该窗完整公共候选catalog及数量。说明真实动态数量N如何导出构造/reset、N×最多30分支步。硬cap可保守设定，超过必须完整拒绝，禁止截断候选或复用25动作布局。 |
| WM forward | batch_forwards=1 与 updates=10 不自洽 | 训练forward至少10；预测、恢复等价、候选置换、unknown梯度测试均另计或受已定义总forward限。可将字段明确为inference-only，但所有训练/验证前向仍需覆盖计量。 |
| episode与step | episodes=1与25候选分支/PPO采集未分开，total800缺少计算式 | 定义主场景、collect rollout、branch rollout、PPO rollout、恢复审计的计数。environment construction/reset、physics step、sequential assignment、prediction/decision单位分别明确；预算覆盖全部真实消耗。 |
| reserve | settlement 30wall/10CPU是否包含1200/900未知 | 在总限内保留，例如工作可消费wall<=1170、CPU<=890；资源保留在运行前锁定，结算/导出所属项明确，外守护要允许安全结算而不越过总限。 |
| memory | rss_bytes与cgroup_memory_max同为4GiB但不是同一统计 | 明确process-tree RSS采样、cgroup memory.current/peak、MemoryMax硬限分别含义；不能用cgroup数值声称RSS。保留采样间隔、漏采局限及OOM events。 |
| storage | work512MiB、export512MiB与output_bytes_total512MiB含义不清 | 定义独立目录、嵌套/重复计算、联合峰值、最终bytes。临时归档并存/checkpoint/ledger/receipt/日志/导出均须纳入峰值；确定32 writes是否涵盖原子临时文件、manifest、结算等操作。 |
| CPU | complete_process_cpu_seconds缺计量来源 | unit完整cgroup CPU、worker/guardian/children/export/ExecStopPost可知范围、先验/部署成本单列且不双计；不能只用worker process_time。CPU0 affinity须目标cpuset实测允许。 |
| wall | RuntimeMaxSec与external wall guard仅有数值 | 新unit的Type、TimeoutStartSec/RuntimeMaxSec真实readback；历史oneshot RuntimeMaxSec无效，不能重用。实测外guard与失败结算能正常结束，保留InvocationID。 |
| checkpoint | model initialization1、loads2/1未覆盖实例化规则 | load若创建新模型/优化器，计数按实际API语义覆盖；strict mismatch/正恢复所需加载次数和验证forward明确。 |
| 状态与授权 | 只有草案，没有实际fresh identity绑定的消费记录 | 冻结工程identity、调用预算hash、所有pending/failed和first_error；工程与正式预算不可互用。测试负例造成的预期拒绝与真实首错/停止明确区分，不能把预期负例删出账本。 |

已将以上纠正项发给协调者与执行器；此报告只提出审查要求，不修改额度或工程源码。后续应审核新版本hash及真实计量实现，而非仅接受文字说明。
