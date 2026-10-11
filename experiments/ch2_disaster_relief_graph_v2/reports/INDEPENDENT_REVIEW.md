# 图策略迁移 v2 独立工程修订审查

日期：2026-10-11。审查人：用户指定 GPT-6.1 Sol `execution_plan_review`。

**最新结论：v2同源目标工程验收及六路正式运行的独立结果审核通过；真实迁移、训练、评价与导出闭环完成。本轮未观察到明确图层增益。** 2026-10-11目标证据及最终结果审核详见文末。本审查不重复已通过的模型/环境本地72项检查，也没有启动额外本地full smoke、SSH或服务器任务。审查人没有修改实现源码。

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

上文为部署前工程修订审查；下列为完成目标运行后的独立验收，取代上文中“目标接受未通过”的阶段状态。

## v2目标验收与budget node（2026-10-11）

**独立验收通过，无实现阻塞。** 审查人直接在本地读取Luna回传的98个原始证据文件及补充journal，执行只读审计脚本；没有重跑目标任务或调用本地formal runtime gate。可复核脚本：`E:/Z博士/.codex-tmp/ch2-graph-release-v2/independent_target_audit.py`；逐项结果：同目录 `independent_target_audit_result.json`。最终执行通过，4.512秒。

目标package为 `/home/user1/w1-pilot/packages/ch2-disaster-relief-graph-v2-20261011`，workroot为 `/home/user1/w1-pilot/runs/ch2-disaster-relief-graph-v2-20261011-once`。原始smoke tar SHA-256为 `34c9c38a6acb36c98cc70c1497b7ea39c307ee9c4f2c15821254abf5dc80d7bc`。实际发布tar摘要 `6f774cff78e7a3ada4a1b8dbdff472021c4400f08c821841b973fe9f78398ec5`、manifest摘要 `05a9bed38d8728f5ae7a068122e81abf2df60153505c5d64ac614d1feeb41c47` 均独立重哈希匹配。26项源码、182项manifest文件和9项prior绑定证据逐文件重哈希全通过；源码身份仍为 **bed250f4cc5c9cd001b9d5fe4b596780ccc24ac1ef9cd50dbdf3ea182a87a0f3**。

目标runtime精确为Python3.11.16/Torch2.7.0+cu128/NumPy1.26.0，CPU0、Torch两线程配置均1、CUDA_VISIBLE_DEVICES为空、GPU始终未初始化。CPU tensor/autograd/clipped-gradient/Adam witness为有限数值且参数真实改变。admission、smoke、freeze的source/data/package/workroot/runtime绑定相同，smoke绑定freeze、admission与export文件摘要全部匹配。

主ledger恰好两行：admission accepted、engineering_smoke complete。两driver及两Linux guardian内嵌resource_entry与最终主行逐值一致，无first_error/outer_error/kill_reason，真实wait4 child_returncode均0。finished-started、child+guardian CPU、分stage与pilot累计均独立复算通过。当前累计54.007748174481094 wall /53.714075130999994 CPU秒，加prior后为 **59.742477174481095 wall /56.62870413099999 CPU秒**；admission含prior为8.60580915595004/5.985777626，smoke为50.759695620741695/50.499738922999995，历史shutdown仍0.3769723977893591/0.143187582。峰值RSS818872320字节，work/export44003593字节，均低于原上限。

独立打开全部真实checkpoint并复算模型与optimizer摘要，核对source/data/config/architecture、round及Adam state step为16/32；L0/L1各两正常round、各一恢复round、受控失败一round，共 **7轮、112次optimizer更新**。每轮240 transitions、4×60 ticks，rollout与checkpoint实际文件摘要等于学习曲线绑定。L0/L1严格恢复的第二轮完整归一化行为、rollout字节、模型state和optimizer state均相等，round_record摘要重新计算匹配；两final checkpoint标记完整两轮。28条C0/C1/L0/L1工程夹具轨迹均为60tick，并重新运行full independent_audit，结果逐值匹配目标audit。没有正式heldout轨迹，formal_training/formal_evaluation不存在或为空。

工程export86项文件及bundle84项文件全部独立逐字节重哈希，export manifest摘要为 `e26533e163c7744a41f73efc48dd35836548b9e91d9698d0ed5631fb61ce6415`。strict_restore、controlled failure和snapshot均被manifest/最终smoke绑定。受控失败保留首错 `RuntimeError: controlled_failure_after_checkpoint`、failed driver及相同failed ledger，真实16更新的部分checkpoint存在，final checkpoint不存在；其成本由外层smoke计入，不能再把内层账本成本重复相加。snapshot明确只截取smoke最终结算前的admission及prior；最终累计以主ledger为准。

