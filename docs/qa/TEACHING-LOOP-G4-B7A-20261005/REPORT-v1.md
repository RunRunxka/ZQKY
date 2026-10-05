# G4 限定技术关闭与 B7-A 离线交付 v1

ROOT，2026-10-05。本批按用户“只完成离线工具与验收准备”收口：G4四项已独立技术关闭，随后B7-A工具与材料完成并独立通过。真实模型、教师教学判断和原生Word/WPS待验，原B6/B7整体未关闭。没有Git写入、切分支、推送、部署、正式数据操作或自动下一批。

G4恢复入口重新持久化可信当前包后才恢复相应操作；保留11字段、secondary、上下文、来源、原操作身份及unknown/CAS语义，坏缓存仍拒绝覆盖。显式清除教材使旧在途核验失效，新的核验意图可正常采用。质量汇总按冻结预期集合失败闭合，live范围预检严格类型、秘密字段、预算形状和案例身份，只给人工范围审查状态。四收据与实际正确行为见[G4关闭矩阵](G4-CLOSE-MATRIX-v1.md)和[关闭收据](G4-CLOSE-v1.json)。

| 本批实际验证 | 最终完整单轮 |
| --- | --- |
| 工程check | 125文件1354单测、typecheck、lint零警告、build通过 |
| G4独立组件 / 独立工具反证 | 38 / 59预期结果通过 |
| 新真实故障 / 原真实来源门禁 | 11 / 14通过 |
| 当前完整E2E | 29spec174通过；含保留的21个外部UI用例 |
| B7新离线工具作者 / 独立CLI | 21 / 46通过；独立为2正常、44正确硬拒 |

以上分开计数，无拼轮、skip/retry/flaky/reporterErrors。B7工具仅新增独立Python入口、专属测试/README；已验G4前端、后端、旧三工具、契约和构建全等，适用工程/浏览器门禁精确引用，没有声称B7再次跑全API/恢复/聊天或重复导出。后端410、chat关联186、导出核心11、旧材料1056的精确历史绑定与未执行边界见[来源核对v2](v00/references/SOURCE-REFERENCE-v2.md)；旧export/styles43中的12项漂移不转移整体排版证明。

[B7离线验收收据](B7A-OFFLINE-ACCEPT-v1.json)SHA `31af4a23ab55c6f5822fa30327a1ea50871ed50ca94f2207285e992751d7c6f6`，[独立验收](v00/b7a/RESULT-v1.md)绑定r2候选与release-v2。完整46工具CLI只执行一轮；外层PID4488/exit0，外层elapsed未捕获，各46子命令均有实际PID/时间/exit/耗时/原log，合计6950.558ms仅为子耗时。网络、app导入、.env读取、数据库打开四guard尝试0，273材料引用及空字段另经独立核对。

[材料与人工验收入口](B7A-OFFLINE-MATERIALS-v1.md)提供原15例/15逐例DOCX、四代表DOCX/四PDF/13旧页、八维rubric、原15行空人审表及新四行native起始空表的SHA和直接文件链接。材料没有重复生成；13页历史PDF不当原生页数，教师理由与评分、应用版本和实际原生页码均待人工填写。[需求矩阵](B7A-REQUIREMENTS-MATRIX-v1.md)先于工具实施建立，原件保持。

最终候选r2 SHA `3a73dd766c2e23e57e5726e157f7ef5ef1efe9a7c5f815429b3774ca24568297`，源码959/执行QA3496/契约33/build970/历史QA19169逐项零漂移。构建`VeOLFBYrp-8v24Yjm-HFi`，实际代理8001，next-env原字节恢复，main@b7f99ab保持。五份权威文档仅增加本批状态，原v2计划书87340字节与任务/伪代码完整，Guide/API/ROUTES未改。见[完整性后验](INTEGRITY-B7A-preclose-v1.json)。文档后续最终审查单列delta，不改原候选/首败。

[资源关闭收据](RESOURCES-BATCH-v1.json)逐自有PID/创建时间核四服务原实例已退出，E2E后代与所有工具子进程/日志关闭，5174/8001监听0；用户/未知进程未停止，全部TEMP保留。[G4首败](FIRST-FAILURES-v1.md)、[B7首败矩阵](FIRST-FAILURES-B7A-v1.md)及[封印追加](FIRST-FAILURES-B7A-v2-DELTA.md)保持原件。

live=not_run_user_offline_scope、teacher_review_pending、Word/WPS=not_run；模型执行器/预算执行保证不在本批。旧物理SQLite/Blob及恢复证明缺失、旧VISUAL-REVIEW唯一缺件单列not_run，完整canonical冻结来源绑定不等于当前物理源通过。RAG-REL、R14、CV01～03、OBS-LP-MODE-LABEL及原环境观察保持OPEN；正式Qdrant/迁移、额外压力、6333/正式数据和发布部署未执行。

本批完成后STOP。后续仅按教师反馈或用户新的明确范围接续，不由合法预检、既有连接或未回复推定真实调用授权。
