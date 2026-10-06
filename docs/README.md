# 当前文档索引

> 使用指南：[教学闭环使用教程](教学闭环使用教程.md)——教师视角的完整 walkthrough（环境准备 → 知识点/名单/原卷/施测/成绩/学情/练习/回流/教案 → 护栏与排错）。

<!-- G7-B7C-LIVE:20261006 -->
2026-10-06：[G7 修复 + B7-C 单模型 live 首发 + 用户材料闭环](qa/TEACHING-LOOP-G7-B7C-20261005/README.md)。G7 两项已独立限定关闭；首次真实受控试评成功（C01，HTTP 200， settle 8748，`live_technical_pass` + 结果入口 `RESULT_INTEGRITY_PASS`）；用户材料闭环单轮 0 偏差。产品级发现：非流式 30 秒默认等待使 `reasoning=max` 教案生成在产品自身超时（未改产品）。teacher/native/RAG-REL 与原始台账仍待验；唯一进度见[CURRENT_STATUS](CURRENT_STATUS.md)。
<!-- /G7-B7C-LIVE:20261006 -->

<!-- LOOP-RERUN:20261006 -->
2026-10-06：[教学闭环复跑与 10-04 结论入库](qa/TEACHING-LOOP-LOOPRERUN-20261006/README.md)。用 `C:\Users\96022\Downloads\test` 的 10-04 资料在 main@1f1b7b3 重跑：核心闭环 PASS（110 HTTP/577 断言，模型 0）、浏览器专项 15/15（既有 G7 构建）；LOOP-01/02（原卷导入）仍复现、LOOP-04 显式清除已修但切片/固定教材两条仍失败、LOOP-03 口径差异待裁定、QA-02 复现、QA-01 未重跑。产品只读、无提交。同日 18:20 二次复跑结论一致（run08 PASS、浏览器再次 15/15、QA-02 逐字节相同），脚本目录被清理后重建的 harness 在 `Downloads/test/harness-20261006/`。同日 19:15 **LOOP-01/02 已修复**（分节标题作结构边界、独立子题号归完整子题路径；新增 2 条回归用例，全量后端 1921 例 exit 0），修复后闭环 run09 PASS、浏览器 15/15。同日 19:30 **LOOP-03/04 口径经用户裁定为保持现状**：LOOP-04 保留"改切片参数不取消在途核验"并补一行界面分工说明，LOOP-03 保留"先点重试恢复缓存再保存"；`npm run check` 全绿（单测 1484 例、构建 `sBZJ0fQ7zQuuZSbRpWLTT`）、新构建 lesson-plan e2e 9/9。QA-01/02 留待质量批。唯一进度见[CURRENT_STATUS](CURRENT_STATUS.md)。
<!-- /LOOP-RERUN:20261006 -->

<!-- G7-B7C:20261005 -->
2026-10-05：[G7两项修复与B7-C缺项交接](qa/TEACHING-LOOP-G7-B7C-20261005/README.md)。R-G6-WRITE-OWNER-01与R-B7B-NATIVE-01已修复并由非作者独立限定技术关闭（check r2/r3全绿、全量e2e 174/174、同源双页r2b 4/4、页图三反例硬拒）；B7-C因无授权范围/模型proof/可信host未执行真实调用，real0，缺项与代码定位见B7C-GAP-v1.md。教师/原生页核/RAG与原始台账仍待验；唯一进度见[CURRENT_STATUS](CURRENT_STATUS.md)。
<!-- /G7-B7C:20261005 -->

<!-- G6-B7B-REVIEW:20261005 -->
2026-10-05：[G6/B7-B后续代码审查](qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/REVIEW.md)新增写入归属、native页图解码两个P2；原ACK修复/离线预算验收保持。[G7→B7-C提示词](design/teaching-loop-v1/B7C_总控启动提示词_20261005.md)已写未执行：先两修，再条件单模型试评，无范围则STOP，不重复离线包。唯一进度见[CURRENT_STATUS](CURRENT_STATUS.md)，真实模型/教师/原生页核/RAG仍待验。
<!-- /G6-B7B-REVIEW:20261005 -->

