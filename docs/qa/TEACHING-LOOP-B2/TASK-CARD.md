# TEACHING-LOOP B2 任务卡（原卷 / 题库增量 / 施测 / 知识点前端）

- 批次：**B2 = CTRL + T40 + T50 + F10-KP（第一波）+ T30-b（第二波）**；依 [多Agent实施任务计划书 v2.0 §二.3](../../design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)
- 版本：v1.0；建立：2026-09-30
- 起点：`main@0f4b8cb190c2265d819b90e5d6df4e3954ad1906`（B0+B1 已由用户提交）；
  开工核对 [B1 r2 冻结记录](../TEACHING-LOOP-B1/FROZEN-CANDIDATE.json) **95/95 一致、0 差异**（含 postVerificationDocChanges）。
  工作区保留 `docs/design/teaching-loop-v1/**` 未跟踪设计交付物与用户改动。
- 批次完成条件：T40 原卷可真实确认；T50 关联/生成/统一任务与旧题库兼容可用；T30-b 在真实原卷上建立冻结参测快照；
  F10-KP 真页面端到端可用；迁移兼容；适用自动化 + 独立验收通过，无遗留阻塞 fail。
- **第一波**：CTRL 冻结契约/迁移/归属 → 并行 T40、T50、F10-KP。**第二波**：T40 的确认链与 `ConfirmedPaperReader`
  联调通过后实施 **T30-b**（T50 完成不是 T30-b 前置）。本批完成后停止，不启动 B3。

## 0. 本批不做

成绩（T60）、学情（T70）、练习（T80）、教案后端（T90）、F20 名单/原卷/成绩前端、题库新业务前端、
`POST /assessments` 以外的成绩相关接口、正式数据迁移演练。既有教案编辑/规则填充/导出保持不动。

## 1. 文件归属（未列入者不得写；公共变更提交建议给 CTRL）

| 归属 | 新建 | 修改 |
| --- | --- | --- |
| **CTRL（总控）** | `app/contracts/papers.py`、`app/contracts/assessments.py`、`apps/web/src/contracts/{papers,assessments}.ts`、`apps/web/src/contracts/question-bank.ts`（六态/关联/生成镜像）、`apps/api/tests/test_b2_migrations.py`、`apps/api/tests/test_b2_contracts.py` | `app/core/migrations/{teaching,question_bank}.py`、`app/schemas/question_bank.py`、`app/main.py`、`apps/web/src/services/navigation.ts`（页面落地后）、`docs/{API,ROUTES,PROJECT_GUIDE,CURRENT_STATUS}.md`、实施计划书、`docs/qa/TEACHING-LOOP-B2/**` |
| **T40** | `app/repositories/teaching/papers.py`；`app/services/papers/{__init__,service,imports,proposals,reader}.py`；`app/api/v1/papers.py`；`apps/api/tests/{papers_support,test_papers_import,test_papers_draft_confirm,test_papers_proposals}.py` | 无 |
| **T50** | `app/services/question_bank/generation.py`；`apps/api/tests/{test_question_generation,test_question_job_engine}.py` | `app/repositories/question_bank/catalog.py`、`app/services/question_bank/{service,organizer,validation,fingerprint,views}.py`、`app/api/v1/question_bank.py`、既有 `tests/test_question_bank*.py`（兼容性调整需逐条说明） |
| **T30-b（第二波）** | `app/repositories/teaching/assessments.py`；`app/services/assessments/{__init__,service}.py`；`app/api/v1/assessments.py`；`apps/api/tests/{assessments_support,test_assessments_api}.py` | 无 |
| **F10-KP** | `apps/web/src/app/knowledge-points/page.tsx`；`apps/web/src/features/knowledge-points/**`；`apps/web/src/services/knowledge-points-api.ts`（+`.test.ts`）；`tests/e2e/knowledge-points.spec.ts` | `apps/web/src/features/question-bank/{SuggestionPanel,ReviewWorkspace,labels}.tsx/ts`、`apps/web/src/services/question-bank-api.ts`（+其测试）= **题库六态/DTO 兼容修复** |
| **V00** | `docs/qa/TEACHING-LOOP-B2/V00-REPORT-*.md`、`V00-probes/**` | 无（只读） |

## 2. 冻结契约（实现者按此编码；类型不得复制第二份）

- `app/contracts/papers.py` + `apps/web/src/contracts/papers.ts`：草稿 PATCH（**整表替换** items/blocks/issues）、
  确认（`submissionId`）、建议读取/应用/拒绝、视图与错误码；**分值只走十进制字符串**（`maxScore`），
  服务端用 `Decimal` 转 `×100` 整数；`PaperItemInput`/`PaperItemView` 字段以契约文件为准。
