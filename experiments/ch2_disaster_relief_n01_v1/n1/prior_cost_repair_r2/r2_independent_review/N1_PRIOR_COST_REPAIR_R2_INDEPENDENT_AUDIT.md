# N1 r2 prior-cost 修复包独立审核

日期：2026-10-12  
审核对象：`E:\Z博士\development\ch2_disaster_relief_n01_v1\n1\prior_cost_repair_r2`  
新身份：`ch2-disaster-relief-n01-full-evaluation-r2-prior-evidence-20261012`

## 结论

修复包对 r1 首错的证据路径问题已作出可复现的本地修正：9 项 prior-cost 证据逐字节纳入包内，receipt 固定指向 `package/prior_evidence`，缺失或篡改会被拒绝。身份、服务、静态计划和预算绑定到 r2；静态注册仍是 350 个 scenario、2800 个 episode 和 6 个固定 checkpoint。tar 解包后的完整静态 preflight 通过。

本审核没有进行 SSH、admit、正式评价或训练。当前冻结包的 stage budget 状态为 `proposed`，表示审批提案；包外 `BUDGET_REQUEST_NOT_APPROVED.md` 的申请状态为 `NOT_APPROVED`。包内 `approval_reference` / `approved_by` 为空，且不存在外部 `N1_FULL_EVALUATION_BUDGET_APPROVAL.json`。本报告不是启动授权，也不建议据此启动。

## 核验记录

- Receipt 列出的 9 个 evidence 文件均与 `engineering_revision` 下对应源文件的 SHA-256 相同，也与包内 `prior_evidence` 副本相同。证据明细及哈希见修复目录的 `N01_FULL_EVALUATION_PRIOR_COST.json`；该文件记录已知历史累计成本 wall `173.07905203544348` 秒、CPU `124.840999441` 秒，并将未量化历史用量保留为未知。
- 包内 560 项 source manifest 文件逐项复算无 SHA 不匹配。归档 `n01-prior-cost-repair-r2-20261012.tar.gz` 的 SHA-256 为 `c07771ce1bf9434f8e3a33a5685bd5f5e1b8e973c9d8cde92e7ed78132af9fc9`，与交付清单一致。
- 修复器报告的 prior-cost-only 检查在直接包和 tar 解包包均成功，9 项证据被识别，且声明未调用 admit。对解包临时副本进行的独立拒绝检查中，缺失 `received/resource-ledger.jsonl` 时退出码为 1 并报 `FileNotFoundError`；篡改同一 ledger 时退出码为 1 并报 SHA mismatch `PermissionError`。
- 本审核运行了完整 `--mode dry-run`，直接包和归档解包包都返回 `static_preflight_passed`，输出一致：350 场景，2800 episode，其中 heldout 2240、development 560，plan SHA-256 均为 `4c957b5e7c199afc43142758995d1f5d11ea9c98539edb4cf33a37a97d3897c2`。该检查同时核对 scenario 内容及 checkpoint 清单和文件哈希。
- Identity、checkpoint manifest 和实际六个 checkpoint 文件哈希一致：L0/L1 各对应 seeds 8201、8202、8203。scope、scenario count、episode count 和 checkpoint 文件数均未变化。
- Identity、service、runner、stage budget 和静态计划均使用唯一 r2 identity。systemd unit、package root、working directory 和一次性 run root 都使用 r2 名称；新身份总限额为 5940 wall / 4800 CPU 秒。stage budget 保持 `proposed`，其包外请求明确为 `NOT_APPROVED`，approval reference 和 approver 为空；r1 approval 不适用于此身份。历史训练/服务器说明文档加有不适用及不得启动声明。
- r1 的 journal SHA-256 仍为 `7a6678807de343ec25598fc0c807758441f0130cc2251633964dbb51f0ff5b00`，settlement SHA-256 仍为 `95c5b18b454c04e3db51d5831f0c3b2e0f535e499ee19451628f7f68e27c0c42`；未发现 r1 文件被本次审核改写。

## 预算门修正

较早的审核稿把 stage budget 状态写为 `proposed-not-approved`。这与正式 `_approved_budget()` 的冻结提案契约不一致：读取器要求 stage budget 为 `proposed`，并另行要求包外 approval 文件状态为 `approved`，同时绑定 r2 evaluation identity、stage-budget SHA、各 stage caps、总上限、审批编号和审批人。修订包已将包内状态统一为 `proposed`，未批准状态保留在包外申请文档；approval 文件仍缺失，因此尚不能通过正式准入门。

执行器在临时副本检查了 approval 函数边界：没有 approval 文件时拒绝；提供 schema、r2 identity、当前 stage-budget SHA、stage caps 和总上限全部匹配的合成 approval 时，该函数接受。合成文件未放入候选或正式包。此项只检查 approval 读取与绑定逻辑，没有调用 admit、加载 checkpoint、执行训练或评价。修订后 prior-cost-only 检查输出状态为 `proposed`，其身份和 source hash 清单与更新后的 stage budget 一致。

## 审核操作披露

完整 dry-run 的代码路径在 `_verify_checkpoints` 中对六个 checkpoint 各执行一次 `torch.load(..., map_location="cpu", weights_only=False)`，随后因 `strict_model_load=False` 跳过 policy/model 构造。直接包和解包包各运行一次，因此本审核共反序列化 checkpoint 12 次。没有执行 `_load_policy`、模型 forward、admit、训练或正式评价。此前所称“0 checkpoint load”只适用于 `prior-cost-dry-run` 模式，不适用于本轮完整 dry-run。该操作仅发生在本地审核副本，没有改变交付包或 r1。

## r1 停止资源口径

r1 首错为部署位置缺少 `/home/user1/w1-pilot/packages/received`，停止时未进入评价；正式轨迹、训练更新和 N2/N3 均为 0。其资源字段须按采样口径区分：最终 `CPUUsageNSec=134700000` 为 0.1347 秒；settlement 的 `CPUUsageNSec=123739000` 为 0.123739 秒，cgroup `cpu.stat usage_usec=127108` 为 0.127108 秒。这些读数来自不同时间/采样阶段，不应互相替代。`memory.peak=12222464` 是 cgroup memory 峰值，不是 RSS。主进程 monotonic wall 差 0.227406 秒不代表完整 systemd 生命周期或结算 wall。
