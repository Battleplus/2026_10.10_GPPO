# 参考论文迁移边界

核验日期：2026-10-13（Asia/Shanghai）。

论文：Jin Yu, Ya Zhang, Changyin Sun. Multi-UAV Dynamic Task Assignment Based on Event-Triggered Graph Reinforcement Learning Under Weak Communication. IEEE TASE 22, 2025. DOI: 10.1109/TASE.2025.3593125。
本地原 PDF SHA-256：860f3b0ebdcd95407ce002077af84d8652c8ae6a1e60ec61f124348c252d24e0。
用户最新提供的 WeChat 临时路径未找到；读取的是此前提供的 Desktop/奖学金同名副本。此身份是所读副本身份，不宣称与缺失文件字节相同。

## 已从正文核验的机制

- 摘要与 Section III：UAV/任务异构节点、能力约束边与任务先后依赖边；到达/处理时间作为边属性。
- Section III.B：分别更新平台和任务嵌入，使用 adaptive attention 聚合邻居及边特征。
- Section III.C：动态同步分配状态及任务依赖，减少冲突。
- 事件触发和 heartbeat 面向弱通信及动态任务，不等于世界模型预测。
- 本轮检索未找到 world model 实现或 GitHub 代码地址；不能据此宣称已复现论文，也不能把 Dreamer 作为论文原算法。

## 本轮决定

保留已有灾后巡查/救援运输模拟器、公开报告边界、规则基线和图 GPPO。先用开源 Dreamer 实现新的 RL+WM 比较。图编码组合、事件触发频率和通信实验以后另立消融，避免本轮同时改变多个因素。
论文存在任务先后依赖；已有 N0 审计显示当前民用任务无显式先后依赖边。本轮不为展示图优势临时添加依赖，也不引用论文结论证明当前民用模型有效。

## 公开归档

只发布本说明、书目信息和本地副本摘要。原 PDF 和完整提取文本不加入 GitHub 交付。
