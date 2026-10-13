# 民用救援环境与 Dreamer Replay 接口审计

日期：2026-10-13  
范围：环境适配、源码可移植性、N2 新场景注册与 replay 元数据合同。  
状态：接口受控验收通过；神经网络接线、世界模型训练和策略评价未执行。

## 结论

本包把原民用 `ReliefEnv` 保留为底层仿真器，新增 `ReplayReliefAdapter` 与工厂，不改旧环境动力学。适配器以已公开任务和平台信息编码固定维度观察；隐藏任务不会占用公开任务槽，也不会进入候选动作。动作按 4 个平台槽、16 个公开任务槽固定为 65 项：`0..63` 是平台—任务派遣选择，`64` 是 `COMMIT`。派遣选择只是同一物理分钟内的零时长决策微步；唯一推进物理时间的动作是 `COMMIT`，它将已选批次一次性交给原 `ReliefEnv.step()`。派遣不会自动提交。若四个平台槽均已占用，mask 只允许 `COMMIT`。

这满足 Dreamer/R2 Buffer 的时间对齐合同：raw frame `x_t` 保存 `vector_t`、`action_mask_t`、`is_first_t` 和从该观察发出的 `action_t`；`reward_t`、`is_last_t`、`is_terminal_t`、`dt_t` 是从前一帧动作收到的 transition 结果，并附在 `x_t`。Buffer 将 outgoing action 前移到下一编码状态对应的 RSSM transition。`dt` 可仅由 action 推导：dispatch 为 0，COMMIT 为 1；它不进入 encoder。`vector` 是唯一送入 encoder/重建 decoder 的键；mask 是 actor 输入及同状态辅助预测 target；其余标志和签名只作 replay/外部验证元数据。

## 源码与可移植性

原民用源码原字节放在 `vendor/relief_env_v2/`，来源、旧协议说明和源文件 SHA-256 见 [`vendor/relief_env_v2/SOURCE_PROVENANCE.json`](../vendor/relief_env_v2/SOURCE_PROVENANCE.json)。`relief_adapter.vendor_source` 用按源码根隔离的包名导入，避免 `sys.modules` 中的同名旧环境污染。`make_relief_adapter(scenario, source_root=None)` 默认从包内 vendor 构造 `ReliefEnv(scenario)`；传入 `source_root` 可改用外部 `relief_env_v2` 源码目录。

`relief_adapter/data/registry.json` 记录 vendor 逐文件摘要、vendor 源树摘要、provenance 摘要、场景文件摘要及语义摘要；`summary.json` 汇总注册集摘要。最终主线程回执为：canonical registry SHA-256 `18168de200a5549dda3f4a0f270c368a9e480fd3991a87203c2621024493fea3`，registry 文件 SHA-256 `3f96d6ad8a421d9d2890c4df34d3bdba2a81999fa76976e68d33492958bd161a`，scenario-content aggregate `9523328f310ef869f46c8358b39e2c97a751009376f9258874e2dd5ef5b3bdc4`，vendor source-tree SHA-256 `fabd909ada277a73f12d18e1214c4407fc0024509ee78ec0a35254984950f07c`。最终生成日志为 `registry-generation-final-20261013.log`。历史 source 与结果目录仅用于父 ID/语义哈希排重。新的 parent ID 使用独立 seed namespace。生成器对新场景去掉 `scenario_id` 后重算语义哈希，若与旧注册/结果重叠或新集中重复，会在写入前停止。

新注册集固定为 train 56、development 14、heldout 56；每个 split 中 carrier competition 与 stock competition 各半。场景从 vendored control fixture 复制，调用旧协议的 `_apply_common_variation()`，随后只施加 N1 已审计的两种机制变换。此处复用的是两类压力条件，不声称复刻 N1 全部七种 strata 分布。carrier 条件同时设置已知 food 与隐藏 delivery 数量为 16；stock 条件将各 depot 的 water stock 设为 water 总需求的 60%。Heldout 只完成场景结构和哈希准入，未用于策略推理或效果评价。

