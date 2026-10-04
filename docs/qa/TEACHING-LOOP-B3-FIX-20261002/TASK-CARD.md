# TEACHING-LOOP B3 修复与补齐任务卡

任务版本：v1，2026-10-02。总控 `/root`；用户本轮明确授权完成 B3，完成后停止，不启动 B4，不提交/推送/部署。

实际起点 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`，仅 `apps/web/next-env.d.ts` 为既有用户改动（必须逐字节保留）。B2/B3 已交付实现作为基线；原冻结件、审查报告和探针保持原样。旧提示中的 `0f4b8cb` 不作为今日 HEAD。核对结果另存 BASELINE.json。

| 任务/负责人 | 独占写入文件 | 验收条件 |
| --- | --- | --- |
| SCORE v1 / scores_backend | `apps/api/app/services/scores/imports.py`、`service.py`；`apps/api/tests/test_b3_review_score_fixes.py`；本目录 SCORE-RESULT.md、score 专属日志 | R03–R07 正确行为；C/c 与身份占列冲突零正式写入；表头/身份重建保留适用校正；人工映射恢复；编码证据完整；修正状态定位 422；权威承认范围与 confirm 同源 |
| F20 v1 / assessments_frontend | `apps/web/src/features/assessments/AssessmentsPanel.tsx`、`ScoreImportReview.tsx`、`labels.ts`、`labels.test.ts`；新 `AssessmentsPanel.test.tsx`、`ScoreImportReview.test.tsx`；必要时 `hooks.ts`、`hooks.test.tsx`；本目录 F20-RESULT.md、f20 专属日志 | R02/R08：真实四态承认，卸载/换上下文迟到零副作用；409/422保留编辑，出勤校正/刷新明确 |
| F10 v1 / question_frontend | `apps/web/src/features/question-bank/jobs.ts`、`jobs.test.tsx`、`GenerationPanel.test.tsx`；本目录 F10-RESULT.md、f10 专属日志 | R01 首次 queued(0)→terminal(1) 可见；首次失败可见；retry窗口与N+2守卫；StrictMode/旧操作隔离 |
| CTRL v1 / root | 公共任务引擎/租约仓储、题库 organizer 服务/公共 catalog、tabular、Python/TS contracts、API/客户端、施测出勤业务、主装配/迁移（若需）、e2e、权威文档、本目录其余文件 | R09/R10 原租约 CAS、取消调用数0；补原授权缺口；全量检查/真实API浏览器链/规模；冻结新候选 |
| V00 v1 / 后续独立 Agent | 产品只读；本目录 V00 专属报告/探针/日志 | 候选稳定后自建反例/故障注入，逐项 pass/fail/not_run；不得边验边修 |

总控独占依赖锁/Git/公共契约/权威进度/最终集成；最多同时3名实现者。实现者只跑自己的窄回归，交 ready_for_review 后停止写。总控串行组织全量测试、构建、8001/5174服务与浏览器资源；不结束未知进程。

公共扩展先冻结：`ScoreImportView.requiredAcknowledgements = {absences, missing}`，由服务端当前有效全矩阵产生并绑定 `previewVersion`；前端不从原始空白推断。总分/出勤映射、参测出勤校正/预览刷新接口由总控在双侧类型和 API 登记后派发，均属原 B3 授权，学情/教案/练习不实施。

所有应用导入/启动前先设临时 `ZQKY_DATA_DIR`；不读正式 `.env`/`.local-data`。固定输入和受控 Provider，真实供应商质量单列 not_run。已有0001–0007迁移与散列不改。旧G0独立证据保留，本次相关回归重新执行。

结果必须列：精确文件、行为变化、失败与竞态、命令/退出码/证据、首败、未执行、剩余问题、资源释放和 ready_for_review；总控经独立验收后更新 CURRENT_STATUS。

## v2/v3 补齐归属（2026-10-02，原授权内）

- SCORE v2 已 `ready_for_review`；原两服务与32例正确行为回归停止写。
- F20 追加独占：`ScorePanel.tsx`、`ScorePanel.test.tsx`、`ParticipantAttendanceEditor.tsx`、`.test.tsx`、`PapersPanel.tsx`、`PaperImportReview.tsx`、`.test.tsx`；原卷手工全过程、源块/受管资产与AI建议。
- F10-BROWSER 独占 `tests/fixtures/teaching_loop_backend.py`、`tests/e2e/question-bank-real.spec.ts`，已 ready；之后root集成、串行运行。
- ROSTER v1 / question_frontend：`RosterPanel.tsx`、新 `RosterImportPanel.tsx`、`.test.tsx`、`ROSTER-RESULT.md`与名单专属日志；CSV/XLSX导入、映射、link/create/ignore、批次恢复、转班及旧归属可读。复用冻结提交原语，禁止旧请求覆盖新班。
- QB-RICH v1 / scores_backend：`services/question_bank/service.py`（root R09修改已停止）、`validation.py`、`fingerprint.py`（如需）、新 `tests/test_question_rich_content.py`；允许新局部 `rich.py`但需登记。可选富内容实际存读、显式权威转换、资产归属/字节校验与派生指纹。root独占schema/双侧契约/路由。
- CTRL 追加独占：`components/ui/RichContentRenderer.tsx`、`.test.tsx`、`rich-content.css`，`services/use-workflow-job.ts`、`.test.tsx`，题库 `QuestionPreview.tsx`、`ContentForm.tsx`、`draft-form.ts`、`QuestionDetailPanel.tsx`；所有客户端/API共享变更；`tests/test_participant_attendance.py`、`test_b3_migration_failure_stages.py`、`tests/e2e/assessments.spec.ts`和名单原卷完整链fixture。
- PARTICIPANT-ADD v1 / assessments_frontend：新 `ParticipantAddPanel.tsx`、`.test.tsx` 与原归属 `AssessmentsPanel.tsx`；既有施测补录/补考显示人次，复用真实 `addAssessmentParticipants`，冻结请求与 CAS，迟到守卫，409/422保留编辑。
- F10-GUARD v1 / question_frontend：ROSTER 已ready后追加 `DraftEditor.tsx`、`QuestionDetailPanel.tsx`、`ReviewWorkspace.tsx` 及对应窄测；root已停止原富内容相关文件写入。草稿富内容预览复用共享renderer/受控assetloader；初次整理queued窗口、写操作与冲突读回的卸载/对象代次守卫。

统一共享renderer只有root一个写入者。已有0001–0007计划与散列保持；新隔离迁移故障回归验证copy/换表/trigger/fk检查与integrity第一行ok后错误都回滚、恢复外键且可重跑。运行SQLite 3.53.1；对照官方[重建流程](https://www.sqlite.org/lang_altertable.html#making_other_kinds_of_table_schema_changes)和[foreign_keys PRAGMA](https://www.sqlite.org/pragma.html#pragma_foreign_keys)，正式迁移不执行。
## v4 独立验收反例修复归属
实现者均已ready并停止写。root独占接管：scores imports/service及新test_score_precision_exact.py、test_score_preview_boundaries.py；question_bank service及新test_question_publication_boundaries.py；jobs repository及test_b3_review_job_fixes.py、test_jobs_engine.py；assessments hooks/三确认组件；question-bank ReviewWorkspace/ConfirmPanel/DraftEditor及对应测试；knowledge-points hooks及strictmode测试；real browser两spec的精确选择器/名单既有dataNo口径。验收者只写V00专属探针/日志/报告，首次失败完整保留，产品稳定后重新冻结r3。修复不改变0001–0007迁移及锁文件，不改变HTTP200+题库failures整批未登记语义。
## v5 全量回归的测试时钟/旧契约修正
root独占tests/test_scores_confirm.py（旧隐式PATCH刷新改为显式refresh与更严格CAS/原值断言）、tests/test_jobs_engine.py（同时等待两租约仍running有效续期再推进假时钟）、tests/test_rag_sessions.py（R19以模块独立任务钟核50ms TTL、70ms过期、容量与重启，真实事件循环/检索及产品不变）。Windows CLI测试使用PYTHONUTF8=1统一父子进程编码。r3产品全部停止写，r4只有此三个Python回归文件差异，V00逐一只读审口径，首败全文/XML保留，完整后端重跑。不以clock调整改变租约/过期/容量业务门槛。

## v6 真实浏览器首败修正归属
root继续独占两e2e spec；r4真实6例3过2败1未跑保全browser-r4。原卷磁盘File被测试postDataBuffer遗漏字节，固定8001时走已配置真实Next同源代理，并显式读固定DOCX bytes>0；题库改内容按既有catalog强制needs_review，先保存真实PATCH并核新内容/待校对，再审核该修订。产品/Python/构建输入不改；新冻结r5仅两spec差异。独立V00只读复核，不改产品闸门。

## v7 真实窄屏溢出修复归属
root独占features/assessments/styles/assessments.css及真实浏览器spec。r6全链事实与修正/v1不变已过，390px修正人次选择器携32字符classId导致外层413px；browser-layout-first图片/1440、1920、390测量/首败日志保留。新增仅模块field/select宽度约束，矩阵内部横滚保留，不隐藏页面overflow；r7冻结，全check/build与真实链重新执行，独立前端只读审CSS+最终图片。其他后端产品/迁移不改。