固定开销各分项、runtime/import残差和8个实际checkpoint-inclusive轮样本分别重算通过。wall fixed=8.19829833926633、max round=7.4779634471051395；CPU fixed=7.810585518000015、max round=7.094328230999999。按原冻结公式，wall floor=133、CPU floor=131，故 **R=min(32,133,131)=32**，满足最低8轮。六个新运行为L0/L1×8201/8202/8203；共192轮、3072 optimizer updates，工程权重不复用。六路32轮含1.5倍裕量的训练估计为 **2165.9509202751797 wall /2054.8824088049996 CPU秒**，低于训练9000/8400额度。prior没有training成本，原训练公式无需改变。

systemd证据范围明确：原show为post-GC的not-found快照，不能据此声称unit exit0。补充user journal四条记录以USER_INVOCATION_ID/_SYSTEMD_INVOCATION_ID绑定 **523a72b882b34f3185780a11a7d8d933**，两子PID与guardian一致；Started及资源结算可核实，无显式systemd退出码。成功结论来自已独立核验的真实driver和wait4 guardian最终结算，不要求unit常驻，也不重提smoke。

补充journal精确CPU_USAGE_NSEC=53796454000，即本次service CPU53.796454秒，比当前主ledger多 **0.08237886900000291秒**。从首guardian起点至service资源日志的已知墙钟包络54.06253105401993秒，比两stage wall合计多 **0.054782879538834095秒**。含prior及该外围已知包络为 **59.79726005401993 wall /56.711082999999995 CPU秒**，剩余whole至少按已知耗用扣至14340.20273994598/11943.288917秒；这不是完整service尾部计量保证。最终报告须保留此差值、0.25秒RSS/磁盘采样限制及未完全覆盖的末尾写账/写receipt范围，禁止把额外成本清零。若执行wrapper需要总timeout，应扣除已用预算；不修改冻结算法或重跑smoke。

审查人向主模型回报通过的budget node。主模型已基于此作出六路共同R32的单次启动判断；本文件不宣称研究效果或正式训练完成。后续正式监控与最终数据仍需独立审查。

## 正式运行与最终结果独立审核（2026-10-11）

**正式运行证据审核通过。** 主模型已接受最终结果节点：真实迁移与六路对比闭环完成；本次数据未显示明确消息传递收益，不能推断算法无效、等价、优越或泛化能力。审查人直接对已取回证据执行本地只读审核，未再调用服务器或重提任务。

全量回传tar：`E:/Z博士/.codex-tmp/ch2-graph-release-v2/target-smoke-evidence/formal-run-evidence.tar.gz`，SHA-256 **9259d39d8c8ec1950b2f6b27376c30068594f8e39ac6e0e4b055a065d296e3c3**；解包后1855个文件。独立脚本 `E:/Z博士/.codex-tmp/ch2-graph-release-v2/independent_final_audit.py` 与结果 `independent_final_audit_result.json` 保留，可复查；最终执行通过，23.044秒。冻结26项源码身份仍为 **bed250f4cc5c9cd001b9d5fe4b596780ccc24ac1ef9cd50dbdf3ea182a87a0f3**；126份注册场景字节摘要逐项匹配原registry。

实际训练L0/L1×8201/8202/8203均32轮，共 **192轮、3072次optimizer.step、46080 transitions**。逐一打开全部192份round checkpoint，重新计算model/optimizer state摘要，并核对学习曲线、进度日志、rollout文件、四个60tick episode、奖励求和、source/data/config、round和Adam步数；六个final checkpoint均完整32轮/目标32轮、严格state加载通过。目标architecture/paired初始化receipt、six-final manifest和evaluation checkpoint barrier相互匹配，后者列明六模型已在读取heldout前严格加载；新seed未导入工程或旧checkpoint。

Adam的参数步数需精确表述：每个optimizer实际执行512次更新。四个pair_actor参数在minibatch只有NOOP决策、其grad为None时不执行该参数的Adam更新，最终L0三个seed分别500/501/508步，L1分别505/508/505步；其余具有optimizer state的参数均512步，逐轮pair_actor步数单调且每轮增量≤16。不能把“3072次optimizer.step”误写成每个参数均更新512次。

本地Torch2.13与目标Torch2.7初始化字节可不同，直接以本机构造器重算target common_init_sha256会产生诊断不匹配；本审核没有把它误判为目标屏障失败。六个目标checkpoint的配对初始化证据相同、结构属性与冻结构造器相符、state严格加载及摘要独立复算通过。最终脚本因此比较目标配对receipt与结构，并明确排除跨版本初始化字节相等这一无效要求。

**448条正式评价轨迹均重新执行full independent_audit**，覆盖56个heldout父场景×C0/C1及六个模型，每条60tick。完整audits与task_rows逐值匹配；独立任务指标、块外承诺延误、episode metrics及决策时间的每tick换算均复核通过。训练PPO reward只是优化信号；下列主指标由独立任务事件审计产生，没有用训练reward代替。1850项export文件及大小逐项重哈希全通过，manifest SHA-256 **4fcca36b5765b35d357003749fc58f6da29fef54e6a8d79bb13016cbdd8f9931**，评价summary SHA-256 **f7b73ad8febff66498dfa3fe9ac955f8f70343b11e9642cb0c5ccd9d5ffe325f**。export snapshot仅含前四stage最终账本，最终export结算须读取主ledger及05-export receipts。

