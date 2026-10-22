# API 契约

更新：2026-10-20（归档功能全局移除：所有 `archive/restore` 端点删除，题库 DELETE 改为物理删除；知识点 DELETE 改为整棵子树）。未列出的 `/api/v1/*` 返回 501
`FEATURE_NOT_IMPLEMENTED`（域已装配但依赖缺失时返回 503 `SERVICE_UNAVAILABLE`，绝不假成功）。

## 公共

| 方法和路径 | 用途 |
| --- | --- |
| GET `/api/v1/health` | 健康检查 |
| GET `/api/v1/capabilities` | 能力清单（随域装配动态汇报） |
| GET/POST `/api/v1/workflow-jobs/{id}`、`/{id}/cancel`、`/{id}/retry` | 任务观察/取消/重试（`?domain=knowledge|question|teaching`；执行器注册表调度） |
| GET `/api/v1/export-artifacts/{id}`、`/{id}/download` | 导出产物读取与下载（练习链走 `export_artifacts` 表；分析报告/教案产物按 `file_assets(kind=export)` 身份读取） |

## 模型配置

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/model-providers` | 供应商目录（38 条注册表） |
| `/api/v1/model-connections`（GET/POST/PUT/DELETE） | 连接 CRUD；凭证经 SecretStore（响应只返回凭证状态，不回显明文） |
| `/api/v1/model-connections/{id}/auth/{start,cancel,logout}` | OAuth 受管认证（Codex/Copilot） |
| `/api/v1/model-catalog`、`/model-defaults`、`/model-connections/{id}/models` | 模型清单与默认配置；发现条目透传 `contextLength/maxOutputTokens/supportedParameters/capabilities`；`reasoningSupport` 带 `selectable`（除档案显式关闭思考外恒为 true，未验证模型也保留档位控件）；`contextWindow.source` 为 `profile/model/model-table/unknown` |
| POST `/api/v1/model-metadata/preview` | 只读预览单个模型的自动元数据（`connectionId + modelId`），不写档案；供新建档案表单填充 |
| POST `/api/v1/model-profiles/{id}/refresh-metadata` | 自动读取并写回上下文/输出上限（已有值按用户策略覆盖，返回 `changes` 的 old→new 与来源）；`?force=true` 强制刷新 models.dev 缓存 |
| POST `/api/v1/model-metadata/refresh` | 批量刷新：`{profileIds?, connectionId?, force?}`；catalog 只拉一次、每个连接只发现一次，返回逐模型 `changes` 与汇总 |
| POST `/api/v1/model-profiles/{id}/refresh-context` | 兼容旧前端的上下文刷新别名（内部转调 refresh-metadata，只返回上下文部分） |
| `/api/v1/model-profiles`（CRUD + `/{id}/test`） | 模型档案与真实连接测试 |

**模型元数据来源优先级**：供应商 `/models` → models.dev 公开目录（`https://models.dev/api.json`，24h 本地缓存，失败回退过期缓存）→ 内置精确模型表 → 模型族暂估（仅展示，不写回）。缓存只含公开元数据，不含凭证；`ZQKY_MODELS_DEV_URL` 可覆盖目录地址，置空禁用远端。

## 对话与 Agent

| 方法和路径 | 用途 | 事件 / 说明 |
| --- | --- | --- |
| POST `/api/v1/chat/stream` | 普通对话 SSE（三协议适配） | `message.start / text.delta / reasoning.delta / usage / message.end / error` |
| POST `/api/v1/agent/stream` | Agent 对话 SSE（LangGraph 编排，21 工具） | `message.start / text.delta / tool.call / tool.result / usage / wait-confirm / message.end / error`；`attachments` 上传引用；`reasoningEffort` 本轮覆盖。`usage` 为供应商返回的真实 token（`inputTokens`=最近一次模型调用的上下文快照，`outputTokens`=本轮累计，另含 `totalTokens/cachedInputTokens`）；工具内部 LLM 的用量不计入。事件上限只计控制流事件（流式 token 不计），长回答不会被误判为 `AGENT_EVENT_OVERFLOW` |
| POST `/api/v1/agent/confirm` | 写操作确认（`Command(resume)` 恢复中断） | `submissionId` 幂等；`reasoningEffort` 可选，续跑沿用触发该卡的思考强度 |
| POST `/api/v1/agent/upload` | 上传落受管 blob（内容寻址 sha256） | multipart；上限 100 MiB |

