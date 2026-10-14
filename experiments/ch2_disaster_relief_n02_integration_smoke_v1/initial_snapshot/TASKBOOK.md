# N2 服务器执行任务书：世界模型与图 GPPO 最小真实集成

## 1. 执行目标与分工

**所有真实采集、分支推演、世界模型训练、图 GPPO 训练和评价，均在服务器 `ru-server-MS-1` 完成。**

本地仅用于源码开发、静态检查、生成发布包、读取取回的证据和 GitHub 归档。不得在本地悄悄训练，不能用本地或合成验收结果代替服务器真实训练结果。

本轮目标是跑通：

```text
民用场景
→ 真实配对后果数据
→ 世界模型真实训练
→ checkpoint 严格恢复
→ 图 GPPO critic 接线
→ 真实 PPO 更新
→ 配对开发评价
→ 资源结算与独立审核
```

| 角色 | 模型 | 工作 |
|---|---|---|
| 执行者 | GPT‑6 Luna | 实现、验收、部署、服务器运行、证据整理 |
| 独立审核者 | 独立上下文的 GPT‑6 Luna | 复核信息边界、动作合同、更新真实性、指标和资源 |
| 节点判断 | 当前主模型 | 决定下一步扩大、修复或停止 |

审核者只读冻结包和执行证据，不直接修改被审核版本。需要修复时由执行者产生新版本，再审核。

**本轮是单 seed 工程烟测，不能据此宣称世界模型或图 GPPO 优越。**

## 2. 服务器、运行时和发布规范

### 2.1 固定目标运行时

目标服务器：`ru-server-MS-1`。

优先使用此前已登记的 Python：

```text
/home/user1/w1-runtimes/w1-py31116-torch270cu128-v2/w1-light-repaired-fair-rerun-py31116/bin/python
```

预期版本：

```text
Python 3.11.16
PyTorch 2.7.0+cu128
NumPy 1.26.0
```

这些是待重新核验的历史配置，不能直接报告为当前已通过。

执行要求：

- 使用绝对 Python 路径和 `-B`。
- CPU0、单线程运行。
- `CUDA_VISIBLE_DEVICES=""`。
- 设置 OMP/MKL/OpenBLAS 等线程数为1。
- PyTorch内部线程配置在worker启动时固定并记录。
- GPU不得初始化。
- 不自动安装依赖、不升级服务器运行时、不修改全局环境。

若版本、CPU亲和性或关键依赖不符合冻结要求，停止于preflight，提交差异。

### 2.2 目录布局

统一使用：

```text
本地开发：
E:/Z博士/development/ch2_disaster_relief_n02_integration_smoke_v1/

服务器临时上传：
/home/user1/w1-pilot/staging/<release-id>/

服务器只读发布：
/home/user1/w1-pilot/packages/ch2-disaster-relief-n02-integration-smoke-v1/

服务器运行产物：
/home/user1/w1-pilot/runs/<attempt-id>/

包外授权：
/home/user1/w1-pilot/authorizations/<attempt-id>.json

工程验收证据：
/home/user1/w1-pilot/diagnostics/<engineering-id>/
```

发布包不能直接充当可写运行目录。训练日志、模型、SQLite和结算文件写入独立run目录。

上传流程：

1. 本地生成源码清单和SHA-256。
2. 上传到新staging目录。
3. 服务器核验文件集合、文件大小和摘要。
4. 拒绝未登记文件、`__pycache__`、`.pyc`及`.pyo`。
5. 全部通过后，在同一文件系统原子发布。
6. 发布后冻结，运行期间不修改。

不得覆盖旧N1、旧世界模型包或历史失败目录。

### 2.3 身份和入口

本轮使用新Attempt、Manifest、Hashes和Request绑定，不复用任何历史授权。

入口至少支持：

```text
--preflight
--authorization <absolute-path>
```

`--preflight`不得创建正式token、attempt、训练目录或启动学习。

正式入口负责核验授权、身份和未消费状态，再完成托管交接。`W1_VERIFIED_ATTEMPT`只能由核验通过的入口内部设置；不能依赖SSH shell手工提供。

最终命令由发布脚本生成并保存，使用结构化参数调用，禁止临时拼接多层shell quoting。

## 3. 实验实现与真实工作量

### 3.1 复用资产

复用：

- 民用灾后巡查与救援运输环境。
- 图策略、真实PPO/critic/GAE及C1规则基线。
- 世界模型多头BCE/Huber、unknown mask、候选排序和恢复合同。

重新适配：

- 动态平台、任务与候选布局。
- 公共观察与内部快照隔离。
- 完整环境动作对应的候选编码。
- 民用后果头与标量critic辅助通道。

旧军事数据、旧世界模型权重不进入本轮训练。

源码盘点阶段必须核验实际动作结构、时间步长和奖励定义，不得依靠历史描述直接接线。

### 3.2 场景和后果采集

固定：

- 8个训练父场景、4个开发父场景。
- 每组一半基础可行场景、一半承运竞争场景。
- 3架无人机、1架直升机。
- 60分钟episode。
- 训练与开发父场景身份及事件种子不同。

