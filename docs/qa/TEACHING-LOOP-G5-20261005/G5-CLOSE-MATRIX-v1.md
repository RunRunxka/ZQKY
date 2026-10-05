# G5 限定关闭矩阵 v1（2026-10-05）

依据[总关闭收据](G5-CLOSE-v1.json)、[独立签收](v00/RESULT-v1.json)及[各实际门禁身份转签](GATE-TRANSFER-v1.json)。仅关闭本次两项修复及必要技术条件；原 v2 整体 G5/B6/B7 仍按实际待验边界管理。

| 要求 | 实际结论与证据 | 保持的边界 |
| --- | --- | --- |
| R-G4-RECOVERY-01 | [独立限定关闭](R-G4-RECOVERY-01-CLOSE-v1.json)：本次结果/冻结包/会话绑定；create/import连续失败恢复保留稿件，恰两POST；第二次success仅本次receipt并保留离开决策 | 原result共享语义不改；unknown/发送前失败重放原包；旧反例首败只读 |
| R-B7A-QUALITY-01 | [独立限定关闭](R-B7A-QUALITY-01-CLOSE-v1.json)：精确CSV形状/15行/人审空值，固定15案例MD/210空槽内容核验，合法SHA不代替空反馈 | 原273/15案例/四历史导出保持；没有live执行器或真人代填 |
| 完整工程 | [check](ctrl/g5-check-r1-command.json)126文件1380单测/typecheck/lint0/build完整新跑，next-env原字节精确恢复 | 实际prebuild-r2，产物2Gg_WxijBmV9IGIkY1vmG/proxy8001 |
| 独立组件 | [新完整152](v00/product-second/command.json)全部通过、四域前后0漂移 | 实际built-r2；第一轮150/152定位首败保存，没有拼轮 |
| 独立工具 | [102实际调用](v00/run-quality-first/SUMMARY.json)：5正常97正确硬拒、四guard尝试0 | 实际built-r1；expected refusal不是exit0，canonical不等于物理源验收 |
| 新真实页面 | [8场景原件](v00/browser/g5-browser-first.json)四视口完整通过、[独立原图/trace审查](v00/browser-review/RESULT-real-v1.json)通过 | HTTP/Storage受控、模型0；焦点+Enter实测，不声称Tab遍历 |
| 现行完整E2E | [29spec174](v00/browser/g5-full-e2e-first.json)一次完整通过、[174 trace实核](v00/browser-review/RESULT-full-v1.json)通过，原21UI/R14保持 | 含6既有隔离真实FastAPI场景/2fixture；模型0，不是全mock，不关闭R14间歇台账 |
| 历史API/聊天/导出 | [同源引用](HISTORICAL-REFERENCE-v1.json)：backend410/chat186/exportCore11精确，59原引用精确+1 MISSING_NOT_RUN | 本批pytest API/chat专项/导出未执行；旧export43有12漂移不得整域转签 |
| 保全与文档 | [开工原件](OPENING-v1.json)＋[当前独立文档审查](doc-audit/)；六权威仅新增G5状态，原完整字节保留 | 原v2任务/伪代码/Guide/API/ROUTES/PLAN/模板不改；后加文档单列后验，文件数不是测试数 |
| 资源 | [四实例/26后代收据](RESOURCES-final-v1.json)闭合，5174/8001无监听；[2fixture](RESOURCES-FIXTURE-CLOSURE-v1.json)child/logClosed | 所有TEMP/首败保留；未知/用户进程未操作，旧被拒额外HTTP probe未重试 |
| 后续模型/教师/native | [仅交接](B7B-HANDOFF-v1.md)，B7-B未开始/live0；教师pending；Word/WPS not_run | 明确profile/model/case/sample/attempt/总token或费用、真人反馈和原生页核方式后才另批；本批无授权/执行保证 |
| 旧缺物理源/相关性/整体 | not_run_source_temp_unavailable；RAG-REL/R14/CV01～03/OBS-LP-MODE-LABEL/环境观察OPEN；原B6/B7未整体关闭 | 新fixture TEMP不能代替旧SQLite/Blob恢复证明；历史13PDF页不等于原生页数 |

作者编辑126和工具49/52单测、80/53CLI各为自检轮，独立门禁单列；完整记录见[报告](REPORT-v1.md)与[首败保全](FIRST-FAILURES-v1.md)。当前built-r2为960source/3660执行QA/33contract/970build，实际152在r2，check/102/8/174保持各原实际candidate及显式同源转签。所有必要新浏览器轮次无skip/retry/flaky/reporter errors；旧历史规模skip单列。

最终文档审查和封印仅完成本批收口。STOP：无Git写入/推送/切分支/部署，无新模块/API/迁移/依赖，没有再次生产离线交付包或启动B7-B。
