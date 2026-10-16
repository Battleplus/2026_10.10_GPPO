# N02 L1 独立复核记录

## 复核范围

本记录整合了 L1 发布包外静态复核、正式 run 的本地回执复核，以及已收到的 GPT-6.1 Sol 独立审核结论。复核没有重新连接服务器、没有重跑训练、没有修改冻结 release，也没有修改正式 run 证据。

## Sol 审核结论

Sol 的独立审核文件为 `development/n02_cost_chain_repair_engineering_release_20261016/INDEPENDENT_REVIEW_RESULT.md`。其结论是：L1 release 与 formal authorization binding 的本地静态控制流 **PASS**；审核确认 manifest、bundle、request、attempt 的身份链一致，目标 package 文件集与声明哈希一致，测试覆盖通过。该审核明确不把静态审核当作服务器运行或算法收益证据。

本 execution 目录的 `REVIEW.md` 进一步对最终 L1 修复 release 做了独立静态闭合复核：53 个 package 文件与 manifest 精确一致，L1 构造覆盖训练和开发 strict restore，seed 8201 的 actor pairing、WM freeze、cache、critic adapter 和 checkpoint restore 接线均保留。该结论的范围仍限于静态发布完整性。

## 正式 run 复核

本地正式证据显示唯一 systemd invocation `66dd44280c67427faaddb196dc9a4b09` 以 `Result=success`、`ExecMainStatus=0` 结束。七阶段 receipt 的 `first_error` 均为 null；`input_admission` 为 accepted，其余六阶段为 complete。导出 ledger 的 `all_successful=true`，work calls failed/pending 为 0，故工程执行门可判 PASS。

checkpoint 审计确认：

1. G checkpoint SHA-256 为 `c46c6c54f67358f3f771fef29380d8fc80e511133785d553449b28c226a9ae18`；G-WM 为 `4bcbb4ec9dc6c6cd9ab5c356caefee8d5bb76ab907eb7dd033191b845911909e`。
2. 两者均含真实 `literal_attention`、`task_update` 和 `critic` 参数，不是仅改 variant 标签。
3. 两者的 WM 张量 exact equal，并与 `world_model.pt` exact equal；receipt 标注 WM frozen。
4. G/G-WM critic optimizer step 均为 8，critic Adam moment 非零，且训练 receipt 有非零 gradient norms、actor/value losses。

strict restore 子进程 status complete，4/4 prediction forwards 和 4/4 candidate evaluations 完成；正式代码对同一组 `training_windows` probe 的 parent/child prediction hashes 做了 4/4 exact 比较。development windows 是另一组诊断 probe，不能把两组摘要 digest 交叉比较。

## 结果解释

开发评价只有 2 episodes、120 environment steps；G 与 G-WM 的配对 energy、inspection-on-time rate、weighted-on-time-delivery-rate 差异全为 0。该结果是配对诊断中的零差异，不是收益证明。世界模型全局 MAE 为 `0.0793732250`，global utility ranking 没有有效非平局 pair，因此 ranking accuracy 为 unknown；不能从该 run 宣称 ranking 能力或决策收益。

## 资源与限制

资源快照总计 CPU `22.582237053 s`、wall `30.429306381 s`，上限 900/1800 s；worker RSS 峰值 `684748800` bytes，外层 guardian high-water `1646800896` bytes。原始 ledger 的 settlement entry 不在导出 snapshot cutoff 总计中，二者采用不同范围，不应相加。systemd `CPUUsageNSec` 未设置，因而 systemd CPU 账本不完整；正式资源结论仅引用阶段 receipt/ledger，并保留该限制。

## 独立复核判定

**工程 PASS，研究效应未判定。** 发布身份、CPU-only 运行条件、七阶段闭环、checkpoint/restore、资源结算和导出均有证据。单次、单 seed、小样本配对评价不足以支持算法优越性、跨规模泛化或世界模型收益结论。
