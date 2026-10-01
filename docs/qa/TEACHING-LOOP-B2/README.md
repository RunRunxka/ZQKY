# TEACHING-LOOP B2 批次证据（原卷 / 题库增量 / 施测 / 知识点前端）

- 批次：**B2 = CTRL + T40 + T50 + F10-KP（第一波）+ T30-b（第二波）**（依 [多Agent实施任务计划书 v2.0 §二.3](../../design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)）
- 起点：`main@0f4b8cb190c2265d819b90e5d6df4e3954ad1906`（B0+B1 已由用户提交；开工核对 B1 r2 冻结记录 **95/95 一致、0 差异**）
- 日期：2026-10-01
- 任务卡（范围/归属/契约/验收）：[TASK-CARD.md](TASK-CARD.md)；独立验收任务卡：[V00-TASK-CARD.md](V00-TASK-CARD.md)
- 冻结指纹：[FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)；命令与结果：[EVIDENCE-COMMANDS.md](EVIDENCE-COMMANDS.md)

## 1. 本批交付

| 计划 B2 条目 | 交付 |
| --- | --- |
| T40 原卷后端 | DOCX 导入（T10 富解析 + 受管资产）→ 块/问题清单/规则拆题持久化 → 草稿整表校对 → 确认闸门 → 确认后不可变；AI 知识点建议（`ai_proposals`，pending/stale/apply/reject）；`ConfirmedPaperReader` 真实 adapter（只放已确认修订） |
| T50 题库增量 | 草稿/正式知识点关联（改内容复制、改关联替换、按知识点检索）；AI 补题（`question:generate` 独立 GenerateReply，候选进既有校对确认链）；版本化派生指纹；组织/生成任务接入统一 JobEngine 六态并纳入启动收敛 |
| T30-b 施测 | 真实 `GET/POST /assessments` 与详情/更新/补录人次；只用已确认固定修订；参测姓名/学号服务端读取冻结；空名单拒绝；班级范围与人次唯一；归属未覆盖施测日 → 教师显式确认并落库依据（不改归属历史）；同库同事务 + 幂等 |
| F10-KP 前端 | `/knowledge-points` 真实页面（学科/父树/建立更新/别名/归档/教材依据/表格导入校对确认/AI 候选六态）+ 题库六态兼容（interrupted 横幅 + 显式重试） |
| CTRL | 迁移 0003/0004（teaching）与 0004（question_bank）；`contracts/{papers,assessments}.py` + TS 镜像 + `schemas/question_bank.py` 六态/关联/生成；main.py 装配（题库三依赖、原卷/施测服务与路由、question 域收敛）；导航/壳/ROUTES/API/PROJECT_GUIDE/CURRENT_STATUS |

**未做（按范围）**：成绩（T60）、学情（T70）、练习（T80）、教案后端（T90）、F20 前端、题库新业务前端、正式数据迁移演练。

## 2. 迁移与分期约束

| 库 | 迁移 | 内容 |
| --- | --- | --- |
| 教学库 | `0003_teaching_paper_tables` | 设计四表 + `paper_source_blocks`/`paper_issues`/`ai_proposals` + 全套触发器（父子环/确认闸门/确认后冻结/不可变） |
| 教学库 | `0004_teaching_assessment_tables` | 设计三表 + 参测班级显式确认列 + `assessment_confirmed_paper_insert`/`assessment_paper_fixed` |
| 题库 | `0004_question_knowledge_links` | 设计关联表逐字（不可变触发器）+ 草稿关联/生成来源/版本化指纹 |

**分期偏差**：`source_practice_revision_id`、`active_score_revision_id` 本批只允许空（无未来表外键 + CHECK 拒非空）；
`source_file_id` 必须非空；草稿总分允许 0（确认闸门 >0 且=叶子合计）。B0/B1 已登记散列零漂移（`test_b2_migrations.py` 固定常量断言）。

## 3. 验证（实跑；命令/退出码见 [EVIDENCE-COMMANDS.md](EVIDENCE-COMMANDS.md)）

- 后端全量 `npm run test:api`：**1296 passed / 0 failed，退出码 0**（B1 基线 1170 → +126）。
- 根检查 `npm run check`：**退出码 0**（typecheck + lint 0 警告 + unit **86 文件 / 799 例** + build）。
- 全量 E2E（先 build，隔离 5174）：r1 `142/5` → r2 `146/1` → **r3 `147 passed / 0 failed`**（失败全部在新页面 spec，逐条修复见 §4/B2-F8）。
- 装配冒烟：六服务 + 全部路由（knowledge 10 / roster 12 / papers 10 / assessments 3 / workflow-jobs 3）；
  `question_bank_service` 的 knowledge_catalog/coordinator/job_engine 三依赖就绪；`RECONCILE_DOMAINS` 含 question。
- 独立验收 V00：见 §6。
- CTRL 另更新了 `docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md`（B2 交付状态 + **B2 分期 DDL 交接**：
  练习/成绩批次必须补齐的两处未来外键与一处触发器分支）——该文件属用户设计目录，不在冻结候选内。

## 4. 首败与修复