场景必须具有真实合法选择。至少一个手工案例能够验证：当前分配会影响其他订单后续交付。

在第8、16、24、32分钟保存pre-action快照，最多48个窗口。源episode由C1推进。

每窗最多8个公开候选：

1. 合法NOOP／维持安排。
2. C1完整动作。
3. 公开信息生成的局部改派，转换为完整合法动作。

按稳定身份去重和截断，记录未保留提案数。这是有限提案集合，不声称枚举全部合法动作。

每个候选：

- 从同一快照恢复。
- 使用相同外生事件安排。
- 执行候选后，由C1继续。
- 推进30分钟或至episode结束。

最多384个分支。无机会窗口、合法false与unknown分别记录。

### 3.3 标签与输入边界

保存：

- 当前运输按时交付。
- 当前巡查按时完成。
- 当前报告及时到达。
- 其他订单新增过期。
- 未满足需求。
- 能耗。
- 改派。
- 全局效用。

保留绝对结果和适用的相对NOOP差值；单位、有效位和unknown原因明确登记。

全局效用使用原环境同一物理窗口内reward累加值，本轮不另造奖励函数。

模型只能读取公共观察、候选动作和已接收报告。内部快照、隐藏需求、未来故障仅用于恢复和生成标签，不能进入模型输入、合法mask或候选筛选。

每条记录绑定：

```text
(parent_id, repeat, window_id)
PublicPrefix摘要
candidate_key与完整环境动作
快照与外生事件身份
分支轨迹摘要
labels / label_valid / unknown_reason
```

标签有效位不作为预测时的输入特征。

### 3.4 世界模型真实训练

固定：

| 项目 | 配置 |
|---|---|
| seed | 8201 |
| epochs | 2 |
| batch size | 8个窗口 |
| 训练窗口 | 最多32 |
| 优化更新 | 最多8次 |

候选随窗口一起进入损失。保留既有默认排序reduction，本轮不同时修改损失归一化。

训练日志记录逐头loss、有效标签数、排序对数、梯度范数和每次更新耗时。归一化统计只来自训练集。

保存最终checkpoint，不根据开发表现挑选epoch。

在新进程中严格恢复，核验模型参数、布局、统计、数据摘要和预测一致性。

开发预测报告包括覆盖率、BCE/Brier、回归误差、排序准确率和全局效用高估。预测差可以继续工程烟测，但必须标明质量不足；合同错误、无有效监督、NaN或恢复不一致则停止。

### 3.5 图 GPPO 真实组合训练

两组：

| 方法 | 图消息传递 | 世界模型辅助critic |
|---|---|---|
| G | 开启 | 关闭 |
| G-WM | 开启 | 开启 |

两组重新初始化，基础actor/critic参数、seed、场景顺序、奖励和PPO超参数一致。

每组2轮，每轮4个训练episode、16次优化更新：

- 合计16个训练episode。
- 合计64次PPO优化更新。
- 两组分别评价4个相同开发父场景，合计8个评价episode。

辅助critic使用五类全局预测：其他订单过期、未满足需求、能耗、改派和全局效用增量。

```text
q_j = softmax(log π(a_j | observation))
z = Σ detach(q_j) × detach(WM(observation, a_j))
V_G-WM = V_base + auxiliary_MLP(z)
```

辅助MLP为5维输入、32维隐藏层、标量输出，最后一层零初始化。

完整动作概率按真实actor及其自回归mask计算。世界模型输出可以缓存，PPO更新时候选聚合概率由当前actor重算。

禁止：

- 直接修改actor logits。
- 使用真实未来标签辅助critic。
- 生成虚构rollout。
- 增加额外actor损失或优化步。
- 更新冻结世界模型。

记录提案集合概率质量，并注明该聚合不是对全部动作的精确期望。

## 4. 托管、资源和故障处理规范

### 4.1 必须使用持久托管

训练不能挂在交互SSH前台，也不能仅依赖`nohup`或`&`。

唯一入口提交一次systemd user service，包含：

```text
Restart=no
KillMode=control-group
CPUAccounting=yes
MemoryAccounting=yes
MemoryMax=4G
TasksMax=64
```

配置固定WorkingDirectory、绝对ExecStart和显式环境变量。服务需具备SSH退出后继续运行的条件；若用户服务无法持久存活，preflight拒绝，不临时换托管方式。

真实worker必须经过：

```text
入口核验
→ systemd
→ supervisor
→ StageServer
→ BudgetLedger
→ worker
```

提交返回后，使用新SSH连接回读同一unit的InvocationID、PID、cgroup和心跳，验证交接成功。

### 4.2 本轮预算

新Request冻结前，先在目标runtime完成有界工程实测。保持以下总体上限：