**模型接入**：Agent 与全部模块 LLM 调用统一经 LangChain 官方包；凭证只经后端 `SecretStore`
**显式注入**（本地免 Key 用占位符），构造前断言 `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` 进程环境未设置；
受管认证（Codex/Copilot/CodeBuddy）暂不可用于 Agent/模块（`AGENT_MODEL_UNSUPPORTED`），可用于
`/chat/stream` 直连。Agent 会话/中断状态经 checkpointer 落 `data/agent/agent_checkpoints.sqlite3`。

**对话内生成教案**：工具表新增 `list_subjects`（学科字典）与 `create_lesson_plan_draft`
（缺学科/班级时先经 `list_subjects` / `confirm_context(need=subject|class)` 补齐；工具内部
`interrupt` 弹写确认卡，确认后按教学分析/目标/策略/过程/练习/评价/反思七模块生成正文，
经 `LessonPlanService.create_lesson` 写入第 1 版教案草稿）。生成是 7 个小结构化调用并行
（同时 3 路），单模块 120s、最多 2 次尝试；部分模块失败仍保存成功部分并在工具回执中列出缺失模块。
`apply_lesson_proposal` 同步修正为 async + 完整 `expectedRevision/baseRevisionId/selectedFields` 请求体。
工具内部的七模块生成调用带 `INTERNAL_TOOL_LLM_TAG` 且不继承外层流回调；Agent 运行器过滤这些嵌套
`on_chat_model_stream` 事件——聊天里只出现工具回执与最终摘要，不出现模块 JSON 原文。

## 教材资料库（textbooks 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/textbook-taxonomy`、`/textbook-libraries*`、`/textbooks*` | 分类字典、逻辑库与文档 CRUD（`GET /textbooks/{id}`、PATCH 元数据、DELETE）。逻辑库 = 教材册的归属/检索范围容器（`kind`=基础库/我的教材 + 学科 + 版本 + 可选年级，书册与库多对多）；界面入口：教材资料库页头「新建逻辑库」+ 导入面板第 4 步「加入逻辑库」（至少一个） |
| POST `/api/v1/textbook-imports` → `/{id}/commit`、`/{id}/discard` | 导入草稿 → 封存修订并入库；`/textbook-imports/{id}` 观察状态 |
| `/api/v1/textbook-jobs*`（GET/cancel/retry）、`/textbook-index/status`、`/textbook-index/rebuilds` | 入库任务与索引代状态/受控重建 |
| `/api/v1/textbook-revisions/{id}/source` | 修订原文区间读取（指纹校验） |
| `/api/v1/embedding-models`（GET/probe）、`/embedding-profiles*` | 本机 Ollama 嵌入模型清单与真实探测 / 嵌入档案（配置）建立、停用、受守卫删除 |
| `/api/v1/textbook-index/status`、`/textbook-index/rebuilds` | 索引代状态（代/档案/Qdrant/可检索范围/重建任务）与受控重建（换模型/重算全量）。**空库首启不自动建代**：先建嵌入档案，再发起一次重建发布起始（空）索引代，之后「提交入库」才可用（否则 409 `INDEX_NOT_READY`）；界面入口：教材资料库页头「索引与嵌入」 |

## 知识点（knowledge 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/knowledge-points`（GET/POST）、`/{id}`（GET/PATCH/DELETE） | 列表（`scope=subject|taught`、subjectId/关键词；**`status` 过滤已移除**，归档数据已归一化）与节点 CRUD（含 `objectives` 学习目标；空白=不修改，`clearFields` 显式清空）。`DELETE ?expectedRevision=N` **删除整棵子树**（物理删除，不可恢复）；子树内任一节点有教材依据/原卷/题库引用 → 409 `KNOWLEDGE_POINT_IN_USE`，`details.points` 逐节点给 `pointId/name/total/counts`，`details.subtreeSize` 为节点数；导入预览行的 `targetKnowledgePointId` 在同一事务置空 |
| `/{id}/textbook-links` | 教材依据链接（归档/恢复端点已于 2026-10-20 移除） |
| POST `/api/v1/knowledge-points/tree-from-textbook` | 教材目录成树（幂等；水印与纯符号标题段透明过滤；R11：口径改为读取**封存正文的 Markdown 标题**（`heading_paths`）而非分块 `chapter_path`；习题/复习参考题/章末类标题段透明、不建节点，判定复用 `regions.is_exercise_marker_line`；原文阅读器未装配或原文不可读 → 503，不静默少算） |
| `/api/v1/knowledge-imports*`、`/knowledge-extraction/preview`、`/knowledge-extraction-jobs`、`/knowledge-suggestion-jobs` | 表格导入两阶段确认、教材抽取预览、AI 候选任务；``POST /{id}/discard`` 放弃（置 cancelled，记录保留）与 **``DELETE /{id}`` 彻底删除批次+预览行**（任何状态可删，含已确认；已入库知识点/教材依据保留 —— R10 2026-10-13 用户裁定「批次只是导入记录」） |