<!-- G6-B7B:20261005 -->
2026-10-05T18:53:42.302168+08:00：[G6/B7-B证据](qa/TEACHING-LOOP-G6-B7B-20261005/README.md)。

G6 R-G5-CACHE-01/P2已独立有限技术关闭；B7-B受控离线技术已独立验收，ROOT收据为G6-CLOSE-v1.json、B7B-OFFLINE-ACCEPT-v1.json和CLOSE-v1.json。G6作者274、完整check127文件1463单测/type/lint0/build、独立211、新同源双页8＋原G5 8共16、现行29spec174各单轮通过，24原PNG/190原trace已独立核。actual check/prebuild-r1、211/built-r1、16/174/built-r2各自身份保留；all候选不冒称这些门禁重跑。build wsH0-uD7VDC2ACYsbiRfS/proxy8001与next-env原字节恢复，正常ACK/cleanup共用归属核验，不宣称原子CAS。

B7B最终独立full-r2：预算64/64、27 fixture边界；结果76/76、77 checker＋1setup、18 fixture，真实调用0；两轮source/执行QA/契约/build零漂移。all候选SHA08e71f7d386e4005406209718317220506829bf9816d9d9e4bce1b934dc61988含972source/3771执行QA/33contract/970build，文件数不是测试数。首完整r1行为与venv launcher出生错绑原件保留；新完整r2仅换同源CPython base和原venv依赖，QA/oracle不改，实际worker PID/birth/wait/日志闭合。作者73、11组84CLI及旧quality52/prepare49＋34subtests是作者自检，分开计数。

本批无真实模型/精确caseIds/sampleCount/attempt/可执行总预算授权，real0；当前CLI缺具体模型proof registry/可信live host，费用模式不支持，不能称输入范围补齐即可任意模型试评。teacher/native仍pending、Word/WPS原生not_run、RAG-REL及原B6/B7整体与R14/CV01～03/OBS-LP-MODE-LABEL/环境观察保持OPEN/待验。旧物理SQLite/Blob缺源保持not_run，新TEMP不补造；原13PDF不代原生。旧QA46952、原材料1056/273、原Word及v2完整任务/伪代码只读，六现行文档仅本批新增状态。自有进程和捕获后代已核闭合、5174/8001无监听，TEMP/所有首败保留，历史未采worker出生不伪补；未知用户进程未操作。独立文档后验和最终资源/INTEGRITY/封印另存后追加证据，本批结束即STOP，下一动作只等用户新指示，无被拒HTTP probe重试、正式数据/6333、Git提交/推送/切分支/部署或自动下一模块。
<!-- /G6-B7B:20261005 -->

<!-- G5-REVIEW:20261005 -->
2026-10-05：[G5后续代码审查](qa/TEACHING-LOOP-G5-REVIEW-20261005/REVIEW.md)与[G6→B7-B提示词](design/teaching-loop-v1/B7B_总控启动提示词_20261005.md)。原G5修复保持，新正常ACK缓存归属P2尚未修复；工具空反馈复核通过。当前仅审查/提示词，不启动下一批或重复离线准备包。进度只看[CURRENT_STATUS](CURRENT_STATUS.md)，真实模型/教师/原生页核仍待验。
<!-- /G5-REVIEW:20261005 -->

<!-- G5:20261005 -->
2026-10-05T15:21:15.335336+08:00：[G5证据](qa/TEACHING-LOOP-G5-20261005/README.md)。

2026-10-05 G5两项P2已独立限定技术关闭：R-G4-RECOVERY-01清缓存只采用本次操作/会话/明确结果，失败保持当前稿件且不误开历史成功文档；R-B7A-QUALITY-01严格核CSV形状与空人审、固定MD完整空槽，合法SHA不代替内容判据。G5-CLOSE-v1与两finding收据已生成，独立V00签收并STOP；这是本次修复批G5，不等于原v2整体交付G5，不关闭原B6/B7整体。

