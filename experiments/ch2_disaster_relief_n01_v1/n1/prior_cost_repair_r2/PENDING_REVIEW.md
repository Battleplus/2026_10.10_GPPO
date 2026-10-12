# 发布前待审核

- [x] Clean clone状态确认：main分支、原有工作树干净。
- [x] r1停止证据及独立审核原字节纳入。
- [x] r2 package、六个checkpoint、输入/检查点索引、tar和hash清单纳入。
- [x] 包内stage budget为proposed；包外budget request为NOT_APPROVED；未创建新提交授权。
- [x] `.gitattributes`为冻结package和原始证据设置`-text`，避免autocrlf改写字节。
- [ ] 修复独立审核初审通过；预算契约变更后待复核；完整dry-run反序列化checkpoint 12次，无forward/admit/训练/正式评价。
- [ ] 发布内容审阅通过。
- [ ] 明确授权后才允许push。

当前草稿不应发布或push。