## 题库（question_bank 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/question-imports*`（含 POST `/question-imports/from-textbook`） | 导入草稿；从教材课后习题提取（无习题 422 `TEXTBOOK_EXERCISES_EMPTY`） |
| `/question-drafts/{id}`、`/question-imports/{id}/{split,merge,organize}`、`/question-suggestions/{id}/apply` | 草稿编辑/拆分/合并/AI 整理与应用（AI 整理经 `run_structured`，供应商不支持 `json_schema` 时自动降级 `json_mode`）。**2026-10-13 一键整理并绑定**：`POST .../organize` 请求体新增 `autoApply`（默认 `false`）——`true` 时整理结果（内容 + 知识点库绑定，提示词 v2）在同一事务直接写入草稿（建议落 `applied`），教师只做多选入库；`false` 仍只产生 `pending` 建议。草稿**改学科**且未显式给 `knowledgeLinks` 时，旧关联（含 AI 绑定）自动清空并写 `warnings` 留言（正式题 `PATCH /questions/{id}` 仍 422 `KNOWLEDGE_REFERENCE_INVALID` 要求显式处置） |
| `DELETE /question-imports/{id}` | 彻底删除导入批次与解析产物。R10：**任何状态可删**（含已确认、含"草稿已并入正式题"）；题目一律保留——`question_sources.import_id` 置空（来源跨度保留，回执 `unlinkedQuestionSources`），批次自身的原文块/草稿/建议/并入记录/生成来源随批次删除 |
| `/question-imports/{id}/confirm` | 教师确认 → 正式题目入库（发布边界）。**2026-10-13「多选即确认」**：只拦 `excluded` 草稿（`DRAFT_EXCLUDED`）；未标记 `reviewed`（旧 `DRAFT_NOT_REVIEWED`）与缺答案（旧 `MISSING_ANSWER_NOT_ACKNOWLEDGED`）都不再阻断，缺答案以 `answerState=not_provided` 落库 |
| GET `/api/v1/questions`（`knowledgePointId`、`difficulty=easy|medium|hard|unspecified`、`q`）、`/questions/{id}`（GET/PATCH/DELETE） | 题目库查询与维护。`DELETE ?expectedRevision=N` 为**物理删除**（题目、修订、知识点关联、来源、内容指纹一并删除；任务/提交历史保留）；被审核练习或教案生成固定输入引用 → 409 `QUESTION_IN_USE` + `details.counts={practices, lessonFixedQuestions}`。归档/恢复语义已移除 |
| POST `/api/v1/question-generation-jobs` | AI 补题（needs_review 草稿） |

## 班级/名单/试卷/施测（teaching 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/classes*`、`/students*`（CRUD、transfer、batch） | 班级与学生管理（`gender` 可空存原文）；**archive/restore 端点已移除**（2026-10-20），删除是唯一出口。`students.status='archived'` 仅作为「有历史成绩已移除」的内部状态保留（删除回执 `removed_with_history`、名单导入可重新关联），不再作为归档功能暴露 |
| `/api/v1/roster-imports*`（`/{id}/confirm|discard`） | 名单 xlsx/csv 导入两阶段（含「性别」列表头映射） |
| POST `/api/v1/paper-imports`、`/api/v1/papers*` | 试卷导入（DOCX/PDF 文本层规则拆题，草稿→确认）/列表/修订/删除 |
| GET `/api/v1/papers/{id}/knowledge-distribution` | 知识点占比（环图数据；primary 聚合） |
| `/api/v1/paper-proposals/{id}`（GET/apply/reject） | AI 分类提案（只进 ai_proposals、应用复核 stale、只建 ai_confirmed） |
| `/api/v1/assessments*` | 施测（班级×试卷）创建/参与者/出缺席（创建界面入口：学情分析页「新建施测」——选已确认原卷 + 班级，参测名单取该班在册学生；2026-10-13 补齐） |

