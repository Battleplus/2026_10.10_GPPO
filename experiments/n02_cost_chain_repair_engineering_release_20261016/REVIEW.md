# 独立审核记录（最终：PASS，仅工程入口准备）

以下前半部分保留初次 BLOCK 及当时快照；修复后最终结论与当前哈希见末节。

审核日期：2026-10-16。范围仅为本候选目录原五文件及其直接调用的 v5 计量/校验接口。只读检查，未远连、未提交 systemd unit、未训练、未生成模拟 measured receipt；仅写本报告。结论针对新工程入口准备，不代表正式研究就绪。

## 两个阻塞

1. **成功 transient unit 的计量证据可能在读取前被回收。** `engineering_cost_bootstrap.py:251` 提交的 transient service 没有保留机制；轮询在 `:305` 才读取，成功退出后可被 systemd GC。随后读取可能丢失 InvocationID、CPUUsageNSec 和主进程时间，或直接异常，而 writer 在 `build_prior_resource_cost.py:106` 又要求 `loaded/inactive/dead`。最小修复：明确保留成功 unit，先保存同一 InvocationID 的完整进程退出计量，再释放 unit。若使用 `RemainAfterExit=yes`，应将“主进程已退出但 unit 保留为 active/exited”明确作为采集状态，并同步调整 launcher/writer 的成功判据；不能直接添加该属性却保留原 inactive/dead 终态条件。失败及释放后不得回填零值或复用别的 unit。

2. **最终校验失败会留下已替换的 pending 文件。** `build_prior_resource_cost.py:241` 先以 receipt 覆盖 `PRIOR_RESOURCE_COST.json`，`:242` 才调用原校验器；任何校验异常均直接返回 receipt_rejected，原 pending 不会恢复。最小修复：保留 pending 原始字节；仅在完整校验成功后提交，或在最终校验异常/不接受时原子恢复原 pending 字节，并保留失败证据。不得只在报告中声称“拒绝后 pending 保留”。

## 其余核对

- 原 v5 pending 未被改写；候选 diff 只调整 stage protocol、前移既有 cost gate，pending 的 measurement/gates 值保留。`source-hashes.json` 的 11 项原始输入哈希全部匹配。
- helper 只调用既有 `run_guarded_pipeline(preflight_only=True)`；该调用限制为 input_admission，未包含训练/forward/checkpoint、正式 attempt 或授权创建路径。预算明确为后续申请值，当前没有工程执行授权或执行事实。
- writer 的 stage_costs 与原 `/2` 校验器的求和和 wrapper overhead 归入 input_admission 规则相符；单阶段覆盖已如实标注。只有修复上述 unit 留存后，才有可靠产生这些真实证据的路径。
- receipt 引用前序测量部署的 source/archive identity，最终发布再收录 receipt/evidence 并重算静态身份，结构上没有自摘要循环。当前 deployment 字段交叉一致性不证明代码与最终 release 一致；准备文档已经披露，封版仍须核对。
- 建议随最小修复补齐已有字段的绑定：将 context.pending_status_sha256 与当前 pending.status_sha256 比较，并交叉核对 context/terminal 的 unit_name。无需增加测试或调度框架。

## 本次审核快照

以下 SHA-256 对应作出 BLOCK 判断时的文件；执行者后续更改需复核两个阻塞，不能将本报告视为新版本审核结论。

| 文件 | SHA-256 |
|---|---|
| engineering_cost_bootstrap.py | 9d08221586d03aa4636aedc2dac9f3656a5b158fa3a1203a8167e48fb96a145d |
| build_prior_resource_cost.py | 214210f1b67d142194b39359ecd58cfa307627ff26de7aa8ff5b9e9eb1866066 |
| patch-v5-minimal.diff | bca4b9c9d233a3177aa73157998f5bede429276de2a7775e670e695ce439b8ca |
| REPAIR_PREPARATION.md | 6c606263bb385ffca05a628370201d84dd30fab7622984623ff6d642feee6760 |
| source-hashes.json | 058af06733406effba55bd4a9ee5d615cd3d5ef9a08b83ddb5b9088f074599f6 |