| 编号 | 现象 | 修复 |
| --- | --- | --- |
| B2-F1 | T40 自检：块行 id 跨修订主键冲突（同一 DOCX 导入两次） | 块 id 带修订命名空间，复制修订同步重写引用 |
| B2-F2 | T40 自检：PATCH 响应总分陈旧（写后仍用旧记录渲染） | 渲染前重读修订 |
| B2-F3 | T50 自检：publish 注入失败后任务停在 `running`（B0 引擎"异常上抛"契约） | 服务侧补收尾：仍是本 worker 租约的 running → `failed`（同域边界登记） |
| B2-F4 | T30-b 自检：`PATCH /assessments/{id}` 后 `revision` 未 +1 | 服务补 `bump_revision_in` |
| B2-F5 | CTRL：新增 B2 迁移使 B0/B1 旧测试硬编码清单失败（5 处） | 改为**动态期望**（读取注册表），不再逐批改常量 |
| B2-F6 | CTRL：导航新增条目使 `navigation.test.ts` 硬编码清单失败 | 更新清单（新增 `knowledge-points`） |
| B2-F7 | CTRL：`npm run check` 首次 1 例失败（B2-F6 同一根因） | 同上；复跑退出码 0 |
| B2-F8 | CTRL：**全量 E2E 5 例失败全部在新页面 spec**（strict mode 重复匹配 ×2、alert 计数、元素缺失 ×2） | 交 F10-KP 修复 spec/页面（见 §6） |
| 其余 | 各实现者自检首败（生成执行器 async 漏标、路径扫描正则误判、Harness 字段名等） | 见各自结果卡 |

## 5. 遗留与边界（如实登记）

1. 正式题关联表无 `source` 列（设计逐字）；来源保留在草稿关联表（human/ai），确认后不再区分。
2. `ai_proposals` 无冻结触发器（设计无）；对已确认修订的越权写入由服务拒绝，绕过服务的直写仍可改 state。
3. T50 的发布失败收尾只在 question 域；其它域如需同类收尾属引擎级改动。
4. 生成原件的 orphan blob（发布失败时模型回复已落盘、不可发布，仅占盘）；派生指纹对 `blobs/<hex>` 只取键值散列（生成路径实读校验字节）。
5. 施测 `ParticipantMutationResult` 只返回本次新增人次；`ASSESSMENT_REVISION_STALE` 为契约专用码（非通用 REVISION_CONFLICT）。
6. 原卷 `paper_issues` 的 UNSUPPORTED_OBJECT 判 blocking + 必须 resolution/exclude：真实带图形卷会要求教师逐条确认（设计意图，F20 前端需支持）。
7. **V00 r1 的 observation（已登记，不判 fail）**：原卷域 publish 失败后任务停 `running`（业务零残留；收尾统一留 B3）；
   `GENERATION_*` 实际码以 `generation.py` 为准（API.md 已订正）；`KnowledgePointView` 字段是 `id`（无 `pointId`）。
8. **T50 披露**：其实现在 pytest 之外两次 `import app.main` 触发了模块级 `create_app()`，对正式 `.local-data` 应用了已登记的 B2 迁移（question_bank 0004、teaching 0003/0004）；只读复核 integrity ok、无业务数据写入；该迁移在下次后端正常启动时同样会应用。
8. 真实模型/Word-WPS 排版/真实 Qdrant/正式数据迁移演练 `not_run`；台账间歇项（R-14/R-15/R-18/R-19）按 CURRENT_STATUS 口径。

## 6. 独立验收（V00）

### 6.1 r1（[V00-REPORT-01.md](V00-REPORT-01.md)）

**指纹 83/83 一致；V1–V8、V10 全部 pass**（自建探针：迁移 87、原卷导入 59、确认不可变 44、建议/reader 32、
题库关联与生成 32、统一任务 14、施测 33、前端组件 9、变异 11 例；变异 3 处均被断言抓到）；
**V9 fail（2 处 `docs/API.md` 事实错误）**——`GENERATION_INVALID_EVIDENCE`/`_UNSAFE_REFERENCE`/`_TRUNCATED`
三个码名不存在（实际为 `GENERATION_UNKNOWN_EVIDENCE`/`GENERATION_FORBIDDEN_REFERENCE`/`GENERATION_OUTPUT_TRUNCATED`）、
施测域 `CLASS_ARCHIVED` 标为 409 而实测 422（名单域 409 正确）。**零产品阻塞 fail**。

### 6.2 r1 的 observation 处置

| 编号 | 内容 | 处置 |
| --- | --- | --- |
| OBS-1 | 原卷域 publish 失败后任务停 `running`（业务零残留、`PAPER_PROPOSAL_STALE` 真实抛出；与 T50 的 question 域收尾不同） | 登记为边界，收尾统一留 B3（任务卡 §11.8） |
| OBS-2 | `apps/api/AGENTS.md` 未同步 B2 | CTRL 已补（r2 新增项） |
| OBS-3/4/5 | 错误码命名映射、`KnowledgePointView.id` 口径、草稿"一变即回 needs_review" | 前两项已在 API.md/任务卡订正登记；第三项为明示语义 |
| OBS-6 | 验证窗口内正式 `.local-data` 零写入；13:37 的迁移与登记 id 一致（CTRL 已披露） | 接受；正式数据迁移演练仍 not_run |
| OBS-7 | R-14/R-15/R-18/R-19 台账项 | 未复现/未"修"/未放宽，按 CURRENT_STATUS 口径 |

### 6.3 r2 窄复验（[V00-REPORT-02.md](V00-REPORT-02.md)）

- r2 = r1 **新增 1**（`apps/api/AGENTS.md`）+ **修改 3**（`docs/API.md`、`CURRENT_STATUS.md`、`TASK-CARD.md`），
  **零产品/测试/脚本变化**；`FROZEN-CANDIDATE.json` 记录 84 文件与 `changedSincePrevious`（r1 记录保留为 `FROZEN-CANDIDATE-r1.json`）。
- 窄复验内容与结论见报告（V9 复跑 + 指纹 84/84 + 关键三项探针重跑）。
