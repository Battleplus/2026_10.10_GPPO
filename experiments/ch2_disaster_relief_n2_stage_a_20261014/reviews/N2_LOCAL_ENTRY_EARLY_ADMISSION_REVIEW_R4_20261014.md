# N2 LOCAL真实工程入口早期准入审核 R4（未冻结）

日期：2026-10-14。只读文件：`E:/10.14/n2-development/LOCAL_ENGINEERING_BUDGET.json`、`run_local_engineering.py`、`run_local_engineering_watchdog.py` 和其实际调用的 `references/existing_n2/{branching.py,world_model.py}`、民用PPOTrainer。文件仍变动，本次未运行smoke/优化器或SSH。

结论：**NOT READY，计量与入口缺陷修正后才可形成有界本地工程收据。** 协调者已说明LOCAL可用12个PPO rollout episodes、真实PPO optimizer最多64，期望旧三round比较路径48更新；不需要改民用PPO核心凑恰好2更新。此profile仅本地工程，Windows cgroup N/A，真实托管/正式研究仍未通过。

## 已确认可复用接线

入口从工程机会fixture真实C1完整rollout取t8 snapshot，对完整catalog逐候选分支，引用版本reference首步已改为NOOP，随后C1；训练DynamicConsequenceModel，再将其state用于CriticAugmentedGraphPolicy及CriticAugmentedPPOTrainer。实际train_round+verify_next_update_equivalence内部连续/恢复各一round，共三round，民用PPO每round16 optimizer updates，总48、12 episodes。此为源码路径核验，尚非实际执行完成收据。

新合同修订源码已补savedcatalog/key唯一性/context.time校验；新validate_public_view在branch/WM入口已有引用。但完整标签仍缺未满足需求、改派、其他新增过期及绝对后果，入口limitations如实记录，不得据本地工程成功称阶段A完整ready。critic末层零初始化/训练归一化仍待实施冻结核验。

## 运行前必修项

1. **立即失败的repeat/time混用。** 当前world_model.branch_records_to_targets以tuple(parent,repeat,window_id)比较context，却另用record.window_start比较tuple第二项repeat。入口传repeat0、真实t8将被拒绝。应与context.time/public observation.time比较，不可把repeat改8绕过。
2. **联合环境步缺硬限。** profile branch_steps8000、PPO_steps8000、base240可联合超8000，须增加并实际执行overall_environment_steps_max8000。完整base scan、source重建8步、candidate/reference、strict restore中C1 prefix replay、PPO三个rollout路径均纳入实际计数；环境step调用前保留额度，不是结束后估计。
3. **分支步报告错误。** `sum(horizon_minutes+1)`不是两条实际分支调用数；候选与reference各horizon，额外restore/prefix replay也要覆盖。以真实ReliefEnv.step instrumentation区分collector/branch/reference/replay/PPO并联合对账。
4. **工作量上限未执行。** WM/PPO optimizer、WM forward/candidate rows、checkpoint read/write等目前没有before-effect计数拒绝；WM forward posthook仅增加数字，不拒绝超额。restored_wm未挂hook，漏恢复下一步两次前向。PPO `3*first_result`只能预期数量，须实际optimizer step trace（仍用真实PPOTrainer，不用scalar trainer）。
5. **profile与源码身份未在启动前冻结。** worker仅运行尾读取profile hash，硬编码1000/128；需prevalidation固定profile bytes/hash/status/完整字段与source manifest，并消费同一对象，执行尾拒绝中途源码/预算变更。scope“not training authorization”应清楚指非FORMAL研究，避免否认已授权的local真实WM/PPO工程。
6. **原始证据需落盘。** branch records/标签/轨迹当前留内存，仅摘要报告无法独立复算；在额度内保存完整raw evidence与输入/状态/来源摘要。保存的WM checkpoint为10更新，而PPO用next-update等价性后11更新的WM state；明确最终frozen WM digest、checkpoint来源和更新index，不得把10checkpoint误说成PPO实际来源。
7. **write与checkpoint统计。** workerPython audit hook只覆盖output-root相关open/rename/remove，父stdout/收据不在其内；stdout写入不是文件个数。checkpoint底层序列化/C API操作需确认hook是否覆盖，使用真实保存/加载入口计数。最终receipt自己的写入和临时文件也计入，不可报告写receipt前的计数为全部消费。

## watchdog 必修与测量局限

- 当前活进程树CPU累计值求和再取peak会丢已退出子进程CPU；按pid/create_time保留每进程已观测累计最大/最终值，逐进程处理NoSuchProcess而不是整个tree sum失败回旧peak。报告采样盲区，不将sampled peak冒充完整CPU。
- 整个启动/监控/扫描/等待需try/finally保留首错并停止已记录worker/descendants；目前path.stat、psutil、wait异常可能跳过终止和收据。kill后逐PID/创建时间核验退出，cleanup不足记UNKNOWN，不能固定写“worker exited”。
- 1155秒工作deadline后45秒结算、870CPU后30CPU reserve须另有总1200/900保护；当前退出后读全log/扫描/写receipt未继续守护或纳入最终CPU/RSS/bytes。
- 目录采样允许短时超峰后才发现，Windows无kernel/cgroup硬限应如实说明采样间隔与限制。len(files)>1000仅文件数，不是output write操作；父日志与receipt也须纳入联合512MiB及写操作计数。
- profile应启动前pin，父子一致；最终hash不能把运行中替换的预算当原依据。父监控与worker输出/首错/partial/pending/退出码及有效receipt一致后才称LOCAL完成。

已把具体必修项直发执行器并抄送协调者。本审核不修改实现、不授予新的远端身份或复用已消费授权。缺研究标签头可保留明确NOT_IMPLEMENTED，不阻碍取证本地已实现链路，但禁止提升完整阶段A结论。
