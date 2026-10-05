# G5 总控交付报告 v1（2026-10-05）

R-G4-RECOVERY-01 与 R-B7A-QUALITY-01 两项 P2 已由稳定候选独立验收通过，必要完整工程与实际页面门禁完成。[G5 关闭收据](G5-CLOSE-v1.json)状态为 `G5_CLOSED_LIMITED_INDEPENDENT_TECHNICAL`，SHA `fa307c6589797c58ba916ea5df9aff82e4339402dd3b6a1ec027f5989d6d292a`。本次修复批 G5 与原 v2 整体交付 G5 分开，原 B6/B7 整体不由本批关闭。当前任务授权到此结束；文档独立审查及证据封印完成后停止，无自动下一批。

## 实际变化与教师可见行为

教案创建/导入现在把缓存清理恢复绑定到实际本次 FrozenSubmission、contextKey/loadGeneration 和明确结果类型。只有本次 success 才携带本次 receipt 并继续走现有离开保护；明确 failure 清缓存与解锁后保留当前稿件及失败提示，不打开前一次成功文档，也不发送第三次创建/导入。未知结果或发送前写失败保持原包身份与公开重放入口；跨文档/卸载/迟到或同 context 外来包不能删除另一操作缓存。

产品改动仅 [useLessonOperation](../../../apps/web/src/features/lesson-plan/model/useLessonOperation.ts)、[DocumentsPanel](../../../apps/web/src/features/lesson-plan/components/DocumentsPanel.tsx)及同模块新行为测试。共享 useFrozenSubmission 的历史 result 语义、DocumentContext/Gateway/LeaveProtection/ProposalPanel/ServerControls 均保持。原审查仅证实错误导航，不宣称已证实正文覆盖；本批另以公开行为检查正文、secondary、固定 context/source/选择及 HTTP 身份。

离线准备入口现在先核 CSV 精确 20 列/20 key/string、完整 15 行顺序及固定 case/hash/DOCX，再核 15 人审列均空。Markdown 从固定 caseId/title/hash 构建全 15 案例模板，核 210 个明确空槽及完整说明，仅容忍初始 UTF-8 BOM 与换行规范化，不能吞掉评语、评分、姓名、时间、理由、建议或未知追加内容。CSV/MD 均合格才宣称空反馈。只改 [prepare_review](../../../scripts/teaching-quality/prepare_review.py)、专属测试及 README；common/aggregate/preflight 不改。

原 15 全集、明确 14 子集加 C15 未运行保持有效；原 273 引用和原空人审表逐 SHA 不变，四代表历史导出未重建。正常 prepare CLI 的输出只为测试证据，没有发布第二份 B7 离线交付包。

## 各自完整实际门禁

| 门禁 | 实际完整结果 | 真实执行身份/耗时/退出 | 原实际候选 |
| --- | --- | --- | --- |
| [完整 check](ctrl/g5-check-r1-command.json) | 126 文件、1380 单测，typecheck/lint 0/build 通过 | PID3792；105859.499ms；exit0 | prebuild-r2，产物 built-r1 |
| [独立组件](v00/product-second/command.json) | 152/152，新28＋原反例1＋控制2＋原恢复37＋来源/历史60＋原公开恢复24 | Node22752；23716.542ms；exit0；outer22760/24640.821ms | built-r2 |
| [独立离线 CLI](v00/run-quality-first/SUMMARY.json) | 102 唯一调用：5 正常、97 预期硬拒；网络/app/.env/数据库四 guard 实际0 | outer15400；47425.353ms；exit0；子 CLI 合计23765.44ms单列 | built-r1 |
| [新增实际页面](ctrl/g5-browser-first-command.json) | 8/8，四视口及8原字节截图、成功/失败两连续操作 | PID19380；8985.67ms；exit0 | built-r1 |
| [现行完整 E2E](ctrl/g5-full-e2e-first-command.json) | 29 spec、174/174、174 trace，保留原21 UI和R14 | PID14648；492652.953ms；exit0 | built-r1 |

