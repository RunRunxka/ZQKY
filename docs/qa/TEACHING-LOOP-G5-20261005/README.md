# G5 两项修复与独立技术验收（2026-10-05）

唯一当前状态见[CURRENT_STATUS](../../CURRENT_STATUS.md)。本批授权只到G5：连续操作cleanup结果绑定与空人审CSV/MD严格校验，完成必要工程/浏览器/独立验收及当前文档后停止。

开工原B7A-r2源码959/执行QA3496/契约33/构建970逐SHA相符，main@b7f99ab及构建VeOLFBYrp-8v24Yjm-HFi保持；当前历史QA22207和原273材料只读保留。已有审查、G4/B7-A限定收据和新文档增量保留，不倒改历史。

- [任务卡与单一写入范围](TASK-CARDS-v1.md)
- [开工原字节、候选与历史清单](OPENING-v1.json)
- [本次代码审查](../TEACHING-LOOP-G4-B7A-REVIEW-20261005/REVIEW.md)
- [连续操作原正确行为首败](../TEACHING-LOOP-G4-B7A-REVIEW-20261005/recovery/stale-ack-first.log)
- [工具两绕过原件与对照](../TEACHING-LOOP-G4-B7A-REVIEW-20261005/tools/RESULT.json)

本批两项 P2 已独立通过并限定技术关闭，关闭状态 `G5_CLOSED_LIMITED_INDEPENDENT_TECHNICAL`。授权只到本次修复批 G5，不等于原 v2 整体交付 G5，也不关闭原 B6/B7 整体。

- [总控报告与验收边界](REPORT-v1.md)
- [关闭矩阵](G5-CLOSE-MATRIX-v1.md)／[总关闭收据](G5-CLOSE-v1.json)
- [当前结果清理问题关闭](R-G4-RECOVERY-01-CLOSE-v1.json)／[空人审严格校验问题关闭](R-B7A-QUALITY-01-CLOSE-v1.json)
- [独立 V00 签收](v00/RESULT-v1.md)／[独立 STOP](v00/ACCEPTANCE-STOP-v1.json)
- [最终稳定候选 built-r2](CANDIDATE-G5-built-r2.json)／[各实际候选同源转签](GATE-TRANSFER-v1.json)
- [首败与完整复验](FIRST-FAILURES-v1.md)
- [自有资源释放](RESOURCES-final-v1.json)／[现有 E2E 临时后端夹具关闭](RESOURCES-FIXTURE-CLOSURE-v1.json)
- [历史同源引用与缺件](HISTORICAL-REFERENCE-v1.json)
- [独立当前文档审查目录](doc-audit/)／[审查计划](doc-audit/PLAN-v1.md)
- [仅供下一批授权交接](B7B-HANDOFF-v1.md)

实际新完整 check：126 文件、1380 单测、typecheck、lint 0 警告及 build 通过；独立组件新完整轮 152/152；独立 CLI 102 次为 5 正常及 97 正确硬拒、四 guard 尝试 0；新实际页面 8/8、现行 29 spec 完整 E2E 174/174，含原 21 UI、R14 和既有隔离真实 FastAPI 夹具。各轮均无 retry/skip/flaky/reporterErrors，不将历史 API 的 1 个规模 skip 当本批新 skip。

新构建 `2Gg_WxijBmV9IGIkY1vmG`，实际代理 8001，next-env 精确恢复开工字节。built-r2：source960／执行QA3660／contract33／build970。新完整 152 实际跑 r2；check 实际跑 prebuild-r2，102／8／174 实际跑 built-r1。r1→r2 产品、契约及整构建精确相同，仅两份非其执行闭包的 QA 差异显式登记；原实际身份保留，不冒称这些门禁在 r2 重跑。文件数与测试数分列。

六份当前权威文档仅增加 G5 状态块，全部开工内容（含原 v2 任务及伪代码、旧状态与审查）保持原字节。独立文档收据及后加报告/权威状态属于单列后验增量，由最终批次清单逐 SHA 绑定，不声称产品候选覆盖这些后加文档。全部 TEMP/首败保留；自有原实例、捕获后代和日志闭合，未操作未知用户进程。当前批次到此收口并 STOP，后续等待用户新的明确指示。

B7-B/live、教师评价、Word/WPS、当前物理SQLite/Blob与旧恢复缺件、正式Qdrant/迁移/压力各自待输入/待验/not_run；旧被拒额外HTTP身份probe不重试。RAG-REL/R14/CV01～03/OBS-LP-MODE-LABEL及原观察保持。无真实凭证/草稿访问、原材料再生成、正式数据/6333或Git动作。
