# 近期交付与审查索引

更新：2026-10-03。保留 2026-09-29 起的教材 RAG 与教学闭环证据。报告是对应批次的历史事实；当前状态、后续缺陷和下一动作只看 [CURRENT_STATUS](../CURRENT_STATUS.md)。

| 批次 | 入口 | 用途 |
| --- | --- | --- |
| RAG-QUALITY v1.1，09-29 | [报告](RAG-QUALITY-v1/README.md) | 教材清洗、首答预算、证据、模型与备份恢复 |
| TEACHING-LOOP B0，09-30 | [报告](TEACHING-LOOP-B0/README.md) | 公共契约与基础设施 |
| B1，09-30 | [报告](TEACHING-LOOP-B1/README.md) | 富内容、知识点、名单 |
| B2，10-01 | [报告](TEACHING-LOOP-B2/README.md) | 原卷、题库增量、施测、知识点前端 |
| B2 后续代码审查 | [审查](TEACHING-LOOP-B2-REVIEW-20261001/REVIEW.md) | RV01–RV11，修复记录见 B3 G0 |
| B3，10-01 | [交付](TEACHING-LOOP-B3/REPORT.md) | G0、成绩后端、五步工作区与题库前端 |
| B3 原后续代码审查 | [审查](TEACHING-LOOP-B3-REVIEW-20261001/REVIEW.md) | 原 2 项 P1、8 项 P2 已由 10-02 修复交付复验，证据保留 |
| B3 修复/补齐，10-02 | [交付](TEACHING-LOOP-B3-FIX-20261002/REPORT.md) | r7 与原全量门禁、独立验收及资源保全 |
| B3 修复后代码审查 | [审查](TEACHING-LOOP-B3-FIX-REVIEW-20261002/REVIEW.md) | 8项P2原审查与探针保留；本轮G1结果另记 |
| G1八项原批，10-02 | [历史报告](TEACHING-LOOP-G1-B4-20261002/REPORT.md) | 原批八项行为/check/API已过，当时浏览器/E2E未执行；接续结果另记 |
| G1后续代码复查，10-02 | [审查](TEACHING-LOOP-G1-REVIEW-20261002/REVIEW.md) | 本范围未发现新增可复现产品缺陷；新增边界/窄回归实跑，续验与B4提示词更新；不关闭待验门禁 |
| G1接续与B4，10-02～03 | [G1关闭](TEACHING-LOOP-G1-RESUME-B4-20261002/G1-REPORT.md)、[B4矩阵](TEACHING-LOOP-G1-RESUME-B4-20261002/B4-CLOSE-MATRIX.md) | G1关闭；B4 check1110/第六完整浏览器通过，最新E2E152/1书籍中断、原14聊天未执行；[暂停交接](TEACHING-LOOP-G1-RESUME-B4-20261002/B4-PAUSE-HANDOFF.md)，当前进度只看CURRENT_STATUS |
| B4每日接续，10-03 | [今日批次](TEACHING-LOOP-B4-RESUME-20261003/README.md) | 原153完整单轮153、原14chat14及固定后两UI2通过；独立来源/资源/文档收口通过，CTRL已关闭B4；等待用户下一指示，旧证据保留 |
| B4后续代码审查，10-03 | [审查与证据](TEACHING-LOOP-B4-REVIEW-20261003/REVIEW.md) | 原review当时新增三项P2，4学情/65既有回归通过、新反例失败；后续修复与关闭见G2批，本行不追改原审查事实 |
| G2修复→B5，10-03 | [本批记录](TEACHING-LOOP-G2-B5-20261003/README.md) | G2已关闭；B5修后1256 check/27独立/8浏览器通过，完整153进行中；各首败/候选保持，当前只看CURRENT_STATUS |
| 当前文档整理 | [记录](DOCS-FOCUS-20261001/README.md) | 历史归档、说明修正与保全检查 |

31 个旧 QA 批次已移至 [历史归档](../archive/pre-20260929/qa/)。`RAG-REBUILD-v1` 原路径只保留近期冻结件所需的兼容副本及跳转说明，完整批次已归档。历史报告、探针和冻结清单不随当前说明修订而追改。
