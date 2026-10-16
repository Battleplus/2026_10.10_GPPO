# N02-v5 成本链首错诊断

## 结论

实际首错是缺少已测量的 prior resource-cost receipt。v5 包内 PRIOR_RESOURCE_COST.json 是合法的 pending 状态：measurement.status=pending、actual=null、validated_receipt=null，且 pipeline_execution_allowed=false。resource_supervisor.py 的 _read_prior_resource_cost 会将它解析为 execution_allowed=false；process_guardian.py 在第 1024 行读取后，于第 1027–1028 行拒绝正式执行。该拒绝发生在 work-root 账本初始化和 driver 子进程启动之前。driver.py 另有同类门禁，但不是本次首错。

因此最小修复是补齐真实且可验证的 measured receipt；翻转许可字段、把已知零消耗改成实测值或绕过 guardian 都不能修复成本链。

## 现有测量能否复用

development/ch2_disaster_relief_graph_v2 中存在一份真实旧收据，所引用的 9 个证据文件哈希均匹配。它记录 graph-v1 的失败 admission 和 shutdown：systemd 总计 5.734729 wall 秒、2.914629 CPU 秒；旧账本为 5.689454 wall 秒、2.854474 CPU 秒，差额可复算为包装开销。失败原因为 RSS 字段缺失。

这份材料不能直接作为 v5 的 prior receipt：旧收据 schema 是 resource-cost-carry-forward/1，stage_protocol 为空；账本 schema 为 resource-ledger-entry/1，stage 只有 admission/shutdown；部署证据绑定 graph-v1。v5 校验器要求 /2 收据、当前七阶段账本和哈希绑定的 systemd/deployment/ledger 证据。校验器还要求证据相对路径留在 canonical package_root 内，不能直接从旧 graph_v2 目录读取。把旧数值改装成新字段也会把旧失败运行误记为当前协议测量。

当前 v4 100x100 的 accepted preflight 只证明目标运行环境和 systemd 配置可用；training_started=false，不能充当执行成本测量。

## 协议闭环阻断

v5 resource_supervisor.py 第 32 行及包内 pending receipt 使用 n02-integration-smoke-v4/seven-stage；但 v5 release manifest 和 preflight 使用 n02-integration-smoke-v4-100x100/seven-stage，协议标识为 n02-integration-smoke-v4-100x100，地图契约为 relief-grid-100x100-v1。当前 prior-cost 校验只把 receipt.stage_protocol 与代码常量比较，没有把成本收据绑定到 release manifest 的 100x100 协议身份。因此，即使补入一份符合当前代码常量的收据，当前代码本身也不能证明它属于 100x100 release。校验器也只验证 deployment receipt 与成本收据自身的 source/archive 摘要一致，没有将该身份与当前 release manifest 比较。

## 最小修复

在后续未冻结版本中先统一成本收据、资源账本、release manifest 和 preflight 的 stage_protocol 为明确的 100x100 七阶段标识，并重算相应发布身份；同时明确 carry-forward 证据允许绑定的 source/archive 范围，并让校验器对照当前 manifest。随后取得能证明属于该 100x100 协议和声明 source/archive 范围的真实工程测量，生成 resource-cost-carry-forward/2 收据。至少需要：

- evidence_files 中含 SHA-256 绑定的 resource_ledger、systemd_show、deployment_receipt 三类证据，且证据留在 canonical package_root 内。
- resource ledger 具备当前协议七阶段的 measured wall_seconds、cpu_seconds，可复算 ledger_stage_costs。
- systemd show 中有 InvocationID、ExecMainStartTimestampMonotonic、ExecMainExitTimestampMonotonic、CPUUsageNSec；收据总 wall/CPU 和分配给 input_admission 的 wrapper overhead 与账本一致。
- deployment receipt 的 source_identity_sha256、archive_sha256 与收据匹配；最终收据协议标识与同一 release 的 100x100 manifest/preflight 一致。

现有工作没有可直接复用的 v5/100x100 measured receipt。按本次诊断范围，没有连接服务器、运行研究、创建授权或修改冻结包；要生成上述测量需要后续授权的工程运行及新的未冻结 release。