必要新完整check126文件1380单测/typecheck/lint0/build；独立最终152/152；CLI102为5正常97正确硬拒，四guard实际0；新实际页面8和现行29spec174各单轮完整通过，0skip/retry/flaky/reporterErrors，174含原21UI/R14和6既有隔离真实FastAPI场景（2fixture），模型0，不称全mock。单独pytest API、聊天专项及导出本批未执行，backend410/chat186/exportCore11逐SHA历史绑定；59历史引用精确+1旧MISSING_NOT_RUN，旧export43有12漂移不能整域转签。

当前CANDIDATE-G5-built-r2 SHA049ad4057540ba1e2bd6f383c3944bba738ff2e47acd2d1dde542d210506c533：960source/3660执行QA/33contract/970build，构建2Gg_WxijBmV9IGIkY1vmG、实际proxy8001、next-env原字节恢复。152实际跑r2；check实际prebuild-r2，102/8/174实际built-r1。两非其执行闭包QA差异与同源码/契约/整构建转签单列，保留原实际候选身份，不冒称r2重跑；组件首轮150/152两QA入口首败及最终新完整152分别保留，无拼轮。文件数不是测试数。

六当前权威文档只新增本批G5状态块，完整开工内容含原v2任务/伪代码/旧审查保持原字节；原Word/Guide/API/ROUTES/PLAN、旧QA22207、原材料1056及原273引用保持。当前文档与最后独立文档审查、封印单列后验收据，不声称产品候选覆盖后加文档。ROOT自有四原实例及捕获26后代收据闭合，5174/8001无监听，2fixture child/logClosed；所有TEMP/首败保留，未知用户进程未动。

本批在最终文档独立收据及封印完成后STOP，下一动作只等用户新明确指示。B7-B/live未开始、教师pending、Word/WPS原生not_run、旧物理SQLite/Blob恢复源TEMP缺件not_run_source_temp_unavailable；canonical来源绑定不代替物理通过，历史13PDF页不代替原生页核。RAG-REL/R14跨批间歇/CV01～03/OBS-LP-MODE-LABEL及原环境观察保持OPEN。旧被拒额外HTTP身份probe未重试；无正式数据/6333/迁移/压力，无Git提交/推送/切分支/部署，没有自动下一批或重制离线包。真实试评交接仅列未来授权输入，executorPresent=false/budgetEnforced=false。
<!-- /G5:20261005 -->

<!-- G4-B7A-REVIEW:20261005 -->
2026-10-05：[G4/B7-A后续代码审查](qa/TEACHING-LOOP-G4-B7A-REVIEW-20261005/REVIEW.md)与[G5限定修复提示词](design/teaching-loop-v1/G5_总控启动提示词_20261005.md)。新增回执归属/空反馈验证两项P2，尚未修复；原正常离线包保持，真实模型/教师/原生排版仍待验。当前状态只看[CURRENT_STATUS](CURRENT_STATUS.md)，本轮止于审查与提示词，不重复离线准备或自动开批。
<!-- /G4-B7A-REVIEW:20261005 -->

<!-- G4-B7A:20261005 -->
2026-10-05T14:02:43.529062+08:00：[本批证据](qa/TEACHING-LOOP-G4-B7A-20261005/README.md)。

2026-10-05本批交付：G4四项已独立限定技术关闭；随后B7-A离线工具与验收准备完成。G4-CLOSE-v1.json与四项收据保持原件；本轮只完成离线，不关闭原B6/B7整体。

G4实际完整check125文件1354单测/typecheck/lint0/build通过；独立组件38、质量工具59预期结果、新真实浏览器11、原真实14、现行29spec174 E2E分别完整单轮通过，0skip/retry/flaky/reporterErrors。构建VeOLFBYrp-8v24Yjm-HFi，实际代理8001，next-env原字节恢复。B7仅新增离线Python入口/专属测试/README，前端、后端、旧三工具、契约与构建逐项未变；精确引用上述G4门禁及适用历史同源证据，不冒称再次跑完整API/聊天/恢复或重新导出。

