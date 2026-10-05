# B4-F-QA-R07 v1 — 准备完成，待重冻

唯一修改 `seed.py`，完整 SHA **`4f50256da7bc41bd7c09b6be3364969eae8f7a66999fd811b19ee4509970d044`**，全部可执行源已停写。**新 seed/browser 尚未执行**，等待 CTRL/P 审核与新冻结、新样本；不能把准备结果标为通过。

确认前通过既有 `PaperRepository.insert_blocks_in` 保存各固定题的完整 stem/source/共同材料/options/答案/解析块：完整块值深拷贝、修订/题目命名空间行 ID、递增 ordinal、disposition=item 和 item_id。locator 保留真实受管原 DOCX asset/hash 及题号/section/blockIndex；题目 source_locator 记录对应持久化 sourceBlockIds。图片仍原受管键/字节，产品图片授权规则不改。

初始 seed 增加标准 main TestClient 真实图片 GET 的 status200、exact bytes==PNG、SHA 和 mediaType 四项强校验；未来新 seed 真执行成功才写 initialAssetHTTP metadata 的实际字段。未扩大初种子业务事实，初始 B4 五类表仍必须全0，原真实 T30/T60调用与全部断言保留。

原始 byte 副本 `seed.r5-before.txt` SHA `c29c9fc2a40903a8fa43ef19dc5984263224c5363d8c83e3c98b49852ea03e29`；`real-browser.spec.r5-before.txt` SHA `cb425d1ca424f4e59a10f9362eaa590b8d64172a7f52cf574a434fb2ff461dae`。精确 Node24 求值证明第181行返回练习正则正确匹配实际正常 URL，**spec原字节完全未改**，全部12图片/三下载/回流原断言保持。

仅静态 AST/SHA解析 exit0：原2 assert/115 call节点全文（忽略源码行号）全部保留，新追加4 assert；877产品、其它35可执行QA、5契约零差异，仅seed一项变化。完整精确 diff 和原断言/call保留证明见 [QA-R07-static.json](QA-R07-static.json)。这个检查不导入 main、不执行seed、无服务/浏览器。

旧 `ssyc3aiq` seed/data与首轮失败原件均保留，未补写。首轮真实结果与资源收尾见 [RESULT-browser-real-first.md](RESULT-browser-real-first.md)。