- `app/contracts/assessments.py` + `apps/web/src/contracts/assessments.ts`：创建/更新/补录人次、
  参测输入（`studentId`/`classId`/`attendance`/`attemptNo`/`classConfirmed`/`classConfirmationNote`）、
  视图与错误码；`Attendance`/`ParticipantSnapshot` 复用 `app/contracts/roster.py`（不复制）。
- `app/schemas/question_bank.py` + `apps/web/src/contracts/question-bank.ts`：`OrganizeJobView` **六态 + attempt**、
  `DraftView.knowledgeLinks`、`DraftPatchRequest.knowledgeLinks`（提供即整表替换）、
  `QuestionDetail.knowledgeLinks`、`QuestionGenerationRequest`/`GenerationJobView`。
- 通用：camelCase、`expectedRevision` 守卫、`submissionId` 幂等、`ApiError.details`
  （409 带 `currentRevision`，422 带可定位 `issues[].{row,column,field,code,message}`）。

## 3. 迁移（已登记；编号与分期偏差）

| 库 | 迁移 | 内容 |
| --- | --- | --- |
| 教学库 | `0003_teaching_paper_tables` | 设计四表（papers/paper_revisions/paper_items/paper_item_knowledge，逐字）+ B2 补齐表（`paper_source_blocks`/`paper_issues`/`ai_proposals`）+ 触发器（`paper_cycle_*`、`paper_confirm`、`immutable_paper_revisions_*`、`no_direct_sealed_paper_revisions`、`freeze_paper_items_*`、`freeze_paper_item_knowledge_*`、`freeze_paper_source_blocks_*`、`freeze_paper_issues_*`） |
| 教学库 | `0004_teaching_assessment_tables` | 设计三表（assessments/assessment_classes/assessment_participants）+ `class_confirmed/class_confirmation_note/class_confirmation_at` + 触发器（`assessment_confirmed_paper_insert`、`assessment_paper_fixed`） |
| 题库 | `0004_question_knowledge_links` | 设计表 `question_knowledge_links`（逐字 + 不可变触发器）+ `question_draft_knowledge_links`、`question_import_provenance`、`question_content_fingerprints` |

**分期偏差（不得私改，见迁移文件 docstring）**：`paper_revisions.source_file_id` NOT NULL；
`source_practice_revision_id` 与 `assessments.active_score_revision_id` 保留列 + `CHECK(... IS NULL)` 且**无外键**
（未来表属 B3）；`paper_revisions.total_score_units >= 0`（草稿容差，确认闸门要求 >0 且等于叶子合计）；
`paper_confirm` 无 `PRACTICE_NOT_REVIEWED` 分支。B0/B1 已登记声明与散列不得改写。

## 4. HTTP 接口（`/api/v1` 前缀；详细语义见第 5–7 节）

| 模块 | 接口 |
| --- | --- |
| 原卷（T40） | `POST /paper-imports`（multipart DOCX + subjectId/title）、`GET /papers`（列表筛选）、`GET /papers/{id}`、`PATCH /papers/{id}/draft`、`POST /papers/{id}/confirm`、`GET /papers/{id}/revisions/{revisionId}/content`、`POST /papers/{id}/knowledge-proposals`、`GET /paper-proposals/{id}`、`POST /paper-proposals/{id}/apply`、`POST /paper-proposals/{id}/reject` |
| 题库（T50） | 既有全部路由保持；新增 `POST /question-generation-jobs`；`PATCH /question-drafts/{id}` 接受 `knowledgeLinks`；`GET /questions` 支持 `knowledgePointId` 筛选；`OrganizeJobView` 六态 + attempt |
| 施测（T30-b） | `GET/POST /assessments`、`GET /assessments/{id}`、`PATCH /assessments/{id}`、`POST /assessments/{id}/participants`（补录人次） |

## 5. T40 关键行为（逐条有测试）

1. 导入：T10 `parse_docx_rich` → 全部块持久化（顺序/定位/真实图片字节与尺寸/OMML/合并表格/共同材料）；
   块默认 `unassigned`；规则候选拆题（题号/容器/计分叶子）；解析告警与未知对象进 `paper_issues`（**可无 block_id，用 locator 定位**）。
2. 草稿 PATCH：整表替换，`expectedRevision`= `papers.revision`；`papers.revision` 同事务 +1；校验题号唯一、
   父子同卷无环、只有叶子计分、`maxScore` 十进制 ≤2 位小数且 >0、知识点关联同库存在且同学科未归档（跨库读经 PublicationCoordinator）。
