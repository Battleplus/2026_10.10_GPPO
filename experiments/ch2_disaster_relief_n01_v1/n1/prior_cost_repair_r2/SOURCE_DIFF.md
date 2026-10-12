# 修复差异和源清单

源冻结package：`../engineering_revision/package`。复制文件不含`__pycache__`；目录树与SHA-256完整清单见`source-manifest.json`。

相对源包的有意差异：

- `N01_FULL_EVALUATION_PRIOR_COST.json` 将evidence root改为包内`prior_evidence`，并绑定r2 identity；9项receipt哈希值及证据字节不变。
- 新增`prior_evidence/`，保存receipt列出的9项原始证据。
- identity、stage budget、runner、service及systemd probe名称改为r2唯一身份；包内stage budget保持`proposed`，包外预算申请为NOT_APPROVED；上限数值5940/4800不变，获批需包外hash-bound r2 approval。
- runner加入`prior-cost-dry-run`只读模式，拒绝证据清单变化、包外路径、缺件或篡改。
- `SERVER_EXECUTION.md`、`EXECUTION_CONTRACT.md`顶部增加不适用说明，旧训练指令不构成本包授权。
- 新增静态plan与独立停止结算correction addendum；r1原报告、审批和源包均未改动。