## 修复后定向复核：PASS

2026-10-16 再次读取稳定文件，仅复核上述两个阻塞、新增字段绑定及 oneshot 预算修复；未新增测试框架、未运行 systemd、未远连、未执行 helper 测量或 receipt 构建。

1. **unit 留存阻塞已解除。** 提交采用 `--service-type=oneshot --no-block` 和 `RemainAfterExit=yes`，主进程成功退出后 unit 保留为 `loaded/active/exited`；launcher 与 writer 同步使用该采集状态。writer 将 context、terminal 与 systemd Id/InvocationID 交叉绑定，且 terminal 的整组 systemd 属性必须等于保存的 show 内容。
2. **pending 提前替换阻塞已解除。** writer 先将完整 package 与证据复制到临时 canonical 根，在隔离 Python 进程运行原 `/2` 校验器，并核对返回 receipt SHA-256。校验通过后再次确认原 pending 状态与哈希不变，才执行同目录 `os.replace`；校验失败不触及 pending 原文件。
3. **绑定与预算复核通过。** context.pending_status_sha256 必须等于当前 pending.status_sha256；unit_name 必须在 context/terminal/systemd Id 一致。oneshot 执行处于 activating，修复已添加 `TimeoutStartSec=270s`，手动 wall/CPU 检查覆盖 activating 与 active，并在 InvocationID 尚未出现时照常先检查预算。准备文档已明确 RuntimeMaxSec 在 oneshot 启动阶段不能提供有效运行上限。

本次 PASS 仅表示本地新工程入口候选准备通过静态定向复核；没有实测成本结果、没有 measured receipt、没有新工程执行授权，也不代表正式研究就绪。首次审核中单阶段覆盖、`/2` 求和规则及无自摘要循环的结论仍适用。11 项原始输入和 4 项候选输出清单均重新核对，全部匹配。

### 最终五文件 SHA-256

| 文件 | SHA-256 |
|---|---|
| engineering_cost_bootstrap.py | e78573e76ba9130a6bd709e929ca77bddb4a78d46c51fea46dbf2823c3722154 |
| build_prior_resource_cost.py | 60927aef0ae26e953f93eca15726259b4096c5cac1067dcd344490c1f100d91e |
| patch-v5-minimal.diff | bca4b9c9d233a3177aa73157998f5bede429276de2a7775e670e695ce439b8ca |
| REPAIR_PREPARATION.md | 29afb01b0d2f5ef7934d4af5034c8c71987c2e6f92e6999a1ab722e11ba880c1 |
| source-hashes.json | ac97c2ae46a8da4bf3f0cecd999d9f16c6274c8e84392dd47c151eab99fca128 |

REVIEW.md 为独立审核记录，自身不纳入上述五文件哈希，避免自摘要循环。

## 组装后部署传输增量（2026-10-16）

本目录的部署脚本随后增加了 ZIP 传输绑定，前述审核结论不被追溯修改。`deploy_preflight_once.py` 在建立 SSH 连接前只构建一次 `deployment-package.zip`，读取同一字节串并重新核对本地 SHA-256；SFTP 上传使用这组冻结字节，不从路径重新读取。它把 ZIP 上传到独立的远端 staging 对象，远端 verifier 在发布 package 前重新计算该对象的 SHA-256，并要求等于命令参数中的本地摘要；校验通过后删除该 staging 对象，再原子发布 package。远端校验失败不会生成 deployment receipt。只有远端 ZIP 校验、逐文件 manifest 校验和目标 `driver.py --preflight` 全部成功后，脚本才写入并同步含 `source_identity_sha256` 与 `archive_sha256` 的 receipt。

本增量未执行 SSH、上传、远端校验、目标 preflight 或 receipt 生成。新的 `deploy_preflight_once.py` SHA-256 记录在 `engineering-file-hashes.json` 中；该清单和本说明只描述工程副本，不改变研究矩阵、预算、静态 Request/Attempt identity 或原 v5。
