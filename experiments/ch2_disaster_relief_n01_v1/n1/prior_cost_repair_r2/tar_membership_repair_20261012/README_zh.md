# N01 R2 tar 成员校验修复归档

状态：**NOT_READY**。本目录记录本地 tar 校验修复及独立离线审核，不代表服务器部署、预算批准或正式评估通过。

冻结包及清单沿用本仓库既有文件，未复制、覆盖或改写：

- 冻结包：`../n01-prior-cost-repair-r2-20261012.tar.gz`，SHA-256 `36f4fb3b72eba0dcbf82c16a3bfe062901e6d6590cd3271099cdf6941ab3b860`
- tar 清单：`../tar-sha256-manifest.json`，SHA-256 `5c6d25f691075985147a53cf38b7c237f8d31080c3166de071b86b9eb57d7fa8`
- 文件清单：`../source-manifest.json`，SHA-256 `2e0eb1a1fd2eadaecbe5e9192ce492ac8a07d49691a7bc1541253f3e2a8f26e8`

修复允许规范的 `package` 目录根条目，并限制成员在其下；拒绝绝对路径、`.`/`..`/空路径段、反斜杠、重复条目、链接、设备及其他特殊成员、文件父路径冲突。真实冻结 tar 离线校验通过：594 个成员（560 文件、34 目录），560 文件与 source manifest 的路径集合、字节数和 SHA-256 一致。身份及 stage budget 哈希也匹配。结果见 [offline_validation_output.json](offline_validation_output.json)，审核结论见 [independent_review_zh.md](independent_review_zh.md)。

只归档去敏后的校验代码与结果摘要。没有收录原始部署操作脚本、首错完整 transcript、密钥、凭据或凭据哈希。没有再次接入服务器，没有训练、forward 或评价。服务器侧仍需独立验证，因此研究状态保持 `NOT_READY`。

原本地 hash 索引副本及部署脚本哈希笔误说明见 [索引勘误](HASH_INDEX_ERRATUM_zh.md)；修复值见 [归档 hash 索引](hashes.json)。
