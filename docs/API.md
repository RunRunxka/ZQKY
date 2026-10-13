# API 契约

更新：2026-10-13（R10-BE 删除语义：舍弃归档、拆开交叉引用）。未列出的 `/api/v1/*` 返回 501
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
| `/api/v1/model-catalog`、`/model-defaults`、`/model-connections/{id}/models` | 模型清单（含上游上下文长度/受支持参数透传）与默认配置 |
| `/api/v1/model-profiles`（CRUD + `/{id}/test`） | 模型档案与真实连接测试 |

## 对话与 Agent

| 方法和路径 | 用途 | 事件 / 说明 |
| --- | --- | --- |
| POST `/api/v1/chat/stream` | 普通对话 SSE（三协议适配） | `message.start / text.delta / reasoning.delta / usage / message.end / error` |
| POST `/api/v1/agent/stream` | Agent 对话 SSE（LangGraph 编排，19 工具） | `message.start / text.delta / tool.call / tool.result / wait-confirm / message.end / error`；`attachments` 上传引用；`reasoningEffort` 本轮覆盖 |
| POST `/api/v1/agent/confirm` | 写操作确认（`Command(resume)` 恢复中断） | `submissionId` 幂等 |
| POST `/api/v1/agent/upload` | 上传落受管 blob（内容寻址 sha256） | multipart；上限 100 MiB |

**模型接入**：Agent 与全部模块 LLM 调用统一经 LangChain 官方包；凭证只经后端 `SecretStore`
**显式注入**（本地免 Key 用占位符），构造前断言 `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` 进程环境未设置；
受管认证（Codex/Copilot/CodeBuddy）暂不可用于 Agent/模块（`AGENT_MODEL_UNSUPPORTED`），可用于
`/chat/stream` 直连。Agent 会话/中断状态经 checkpointer 落 `data/agent/agent_checkpoints.sqlite3`。

## 教材资料库（textbooks 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/textbook-taxonomy`、`/textbook-libraries*`、`/textbooks*` | 分类字典、逻辑库与文档 CRUD（`GET /textbooks/{id}`、PATCH 元数据、DELETE） |
| POST `/api/v1/textbook-imports` → `/{id}/commit`、`/{id}/discard` | 导入草稿 → 封存修订并入库；`/textbook-imports/{id}` 观察状态 |
| `/api/v1/textbook-jobs*`（GET/cancel/retry）、`/textbook-index/status`、`/textbook-index/rebuilds` | 入库任务与索引代状态/受控重建 |
| `/api/v1/textbook-revisions/{id}/source` | 修订原文区间读取（指纹校验） |
| `/api/v1/embedding-models`（GET/probe） | 本机 Ollama 嵌入模型清单与探测 |

## 知识点（knowledge 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/knowledge-points`（GET/POST）、`/{id}`（GET/PATCH/DELETE） | 列表（`scope=subject|taught`、subjectId/status/关键词）与节点 CRUD（含 `objectives` 学习目标；空白=不修改，`clearFields` 显式清空） |
| `/{id}/archive`、`/{id}/restore`、`/{id}/textbook-links` | 归档/恢复、教材依据链接 |
| POST `/api/v1/knowledge-points/tree-from-textbook` | 教材目录成树（幂等；水印与纯符号标题段透明过滤） |
| `/api/v1/knowledge-imports*`、`/knowledge-extraction/preview`、`/knowledge-extraction-jobs`、`/knowledge-suggestion-jobs` | 表格导入两阶段确认、教材抽取预览、AI 候选任务 |

## 题库（question_bank 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/question-imports*`（含 POST `/question-imports/from-textbook`） | 导入草稿；从教材课后习题提取（无习题 422 `TEXTBOOK_EXERCISES_EMPTY`） |
| `/question-drafts/{id}`、`/question-imports/{id}/{split,merge,organize}`、`/question-suggestions/{id}/apply` | 草稿编辑/拆分/合并/AI 整理与应用 |
| `/question-imports/{id}/confirm` | 教师确认 → 正式题目入库（发布边界） |
| GET `/api/v1/questions`（`knowledgePointId`、`difficulty=easy|medium|hard|unspecified`、`q`）、`/questions/{id}`（GET/PATCH/DELETE） | 题目库查询与维护 |
| POST `/api/v1/question-generation-jobs` | AI 补题（needs_review 草稿） |

