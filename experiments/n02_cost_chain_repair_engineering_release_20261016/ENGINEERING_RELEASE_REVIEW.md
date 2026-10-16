# 工程组装定向复核记录

复核范围：`n02_cost_chain_repair_engineering_release_20261016` 的静态身份、46 文件 package、部署 helper、deployment identity 与未来 receipt 字段。只读检查；未 SSH、未运行 systemd、未执行 target preflight、未创建 receipt/authorization/token/attempt。

## 通过项

- `V4_RELEASE_MANIFEST.json` 声明 46 个 package 文件，实际 package 文件数 46，缺失/多余均为 0。
- `engineering-file-hashes.json` 的 12 个条目全部匹配当前文件；manifest/hash bundle/request/attempt 的交叉字段一致。
- `authorized=false`、`request_frozen=false`、`attempt_started=false`、`target_runtime_preflight=not_run`，未发现工程副本中的运行证据、缓存或正式执行状态。
- `deployment_identity.py` 使用 `ppo_trainer.source_identity()` 的排序紧凑 JSON SHA-256；ZIP 成员排序、去重、拒绝符号链接并原子落盘。helper 只在未来 preflight 返回成功后写本地及远端 deployment receipt。
- `/2` receipt builder 所需的 `source_identity_sha256` 与 `archive_sha256` 字段由 deployment receipt 提供，未来测量前不会伪造。

## 初次阻塞（已修复）

`deploy_preflight_once.py:75-76` 构建了 `deployment-package.zip` 并把其 SHA-256 写入 receipt，但后续 `:96-103` 通过 SFTP 将 package 文件和 metadata 逐个上传；ZIP 本身从未上传、解包或在远端校验。因此 receipt 的 `archive_sha256` 目前不能如实称为“实际部署 archive 的 hash”，后续 `/2` builder 会把这个未部署的 ZIP hash 当成部署身份，形成部署/收据绑定缺口。

最小修复任选其一并同步文档：

1. 将该 ZIP 作为实际部署载荷上传到唯一 staging 路径，在远端解包到唯一 publish 路径，校验 ZIP SHA-256、成员集合及 manifest 后再运行 preflight；receipt 的 `archive_sha256` 继续引用该已上传 archive；或
2. 保持逐文件上传，但将 archive 改为对**同一实际上传文件集的确定性 bundle**，在上传后对每个远端文件做字节/哈希核验，并把字段和文档改名为 upload-bundle hash，避免宣称 archive 已部署。若继续使用现有 `archive_sha256` 字段，必须证明 ZIP 本身参与部署。

此外，archive 创建和逐文件上传之间没有快照；若选择方案 2，应从同一冻结字节快照生成 bundle 与上传，避免本地文件在两步之间变化造成 hash 与部署内容不一致。

## 当前产物哈希

| 文件 | SHA-256 |
|---|---|
| engineering_cost_bootstrap.py | e78573e76ba9130a6bd709e929ca77bddb4a78d46c51fea46dbf2823c3722154 |
| build_prior_resource_cost.py | 60927aef0ae26e953f93eca15726259b4096c5cac1067dcd344490c1f100d91e |
| deployment_identity.py | 079e99c5eba857191d7e1dc0b4d8c606e4e7a2ab951ef0903c7e4c06f4ce4cf8 |
| deploy_preflight_once.py | aea03f5dbf9dcd6f3e68828f6ca18b71778d873190d22ada19d63141c0d81d35 |
| prepare_static_release.py | 0390749a6b2f00995f7ed0a41dd3a6d4e26b32d6e264e55368d4ff44f773ef10 |
| V4_RELEASE_MANIFEST.json | d505881675d9146d2fc5b909fb55543ce4aca7e5cc6642d6a63fe1a575a23197 |
| V4_HASH_BUNDLE.json | 5cba6f801db89bc59cd933e11031f85cd1fdd55055a21660fe56a33f7d6c7bd5 |
| V4_STATIC_REQUEST_IDENTITY.json | a1c27d2f0e1ec871e76be5d34a0c8d1017835d8d88305f9ceff9f93a0a7af2a4 |
| V4_STATIC_ATTEMPT_IDENTITY.json | 3370cedc5b54722ba04e1d02ea97e58ad0240474586040bdf3f7d55a5a883d75 |
| engineering-file-hashes.json | 6a8d067241638bff29a01998d33331077da8d596197098d83b241aa6122e671c |

## 最终定向复核：PASS（工程入口准备）

后续修复已将冻结的 ZIP 字节通过 SFTP 上传至独立 staging 对象；远端 verifier 在发布前重算并比对 SHA-256、检查 package manifest 和完整文件集合，成功后删除 staging ZIP 并原子发布。错误 SHA 会在发布前拒绝。只有远端 archive 校验、逐文件校验和目标 `driver.py --preflight` 全部成功后才生成并同步 deployment receipt。因此原 archive/实际载荷绑定阻塞已解除。

静态身份、46/46 package manifest、engineering inventory 12/12 哈希继续匹配。request/attempt 仍为 `authorized=false`、`request_frozen=false`、`attempt_started=false`、`target_runtime_preflight=not_run`。本次复核未 SSH、未运行 systemd、未执行远端 preflight、未生成 receipt/授权/token/attempt；本地仅复核静态路径与已报告的同字节 ZIP/错误 SHA 模拟结果。

最终结论为 **PASS**，范围仅为新工程部署与成本测量入口准备，不代表已部署、已实测或正式研究就绪。

### 最终关键文件 SHA-256

| 文件 | SHA-256 |
|---|---|
| engineering_cost_bootstrap.py | e78573e76ba9130a6bd709e929ca77bddb4a78d46c51fea46dbf2823c3722154 |
| build_prior_resource_cost.py | 60927aef0ae26e953f93eca15726259b4096c5cac1067dcd344490c1f100d91e |
| deployment_identity.py | 079e99c5eba857191d7e1dc0b4d8c606e4e7a2ab951ef0903c7e4c06f4ce4cf8 |
| deploy_preflight_once.py | 2320658ba97a3ee92e6600a5ad44cbbc275d8df294f5d79a2a0753483299a084 |
| prepare_static_release.py | 0390749a6b2f00995f7ed0a41dd3a6d4e26b32d6e264e55368d4ff44f773ef10 |
| V4_RELEASE_MANIFEST.json | d505881675d9146d2fc5b909fb55543ce4aca7e5cc6642d6a63fe1a575a23197 |
| V4_HASH_BUNDLE.json | 5cba6f801db89bc59cd933e11031f85cd1fdd55055a21660fe56a33f7d6c7bd5 |
| V4_STATIC_REQUEST_IDENTITY.json | a1c27d2f0e1ec871e76be5d34a0c8d1017835d8d88305f9ceff9f93a0a7af2a4 |
| V4_STATIC_ATTEMPT_IDENTITY.json | 3370cedc5b54722ba04e1d02ea97e58ad0240474586040bdf3f7d55a5a883d75 |
| engineering-file-hashes.json | 16afe6a98229b2573a58bdddd69f2c3fa3c7ddf420a5e391c346f20af2c7df83 |

This review file is independent and excluded from the engineering inventory to avoid a self-hash cycle.
