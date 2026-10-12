# N1 prior-cost 自包含修复包 r2

状态：供独立审核；包外预算申请为 `NOT_APPROVED`，包内stage budget保留 `proposed`。此交付物不构成准入、训练或正式评价授权。

新身份：`ch2-disaster-relief-n01-full-evaluation-r2-prior-evidence-20261012`。r1唯一提交 `7b65d35b5b4c464b810ecac918978166` 已停止，首错为部署路径下缺少 `/home/user1/w1-pilot/packages/received`。该次0 checkpoint/model load、0轨迹；不得把本修复解释为结果或复用r1批准。

冻结package由r1工程冻结包逐字节复制，排除 `__pycache__`。先验成本receipt的9项SHA-256证据从r1 source root逐一原字节复制到 `package/prior_evidence/<原相对路径>`；receipt改为包内根 `prior_evidence`。代码拒绝错误根、缺项、多项、缺失文件或hash不符。身份、预算、systemd unit/service和静态plan均绑定r2身份；新服务、unit、run路径使用唯一r2名称。预算数值仍为5940 wall / 4800 CPU秒；包内stage预算状态是 `proposed`，独立批准缺失时对外状态为NOT_APPROVED，授权需由包外、绑定r2预算哈希的新approval提供。

`package/n01_full_evaluator.py --mode prior-cost-dry-run`只校验identity source hashes、先验成本证据和静态scenario登记，不import torch、不加载checkpoint、不调用admit。已在直接package路径及tar解包副本各运行一次；另对副本中的先验ledger篡改字节后，验证器明确拒绝。独立审核另外执行完整`--mode dry-run`，直接包及解包包均通过，合计反序列化6个checkpoint各两次（12次），没有构造policy/model、forward、admit、训练或正式评价。prior-only检查和完整dry-run的读取范围不同，详见独立审核报告。

预算门针对性验证在临时副本调用`_approved_budget`：无包外approval时拒绝；仅在临时父目录添加hash绑定的合成approval后通过。合成凭据没有写入交付目录；测试没有调用admit或加载checkpoint。结果见`budget-gate-verification.json`。

## r1停止资源口径补充

正式停止只覆盖失败的准入生命周期，不能表示完整评价消耗。CPU权威结算读数采用最终报告的 `0.1347` 秒；`systemd CPUUsageNSec=0.123739` 与cgroup `cpu.stat usage_usec=127108` 是不同采样口径/时点，保留为原始观测，不替代最终结算。`memory.peak=12222464`字节是cgroup峰值，不是RSS。`ExecMain`启动至退出wall为 `0.227406` 秒；它不等于systemd结算生命周期的完整wall。见独立correction addendum。

正式评价、模型forward、训练、N2/N3均未执行。完整静态dry-run反序列化了checkpoint状态以核对身份；目标环境preflight未执行。此包仍须获取r2专属外部审批并完成目标环境preflight；在此之前禁止启动。
