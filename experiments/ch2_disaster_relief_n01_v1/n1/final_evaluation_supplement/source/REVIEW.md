# 图策略迁移 v2 独立工程修订审查

日期：2026-10-11。审查人：用户指定 GPT-6.1 Sol `execution_plan_review`。

**结论：v2工程修订候选通过，可以封装并部署同源目标admission与engineering-smoke。目标接受仍未通过，六路正式训练仍关闭。** 本审查不重复已通过的模型/环境本地72项检查，也没有启动额外本地full smoke、SSH或服务器任务。审查人没有修改实现源码。

## 冻结身份与修订范围

v2路径：`E:/Z博士/development/ch2_disaster_relief_graph_v2`。26项 `source_identity` 按 `json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()` 的SHA-256为 **`bed250f4cc5c9cd001b9d5fe4b596780ccc24ac1ef9cd50dbdf3ea182a87a0f3`**。

v1源身份为 `6b2395fca1af120f45d88f86123095903b99f264dd61930305e315002f185b14`，v1失败发布和原始目标证据保留。v2相对v1仅有下列绑定源变化；其余20项源摘要不变。

| 文件 | v2 SHA-256 | 修改目的 |
| --- | --- | --- |
| process_guardian.py | a43b73f519c622ba56e28f10ac5ebc3cb51d6febd61a40284ce45550621501fc | 子进程退出竞争有界wait4确认、起点一致、外层继承已用预算 |
| resource_supervisor.py | b871ba742124a04b4ce1d5b57a3ae316ac9f5821df71c22a05266182d70a3ddc | 验证prior证据并扣除对应stage和whole成本 |
| driver.py | e2d9b5d81deb699e1976b72c018aaf5e5532b45c91668dac3fa909f41449532a | CLI、stage监督及资源摘要统一绑定prior成本 |
| ppo_trainer.py | c0ac1c57ae1a06d8dadf94de80ca4e35f5b136f0879064aac0e0618abb2fc891 | source_identity必需绑定PRIOR_RESOURCE_COST.json |
| REUSE_IMPLEMENTATION.json | 241f1fdf51f4134ff7a664d03217285680a9cbce0c5af91bf5368da30aa72279 | 明确v2资源继承语义 |
| PRIOR_RESOURCE_COST.json | b577b88138699dcefc8286314b64d0c41d7278f36ed3db38eccdae962a5ed263 | 固定失败v1实际成本及9份证据哈希 |

独立AST比较：`ppo_trainer.py` 除 `source_identity` 外全部顶层函数和类与v1相同。图策略、vendored图算子、环境、基线、评价、协议和生成器源码摘要不变。输入registry仍为 `bf50433281761ca3264c62f5e63cc0c49e578bcc1fcafa369f3014daced8e093`。本次没有改变研究设计、学习算法、场景或预算总额度。

## 目标v1失败的实际证据

`diagnostics/prior-v1/server_admission_failure_v1_20261011/` 保留9份绑定证据。systemd InvocationID为 `15e90e871dbe4de79aa989936191fb39`。

审查人读取原回传文件，确认目标Python3.11.16/Torch2.7.0+cu128/NumPy1.26.0、CPU0、线程1及GPU未初始化的kernel witness通过，且子进程退出0；外守护因 `RuntimeError: RSS fields missing for pid 3543979` 把admission最终判failed，systemd退出1。smoke没有启动。主账本两行与各driver receipt和guardian内嵌resource_entry完全相等。

| 成本 | wall秒 | CPU秒 |
| --- | ---: | ---: |
| v1 admission账本 | 5.31248185178265 | 2.711286834 |
| v1 shutdown账本 | 0.3769723977893591 | 0.143187582 |
| systemd相对两行账本补差 | 0.045274750427990895 | 0.060154584 |
| v2继承总成本 | **5.734729** | **2.914629** |

systemd补差保守分配到admission，故v2 admission已用5.357756602210641 wall /2.771441418 CPU，shutdown已用0.3769723977893591 wall /0.143187582 CPU。所有后续stage均继承whole总成本；对应stage也扣除自己的历史成本。新身份不混入旧failed账本行，旧失败仍保留在绑定证据中。

## 修复审查与针对性验证