## 成绩与学情（teaching 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/score-imports*`（`PATCH` 列映射、`refresh`、`confirm`、`discard`） | 小题分成绩单导入（表头识别+人工确认；四态 recorded/missing/absent/exempt 不补零） |
| `/api/v1/score-revisions/{id}`、`/{id}/matrix` | 成绩版本与矩阵（按行列定位校正） |
| POST `/api/v1/assessments/{id}/analysis-runs`、`/analysis-runs*` | 学情报告创建/列表/删除、教师备注（创建界面入口：学情分析页「生成学情报告」——已确认成绩修订 + 该修订 `participantSnapshot` 的人次；同输入复用、同标识重放；2026-10-13 补齐；**归档/恢复端点已于 2026-10-20 移除**） |

## 删除语义（2026-10-20 全局移除归档；沿 R10-BE「只留删除」+「拆开交叉引用」）

**2026-10-20 变更**：所有 `archive/restore` 端点已删除（知识点/班级/学生/试卷/施测/学情报告/教案/练习）；
旧库归档数据由 `apps/api/scripts/normalize_archives.py` 归一（恢复 normal，题库 archived 题物理删除）；
`students.status='archived'` 仅保留为「有历史成绩已移除」的内部状态。题库 `DELETE /questions/{id}`
不再是归档，改为物理删除。

**总原则**：删除一个实体 = 删除它自己拥有的行（结构 + 自身审计历史）；对指向它的引用，
**下游产物级联删除，独立资产置空/409 逐项列出**。所有级联都在单个写事务内完成
（`BEGIN IMMEDIATE` + 延迟外键），任一步失败整体回滚；不可变兜底触发器在事务内按
`sqlite_master` 原文摘除、末尾逐字恢复（`repositories/teaching/triggers.py`）。

| 删除对象 | 级联（随行删除） | 置空 | 409 逐项列出（不可删） |
| --- | --- | --- | --- |
| `DELETE /knowledge-points/{id}?expectedRevision=N` | **整棵子树**的知识点身份行、别名、修订；导入预览行的 `targetKnowledgePointId` | — | 子树内任一节点有教材依据/原卷题目/题库正式或草稿关联 → `KNOWLEDGE_POINT_IN_USE` + `details.points`（逐节点） |
| `DELETE /questions/{id}?expectedRevision=N` | 题目、全部修订、知识点关联、来源跨度、内容指纹；草稿 `duplicateOfQuestionId` 指针 | — | 被审核练习固定题/教案生成冻结输入引用 → `QUESTION_IN_USE` + `counts` |
| `DELETE /students/{id}?expectedRevision=N` | 无参测引用：归属记录 + 学生行；名单导入匹配指针置空 | — | 无（有历史成绩 → 200 `removed_with_history`：关归属 + 身份已移除，成绩保留） |
| `DELETE /classes/{id}?expectedRevision=N` | 归属、名单批次（+预览行）、**无参测人次的**参测范围行；无归属且无参测引用的学生行 | — | 该班有**参测人次**（成绩链证据）、有**教案**/教案生成输入 → `CLASS_IN_USE` + counts |
| `DELETE /papers/{id}?expectedRevision=N` | 全部修订（含已确认）+ 小题/知识点/原文块/处置问题/AI 提案 | — | 被施测引用 → `PAPER_IN_USE`（先删施测） |
| `DELETE /assessments/{id}?expectedRevision=N` | **自有成绩链**：参测人次、成绩导入（+行）、成绩修订（+小题分/修正）、报告（+冻结子表）、派生练习（连带历史）、转换/映射、成绩模板导出（+工件）、参测范围（界面入口：学情分析页「删除该施测」） | — | 链上报告被教案冻结生成血缘引用 → `ASSESSMENT_IN_USE` + counts |
| `DELETE /analysis-runs/{id}` | 报告六张冻结子表；**派生练习集连带历史**（reviewed 修订/导出/转换/工件） | 教案修订的 `analysis_run_id` 来源指针 | 报告被 `lesson_generation_inputs`/`lesson_ai_proposals`（NOT NULL 冷冻血缘）引用 → `ANALYSIS_RUN_IN_USE` + counts |
| `DELETE /practice-sets/{id}?expectedRevision=N[&includeHistory=true]` | 草稿修订链；`includeHistory=true` 时连同 reviewed 修订/导出/工件/转换/映射 | 转换生成的原卷修订的来源指针 | 默认路径有 reviewed 修订/导出/转换 → `PRACTICE_IN_USE`（回执给出 `includeHistory` 路径） |

