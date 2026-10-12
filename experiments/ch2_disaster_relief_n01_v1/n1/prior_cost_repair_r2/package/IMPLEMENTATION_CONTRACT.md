# 首个工程结果的实施合同

日期：2026-10-11。此目录独立于历史冻结包。本阶段只实现标准库CPU离散时间仿真和两种非学习对照，不运行神经模型，不训练。全部参数和第一章交接均为synthetic工程夹具，不能作为真实平台性能。

## 共同文件/API（供并行实现）

- `scenario_schema.py`: `validate_scenario(scenario: dict) -> None`，无效输入抛ValueError；不改输入。`load_scenario(path) -> dict`加载后校验。
- `relief_env.py`: `ReliefEnv(scenario)` 深拷贝并校验；`public_observation() -> dict`仅已接收信息；`candidates() -> list[dict]`返回稳定ID可行动作+NOOP；`run(policy: str) -> dict`运行到固定horizon。策略名 `C0`/`C1`。导出包至少含 `scenario_id, policy, events, transitions, final_state, summary`。独立audit以输入场景和事件日志复算，不依赖summary。
- `baselines.py`: C0严格按初始任务队列执行；队头因公开候选暂时不可行时等待，后续任务不越过它，只有队头完成或终态失败后才推进；不主动改派。C1按公开优先级降序、deadline升序、ID稳定排序，对未承诺可变任务选择预计最早完成的可行本块空闲平台；预计完成时间对每段travel分别向上取整到tick，不复用段间剩余分钟；保留在途及块外承诺；不接收env真值。
- `fixtures/build_fixtures.py`: 生成单一/组合扰动的合成场景及`chapter1_snapshot`，主夹具3 UAV+1直升机、2巡查+2已知订单+2潜在订单。外部承诺作为单独验收场景，不要求所有夹具固定6任务。
- `independent_audit.py`: `audit_run(scenario, result) -> dict`，只消费场景、公共事件日志/执行事实，重建逐任务结果、物资账和指标；错误抛ValueError。输出 `metrics, task_rows, conservation`。不得导入`relief_env`或调用其指标函数。
- `run_demo.py`: 运行每个夹具×C0/C1，写每run JSON、events.jsonl、transitions.jsonl、逐任务CSV、比较CSV、独立审核JSON、中文报告、输入和输出摘要；失败不伪装通过。独立复算与engine summary比对。
- `tests/`: unittest，可 `python -m unittest discover -s tests -v`。

## 场景schema v1

```text
schema_version: "relief-engineering/1"
scenario_id: nonempty string
synthetic: true
units: {distance:"km", time:"min", quantity:"kg", energy:"synthetic_unit"}
map: {rows:10, cols:10, cell_km:1.0, local_block:[0,0,2,2]}
horizon: positive integer minutes; dt: 1
platforms: [{id, type:"uav"|"helicopter", position:[x,y], local:bool,
             capabilities:["inspect","deliver"], capacity_kg, speed_km_min,
             energy_initial, energy_per_km, service_energy_per_min}]
depots: [{id, position:[x,y], stock:{commodity: nonnegative kg}}]
tasks: [{id, kind:"inspection"|"delivery", position:[x,y], local:bool,
         known_initial:bool, deadline:positive integer<=horizon, priority:positive number,
         discovered_by: inspection ID or null, report_delay:nonnegative integer,
         service_minutes:positive integer (inspection),
         commodity, quantity:positive kg, depot_id, load_minutes, unload_minutes (delivery)}]
chapter1_snapshot: {source:"synthetic_initial_assignment", time:0,
                    queues:{platform_id:[known task IDs]}}
disturbances: [{id, time:integer[0,horizon], kind:"failure"|"energy_change"|"stock_loss",
               platform_id (failure/energy), value (absolute new energy for energy_change),
               depot_id/commodity/nominal quantity (stock_loss), report_delay:nonnegative integer}]
```

