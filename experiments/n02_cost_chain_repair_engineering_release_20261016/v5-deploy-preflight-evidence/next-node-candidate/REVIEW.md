# 下一节点单点修复复核：PASS

本地候选与已部署 helper 的副本仅有一个连续改动：launcher 将 `Path(driver.TARGET_PYTHON_PATH).resolve(strict=True)` 改为保留 `Path(driver.TARGET_PYTHON_PATH)`，并以 `is_file()` 检查可用性。其他代码一致。

该修复对应本次首错：已部署 launcher 将虚拟环境解释器符号链接解析成底层 CPython 路径，再交给 systemd 执行；journal 显示底层解释器启动并因缺少 numpy 退出。保留配置的虚拟环境解释器路径可避免这次路径替换。worker 内对解释器 resolved identity 的既有核对保留。

PASS 仅针对改动范围和首错对应关系，不表示下一次目标测量成功。候选仅留在本地，未改已部署包；未运行服务器、systemd、目标模型或训练。

| 文件 | SHA-256 |
|---|---|
| 已部署 helper 的本地副本 `../../engineering_cost_bootstrap.py` | e78573e76ba9130a6bd709e929ca77bddb4a78d46c51fea46dbf2823c3722154 |
| 下一节点候选 `engineering_cost_bootstrap.py` | 3b1fd20c73deabfa8436229b5f070232421e5ff38dbb29561147442ae2b54ace |

本审核可供下一次独立工程测量申请引用，不提供执行授权，不复用 r1 unit/InvocationID。