## 班级/名单/试卷/施测（teaching 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/classes*`、`/students*`（CRUD、archive/restore、transfer、batch） | 班级与学生管理（`gender` 可空存原文）；归档端点保留为历史数据兼容（界面与客户端已无入口），**删除是唯一出口** |
| `/api/v1/roster-imports*`（`/{id}/confirm|discard`） | 名单 xlsx/csv 导入两阶段（含「性别」列表头映射） |
| POST `/api/v1/paper-imports`、`/api/v1/papers*` | 试卷导入（DOCX/PDF 文本层规则拆题，草稿→确认）/列表/修订/删除 |
| GET `/api/v1/papers/{id}/knowledge-distribution` | 知识点占比（环图数据；primary 聚合） |
| `/api/v1/paper-proposals/{id}`（GET/apply/reject） | AI 分类提案（只进 ai_proposals、应用复核 stale、只建 ai_confirmed） |
| `/api/v1/assessments*` | 施测（班级×试卷）创建/参与者/出缺席 |

## 成绩与学情（teaching 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/score-imports*`（`PATCH` 列映射、`refresh`、`confirm`、`discard`） | 小题分成绩单导入（表头识别+人工确认；四态 recorded/missing/absent/exempt 不补零） |
| `/api/v1/score-revisions/{id}`、`/{id}/matrix` | 成绩版本与矩阵（按行列定位校正） |
| POST `/api/v1/assessments/{id}/analysis-runs`、`/analysis-runs*` | 学情报告创建/列表/归档/删除、教师备注 |

## 删除语义（R10-BE，2026-10-13 用户裁定「舍弃所有归档功能，只留删除」+「拆开交叉引用」）

**总原则**：删除一个实体 = 删除它自己拥有的行（结构 + 自身审计历史）；对指向它的引用，
**下游产物级联删除，独立资产置空/409 逐项列出**。所有级联都在单个写事务内完成
（`BEGIN IMMEDIATE` + 延迟外键），任一步失败整体回滚；不可变兜底触发器在事务内按
`sqlite_master` 原文摘除、末尾逐字恢复（`repositories/teaching/triggers.py`）。

| 删除对象 | 级联（随行删除） | 置空 | 409 逐项列出（不可删） |
| --- | --- | --- | --- |
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
| `/api/v1/lesson-plans`（GET/POST）、`/{id}`（GET/PATCH draft）、`/{id}/revisions` | 教案草稿/修订（CAS `expectedRevision`；草稿与候选分离） |
| POST `/api/v1/lesson-plans/generation-stream` | 逐模块流式生成（SSE：`message.start / module.start / module.delta / module.error / module.done / message.end / error`；生成候选采用才写入） |
| `/api/v1/lesson-plans/{id}/proposals`（+`/{pid}/apply|reject`） | 五字段 patch 候选（`apply_lesson_proposal` 工具带中断确认） |
| POST `/api/v1/lesson-plans/{id}/export` | 导出 docx（202）：以空白模板组装，自动补齐封面（第 1 页）+ 目录（第 2 页），正文自第 3 页 |
| `/api/v1/lesson-plans/source-uploads`、`/lesson-plans/evidence/verify` | 学情来源文件登记、依据核验 |

## 练习（teaching 库）

| 方法和路径 | 用途 |
| --- | --- |
| `/api/v1/practice-sets`（GET/POST）、`/{id}`（GET/draft PATCH/review） | 练习集创建（来源=学情报告/描述驱动）、草稿、审核（未审核不可导出） |
| `/{id}/suggestions`、`/{id}/revisions*` | 按需巩固知识点选拔、修订 |
| POST `/{id}/revisions/{rid}/exports` | 学生卷/教师卷 docx + 成绩模板 xlsx（202 任务 → 产物下载） |
| POST `/{id}/revisions/{rid}/assessments`、DELETE `/{id}/revisions/{rid}/conversion` | 回流：练习 → 原卷修订 + 施测（含映射表）；删除边界守卫 |