B7-A已先交需求→固定样本→结构→真实输出→教师理由→排版矩阵，再实施工具。最终作者21/21完整通过；独立46/46完整首次CLI轮通过（15全集、明确14子集+C15未运行，以及44项硬拒），全部网络/app/.env/数据库打开guard尝试0，各子进程和日志关闭。原作者首败、准备定位/封印失败、候选r1/r2与所有TEMP保留，不拼轮或改原业务判据。B7A-OFFLINE-ACCEPT-v1.json、v00/b7a/RESULT-v1.md、B7A-OFFLINE-MATERIALS-v1.md和本批README为收据/材料入口。

正常材料包b7a/prepared-full-v1仅生产一次，273条固定SHA引用；原15案例/15逐例DOCX、四代表DOCX/四旧实际PDF/13旧PNG、八维rubric和原15行空feedback保持。新native逐页表只有四文件起始行，实际原生页码/页数、应用/版本、评审者、证据理由与结论留空；13页PDF只作历史参考，不能代替原生页数或教师评价。

最终冻结CANDIDATE-B7A-offline-r2.json SHA3a73dd766c2e23e57e5726e157f7ef5ef1efe9a7c5f815429b3774ca24568297：source959/执行QA3496/契约33/build970；历史QA19169逐项不变。原v2计划书87340字节完整保留，仅增加本批状态；CURRENT_STATUS/NEXT_SESSION及现行索引原内容同样保留，PROJECT_GUIDE/API/ROUTES不变，main@b7f99ab未改。自有服务、浏览器后代/工具子进程与句柄关闭，5174/8001无监听；不停止用户进程，不删TEMP或旧policy拒删目录。

live=not_run_user_offline_scope，teacher_review_pending，Word/WPS=not_run_pending_human_manual_open。旧物理SQLite/Blob与恢复证明缺失、唯一旧VISUAL-REVIEW引用缺件均单列not_run；冻结canonical来源绑定不冒称新物理通过。旧export/styles43中12项历史漂移不转移整体排版证明；R14跨批间歇、CV01～03、OBS-LP-MODE-LABEL、RAG-REL及原环境观察保持OPEN。正式Qdrant/迁移、额外压力、正式数据/6333、发布部署未执行。

本批到此STOP。下一动作仅按教师后续反馈或用户新的明确范围执行；没有真实模型授权/执行器或自动下一批，不Git写入/推送/切分支/部署。后续接续从本批收据与待验边界开始，原任务和伪代码不改。
<!-- /G4-B7A:20261005 -->

2026-10-04，最新材料：[限定B6后续审查](qa/TEACHING-LOOP-B6-REVIEW-20261004/REVIEW.md)、[G4→B7-A提示词](design/teaching-loop-v1/B7_总控启动提示词_20261004.md)。两项继承产品/两项质量工具P2待修，原G3及限定B6关闭保持；本轮未执行下一批。唯一进度先读[CURRENT_STATUS](CURRENT_STATUS.md)，下面原关闭/开工文字保留历史时点。

<!-- B6-FINAL-INDEX:20261004 -->
2026-10-04T15:35:08.675530+08:00：G3独立技术关闭；本批限定B6技术集成与教学质量验收准备已完成，见[最终矩阵](qa/TEACHING-LOOP-G3-B6-20261004/B6-CLOSE-MATRIX-v1.md)、[收据](qa/TEACHING-LOOP-G3-B6-20261004/B6-CLOSE-v1.json)、[教师试用](qa/TEACHING-LOOP-G3-B6-20261004/b6-exports/TEACHER-TRIAL-v1.md)。1286/check、真实五字段、四视口14、原完整153及独立技术签收完成；最终文档后验单列；真实模型待输入、教师评价待验、Word/WPS排版not_run、RAG-REL OPEN，原B6/B7整体未关闭。以下开工和10-03文字保留历史时点；唯一当前入口仍为[CURRENT_STATUS](CURRENT_STATUS.md)。本批停止，无Git或部署。
<!-- /B6-FINAL-INDEX:20261004 -->


