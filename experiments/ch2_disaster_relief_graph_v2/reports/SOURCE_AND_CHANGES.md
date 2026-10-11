# 来源与变更清单

正式执行包包含 183 个文件，冻结身份 SHA-256 为 `bed250f4cc5c9cd001b9d5fe4b596780ccc24ac1ef9cd50dbdf3ea182a87a0f3`。冻结源包的完整副本在 [`package/`](package/)，其部署哈希和复用清单共同构成来源登记。

| 组件 | 来源 | 本轮复用或新增内容 |
|---|---|---|
| 灾救环境、任务 schema、基线、身份和独立审计 | `development/ch2_disaster_relief_v1/` | 复用现有状态机、公开观测、候选生成、C0/C1 和指标；新增一分钟 `reset/step`、学习策略动作批次、奖励与轨迹导出接口。 |
| 图消息模块 | `src/uav_assignment/paper_faithful_models.py`、`src/uav_assignment/paper_env.py` | 将 Literal 平台注意力、任务更新、共享打分模块和边类型常量 vendoring 到执行包；策略侧使用动态实体 mask 与候选映射。 |
| PPO 优化 | `src/uav_assignment/ppo.py`、`src/uav_assignment/config.py` | 保留 clipped surrogate、value loss、entropy、梯度裁剪与 Adam 配置；新实现明确终止、截断和采样切段 bootstrap。 |
| 对照模型 | 新增 `graph_policy.py` | L0 用逐实体 MLP，L1 用消息传递；共享输入、动作、奖励、训练顺序和优化器。有效参数量差异 0.178%。 |
| 场景登记 | 新增 `protocol/preregistered_protocol.json`、`registered_data/` | 预先登记 56 训练、14 开发、56 评价父场景，七类场景等额覆盖；场景不按结果删选或重采样。 |
| 运行保护与复核 | 新增 `process_guardian.py`、`resource_supervisor.py`、`independent_audit.py` | 登记阶段资源计量、进程监管、库存/能耗与轨迹回放检查。原始复用路径与源文件 SHA-256 见 `package/REUSE_IMPLEMENTATION.json` 和 `package/SOURCE_REUSE_TRAINING.json`。 |

六个正式模型均从新随机初始化开始；没有加载旧 checkpoint、旧任务数据、世界模型、PreCo、多目标偏好控制或跨区域借机逻辑。冻结源包本身未在本地证据准备过程中修改。
