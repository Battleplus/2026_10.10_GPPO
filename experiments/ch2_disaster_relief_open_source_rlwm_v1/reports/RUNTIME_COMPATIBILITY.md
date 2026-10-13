# Runtime Compatibility Record

Recorded 2026-10-13. This is a local engineering compatibility environment, not a production runtime qualification.

The project compatibility environment uses Python 3.11.5 and the read-only system PyTorch 2.5.0+cpu installation, with isolated NumPy 1.26.0, Gymnasium 1.2.0, TensorDict 0.9.1, TorchRL 0.9.2, and Hydra 1.3.2. TorchRL emitted a C++ extension warning. Two earlier PyTorch 2.8 download attempts failed and their evidence was retained. A separate isolated Python 3.11.15 runtime is now installed, but the target dependency stack has not completed qualification.

The adapter/replay/registry subset has 18 reported passing tests. The latest full compatibility suite has 25 tests: 22 passed, 2 failed, and 1 errored. The unresolved failures cover action/dt/mask alignment and terminal-versus-truncated lambda returns; the error is an upstream distribution `.sample()` `NotImplemented`. See `all-tests-compat-20261013.log`. The Dreamer integration reviewer is repairing these cases; the full suite is not passing yet.

The target runtime contract is Python `>=3.11,<3.12`, upstream PyTorch 2.8.0, TorchRL 0.9.2, and TensorDict 0.9.1. Python 3.11.16 is not the only acceptable patch release. The exact candidate runtime has not completed qualification or target Linux preflight. `SummaryWriter` may indirectly import TensorFlow from system-site packages; its RSS impact must be measured in the engineering resource pilot. Server SSH authentication was rejected, so target Linux checks and resource measurements were not run. No formal authorization, token, attempt, training, or policy evaluation was created.

This test snapshot is bounded by `all-tests-compat-20261013.log`; later revision logs supersede it. Machine-readable record: [`RUNTIME_COMPATIBILITY.json`](RUNTIME_COMPATIBILITY.json).
# 最终兼容性节点补记（2026-10-14）

最终回归26/26通过，实际日志 `all-tests-compat-r3-20261014.log`。民用与上游小模型烟测分别见 `civilian-dreamer-smoke-20261014-r4-fp32/civilian-dreamer-smoke-receipt.json` 与 `../upstream_smoke/results-r5-fp32/smoke-receipt.json`，各完成3次工程更新及相应范围恢复。两者明确使用CPU FP32 overlay，非精确上游FP16复现；Torch2.8/目标Linux尚未验证，RSS为null。本文件后续原有测试计数属于早期失败节点历史，不能覆盖最终独立收据，也不能将成功烟测扩展成研究效果结论。
