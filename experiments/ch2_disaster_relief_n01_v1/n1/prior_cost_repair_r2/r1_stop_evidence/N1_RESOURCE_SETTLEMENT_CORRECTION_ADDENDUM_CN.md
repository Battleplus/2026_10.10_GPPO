# N1 正式停止资源结算口径补充（2026-10-12）

本补充更正资源字段解释，不修改原停止报告，也不改变失败结论。唯一systemd InvocationID为`7b65d35b5b4c464b810ecac918978166`，失败发生于准入前，首错为部署目录缺少`/home/user1/w1-pilot/packages/received`；checkpoint/model加载0、正式轨迹0。

- 最终CPU结算采用`0.1347`秒。systemd `CPUUsageNSec=123739000`（0.123739秒）与cgroup `cpu.stat usage_usec=127108`（0.127108秒）是不同采样时点/口径的观测，作为原始证据保留，不替代最终结算数值。
- `memory.peak=12222464`字节是cgroup内存峰值，不是进程RSS。原报告中的RSS表述应以此补充为准。
- `ExecMain`从启动到退出的wall为`0.227406`秒；该区间不是包含systemd stop-post结算在内的完整生命周期wall。
- 所有读数仅覆盖失败准入生命周期，不可累计成评价、训练或完整作业的用量/结果。

原始依据：formal-run目录中的`systemd-settlement.json`与`journal.txt`。本补充仅澄清字段和采样口径；原件保持原样。
