# N1 r1停止记录与r2 prior-cost修复包

本目录是GitHub增量归档草稿，尚未发布。r2身份为`ch2-disaster-relief-n01-full-evaluation-r2-prior-evidence-20261012`。包内stage budget保持`proposed`；包外budget request为`NOT_APPROVED`，当前没有有效r2 approval。不得据此启动准入、评价或训练。r1 approval不适用于r2。

## 内容

- `r1_stop_evidence/`：r1停止journal、systemd结算、状态文件、停止报告、只读独立审核及资源结算纠正补充。记录r1唯一InvocationID `7b65d35b5b4c464b810ecac918978166`、首错和未加载checkpoint/未产生轨迹的范围。
- `package/`：r2自包含完整package，含源码、输入scenario、registered input registry、scenario/checkpoint索引和manifest、9项prior-cost证据、identity和未批准预算。冻结文件按原始字节保存，局部`.gitattributes`禁止换行归一化。
- `n01-prior-cost-repair-r2-20261012.tar.gz`：字节权威分发归档，含完整package及6个checkpoint权重。SHA-256见`tar-sha256-manifest.json`。
- `source-manifest.json`：package每个文件的路径、字节数和SHA-256。
- `verification-report.json`：直接package及tar解包路径的prior-cost dry-run结果，以及篡改证据拒绝结果。该验证没有加载模型或checkpoint、没有调用admit。
- `budget-gate-verification.json`：在临时副本中验证无approval会拒绝、使用正确schema且绑定stage-budget SHA的合成approval会通过。合成approval未进入交付包，没有调用admit或加载checkpoint。
- `r2_independent_review/`：独立审核完整报告。审核员另行执行直接package及tar解包的完整`--mode dry-run`，共反序列化checkpoint 12次（六个文件各两次），没有构造policy、模型forward、admit、训练或正式评价。prior-cost-only检查没有读取checkpoint；不能把这一范围扩展为整轮0 checkpoint读取。
- `REPAIR_REPORT_ZH.md`、`SOURCE_DIFF.md`、`BUDGET_REQUEST_NOT_APPROVED.md`：修复说明、差异说明和明确未批准预算申请。
- `update_release_manifest.py`、`release-file-manifest.json`：逐文件重算候选SHA/尺寸，并检查package inventory及权威tar摘要。

## r1资源字段说明

停止仅发生于准入前，不能作为算法结果。最终CPU结算采用0.1347秒；systemd 0.123739秒与cgroup 0.127108秒为不同来源/时点观测。`memory.peak=12222464`是cgroup峰值，不是RSS。`ExecMain` wall 0.227406秒不是包含stop-post结算的完整生命周期wall。详细解释见r1停止资源纠正补充。

修复独立审核已通过；预算状态契约刚完成修正，需复核修订后的package/tar和预算门记录。发布内容最终审阅仍待完成。目标环境未连接或验证。未创建新授权，未发布，未push。
