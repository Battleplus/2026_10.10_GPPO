# N1 只读取证脚本独立审核

审核日期：2026-10-13（Asia/Shanghai）  
对象：`research-executions/n01_formal_readonly_capture_20261013/` 的最终冻结候选。  
边界：本审核未执行 SSH，也未访问目标机；只核对脚本、哈希清单和离线测试。

## 结论

**通过，可由 executor 在用户已授权范围内执行一次只读取证连接。** 准入只对应以下最终冻结文件哈希：

- `capture_n01_readonly_once.py`: `1E24067CF69A2D59BDFB765031B679698CDED0C90BE54B66F9925A4B146C0FCD`
- `test_capture_n01_readonly_once.py`: `D082C7391E68CD749EE017FE069D597C501EC59B0FF33E31F572F285846DE942`

两者与同目录 `SHA256SUMS.txt` 一致。我独立运行 `python -B -m unittest -v test_capture_n01_readonly_once.py`，7 项离线测试全部通过。测试使用 mock 子进程，不建立网络连接。

## 边界核验

脚本将 identity、unit、run、diagnostics 和预期 InvocationID 固定为本次 R2 formal-repair-v1 值。它启动一个 `ssh` 子进程，设置 `ConnectionAttempts=1`，禁用连接复用、代理跳转和代理命令；没有循环、自动重连或重提路径。

远端内联 Python 只执行固定 unit 的 `systemctl show`、按该 InvocationID 过滤的 `journalctl`，并读取固定 run/diagnostics 目录。目录组件通过 `dir_fd` 与 `O_NOFOLLOW` 打开，项目通过 `follow_symlinks=False` 检查；symlink 不跟随。远端没有执行研究包代码，也没有服务启动/停止/重启、审批替换、锁操作或文件写入。`python3 -B -` 避免生成 Python bytecode。

若 InvocationID 不匹配或 unit 仍 active，脚本不扫描 run/diagnostics，并记录不稳定状态。空目录、缺少固定诊断收据、读取错误、SSH 非零退出或本地管道错误会使本地 `capture_status` 为 partial/unknown 并保留原因。固定诊断收据检查为 `final-status.txt`、`journal.txt`、`run-files.tsv`、`settlement.json`。

SSH stdout/stderr 以二进制管道直接写入本地 `stdout.raw`/`stderr.raw`，随后计算字节数与 SHA-256；嵌入的远端文件也逐块保留并校验长度及哈希。审批只适用于上述脚本哈希和本次单一只读取证，不构成正式结果认可。

## 执行后限制

本次准入不等于结果审核通过。executor 取回后，应以本地原始 stdout/stderr、解码清单及所有回传文件哈希为证据；对缺失文件、非零状态、ID 不匹配或 `capture_status` partial/unknown 保留原状态。研究结果审核仍需单独判断首错、已完成轨迹/阶段、模型加载、资源和导出；不完整记录不得补作成功结论。