3. 确认：同一事务；闸门 = submission 重放 → draft 归属 → 唯一题号 → 无环 → 仅叶子计分 → 每个计分叶有知识点 →
   叶分合计=总分>0 → **所有块已归属或有排除理由** → **无 open 的 blocking issue**；然后置 confirmed、
   更新 `papers.current_revision_id`、`papers.revision+1`、写 submission 结果。
4. 确认后不可变：DB 触发器 + 服务双重保护；**改已确认卷 = 新建修订**（version+1，draft），旧修订与旧施测不变。
5. AI 建议（`teaching:paper_mapping` 经 B0 任务引擎，`uses_model=True`）：冻结草稿版本/计分叶子/允许知识点/模型指纹；
   输出校验（非法 JSON/截断/未知知识点/证据不在允许集合）；候选只进 `ai_proposals`（pending）；
   应用前复核 `papers.revision`（过期 → stale 409）；新知识点走 T20 候选确认后**单独绑定**（第二步失败可重试）。
6. `ConfirmedPaperReader` adapter（`app/services/papers/reader.py`）：只返回 **已 confirmed** 修订，
   校验总分 >0 与计分叶子 ≥1，返回真实标题/学科/计数；T30-b 必须用它。

## 6. T50 关键行为（逐条有测试）

1. 草稿关联：`PATCH /question-drafts/{id}` 的 `knowledgeLinks`（提供即整表替换）；内容或关联变化都 `revision+1` 且回 `needs_review`；
   知识点校验走公共发布路径（同学科、未归档、修订一致）。
2. 正式关联：确认入库时把草稿关联冻结为 `question_knowledge_links`（含 `subject_id_snapshot`/名称快照）；
   `patch_question` 内容修改 → 新修订 + **复制旧正式关联**；明确改关联 → 新修订 + 替换关联；
   旧修订与旧关联不可改（DB 触发器）。
3. 按知识点检索：`GET /questions?knowledgePointId=`。
4. 生成（`question:generate` 经任务引擎，`uses_model=True`）：独立 `GenerateReply`（不复用 organizer 的 sourceBlockIds 解析器）；
   冻结允许知识点/证据/题型/难度/数量/模型指纹；校验未知 ID、虚构依据、任意 URL/路径/越权资产；
   生成原件写 `question_import_provenance(source='ai', model_snapshot)`；候选建 `needs_review` 草稿并保存草稿关联；
   **批次/候选/来源/任务 succeeded 同库同事务**。
5. 统一任务：把组织器接上 B0 JobEngine（租约/心跳/attempt/取消/重试/重启 running→interrupted），
   消除双执行者（旧 `pending_jobs`/`recover` 路径退役或改为只读兼容）；保留旧 URL 与响应形状（六态 + attempt）；
   历史 checkpoint 继续可恢复；旧语义 checkpoint → 明确 `ORGANIZER_MODEL_RESELECT_REQUIRED`（不伪造冻结指纹）。
6. 指纹：旧 `content_fingerprint` 不动；新增版本化派生指纹（算法版本 + 共同材料/富内容/资产真实字节散列）
   写 `question_content_fingerprints`。
7. 取消/失权/旧 attempt 迟到/发布回滚：不得留下可发布的半批结果；`200 + failures 非空` 仍表示整批未确认。

## 7. F10-KP 关键行为

- `/knowledge-points` 薄路由 + `features/knowledge-points/**`：学科筛选、列表/父树、详情、建立/更新（`clearFields`）、
  别名、归档/恢复、教材依据（不可用 → 错误而非"没有依据"）、XLSX/CSV 预览/映射/行校对/整批确认、
  AI 候选（`workflow-jobs` 公共客户端 + `observeJob` 守卫 jobId/attempt，离开页面停止轮询）。
- 候选与正式知识点明显区分；409/422 定位可操作；保存失败保留编辑；迟到响应不污染当前对象。
- **题库六态兼容修复**：`SuggestionPanel`/`ReviewWorkspace`/`labels` 支持 `interrupted` 横幅与显式 retry
  （用 `workflow-jobs-api` 的 `retryJob`/`observeJob`），不改题库其他交互。
- 视口 1440×900 / 1920×1080 / 390×844 + reduced-motion；遵循 `apps/web/AGENTS.md`（含读 Next 16.3.4 本地文档）。

## 8. T30-b 关键行为（第二波）

只用已确认修订（DB 触发器 + reader + 服务）；参测姓名/学号从 `students` 读取后冻结（不信任客户端快照，不一致给定位错误）；
`heldOn` 合法日历日期；`classIds` 存在且未归档；每行 `classId` ∈ `classIds`；历史归属未覆盖 `heldOn` →
422 `PARTICIPANT_CLASS_UNCONFIRMED`（逐行 issues），教师带 `classConfirmed`+依据重提后冻结；
空 participants 422；`attemptNo` 缺省 1、补考新增下一人次、`(assessment,student,attempt)` 唯一；
同学生首次跨班重复必须人工选定；创建/班级范围/人次/幂等结果同库同事务；不写成绩、不生成学情。

