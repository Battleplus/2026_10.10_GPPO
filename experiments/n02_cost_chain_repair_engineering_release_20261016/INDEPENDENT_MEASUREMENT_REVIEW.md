# 独立失败证据复核

结论：**PASS（失败事实与资源计量相互一致）**。这不是 bootstrap 通过；成本 bootstrap 仍 **BLOCK**，未生成 measured receipt。

复核范围为本地 `v5-deploy-preflight-evidence` 中的执行摘要、journal、launcher 输出、请求及下载的 measurement root。未远连、未运行新测量、未修改原证据。本报告仅将已经完成的复核归档。

唯一已记录提交为 `n02-cost-repair-20261016-r1.service`，InvocationID 为 `dfcad74b0b304318b4ba11d44741a577`。journal 首个应用错误为 `ModuleNotFoundError: No module named 'numpy'`，systemd 主进程退出码为 2、Result 为 `exit-code`；launcher 返回 1，执行摘要记录 `launch_submissions=1`。

最后到达 worker 导入前置阶段，尚未进入 input_admission。下载的 measurement root 只有 deployment receipt、measurement request、systemd show 和 terminal 四个文件；没有 measurement context、resource ledger、guardian receipt 或 stage receipt。一次性 wrapper 仅在 launcher 返回 0 时调用 writer，本次返回 1，因此 writer 分支未进入；没有 writer 输出或 measured receipt。

同一 unit 的 systemd 起止单调时间为 `261896287608` 与 `261896373945` 微秒，差值为 **0.086337 秒 wall**；CPUUsageNSec 为 `85698000`，即 **0.085698 秒 CPU**。terminal 与 show 一致。这些数字仅属于该失败 unit 的实际主进程/服务计量，不能称为 input_admission 阶段成本、七阶段成本、整个部署/preflight总成本或成功 bootstrap 成本。4 GiB 是配置上限，不是实际 RSS 观测值。

请求记录的 pending SHA-256 为 `603dffa8e9998089fa4641d50d4dbf21fe4fc816901112ec5a258d779eee2044`，本地 package 的 `PRIOR_RESOURCE_COST.json` 哈希仍与之匹配。worker 失败于写 context/调用 guardian 之前，且 writer 未执行，因此未发现本次路径改写 pending 的行为。**没有提供失败后远端 pending 的独立字节或哈希实读证据**；“远端 pending 保持不变”是基于该执行路径的推断，不能表述为失败后远端实读核验。

## 已复核证据 SHA-256

以下哈希由本地证据字节计算；路径相对于 `v5-deploy-preflight-evidence`。

| 文件 | SHA-256 |
|---|---|
| measurement-execution.json | 2518f55a23dda5add958771044963cccbfdab446d5a067af902546c2bea06df6 |
| measurement-journal.txt | 7b26069bd97b18fa33387a23be47ac5f73fc32f2c574afa47feb806580a3568f |
| measurement-launch.stdout.txt | e72620a760c4b37d80806a0759d3b0cf11dd6610b1f613d59ec3ccebff9c72e4 |
| measurement-launch.stderr.txt | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| measurement-submission.lock | 79ab23948dfe524e130f4fe1118941396d88111dc43abd1387686311b2c3d297 |
| authorized_measurement_once.py | 225926ecb7ad307ebe723bb24f3be0adb56a18a459761036b5af16011ec387a6 |
| n02-cost-measurement-20261016-r1/measurement-request.json | 4a42558c47b1bfd5ad2cf995350cc89f5d2ad38dcdff007661c0fe177c2c7980 |
| n02-cost-measurement-20261016-r1/systemd-terminal.json | b25d0d001aeed4b44b94de3d17ce8c21d107c9138f16ed8dca4b1a7633673959 |
| n02-cost-measurement-20261016-r1/systemd-show.txt | 93b6f5d8f52a82ee7053ff371ce5c51739cc1edadf802045bbde867f3d9e1ccc |
| n02-cost-measurement-20261016-r1/deployment_receipt.json | 36ffb6c614a82979cc4757a44e32e827263f85d5fbd131691d44387968446b5b |
