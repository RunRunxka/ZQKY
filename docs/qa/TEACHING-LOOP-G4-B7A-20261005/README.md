# G4 → B7-A 离线批次（2026-10-05）

唯一当前进度见 [CURRENT_STATUS](../../CURRENT_STATUS.md)。本目录保存本批任务、候选、首次失败、实际单轮与独立签核，旧 QA 原件不改。

用户已明确本批只完成离线工具与验收准备。先修复并独立关闭 G4 的 B6F-R01/R02 与 B6Q-R01/R02，再接入 B7-A 离线准备；真实模型不运行，真人教师评价与 Word/WPS 原生排版待验。原 B6/B7 整体及 RAG-REL 不自动关闭。

- [任务卡](TASK-CARDS-v1.md)
- [开工原字节与归因](OPENING-v1.json)
- [旧四项审查](../TEACHING-LOOP-B6-REVIEW-20261004/REVIEW.md)
- [旧限定 B6 收口矩阵](../TEACHING-LOOP-G3-B6-20261004/B6-CLOSE-MATRIX-v1.md)
- [外部 UI 统一原验收](../UI-UNIFY-20261004/REPORT.md)

开工实际 main@b7f99ab，外部提交是旧6cb6a40的直接子提交；现有 UI/GSAP、原成果及新增21个 UI E2E 均保留。开工构建与 UI 旧验收构建不同，不能推定它已通过门禁；本批产品修改后必须新构建。适用后端/导出/恢复/chat 使用精确字节绑定的旧证据，未新跑项明确标注，不机械重复无关全量。

2026-10-05 13:39，G4 已独立限定技术关闭：[四项关闭矩阵](G4-CLOSE-MATRIX-v1.md)、[汇总与四收据](G4-CLOSE-v1.json)、[新组件38](v00/product/RESULT-v2.md)、[新真实11及原14](v00/browser-review/RESULT-real-v1.md)、[现行174门禁](v00/browser-review/RESULT-full174-v1.md)、[质量工具59独立反证](v00/quality/RESULT-v1.md)、[门禁字节与资源后验](INTEGRITY-G4-gates-v1.json)。所有首败分别保留；source956/执行QA3493/contracts33/build970/历史QA19169零漂移，原四自有服务与全量测试后代关闭，5174/8001监听0。

关闭后先建立 [B7-A需求矩阵](B7A-REQUIREMENTS-MATRIX-v1.md)，随后才释放离线工具实施。工具与材料入口仍在实现/待独立验收；live不运行，教师和Word/WPS待验，原B6/B7整体不关闭。唯一及时状态仍看 CURRENT_STATUS，不从这份历史阶段说明推定后续完成。

2026-10-05 最终离线交付：B7-A工具与材料完成，作者完整21/21、独立完整46/46及正常包273条引用通过，见[本批报告](REPORT-v1.md)、[限定离线验收收据](B7A-OFFLINE-ACCEPT-v1.json)、[独立结果](v00/b7a/RESULT-v1.md)与[材料/人工接续入口](B7A-OFFLINE-MATERIALS-v1.md)。[r2候选](CANDIDATE-B7A-offline-r2.json)、[release-v2](B7A-RELEASE-v2.json)、[源码/QA/历史后验](INTEGRITY-B7A-preclose-v1.json)、[资源关闭](RESOURCES-BATCH-v1.json)、[B7首败](FIRST-FAILURES-B7A-v1.md)及[后续追加](FIRST-FAILURES-B7A-v2-DELTA.md)分别保留。原v2任务与伪代码保持，仅增加当前状态；live/教师/Word-WPS仍待验，原B6/B7整体及RAG-REL保持未关闭，本批STOP。

2026-10-05 最终文档独立审查通过：[final-v2报告](v00/doc-audit/RESULT-final-v2.md)核21755个唯一文件前后SHA一致、109个交付链接有效；原任务、离线完成范围和待验边界正确。[最终完整性与文档QA delta](FINAL-INTEGRITY-v1.json)另行绑定，不改旧候选、收据或首败。权威状态保持最终离线交付，本批STOP。