## 9. 验收条件

| 编号 | 条件 | 责任 | 证据 |
| --- | --- | --- | --- |
| A1 | B2 迁移：新库/B0 库/B1 库三路径幂等 + 中途失败回滚 + `foreign_key_check`；B0/B1 已登记散列不变 | CTRL | `test_b2_migrations.py` |
| A2 | 契约：Python/TS 双侧一致；分值十进制解析边界；`EvaluationDetails` 形状 | CTRL | `test_b2_contracts.py` + typecheck |
| A3 | T40：导入块/定位/图片/OMML/未知对象；草稿校验（唯一题号/环/叶子计分/分值/知识点）| T40 | `test_papers_import.py`、`test_papers_draft_confirm.py` |
| A4 | T40：确认闸门（块归属/排除理由/blocking issue/总分/知识点）与确认后不可变（UPDATE/DELETE 绕过被拒） | T40 | 同上 |
| A5 | T40：AI 建议四类非法 + 过期 stale + 应用后绑定；reader 只放 confirmed | T40 | `test_papers_proposals.py` |
| A6 | T50：关联保留/替换、检索、指纹版本化、旧流程回归 | T50 | `test_question_bank*.py` |
| A7 | T50：生成链（独立 GenerateReply、校验、同库事务、失败回滚）+ 统一任务（六态/取消/失权/重启收敛） | T50 | `test_question_generation.py`、`test_question_job_engine.py` |
| A8 | T30-b：施测闸门/快照冻结/班级确认/人次/幂等/整批回滚 + 名单→原卷→施测集成 | T30-b | `test_assessments_api.py` |
| A9 | F10-KP：页面端到端（编辑/导入/候选/错误/冲突/键盘/移动/reduced-motion）+ E2E | F10-KP | 组件测试 + `knowledge-points.spec.ts` |
| A10 | 工程：定向 pytest + 全量 `test:api` + `npm run check` + `build` + `test:e2e`（隔离 5174） | CTRL | EVIDENCE-COMMANDS |
| A11 | 独立验收 V00：契约/迁移/失败路径/真实装配自建探针 + 变异实验 | V00 | `V00-REPORT-01.md` |

## 10. 测试资源与结果格式

- 一切先设 `ZQKY_DATA_DIR` 再 import `app.main`；DOCX 样本程序化构造（含共同材料/两级小题/合并表格/图片/行内+独立公式）；
  模型受控替身；端口隔离（API 8001 / Web 5174）；不碰正式 `.local-data`。
- 结果格式同 B0/B1（任务 ID/版本、起点 SHA、可写范围、实际修改文件、正常路径、失败取消重试恢复、
  兼容与迁移、验证命令+退出码+证据、首败与修复、未执行及原因、剩余问题、资源释放、状态 ready_for_review）。

## 11. 预先登记的风险

1. `paper_revisions.total_score_units>=0` 是草稿容差（设计为 >0）；确认闸门在服务与触发器双重保证 >0。
2. `source_practice_revision_id`/`active_score_revision_id` 本批只允许空，B3 补齐外键与写入能力（必要时受检重建表）。
3. `ai_proposals` 未被冻结触发器保护（设计无此触发器）；对已确认修订的 apply 由服务拒绝。
4. T50 统一任务接入会触碰既有组织器测试（running/checkpoint 语义）；兼容性调整必须逐条说明并保留旧 URL 行为。
5. 名单导入日 ≠ 入班日是**正常场景**（今日导入、分析过去考试）：以教师显式确认 + 依据落库放行，不阻断、不改历史。
6. 台账间歇项（R-14/R-15/R-18/R-19）按 CURRENT_STATUS 口径记录，不"修"不放宽。
7. DOCX 视觉排版（Word/WPS）与真实模型质量 not_run；结构断言不写排版通过，替身不写质量通过。
8. **V00 r1 登记的 observation（不判 fail，B3 统一处置）**：原卷域"发布失败后任务停在 `running`"（业务零残留、`PAPER_PROPOSAL_STALE` 真实抛出；与 T50 的 question 域收尾不同，建议 B3 统一到引擎级）；错误码命名映射（`GENERATION_*` 五个实际码以 `generation.py` 为准）；`KnowledgePointView.id` 口径（`pointId` 不存在）。
9. `ParticipantMutationResult` 只返回本次新增人次；`ASSESSMENT_REVISION_STALE` 为施测域专用码；正式关联无 `source` 列（设计逐字）。