位置用欧氏距离且无障碍，map中每个格1km仅工程假设。local_block的前两项为格坐标、后两项为格宽高；任务local须与任务位置是否落入按cell_km换算的半开矩形`[x,x+w) × [y,y+h)`一致。初始分配的平台与任务local标记须完全一致，平台local代表交接归属而非飞行瞬时位置。需求分母包括所有应在horizon内服务的订单，含未发现及不可服务。任务deadline、报告产生和报告接收分开记录。stock_loss是名义损失上限，事件时最多扣除当时剩余库存；事件与报告同时记录请求量和实际损失，库存始终不为负。

## 状态、信息和计量

首版每平台同一时刻只执行一个任务；候选为idle平台与公开可变任务配对。巡查：assigned→travel→observe→report_generated→report_received；巡查完成率按观察完成，报告延迟单列。运输：assigned→to_depot→loading→in_transit→unloading→delivery_confirmed。到达不直接完成；至少各有规定的装卸服务时间。分支不允许空中转货或直接改派已装载任务，货物失效转lost账。完成/失败/超期和未发现订单都保留在final_state。

任务执行中的承诺首版不抢占，故障释放未装载任务后C1可调整；原计划尚未开始的任务可变。块外承诺只能保留/按原计划执行，仍评价其完成和延误。C0因平台失效不能完成的任务仍计未满足。NOOP推进时间，按每tick每平台至多一次派单限制零时间动作循环。事件顺序固定：t时刻外生事件与应到报告→公开决策→推进[t,t+1]运动/服务→t+1记录结果；不得提前把t+1报告发给t策略。

状态内部真值与public mirror分开；隐藏订单不能通过tasks长度、候选、mask、deadline、库存预留或摘要泄漏。候选只用public mirror。资源改变尚未报告时允许公开可行动作在执行层拒绝/失败，并产生可接收报告，而非真值裁候选。

事件每条至少 `{seq,time,type, ...实体字段}`。类型须使用可供复算的统一名字：`assignment`、`move`、`service`、`inspection_completed`、`report_received`、`loaded`、`delivery_confirmed`、`cargo_lost`、`stock_lost`、`platform_failed`、`energy_changed`、`task_failed`、`task_expired`；可另加arrival/report_generated。loaded/delivery_confirmed/cargo_lost/stock_lost含commodity、quantity、depot_id、platform_id/task_id（适用时）；move含from/to/distance/energy；service含task_id/platform_id/stage/duration/energy。assignment含previous_assignee、new_assignee、initial(bool)、reason；report_received包含更新kind及主体ID。实现若要调整字段，请先同步另一执行者。

必须计所有运动/服务能耗，任务生命周期事件不得重复计交付；独立audit按每commodity核对initial_stock = remaining_stock + onboard + delivered + lost + stock_loss。平台失败前后energy不可负；energy_change的外生调整单独记账，不当作飞行消耗。

summary须含：`weighted_on_time_delivery_rate`（订单优先级加权、无订单为null）、`inspection_completion_rate`、`inspection_on_time_rate`（无巡查为null）、`delivered_orders`、`late_orders`、`unmet_orders`、`undiscovered_orders`、`energy_used`、`reassignments`（至少一次被分配给非原承运者的原有任务；每个任务最多计一次），`new_assignments`（原快照没有所有者、后续成功分配的任务）。未来模型次数全部为0，不把工程run混称正式评价episodes。

## 工程验收要求

输入错误/重复ID/未知关联/未知字段拒绝；能力/载重/库存/剩余能量约束；隐含状态不变公开输出；报告延迟；完整装卸与重复交付拒绝；未发现/不可行分母；故障前后及有货失效；资源变化；块外承诺及其延误；固定horizon与无订单N/A；C0/C1确定性；事件重放独立守恒及summary篡改拒绝。先各单扰动，再组合。不用结果挑夹具，不声称规则优于学习方法。

必须把实际仿真消耗与实现耗时区分：记录运行器wall、process CPU、场景数、tick数和日志条数；这是本地工程样本，不是训练预算或服务器验收。已发布规划的hash与旧冻结文件不改。