| 项目 | 上限 |
|---|---:|
| 服务器累计wall | 3,600秒 |
| 服务器累计CPU | 1,800秒 |
| RSS | 4 GiB |
| 工作／导出存储 | 各1 GiB |
| 候选分支 | 384 |
| 世界模型优化更新 | 8 |
| PPO优化更新 | 64 |
| 策略训练／开发评价episode | 16／8 |
| 世界模型forward | 2,048批、16,384候选评估 |
| 传输wall／客户端CPU | 600秒／120秒 |
| 传输量 | 2 GiB |

本轮工程实测、受控验收和真实烟测分别登记，均计入相应累计额度；不得把工程消耗隐去。

若环境确为1分钟一步，源推进、分支、策略训练和评价的环境步总上限为13,680。冻结前必须核验；步长不同则按相同物理时长重新计算并更新Request。

根据已消费额度计算真实作业剩余额度。为结算预留至少120秒wall和90秒CPU：

- worker提前停止发起新调用。
- supervisor保留结算及导出时间。
- systemd运行超时与停止宽限之和不得超过剩余wall额度。
- CPU保护采用累计计量监督；披露采样间隔与可能超调，不称为精确硬CPU限额。

实测显示预计超过上限时，停在准备阶段报告，不自行扩额或缩水实验矩阵。

### 4.3 计量和日志

阶段顺序固定：

```text
input_admission
→ paired_consequence_collection
→ world_model_training_and_restore
→ world_model_prediction_check
→ graph_policy_smoke
→ paired_development_evaluation
→ settlement_and_export
```

阶段名称必须在matrix、Request、driver和StageServer中逐项一致。每次阶段切换须确认成功后再执行。

账本至少计量环境步、候选分支、forward、优化更新、episode、checkpoint读写和输出操作。

输出清单必须包含SQLite、首错、状态、结算和导出清单，预留足够写入额度。禁止失败后通过绕过账本补写来伪造成功结算。

心跳每30秒更新一次，至少包含阶段、已完成调用数、累计CPU/wall、RSS和首错状态。监控通常每60秒只读一次。

### 4.4 首错和断线

- 首错追加保存，不覆盖。
- 不重启、不重提、不自动恢复训练。
- 失败调用、pending和部分checkpoint原样保留。
- 不删除SQLite journal、WAL或未完成记录。
- SSH断开时，只读核验原unit；不得提交第二个服务。
- unit消失、SSH退出码或进程消失均不能单独证明成功。
- 成功必须同时具备worker完成标记、unit退出状态、账本结算和制品核验。

CPU口径分别报告worker、supervisor/cgroup和传输。无法覆盖的systemd user-manager、SSH及退出尾部标记unknown，不宣称完整系统计量。

## 5. 验收、提交门槛与交付

### 5.1 正式烟测前必须通过

在最终冻结源码及目标Linux运行时验证：

- PublicPrefix合法0/1、unknown、缺失和类型篡改。
- pre-action恢复、字段差异在flatten前拒绝。
- 动态候选、候选置换和重复身份拒绝。
- 完整候选动作确实等于环境执行动作。
- 标签复算、隐藏信息读取拒绝。
- checkpoint严格恢复。
- G与G-WM初始actor输出一致。
- 辅助critic收到梯度并更新；世界模型参数不变。
- 完整阶段调度、真实socket握手、成功结算和故意失败保留。
- 与正式运行相同的systemd交接路径。

验收必须绑定最终源码摘要；旧工程包的通过收据不能替代新包验收。

新身份及预算冻结后，再运行部署目录的无授权preflight。已有明确绑定授权就继续执行，不重复索取；缺少项目要求的动态绑定授权时，只在包、预算和验收材料全部就绪后申请一次。

### 5.2 交付内容

必须交付：

1. 发布身份、环境版本、源码及数据摘要。
2. 场景可行性表、候选合同和标签复算表。
3. 世界模型真实训练日志、checkpoint及严格恢复收据。
4. G/G-WM真实模型、训练曲线、梯度与通道使用证据。
5. 8个开发评价episode的逐任务结果和配对表。
6. unit配置、InvocationID、托管回读、账本及资源结算。
7. 独立Luna审核和全部制品哈希。
8. GitHub归档commit及核验结果。

代码、报告和清单归档至：

`https://github.com/Battleplus/2026_10.10_GPPO`

大文件先核验远端存储支持，再决定上传方式；不能虚构已上传模型。认证使用现有安全配置，不使用历史对话中公开过的密钥。

### 5.3 最终报告必须分别回答

- **工程是否跑通：**真实训练、恢复、接线、更新、评价和结算是否完成？
- **预测表现如何：**哪些头有信号，哪些头仍差，unknown有多少？
- **组合表现如何：**开发烟测中的描述性差异是什么？
- **尚不能说明什么：**一个seed和小样本不能证明稳定优势。

只有工程链路与独立审核均通过，才报告“世界模型与图GPPO已在服务器真实跑通”。技术停止时报告最后完成阶段、首错、实际消耗和缺失产物。

本任务书可直接交给GPT‑6 Luna执行对话。当前仍为规划阶段；服务器状态和历史runtime须由执行者重新核验，本轮尚未部署或训练。