**成绩链保护策略（调研结论）**：成绩链的所有者是**施测**——`assessment_participants`（证据锚点）
→ 导入 → 成绩修订 → 小题分 → 报告 → 派生练习。因此删除施测 = 删除这条链（唯一的显式销毁入口）；
其它实体（班级/学生/试卷/报告/练习）的删除**永不静默销毁学生成绩**：能拆的引用置空、自身产物随行，
剩下的按 409 逐项列出并给出可执行下一步。**保留不动**（不属于任何删除链）：`file_assets`（受管资产
blob）、`workflow_jobs`（任务历史）、`command_submissions`（提交幂等记录）。
| GET `/analysis-runs/{id}/item-stats` | 小题得分率（题号×班级） |
| GET `/analysis-runs/{id}/knowledge-stats` `/student-knowledge` `/distribution` | 知识点得分率排行 / 学生×知识点矩阵（代称脱敏、null=无依据）/ 分数段分布（学生级低<60 / 中60–85 / 高≥85） |
| POST `/analysis-runs/{id}/ai-commentary` | AI 评价候选（`{commentary, degraded, reason}`；降级不为错误） |
| POST `/analysis-runs/{id}/report` | 生成分析报告 docx 产物（201 → 下载走 export-artifacts） |

## 教案（teaching 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/lesson-plans`（GET/POST）、`/{id}`（GET/PATCH draft/DELETE）、`/{id}/revisions` | 教案草稿/修订（CAS `expectedRevision`；草稿与候选分离）。`POST` 必填 `subjectId`/`classId`（教案必属某班某科）与 `context` 键（手工新建显式 `null`，缺键 422）；`DELETE ?expectedRevision=N` 彻底删除教案自身历史（**归档/恢复端点已于 2026-10-20 移除**，界面只留删除，入口在教案工作台「本地教案」） |
| POST `/api/v1/lesson-plans/generation-stream` | 逐模块流式生成（SSE：`message.start / module.start / module.delta / module.error / module.done / message.end / error`；生成候选采用才写入）。固定数据来源：`analysisRunId`（学情报告匿名聚合）与 **`sourceAssetRef`**（教师上传的学情材料，2026-10-13 起真正消费：读回文本按 6000 字上限截断并标注；引用读不到 → 404 `LESSON_SOURCE_NOT_FOUND`，**不静默忽略**） |
| `/api/v1/lesson-plans/{id}/proposals`（+`/{pid}/apply|reject`） | 五字段 patch 候选（`apply_lesson_proposal` 工具带中断确认） |
| POST `/api/v1/lesson-plans/{id}/export` | 导出 docx（202）：以空白模板组装，自动补齐封面（第 1 页）+ 目录（第 2 页），正文自第 3 页 |
| POST `/api/v1/lesson-plans/source-uploads` | 上传学情材料（multipart `file`）→ 201 `{assetRef,fileName,mediaType,byteSize,sha256}`（受管资产 `kind=attachment`）。**只收可提取文本的文档**（.docx/.pdf/.txt/.md）；成绩表类（.xlsx/.xls/.csv）422 `LESSON_SOURCE_UNSUPPORTED` 并指引「先去学情分析生成报告、再用『分析报告』来源」（学生个人信息不进模型的红线：不把含学号/姓名的原始表格送模型）；空文件 422、超限（10 MiB）413；无可提取文本（扫描件）422 `LESSON_SOURCE_EMPTY` |
| `/api/v1/lesson-plans/evidence/verify` | 教材依据核验 |

## 练习（teaching 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/practice-sets`（GET/POST）、`/{id}`（GET/draft PATCH/review） | 练习集创建（来源=学情报告/描述驱动）、草稿、审核（未审核不可导出） |
| `/{id}/suggestions`、`/{id}/revisions*` | 按需巩固知识点选拔、修订 |
| POST `/{id}/revisions/{rid}/exports` | 学生卷/教师卷 docx + 成绩模板 xlsx（202 任务 → 产物下载） |
| POST `/{id}/revisions/{rid}/assessments`、DELETE `/{id}/revisions/{rid}/conversion` | 回流：练习 → 原卷修订 + 施测（含映射表）；删除边界守卫 |