## 接口与验收

- 输入向量由原适配器以 `array('f')` 返回，固定 float32；新增 replay 字段不拼接进向量。
- `action_mask` 长度固定为 65，COMMIT 永远合法；容量越界由原 adapter 的公开槽检查拒绝。
- `is_first` 只在 reset 观察为 true；`is_last` 在 terminated 或 truncated 时为 true；`is_terminal` 仅在环境真实 terminated 时为 true。
- 返回观察中的 incoming `dt` 与 `info['adapter']['physical_time_delta']`、`discount_exponent` 一致，并在 wrapper 中再次验证 `action index -> dt` 映射。
- `adapter_signature_sha256` 绑定原 adapter 签名、replay contract 和 vendor 源树 SHA；`adapter_signature_sha256` 及 `replay_contract_sha256` 均由训练脚本在 encoder 外验证。
- 主线程报告：adapter/replay/registry 负责的 18 项测试通过；新建项目 compat-venv 的完整 25 项测试为 22 pass、2 fail、1 error。失败项由 Dreamer 集成审核继续修复，不能把整套测试报告为通过。原始日志为 `reports/all-tests-compat-20261013.log`。
- 两项失败分别是 `test_actual_adapter_frames_and_r2_buffer_keep_action_dt_and_mask_alignment`（actual action `64`、expected first action `0`）和 `test_lambda_returns_distinguish_terminal_from_truncated_end`（actual `2`、expected `0`）；一项错误为 `test_real_actor_distribution_never_assigns_probability_to_masked_actions`，上游 distribution `.sample()` 抛 `NotImplemented`。这些结果说明 Replay/R2 与 TorchRL 接线仍未通过，不改变前述 adapter 自身 18 项测试结论。
- compat-venv 使用 Python 3.11.5、只读系统 PyTorch 2.5.0+cpu，以及隔离的 NumPy 1.26.0、Gymnasium 1.2.0、TensorDict 0.9.1、TorchRL 0.9.2、Hydra 1.3.2。TorchRL 输出 C++ extension warning；这不是目标 PyTorch 2.8.0 runtime。两次 Torch 2.8 下载失败及证据均保留。另有隔离 Python 3.11.15；目标 Python 合同为 `>=3.11,<3.12`，不限定为 3.11.16。
- `SummaryWriter` 可能经系统 site-packages 间接导入 TensorFlow；其对进程 RSS 的实际影响尚未测量，需纳入兼容环境资源实测。
- 服务器 SSH 认证被拒绝；目标 Linux runtime preflight、资源测量和正式执行均未发生。该接口审计不构成服务器准入或授权。
- 测试仅验证环境合同和数据注册，不调用神经网络 forward，不训练世界模型，不训练 GPPO，也不运行策略评价。

## 复跑

在项目根目录 `development/ch2_disaster_relief_open_source_rlwm_v1`，用兼容性 venv Python 运行：

```powershell
python -B -m unittest discover -s tests -v
```

生成注册集并核对 N1 父场景及历史语义哈希：

```powershell
python -B -m relief_adapter.data.build_registry `
  --old-root E:\Z博士\development\ch2_disaster_relief_n01_v1 `
  --old-root E:\Z博士\research-executions\ch2-disaster-relief-n01-v1
```

若历史结果根目录与命令中的本机路径不同，应使用实际归档根替换第二个 `--old-root`。新注册的最终摘要以生成后的 `relief_adapter/data/summary.json` 为准；变更 builder 或 vendor 后必须重新生成并复核哈希。

## 未完成范围

本报告不证明预测准确度、世界模型可训练性、Dreamer latent/replay 端到端正确性、策略收益或泛化能力。尚未在精确服务器 runtime 上执行预检，也未启动正式训练或评价。Sealed heldout 必须继续隔离，直至模型、门控规则和分析脚本冻结。