- child `/proc/status` 无RSS时，同时检查status/stat状态；读取期间发生退出可通过wait4确认。只在读取child指标的异常路径进入确认，guardian自身指标异常仍失败。
- 有界确认最多10次5ms请求间隔，11次WNOHANG检查；必须真正回收目标child才使用wait4最终CPU和ru_maxrss。进程仍活着则失败、kill并reap，不能跳过缺失RSS继续成功。实际等待及调度开销包含在outer最终wall/CPU结算中；50ms是请求间隔总量，不能当作调度层绝对时间保证。
- guardian结算现在同步写outer `started_wall_monotonic`，使finished-started与wall一致；child原起点另存metadata。旧v1已记录成本不因该字段修正而下调。
- `PRIOR_RESOURCE_COST.json` 的9文件摘要、旧ledger分stage合计、deployment源/包身份、systemd InvocationID及时间/CPU重新求和都被验证。必需prior缺失时CLI/source identity/supervisor/guardian拒绝，不能退回零成本。
- 独立执行当前受影响测试：guardian **9/9通过，0.080秒**；driver **6/6通过，2.685秒**；resource supervisor **9/9通过，0.248秒**。覆盖非Z快照后退出、延迟reap成功、live缺RSS有界超时失败、guardian缺RSS且child可reap仍失败、首错保留、部分账本恢复和时间字段一致。
- 独立纯诊断：prior9证据验证成功；admission/shutdown/whole成本都实扣，接近stage上限时会因prior成本拒绝。临时副本下调prior stage成本被拒绝，改证据字节被拒绝；连续两次invocation的累计仅计入prior一次，显式缺失必需prior被拒绝。

本次只复跑资源/driver受影响检查。v1的本地模型/环境72项、旧14轨迹指纹及112次工程更新是先前证据；不能冒充v2同源目标接受。v2完整目标工程smoke仍必须实际执行。

## 目标收据接受清单

主任务回传目标workroot及systemd证据后，审查人仅在本地读取回传文件进行以下核验，不调用会检查本机runtime的正式gate。

1. 核对新deployment/source26项、prior receipt及9份原证据摘要；package/workroot必须为当前v2独立身份，原v1不覆盖。
2. runtime_admission精确版本、CPU0、线程1、CUDA空环境/GPU初始化false及真实kernel update；admission、smoke和freeze的当前source/data/path/runtime身份一致。
3. 主账本当前admission唯一accepted、engineering_smoke唯一complete；两driver receipt及两Linux guardian均最终成功、exit0、无first/outer错误，内嵌resource_entry与主行逐值相等。逐行重新核算current成本+prior成本的stage/pilot合计与时间字段。
4. L0/L1各两个实际round、严格恢复分支、受控失败真实round，核对每轮240transition/16更新、总112工程更新、checkpoint/optimizer step与源身份；恢复模型/optimizer/行为记录等价。28条60tick工程夹具轨迹重新独立审计，注册heldout结果尚未访问。
5. 独立逐文件重哈希工程正常export、bundle及其strict_restore/controlled_failure证据，核对final smoke/freeze/manifest绑定；受控失败保留首错和partial checkpoint。不能只信smoke_complete先写的complete而忽略最终guardian结算。
6. 以目标实际慢轮和固定成本重算R，确认eligible且8≤R≤32；formal_training尚无旧/partial证据。仅在以上全部成功后主任务才启动六个全新初始化的研究运行，工程权重不复用。

当前冻结公式：

`R = min(32, floor((9000/1.5 - fixed_wall)/(6*max_round_wall)), floor((8400/1.5 - fixed_cpu)/(6*max_round_cpu)))`

round样本须分别含L0/L1第一轮、未中断第二轮及恢复第二轮的实际含checkpoint成本，取max。fixed包含driver setup、runtime/import residual、完整train数据加载、3次pair初始化、6次trainer初始化及6次final保存。当前prior没有training成本，因此9000/8400训练额度未减少；admission/shutdown及whole额度已扣除上述prior值。若任何进一步修订产生新训练成本，不能继续按未减余额套用该公式。

全pilot14400 wall/12000 CPU秒；stage额度依次为admission600/300、smoke900/600、training9000/8400、evaluation2400/1800、export600/300、shutdown900/600。RSS4GiB、work/export8GiB；禁止换身份清零预算、借用shutdown reserve或只保留成功子集。Linux wait4和/proc/磁盘采样的原范围限制仍存在：最终少量采样/账本/receipt写入尾部不在计时中，0.25秒目录扫描可能漏短暂磁盘峰值。服务器报告须保留这些限制。

**本文件仅允许v2候选进入目标工程验收；没有批准六路正式训练，也没有研究效果结论。**