浏览器各单轮 0 skip/retry/flaky/reporterErrors。新增8使用隔离 Storage/HTTP 受控替身和真实页面，模型0。完整174包含既有真实隔离 FastAPI 场景（6例、2 fixture），不是全 mock：在 app 导入前使用新 TEMP/test、credentials_file=None；Provider仍受控，正式数据库、真实凭证、6333及真实模型均未使用。现有隔离规模浏览器样本不等于正式数据库压力验收。

作者最后各自完整轮为编辑126/126＋lint0＋非增量TS，工具prepare49单测/80CLI、legacy52单测/53CLI。它们是作者自检，与上表独立计数分开；[独立签收](v00/RESULT-v1.md)才是两 finding 独立结论。命令、真实起止、逐文件 SHA、预期判据与原件全部在相应 JSON/log 中。

## 候选、首败与后验

开工 main@`b7f99ab09826c68724e281d01e15215e660c1ce0`，原 B7A-r2 为959/3496/33/970，新 built-r2 为960/3660/33/970；这些都是文件数。新构建 `2Gg_WxijBmV9IGIkY1vmG`，实际 rewrites 指向8001，next-env恢复开工 SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`。

[当前候选](CANDIDATE-G5-built-r2.json) SHA `049ad4057540ba1e2bd6f383c3944bba738ff2e47acd2d1dde542d210506c533`。独立首轮150/152的两处QA入口定位错误保存；174完成后只改公开原包 replay 定位，原业务 oracle 全部保持。整套152在新r2完整复验，未拼首轮150。[显式转签](GATE-TRANSFER-v1.json)保留 check/CLI102/新8/174 的原实际候选，核源码/契约/970构建完全相同；recovery测试与ROOT关闭工具两份QA delta均不在这些通过轮的实际执行闭包，不称这些门禁在r2重跑。[全部首败](FIRST-FAILURES-v1.md)及所有 TEMP 原样保留。

当前源码/执行QA/契约/构建、旧QA22207、原材料1056、原273引用与开工保护文件逐SHA核对无漂移；本批源码范围共六文件（含新行为测试、专属Python测试和README），无共享契约/锁文件/依赖改动。六份权威状态只新增 `G5:20261005` 块，剥离后全部开工字节相同；原v2任务与伪代码、PROJECT_GUIDE/API/ROUTES/PLAN/原Word保持。当前文档与独立审查输出单列后验，最终清单绑定实际新字节，不宣称产品候选覆盖后加文档。[独立文档审查](doc-audit/)结果与最终封印为本批最后的文档收据。

## 同源引用、待验与关闭资源

[历史引用](HISTORICAL-REFERENCE-v1.json) backend410、chat186、exportCore11及原材料1056逐SHA一致；60历史引用为59存在且精确、1旧缺件 `VISUAL-REVIEW-v1.md`继续 MISSING_NOT_RUN。本批未单独重跑pytest API、聊天专项或导出；历史API1918通过/1规模skip和独立42、历史chat14仅按原收据引用。旧exportStyles43有12历史漂移，不能转签整域排版证明。

旧物理SQLite/Blob/恢复TEMP缺件仍 `not_run_source_temp_unavailable`；本批E2E的全新隔离TEMP不补成旧恢复证据。live/B7-B未开始、教师评价pending、Word/WPS原生页核not_run，历史四DOCX/四PDF/13PNG不作原生页数或真人评价。RAG-REL、R14跨批间歇、CV01～03、OBS-LP-MODE-LABEL及原环境观察继续OPEN；正式Qdrant/迁移/压力未执行。旧被拒额外HTTP身份probe仍not_run且未重试。

[资源关闭](RESOURCES-final-v1.json)记录ROOT四原实例及捕获26后代收据闭合、日志关闭、5174/8001无监听；[两现有临时API夹具](RESOURCES-FIXTURE-CLOSURE-v1.json)child/logClosed，TEMP均保留。前端按持有句柄/PID/出生身份关闭，未知用户进程不动。没有提交、推送、切分支、Git身份修改或部署。

[B7-B交接](B7B-HANDOFF-v1.md)仅列未来授权输入；scope_preflight仍executorPresent=false/budgetEnforced=false，不创造授权或预算控制。本批STOP，下一动作等待用户明确的新范围，不能再次制作已交付离线包或自动真实试评。