主指标为父场景宏平均优先级加权按时交付率；L0/L1再平均三个训练seed。结果：

| 方法 | 主指标 |
| --- | ---: |
| C0 | 0.4727118119975263 |
| C1 | 0.9701054401947259 |
| L0 | 0.9645430627573485 |
| L1 | 0.962714071642643 |

独立从448行任务指标重算父场景宏平均，并用固定种子/5000次父场景配对bootstrap独立复算两组区间，均与目标summary在数值容差内匹配：

| 比较 | 均值差 | 95%父场景配对区间 | seed 8201 / 8202 / 8203差值 |
| --- | ---: | --- | --- |
| L1−L0（图贡献） | −0.001828991114705399 | [−0.02271938048723763, 0.018075998075998072] | −0.014523373451944878 / −0.000022943326514753203 / 0.009059343434343435 |
| L1−C1 | −0.0073913685520828375 | [−0.023906445736802874, 0.010225980616605611] | −0.010524247577819007 / −0.013420309848881278 / 0.00177045177045177 |

两个区间均跨零，只能表述为本轮未观察到明确图层收益或优于C1；不能把不显著解释为无效或等价。区间仅反映已观察56个父场景上的配对重采样，不涵盖全部训练seed不确定性。56个heldout结果已消耗并转为开发资料，不能用于后续正式确认或看结果后调参再检验。样本与合成场景限制不支持数量泛化断言。

## 正式结算与外部超时保护范围

原正式服务 `ch2-graph-v2-formal-20261011.service` InvocationID **14a4a0ff2583476b9020a8f0b704453b** 始终未变，没有重启或重提。最终show的Result=success、ExecMainCode=1（CLD_EXITED）、ExecMainStatus=0，MainPID=0、ControlGroup为空；journal保留FORMAL_CHAIN_COMPLETE。起止mono2588177660454/2589230316187微秒，服务wall **1052.655733**秒、CPU **1049.641056**秒。

主ledger恰好admission/smoke/training/evaluation_analysis/export五行，全部最终成功；五个driver receipt及guardian内嵌resource_entry与主行逐值相同，child_returncode均0，无首错、outer错误或kill reason。累计、时间字段与child+guardian CPU逐行复算通过。

| 本次阶段 | wall秒 | CPU秒 |
| --- | ---: | ---: |
| admission | 3.2480525537393987 | 3.2143362079999998 |
| engineering_smoke | 50.759695620741695 | 50.499738922999995 |
| training | 948.6396157718264 | 945.694668918 |
| evaluation_analysis | 98.22599001321942 | 98.178276792 |
| export | 5.485134819056839 | 5.464197284999999 |

主ledger加v1 prior合计 **1112.0932177785837 wall /1105.965847126 CPU秒**。正式service相对training/evaluation/export账本的外围差为 **0.3049923958974432 wall /0.30391300499991303 CPU秒**；再加此前v2 admission/smoke已知外围包络差，已知服务包络及prior合计为 **1112.45299305402 wall /1106.3521389999999 CPU秒**，相对whole14400/12000剩余 **13287.54700694598/10893.647861秒**。stage与whole均低于原上限，未借shutdown reserve。主ledger峰值RSS **824274944字节**，package/work扫描峰值 **964447677字节**，低于4GiB/8GiB。

这些是明确范围的账本/服务包络，**不是全系统计量**。包含bound v1失败、v2 admission/smoke及正式服务；artifact transfer/preparation/deployment另有receipt，取证、辅助timer和全部系统活动未计入这组数字。0.25秒RSS/磁盘采样可漏短暂峰值，最终写账/写receipt有尾部范围限制；acceptance墙钟用首guardian到资源日志包络，不能声称完整服务尾部。

外部wall保护需保留实际时序：Type=oneshot使原RuntimeMaxSec被忽略，TimeoutStartUSec=infinity；动态set-property修改被systemd拒绝。Luna建立独立仅绑定原InvocationID的watchdog timer，审查中修正TERM后deactivating仍须KILL及远端仅支持--kill-who的问题，所有systemctl调用限时2秒。后续又修正多次2秒调用所需安全余量；最终corrected timer在mono2589276662620（14:10:00）进入active，**晚于正式服务14:09:13退出约46.35秒**，不能冒充整个运行期间已生效的修正保护。原独立timer与冻结内部stage/whole guard运行期间存在；本次实际1052.66秒未触及总界，无超预算或重提。最终corrected timer未触发，确认无活进程后取消，取消receipt保留。最终报告应陈述这一外围保护限制。

主模型已据上述审核接受最终结果节点。后续报告/图表/归档仅整理本轮已完成结果，不追加训练或修改冻结算法；发布前的技术sidecar将另行绑定最终交付文件。
