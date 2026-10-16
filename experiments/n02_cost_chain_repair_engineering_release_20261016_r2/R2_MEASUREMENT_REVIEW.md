# r2 实际测量失败独立复核

结论：**PASS（失败事实证据一致）**；这不是成本 bootstrap 通过，r2 仍不能生成 measured receipt。

复核范围为本地 `r2-measurement-evidence` 及候选包的 pending 文件。未远端、未重试、未修改证据或运行新测试。

唯一提交 unit 为 `n02-cost-repair-20261016-r2.service`，InvocationID 为 `4c5e77cb19a249398144e5611aa9d827`。journal 的首错为：`N2 worker failed: ProgrammingError: Cannot operate on a closed database.` systemd 随后记录主进程退出码 1、`Result=exit-code`。launcher 返回 1，`launch_submissions=1`；远端 helper SHA 已核对为候选 helper `3b1fd20c...ae2b54ace`。

本次 worker 已进入 `input_admission`，因此产生了一行失败 ledger 和对应 failed stage/guardian receipt；这些是失败证据，不是成功阶段成本或可结转收据。失败 row 的 `first_error` 是 guardian 观察到的 `guarded pipeline child exited with status 1`，journal 才记录底层 closed-database 首错。没有 receipt-builder/writer 输出，没有 `resource_cost_evidence` 或 measured carry-forward receipt。

同一 unit 的 systemd 终态为 `loaded/failed/failed`、`ExecMainStatus=1`、`CPUUsageNSec=3899507000`，起止单调时间 `263533910221` 与 `263538288259` 微秒。因此该 unit 的 systemd 汇总为 **4.378038 秒 wall、3.899507 秒 CPU**。guardian/ledger 对 input_admission 的阶段分配为 **4.00152651994722 秒 wall、3.1905498989999996 秒 CPU**；`peak_process_group_rss_bytes`/`peak_rss_bytes` 为 **1,092,485,120 bytes**（约 1.017 GiB），来源为 Linux `VmHWM`。这些数值仅描述本次失败 unit/guardian 的实际消耗，不能宣称成功 bootstrap、正式运行或七阶段成本。

pending 证据保持 pending：请求、runtime admission、context 和失败 receipts 都引用 `prior_status_sha256=603dffa8e9998089fa4641d50d4dbf21fe4fc816901112ec5a258d779eee2044`；候选包 `PRIOR_RESOURCE_COST.json` 的当前 SHA-256 也为该值，内容仍是 `measurement.status=pending`、`execution_allowed=false`。由于 writer 未运行，没有发生 pending 替换；这不是一次成功 receipt 提交后的远端复核。

## 关键证据 SHA-256

| 文件 | SHA-256 |
|---|---|
| measurement-execution.json | 9f7a9b181ba15424a0485172e9b899759c9f86d6d248663bb485ddf1b43d9b7 |
| measurement-journal.stdout.txt | fd8caafc2036fe98dbcb1fe3631fce56d1d93e56d9ee5177d7557b87000fa035 |
| measurement-launch.stdout.txt | 0437c4b34128337613cc983da3f0cc2663ab9baec59444274d4b22f1df6cb09d |
| n02.../resource-ledger.jsonl | 69fb78029cf8367f478fc8412b01cbec26687c17510ff17c6c8c813a97e8d67e |
| n02.../systemd-terminal.json | 6225bb20a2d42b04b417dc772f89444a31e166af70c2fbac6545296d4117fd48 |
| n02.../systemd-show.txt | b179dc5ac7cabb7dc9405a3e6f162f19c592aee66b92fe6a8da11acb5d6eeb10 |
| n02.../guardians/01-input_admission.json | 5cf2d2a0d08b703badc30cf7019d02062633c57702eabd02b03ccfddc097d728 |
| n02.../receipts/01-input_admission.json | 482377a1efe5111be85c847640baf587aa29d024a936711a3727544d0de74faf |
| candidate PRIOR_RESOURCE_COST.json | 603dffa8e9998089fa4641d50d4dbf21fe4fc816901112ec5a258d779eee2044 |
