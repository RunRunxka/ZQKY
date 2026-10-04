# B5-REVIEW v2 结果卡（静态，已停写）

- 任务/负责人：B5-REVIEW v2 / `/root/b5_review`；未参与产品实现。
- 可写范围：仅本批 `b5-review/` 新 v2 报告、manifest 与源码快照。v1 原件未改。
- 起点：CTRL 提供 main@6aeb57280f6a7e0d7391cad4d150745479ea58ec；BE v2 停写 45/45、AI v2 停写 144/144、FE v1 停写 50/50 为作者证据。
- 结论：**静态发现阻塞，不能关闭 B5**。R05/P1 实际报告读取 `limit=1000` 与真实 API `max200` 冲突；R04/P2 等待保存及 unknown 原包重试可把旧生成载荷绑定新来源签名；R03/P2 补充确认合法 analysis 参数重挂（CTRL 已窄修）和跨文档残留历史复制 intent（FE v2 已授权修）。具体触发、预期/实际、行号、缺陷 SHA、最小独立反例见 STATIC-REVIEW-v2.md。
- R01/R02：AI v2 路径感知 privacy 与 CTRL literal-preserving schema gate 未再确认具体静态缺陷；没有运行三协议 wire、SQLite/gate/restore，不以作者 144/144 或 10/10 替代独立复验。
- 其他观察：教师要求输入前缺少冻结契约明确要求的个人信息及适用边界说明，已报 CTRL，作为文字缺口记录。
- 检查状态：F30 server/local session、late ACK、unknown/recovery、StrictMode、nav hasProvider 一次决策、root/Gateway lifecycle、历史复制/undo/save、export snapshot 均只读静态追踪。产品/服务/测试/完整门禁/独立 oracle 全部 **未执行**（审查卡禁止，且 FE v2 仍在授权修复）。正式数据与凭证、Git、TCP 未访问/操作。
- 源绑定：before 98 + additional 7（重叠 1）=104 件，起点作者/冻结源漂移 0；after 104 件，仅 ROOT page 与 FE 授权修复中的 SourcePanel/ProposalPanel 3 件变化，分别登记，未当一致性失败。冻结 33 件、v1 报告及结果前后无漂移。停写 after 是审查终点采样，后续作者合法继续修改不属于此卡的稳定候选。
- 后续：等待新的 FE 停写清单/CTRL 稳定 candidate，再逐项独立复核 R01–R05；真实 Next/完整 API/browser/wire/export/恢复等仍由 V00 独立 oracle 和 CTRL 整批门禁确认。

证据 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| STATIC-REVIEW-v2.md | d999226b8d8eb398052faf1b5c50e673907687633174b114c23f98c7de1903c8 |
| SOURCE-BEFORE-v2.json | 9cf58a18a40f531e9aa61787ce5c82ef57f46d2ef6565e983548c4959cae5d11 |
| SOURCE-ADDITIONAL-BEFORE-v2.json | 34c518aa3bff2e03dca54e8dd003558de84800d3cba7516fe075fc25c817d69d |
| SOURCE-AFTER-v2.json | cfa7a62048ac07862b3a3d86bb620411a9de77ef076967c5d4f1281eae891622 |
| SOURCE-SNAPSHOTS-v2/MANIFEST-v2.json | 69c33d6eb6dd9b2b1dc439a3b26288db823a6b7e97c2f6a671eafe6de4701b28 |
| ctrl/B5-CONTRACT-FROZEN-v1.json | 8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db |

本卡写入后独立审查者停止写入；后续复验使用新版本，不追改本卡或本次发现原件。
