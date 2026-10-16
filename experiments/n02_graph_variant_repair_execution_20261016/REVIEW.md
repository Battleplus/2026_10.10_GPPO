# L1 包外执行 helpers 静态独立审核

结论：**PASS，限于本次最小适配的静态控制流。** 审核只读取 deploy_measured_final_once.py、formal_submit_measured_final_once.py、README.md，并与旧成功 run 的同名 helpers 比较、作 AST 解析；未执行或导入 helper、未 SSH、未 forward、未训练，未改冻结 release。

| 文件 | 审核版本 SHA-256 |
|---|---|
| deploy_measured_final_once.py | `87970b8f50c8f0265ebc0d3f24982a50f7ec3b2d8825fce55624da1935ee13c7` |
| formal_submit_measured_final_once.py | `09fb1a8d5961ca33915f12b128ae1c5ac63606f97f472b738eab647d15b277ac` |
| README.md | `7207f543aef204e4160badd9e6f396d32925fd977b5e8f74af9819f95c64fec7` |

部署 helper 第14/20/25行分别固定新冻结 release 目录、release名和新 preflight ID；第29行 METADATA 精确为5静态侧车，与53包文件组成58项部署载荷。旧 engineering_cost_bootstrap.py/build_prior_resource_cost.py 未被误当作本包侧车。上传后继续校验 archive SHA、53包文件 SHA、5侧车 SHA、精确文件集、无 symlink/bytecode，再原子 publish；已有 staging/publish/archive 均拒绝覆盖。第107行仍加载 known_hosts 并使用 RejectPolicy；CPU-only、单线程、taskset CPU0、-B 和 preflight 超时保持。

正式 helper 第15/29/33/35行固定同一新 release、新 run `n02-l1-graph-variant-repair-run-20261016-01`、新 preflight `n02-l1-graph-variant-repair-preflight-20261016-01`。第225行从新冻结包调用 load_release_binding；第243–251行把取得的新 preflight 的 engineering ID 和 manifest/bundle/request/attempt 四身份逐项对当前 binding，随后调用 validate_preflight_receipt。第263–266行从当前 binding 生成包外 contract/授权并再次 gate 验证，第281行只调用新发布包的 driver --run --authorization。FORMAL_BUDGET、FORMAL_SCOPE、资源 gate 和 managed handoff 仍来自冻结新包，未在适配中放宽；wall1800/CPU900/4GiB RSS 与原矩阵不变。

第88行强制 prior stage_coverage=[input_admission]，且保留前序 source/archive/measurement receipt、unit 与证据绑定；contract 里的 measurement 记录前序成本，不是 L1 训练成本。README 也明确此范围。新 L1 的实际 preflight/训练成本仍须由其未来真实执行产生，静态审查没有该类新实测结论。

两个本地 evidence 目录均在本 execution 目录以 exist_ok=False 新建（部署第89行、正式第224行）；正式授权由新四身份和新 attempt ID 新建，远程 AUTH_REMOTE/RUN_REMOTE 任一存在即拒绝（第272–279行，写授权使用 wx）。脚本未读取旧授权或旧 wrapper lock；旧 measurement 路径和 unit 字符串仅作为真实前序测量 provenance，属于有意保留。审核时目录仅含本次三份输入文件，无旧 evidence/授权/锁被带入。

边界：当前用户尚未批准新身份的部署/preflight及第二次正式 run；旧一次性授权已经由历史 L0 run 消费，本审核不将其延用。README 第12行是将来获授权后的先后顺序，不构成当前部署许可。正式 helper 被调用就会创建授权 envelope 并提交，因此静态 PASS 不能替代用户明确授权；本次不调用任何执行入口，也不增加独立于现有授权边界的审批步骤。helper 末尾的 systemd terminal 返回仍仅是运行终态提示，未来结果验收仍应读取真实阶段回执、ledger 与导出，不能由 wrapper 返回值推定模型效果。
