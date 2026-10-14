# N2 阶段A工程进度归档（2026-10-14）

状态：**阶段A未通过；正式研究未启动。** 本归档保留一次本地真实学习证据与独立审核，以及尚未远端验证的托管controller实现。

- 本地工程实际完成12次WM更新、48次真实民用PPO更新；7个t8候选包含NOOP；1384环境步。
- R6独立复核确认连续/恢复的PPO模型与优化器逐张量一致、冻结WM不被PPO修改、raw分支reward/energy和NOOP参照一致。
- 首次运行ZIP包含原始分支、rollout、checkpoint、冻结源码、预算和R5限定准入；SHA256 `459C1403F1ACC995138E48C739B147C5090610ECCA93832385D29B89E3E4E912`。
- R6压缩审核包SHA256 `E05500E032D615FF4C5C66278E17ABD5791107CEE5C0F7E2C40A1B42DCDAD3DC`。
- controller最终18项独立本地测试通过，R7具体修复闭合；尚无目标Linux/systemd/cgroup/StageServer/BudgetLedger托管运行证据。配置模板为NOT_APPROVED。
- 计量限制、未知资源尾部、间接源码身份缺口及未完成head/归一化协议均保留在R6/更正节点包。新revision正在开发，未放入本次‘已核验学习’身份。

此处无正式56/14/24后果数据、三seed预测门、G/G+WM组合评价或确认结论。历史已消费授权不复用。旧错误节点稿留在本地修订轨迹；本归档采用R1更正稿。

仓库现有规范排除直接模型文件。本归档依既有压缩证据包惯例将模型/checkpoint保存在FIRST_LOCAL_RUN.zip，不提交私有凭据或原始远端transport。