<!-- B6-CHECKPOINT:20261004-RELEASED -->
2026-10-04T13:58:43.711694+08:00：G3已独立技术关闭；B6先行需求→实现→原证据→剩余矩阵已形成，三路任务已释放，当前新完整教学链/≥12匿名质量准备/四类导出试用材料进行中。ROOT新隔离8001/PID4056和既有5174/PID21544均回环自有，真实业务沿用现有模块/Transport替身；无真实模型调用。恢复来源v2精确分列原样本16库审计与最终410同源API恢复用例，未本批重跑恢复。live_run待输入、teacher_review_pending、Word/WPS人工排版待验、原B7未关闭。
<!-- /B6-CHECKPOINT:20261004-RELEASED -->


2026-10-04：已授权并开工 [G3→限定B6](qa/TEACHING-LOOP-G3-B6-20261004/README.md)，G3两项修复/独立验收进行中，关闭后才进入B6剩余集成与质量准备。当前进度以[CURRENT_STATUS](CURRENT_STATUS.md)为准；10-03审查与原关闭证据保持。


更新：2026-10-03。当前建设以 **2026-09-29（含）之后**的教材 RAG 与教学闭环为主。日期用于区分任务历史，仍有效的工程约束、许可和既有能力继续保留。

| 阅读顺序 | 文档 | 权威职责 |
| --- | --- | --- |
| 1 | [根 AGENTS](../AGENTS.md) 与模块 AGENTS | 工程规范、数据保护、协作边界 |
| 2 | [CURRENT_STATUS](CURRENT_STATUS.md) | 唯一当前任务、问题和下一动作；区分已修行为与尚未完成的阶段门禁 |
| 3 | [PROJECT_GUIDE](PROJECT_GUIDE.md) | 产品目标与稳定契约，不保存执行进度 |
| 4 | [教学闭环设计](design/teaching-loop-v1/README.md) | 架构、实体、约束、模块、ER 与表设计 |
| 5 | [v2.0 详细实施计划](design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md) | 分批依赖、文件归属、伪代码和验收标准；原始基线不等于今日状态 |
| 6 | [API](API.md)、[ROUTES](ROUTES.md) | 当前接口与页面索引 |
| 7 | [限定B6后续审查](qa/TEACHING-LOOP-B6-REVIEW-20261004/REVIEW.md)、[原G3/B6矩阵](qa/TEACHING-LOOP-G3-B6-20261004/B6-CLOSE-MATRIX-v1.md) | 原关闭保持，新增两产品/两工具P2待G4，不重写旧首败/验收 |
| 8 | [G4→B7-A总控提示词](design/teaching-loop-v1/B7_总控启动提示词_20261004.md) | 四项修复后有限试评；本轮仅编写，真实模型/教师/原生排版需真实依据 |

[PLAN](PLAN.md) 是实施规格索引；[当前接手文本](NEXT_SESSION_START.md) 规定接手步骤；[昨日B4暂停交接](qa/TEACHING-LOOP-G1-RESUME-B4-20261002/B4-PAUSE-HANDOFF.md) 保存历史暂停现场；[协作模板](MULTI_AGENT_COLLABORATION_PROPOSAL.md) 可复用，不将旧角色或授权当作当前任命。

近期交付与验收见 [QA 索引](qa/README.md)。9 月 29 日前的 31 个 QA 批次、旧阅读审查和原始规划已进入 [归档](archive/README.md)。旧三矩阵和旧大篇幅状态/目标正文保存完整快照，当前入口不再重复旧 H1–H6 路线。设计 SQL 和 ER 图是建设规格，正式已登记结构以迁移清单和源码为准。

原报告/冻结件不追改；历史链接与文件位置按归档 MANIFEST 的 source→destination 映射解释。现行说明修正会与旧冻结候选的文档散列不同，这是本次明确的后续文档变更，不重新冻结旧候选冒称无差异。

原G2/B5执行见[原批记录](qa/TEACHING-LOOP-G2-B5-20261003/README.md)，最新只读审查见[B5-REVIEW](qa/TEACHING-LOOP-B5-REVIEW-20261003/README.md)。旧提示词/暂停交接保留历史，实际进度优先CURRENT_STATUS。
