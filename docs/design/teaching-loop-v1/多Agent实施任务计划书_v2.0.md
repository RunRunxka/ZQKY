# 智启课源教学闭环实施任务计划书
## 多 Agent 协作版 · 精确到伪代码 · v2.0

代码基线核查日期：2026-09-30；文档定位修正：2026-10-01。本文记录原核查基线及实施设计。能力表中的‘当前’和‘尚未实现’均指该基线，不代表今日状态；B0–B3 的交付及审查待修以 CURRENT_STATUS 和实际代码为准。

下一轮启动时使用 [多 Agent 启动提示词](多Agent启动提示词_v2.0.md)，由用户复制相应提示词明确授权当前批次。实际执行批次和前置修复由 CURRENT_STATUS 与用户本次请求确定，不重复启动已交付批次。

> 本文是设计与任务参考，不自动授权执行。进度、问题台账、当前任务和下一动作的唯一入口是 [CURRENT_STATUS.md](../../CURRENT_STATUS.md)，目标与稳定决定的唯一入口是 [PROJECT_GUIDE.md](../../PROJECT_GUIDE.md)。执行须由用户启动提示词指定当前批次；不设当前默认批次，按用户本次已给定的范围推进。本文的任务顺序、伪代码和验收要求不构成自动启动全部批次的授权。
>
> 本文件是 Markdown 实施计划。DOCX/PDF 为后续文档交付项，本文件不表示它们已经生成，也不表示任何业务实现已经验收。

### 一、实施基线、目标和固定规则

本计划根据根目录及模块级 `AGENTS.md`、[当前状态文档](../../CURRENT_STATUS.md)、[项目稳定决定](../../PROJECT_GUIDE.md)、现有 API、模块源码和教学闭环设计制定。

代码基线为本地 `main@301fc356493db21d187ab85f32fd49dfffdc51ef`。实施采用以下方式：**用户负责调度，总控 Agent 负责契约与集成，多个实现 Agent 在共享工作区分批并行。** 代码基线只表示已核查的本地提交，不表示已经同步远程最新 main。

#### 1. 2026-09-30 基线能力及实施方式

| 模块 | 原核查基线实际情况 | 设计实施方式 |
|---|---|---|
| 学习问答、模型连接 | 已有真实模型调用和 SSE | 复用模型解析与供应商适配，不重建 |
| 教材 RAG | 已有真实混合检索、证据验证和恢复链路 | 提供可核验教材依据，保留现有检索行为 |
| 题库 | 已有真实导入、拆合题、AI 整理、校对、确认和独立 SQLite | 增量加入正式知识点关联、富内容和 AI 补题 |
| 教案 | 已有编辑、规则填充、撤销重做、草稿恢复、Word 导出及打印 | 保留现有工作台，增加后台保存、学情依据和 AI 建议 |
| 独立知识点库 | 已有参考设计，尚未接入应用 | 新建正式知识点管理、导入和候选确认流程 |
| 名单、原卷、成绩、学情 | 已有参考设计，尚未接入应用 | 实现完整业务后端和前端 |
| 针对性练习及成绩回流 | 已有参考设计，尚未接入应用 | 实现选题、补题、审核、DOCX、成绩模板及回流 |

#### 2. 首版必须遵守的业务规则

1. 原卷中的**独立计分小题**是成绩和知识点关联的基本单位。
2. 相关小题只要存在实际失分，该知识点就显示为 **“本次需巩固”**。
3. 不建立掌握概率、能力预测或自动评分算法。
4. 不实现阅卷，不建立评分点或评分细则实体。
5. `0 分`是有效成绩；空白、缺考、免考分别保存，不补零。
6. 一道小题可以关联多个知识点；发生失分时列出全部相关知识点，具体错因由教师确认，不分摊失分。
7. 知识点独立建库；教材依据是可选关联，题目通过知识点 ID 分类，不以教材章节作为强制父级。
8. AI 提取的知识点、AI 新题及 AI 教案均进入候选或建议状态，经确认后才能进入正式流程。
9. 首版练习采用**题库选题加 AI 补题**，知识点采用**人工建立、表格导入加 AI 候选**。
10. 学情报告固定引用当时的试卷、成绩及名单快照，后续修改不改变旧报告。

首版不启用自动分层算法、在线答题、自动阅卷、OCR、多人账号权限或新的后端 PDF 服务。现有教案打印能力继续保留。

### 二、Agent 任务拆分、文件归属与执行顺序

任务编号代表工作单元，不代表员工数量。一个 Agent 完成任务并停止写入后，可以承接后续任务。

#### 1. 协作规则

- 同批最多 **3 个实现 Agent**，总控占一个协调位置。
- 同一文件、数据库迁移文件、测试端口及构建目录，同一时段只有一个负责人。
- 总控独占共享契约、应用装配、导航与薄路由、依赖锁文件、迁移登记、权威文档及 Git 操作。
- 实现 Agent 不切共享分支，不批量暂存，不修改其他 Agent 的文件。
- 需要共享文件变更时，提交具体修改建议，由总控实施。
- 实现者交付 `ready_for_review`；独立验收者对冻结候选核查，不能边验边修。
- 核查时 `docs/PLAN.md` 已有未提交修改，必须保留。旧设计文件作为参考，不能直接将参考 SQL 执行到正式数据库。

#### 2. 任务卡清单

下表中的目录是可写范围；共享文件例外由总控独占。每个任务还必须包含相应模块测试。

| ID | Agent 任务 | 可写范围与边界 | 前置依赖 | 主要交付及验收 |
|---|---|---|---|---|
| CTRL | 总控与集成 | 共享 contracts/schemas、公共 API 客户端、启动装配、路由导航、锁文件、迁移登记、权威文档 | 无 | 契约一致、资源无冲突、固定候选、集成检查与结果卡 |
| T00 | 公共基础 | 总控分配的任务引擎、资产服务、迁移及备份实现文件 | CTRL 契约 | 幂等、CAS、取消、恢复、四库备份和损坏数据保护 |
| T10 | 富内容解析与导出 | 新原卷富内容解析器、公式和图片处理、练习 DOCX 渲染器 | T00 | 共享题干、表格、公式、图片顺序与来源可核验 |
| T20 | 知识点后端 | 新知识点 routes/services/repositories；迁移内容交总控登记 | T00 | CRUD、父树、别名、表格预览、AI 候选和确认 |
| T30 | 名单与施测后端 | 新班级、名单导入、参测记录 routes/services/repositories | T00 | 学生身份稳定、同名不误合并、参测快照正确 |
| T30-a | 班级·学生·名单导入（B1 实际启动） | 新班级/学生/归属历史/名单导入 routes/services/repositories；施测只冻结请求、人次与身份/出勤快照契约 | T00 | 学号文本保留前导零、人工身份证核对、未出现不退班、转班保留旧归属、确认幂等与整批回滚 |
| T30-b | 施测真实创建（B2 联调后验收） | `assessments`/`assessment_classes`/`assessment_participants` 迁移登记 + 创建服务与端口实现 | T40（已确认原卷修订）、T30-a | 只用已确认原卷修订、参测快照冻结、补考新增人次；B1 不通过假原卷或放宽确认规则宣称施测可用 |
| T40 | 原卷后端 | 新原卷导入、校对、知识点标注与确认业务 | T10、T20、T30 | 每计分叶子有满分和已确认知识点；未处理内容阻断确认 |
| T50 | 题库增量后端 | 既有题库服务、仓储和新增生成器；共享 schema 交总控 | T10、T20 | 草稿与正式关联、改题保留关联、AI 补题进入既有校对链 |
| T60 | 成绩后端 | 新成绩预览、映射、确认和修正业务 | T30、T40 | 全量成绩矩阵、Decimal 校验、原子确认及不可变修订 |
| T70 | 学情后端 | 新分析服务、报告与证据查询、教师备注 | T60 | 按 `any_loss_v1` 复算，分母明确，证据定位完整 |
| T80 | 练习闭环后端 | 新练习选择、修订、审核、导出及施测转换 | T40、T50 | 正式题固定修订、缺题如实展示、学生卷不泄漏答案、成绩回流 |
| T90 | 教案后端 | 新教案保存、旧稿导入、AI 建议与应用服务 | T70、T80 | 保留现有内容结构，版本冲突保护，选定字段事务应用 |
| F10 | 知识点、题库、练习前端 | 对应 features 和专属 services | 对应契约；正式验收依赖 T20/T50/T80 | 导入校对、正式关联、补题审核、练习导出 |
| F20 | 名单、原卷、成绩前端 | 新测评工作区 features 和专属 services | 对应契约；正式验收依赖 T30/T40/T60 | 完整校对流程、行列错误定位、有效 0 与缺失状态区分 |
| F30 | 学情与教案前端 | 新学情 feature、既有 lesson-plan 增量及专属 services | 对应契约；正式验收依赖 T70/T90 | 后台权威报告、建议差异、保存恢复和现有教案回归 |
| V00 | 独立验收 | 只读产品；写专属 fixtures、测试及证据目录 | 冻结候选 | 独立复算、故障注入、跨模块 E2E、真实 DOCX 排版检查 |

前端允许在契约冻结后使用测试替身开发，但结果卡必须标明“替身验证”。真实业务验收须连接实际 FastAPI。

#### 3. 分批顺序

| 批次 | 并行任务 | 批次完成条件 |
|---|---|---|
| B0 | CTRL、T00 | 类型、错误、版本、任务、资产及迁移契约冻结 |
| B1 | T10、T20、T30-a | 富内容基础、正式知识点、班级名单可用（施测契约冻结，真实创建留 B2 的 T30-b） |
| B2 | T40、T50、T30-b、F10-KP | **已交付（2026-10-01，未提交）**：原卷可真实确认、题库关联/生成/统一任务可用、施测在真实原卷上建立冻结参测快照、`/knowledge-points` 前端可用；共享迁移兼容并通过独立验收 |
| B3 | T60、F20 导入部分、F10 题库部分 | 名单→原卷→成绩完成真实链路 |
| B4 | T70、T80、F20 成绩部分 | 学情可复算，练习可审核及回流 |
| B5 | T90、F30 学情部分、F10 练习部分 | AI 教案后端及练习前端可用 |
| B6 | F30 教案部分、CTRL 集成 | 完整教学闭环，迁移和备份更新完成 |
| B7 | V00 独立验收 | 候选停止写入，逐项给出 pass/fail/not_run |

不沿用旧“8 人、8 周”排期。实施进度按批次验收推进，失败修复形成新候选版本。用户本次请求指定的批次及授权范围优先；不设当前默认启动批次，B0–B3 已交付内容不重复开工。

#### B2 分期 DDL 交接（2026-10-01 登记）

B2 已登记：教学库 `0003_teaching_paper_tables`（papers/paper_revisions/paper_items/paper_item_knowledge + paper_source_blocks/paper_issues/ai_proposals + 确认冻结触发器）与 `0004_teaching_assessment_tables`（assessments/assessment_classes/assessment_participants + 参测班级显式确认列 + 只用已确认卷/不能换卷触发器）；题库 `0004_question_knowledge_links`。编号已占用，后续批次**不得改写**。

**B2 的分期偏差（后续批次必须补齐）**：

1. `paper_revisions.source_practice_revision_id`：B2 保留列但 `CHECK(... IS NULL)` 且无外键（`practice_revisions` 属练习批次）。练习落地时新增迁移：建 `practice_revisions` 后按受检流程重建 `paper_revisions`（SQLite 不能 ADD FK）→ 恢复设计 CHECK「原卷/练习二选一」并允许非空；届时回填 `source_practice_revision_id` 的写入路径。
2. `assessments.active_score_revision_id`：B2 只允许空、无外键（`score_revisions` 属 B3/T60）。B3 新增迁移：建 `score_revisions`（含 `(id,assessment_id)` 唯一）后按受检流程重建 `assessments` → 恢复设计复合外键 `(active_score_revision_id,id) REFERENCES score_revisions(id,assessment_id) DEFERRABLE` 并放开非空。
3. `paper_confirm` 触发器缺 `PRACTICE_NOT_REVIEWED` 分支（同因未来表）；练习批次一并补回。
4. `paper_revisions.total_score_units` B2 允许 0（草稿容差），确认闸门（服务 + 触发器）要求 >0 且等于计分叶子合计；该口径保留，不需回改。
5. B3 前置：固定 `paperRevisionId` 与参测快照已由 B2 落库（`assessment_participants` + `class_confirmed` 依据）；成绩导入接口以 `assessments.id` + 确认修订为前置；`score_revisions.participant_snapshot_json`（计划书 §二.2 补齐项）在 T60 迁移中登记。

T30-b 已交付（施测真实创建 + 参测人次 + 只能使用已确认修订），其验收证据见 `docs/qa/TEACHING-LOOP-B2/`。

#### 4. 每个 Agent 的交付格式

```text
任务 ID / 版本：
起点 SHA：
可写范围：
实际修改文件：
实现的正常路径：
失败、取消、重试、恢复行为：
兼容与迁移：
验证命令 / 退出码 / 证据路径：
首败与修复：
未执行及原因：
剩余问题：
运行资源是否释放：
状态：ready_for_review
```

### 三、统一架构、数据库和 API 契约

#### 1. 代码规范

**前端**

- `app/` 保持薄路由，业务放入 `features/<module>`。
- HTTP 调用放入专属 `services`；组件不直接拼接 API URL。
- 跨模块类型由总控统一维护，禁止各模块复制任务、证据和富内容类型。
- 继续使用现有样式变量、字体 token、公共控件和 `/chat` 视觉基准。
- 不在模块顶层读取浏览器存储；页面状态和服务实例按工作区注入。
- 请求失败保留已有列表和编辑数据，不能显示为成功空库。

**后端**

- 真实业务只在 FastAPI；不建立 Next.js 业务后端。
- 路由负责校验和响应，服务负责流程，仓储负责 SQL。
- SQLite 连接复用现有公共连接入口，不跨线程共享连接。
- 文件解析、模型调用、检索和导出在 SQL 写事务外执行。
- 模型统一通过现有 `resolve_chat_model` 解析，冻结 profile 和配置指纹。
- 每个写操作只在所属数据库提交；跨库引用由服务校验。

#### 2. 数据归属及设计补齐

继续保持四个独立 SQLite：

| 数据库 | 权威数据 |
|---|---|
| 教材目录库 | 教材修订、分块、索引代和教材依据 |
| 知识点库 | 知识点、修订、别名、导入候选及确认 |
| 题库 | 原件、拆题草稿、AI 题目候选、正式题修订及知识点关联 |
| 教学库 | 班级、学生、施测、原卷、成绩、报告、教案、练习及导出记录 |

Qdrant 继续只服务教材检索，禁止自动将题库题目写入教材 collection。

现有参考 DDL 必须补齐：

| 位置 | 新增或调整 |
|---|---|
| 知识点库 | `knowledge_imports`、`knowledge_import_rows`、`knowledge_submissions`、`knowledge_jobs` |
| 教学库 | `roster_imports`、`roster_import_rows` |
| 题库 | `question_draft_knowledge_links`、`question_knowledge_links`、`question_import_provenance`、`question_content_fingerprints` |
| 成绩修订 | 增加 `participant_snapshot_json`，冻结身份、班级、人次和出勤 |
| 原卷修订 | 增加完整来源内容及校对清单，保留未归属块和明确排除记录 |
| 任务表 | 补充冻结输入、输入散列、attempt、lease、取消标志、结果及更新时间 |
| 幂等表 | 使用 `(owner_id, operation, submission_id)` 复合身份 |
| 各库 | 增量迁移记录及 SQL 散列，不仅使用 `CREATE TABLE IF NOT EXISTS` |

任务框架统一，任务状态与结果落在同一业务库：

- 知识点候选：`knowledge_jobs` 与候选批次同库。
- AI 补题：复用并扩展既有 `question_jobs`，与题目草稿同库。
- 原卷、学情、教案和导出：使用教学库 `workflow_jobs`。

这使候选生成和任务完成可以在同库事务提交。**确认知识点后绑定原卷或题库，仍是两个明确的写操作**；第二步失败时保留已建立的知识点，重试绑定。

跨库归档和新引用发布使用进程内 `PublicationCoordinator` 协调；其范围只包含数据库读取和短写事务。正式修订永久保留，引用固定修订 ID。

#### 3. 版本和数据格式

```typescript
type RevisionIdentity = {
  id: string;                   // 稳定业务身份
  revision: number;             // 乐观锁
  revisionId: string;           // 固定内容修订身份
};

type ScoreCell = {
  participantId: string;
  itemId: string;
  status: "recorded" | "missing" | "absent" | "exempt";
  scoreUnits: number | null;    // 分数 × 100，整数
};

type Observation =
  | "needs_consolidation"
  | "full_credit"
  | "incomplete"
  | "no_evidence";

type JobView = {
  jobId: string;
  domain: "knowledge" | "question" | "teaching";
  kind: string;
  attempt: number;
  state:
    | "queued" | "running" | "succeeded"
    | "failed" | "cancelled" | "interrupted";
  result: Record<string, unknown> | null;
  error: ApiErrorEnvelope | null;
};

type ApiErrorEnvelope = {
  code: string;
  message: string;
  requestId: string;
  retryable: boolean;
  details?: {
    currentRevision?: number;
    issues?: Array<{
      row?: number;
      column?: string;
      field?: string;
      code: string;
      message: string;
    }>;
  };
};
```

- 外部 JSON 使用 camelCase，内部 Python/SQL 使用 snake_case。
- 分数禁止浮点直接运算。
- 时间保存 UTC，界面转换为本地时间。
- 新列表统一 `{items,total,offset,limit}`；既有接口保持现行结构。
- `202`只代表接受任务，不能显示“生成完成”。
- 同一提交重试使用同一个 `submissionId`；改变输入后生成新 ID。
- 同 ID、不同请求返回 `409 SUBMISSION_CONFLICT`。
- 重放已成功提交时，先返回原结果，再考虑当前版本；避免响应丢失后的重试误报版本冲突。

#### 4. 主要 API

以下全部使用 `/api/v1` 前缀。

| 模块 | 接口 |
|---|---|
| 知识点 | `GET/POST /knowledge-points`；`GET/PATCH /knowledge-points/{id}` |
| 知识点导入 | `POST /knowledge-imports`；`GET/PATCH /knowledge-imports/{id}`；`POST /knowledge-imports/{id}/confirm` |
| AI 知识点候选 | `POST /knowledge-suggestion-jobs` |
| 题库关联 | 扩展草稿 PATCH；`PUT /questions/{id}/knowledge-links`；扩展知识点筛选 |
| AI 补题 | `POST /question-generation-jobs` |
| 班级名单 | `GET/POST /classes`；`GET/PATCH /classes/{id}`；名单查询与成员归属接口 |
| 名单导入 | `POST /classes/{id}/roster-imports`；`GET/PATCH /roster-imports/{id}`；`POST /roster-imports/{id}/confirm` |
| 原卷 | `POST /paper-imports`；`GET /papers/{id}`；`PATCH /papers/{id}/draft`；`POST /papers/{id}/confirm` |
| 原卷证据 | `GET /papers/{id}/revisions/{revisionId}/content` |
| 原卷知识点建议 | `POST /papers/{id}/knowledge-proposals`；建议读取、拒绝及应用接口 |
| 施测 | `GET/POST /assessments`；`GET /assessments/{id}`；参测人次维护接口 |
| 成绩 | `POST /assessments/{id}/score-imports`；导入读取与映射 PATCH；确认接口 |
| 成绩修正 | `POST /assessments/{id}/score-corrections`；`GET /score-revisions/{id}` |
| 学情 | `POST /assessments/{id}/analysis-runs`；报告、班级、学生、证据查询及备注接口 |
| 教案 | `GET/POST /lesson-plans`；`GET/PATCH /lesson-plans/{id}`；`POST /lesson-plans/import-local` |
| AI 教案 | `POST /lesson-plans/{id}/ai-proposals`；`GET /lesson-proposals/{id}`；apply/reject 接口 |
| 练习 | `GET/POST /practice-sets`；读取、编辑、选题建议、review、exports、assessments 接口 |
| 公共任务 | `GET /workflow-jobs/{id}?domain=…`；cancel/retry |
| 文件 | 受管资产读取、`GET /export-artifacts/{id}/download` |

总控补齐现有 API 客户端的三个缺口：保留 `details`、保留取消语义、新增 Blob 下载适配。既有题库确认的 **HTTP 200 + failures 非空**仍表示整体未确认。

#### 5. 富内容契约

```typescript
type RichContentV2 = {
  version: 2;
  sharedMaterials: Array<{ id: string; blocks: ContentBlock[] }>;
  stemBlocks: ContentBlock[];
  optionBlocks: Record<string, ContentBlock[]>;
  answerBlocks: ContentBlock[];
  explanationBlocks: ContentBlock[];
  assets: Array<{ assetId: string; sha256: string; mediaType: string }>;
  origin: {
    originalAssetId: string;
    originalSha256: string;
    sourceLocator: Record<string, unknown>;
  };
};

type ContentBlock =
  | { id: string; kind: "paragraph"; text: string }
  | { id: string; kind: "table"; cells: TableCell[] }
  | { id: string; kind: "formula"; latex?: string; ommlXml?: string }
  | { id: string; kind: "image"; assetId: string; width: number; height: number };
```

题库内容增加可选 `richContent`，兼容旧 Markdown 题。富内容存在时，它是内容权威，Markdown 是派生展示；服务校验两者一致，不能保留旧富内容却只修改 Markdown。

依赖由总控统一加入并锁定：表格采用 `openpyxl==3.1.5`，新公式写入 DOCX 采用 `math2docx==3.1.0`，继续保留已有 `python-docx==1.2.0`。这些库提供读取及转换能力，最终保真仍须通过项目样本验收。[openpyxl](https://pypi.org/project/openpyxl/3.1.5/)、[math2docx](https://github.com/keh9mark/math2docx)

### 四、各模块实现伪代码与验收条件

#### T00：公共基础、迁移、幂等和任务

**写入事务**

```python
def execute_command(command, repository):
    prepared = validate_request(command)       # 不调用模型、不解析文件
    request_hash = canonical_hash(command)

    with publication_coordinator_if_needed(command):
        external = verify_external_revisions(prepared)

        with repository.write_transaction() as tx:
            prior = tx.find_submission(
                owner=command.owner,
                operation=command.operation,
                submission_id=command.submission_id,
            )

            if prior:
                require_same_hash(prior, request_hash)
                return prior.result

            require_expected_revision(tx, command.expected_revision)
            result = apply_domain_change(tx, prepared, external)
            tx.save_submission(command, request_hash, result)
            return result
```

**任务执行**

```python
async def run_job(job_id, domain):
    lease = jobs(domain).claim(job_id)          # attempt + 1，生成 lease token
    frozen = jobs(domain).load_frozen_input(job_id)

    try:
        result = await execute_outside_transaction(
            frozen,
            heartbeat_interval=20,
            cancellation_probe=jobs(domain).cancel_requested,
        )

        with jobs(domain).write_transaction() as tx:
            tx.require_current_lease(job_id, lease)
            tx.require_not_cancelled(job_id)
            persist_domain_result(tx, result)
            tx.mark_succeeded(job_id, result.reference)
    except DomainError as error:
        jobs(domain).fail_if_current_lease(job_id, lease, error)
```

固定行为：

- lease 有效期 90 秒，每 20 秒续租。
- 同时最多两个后台重任务，其中最多一个模型生成任务。
- 重启遗留 `running` 转为 `interrupted`；不自动重新调用模型。
- 用户重试保留冻结输入和模型指纹，递增 attempt。
- 模型配置失效时显式失败，不偷偷换模型。
- 页面停止观察不取消任务；只有 cancel 接口取消。
- 取消后旧 lease 不能发布结果。
- 相同导出输入的成功产物可重用；失败不登记成功文件。

**启动和备份**

```python
def application_lifespan():
    acquire_existing_data_root_lock()
    reject_incomplete_restore()
    verify_existing_databases_are_readable()
    apply_registered_incremental_migrations()
    reconcile_interrupted_jobs()
    assemble_services()
    yield
    stop_owned_workers()
    release_data_root_lock()
```

四库备份沿用停写窗口，复制被引用受管文件及 Qdrant 快照。恢复只写新目录，核验全部跨库引用后才标记完成。损坏已有库不得按空库重建。

**验收：**重复迁移无内容变化；中途迁移失败可恢复；提交响应丢失可重放；取消后迟到结果不发布；新版备份缺库或缺原件时拒绝完整性通过。

#### T20：独立知识点库

表格字段固定为：

```text
subjectCode, code, name, description, parentCode, aliases
```

`code`是学科内身份键。名称或别名相同只提示，不自动合并。

```python
def preview_knowledge_import(file, mapping, subject):
    asset = assets.store_original(file)
    rows = parse_table(asset, mapping)
    normalized = normalize_knowledge_rows(rows, subject)

    issues = validate_codes_and_parent_graph(
        normalized,
        knowledge_repository.read_snapshot(),
    )

    return save_import_preview(normalized, issues, asset)
```

```python
def confirm_knowledge_import(import_id, expected_revision, actions, submission_id):
    with publication_coordinator:
        with knowledge_repository.write_transaction() as tx:
            if prior := replay_submission(tx, submission_id):
                return prior

            batch = tx.require_preview(import_id, expected_revision)
            plan = build_create_update_ignore_plan(batch, actions, tx)

            require_no_blocking_issues(plan)
            require_parent_graph_without_cycles(plan)

            ids = allocate_ids_for_new_rows(plan)

            for row in topological_order(plan):
                if row.action == "create":
                    point = tx.create_identity_and_first_revision(row, ids)
                elif row.action == "update":
                    point = tx.append_revision_after_cas(row)
                else:
                    continue

                tx.save_aliases(point, row.aliases)

            tx.mark_import_confirmed(import_id)
            return tx.save_submission_result(plan.row_to_point_ids)
```

固定行为：

- 同学科同 code 默认冲突；显式选择 update 并核验版本才更新。
- 更新时空白可选单元格默认“不修改”；清空需要明确标记。
- 父节点可引用本批新建知识点；禁止跨学科父节点和循环。
- 知识点改名新增内容修订，旧引用继续显示旧名称快照。
- 归档保留历史，新绑定禁止选择已归档知识点。
- AI 候选进入相同预览确认流程，不直接写正式表。
- 原卷发现不存在的知识点时，先确认候选，再绑定原卷；绑定失败可以单独重试。

**验收：**批内父树、循环、同名不同 code、别名歧义、更新冲突、失败整批回滚、确认重放及历史名称均正确。

#### T30：班级、学生和施测

```python
def preview_roster(class_id, file, mapping):
    rows = parse_roster(file, mapping)

    for row in rows:
        student_no = preserve_as_text(row.student_no)

        if student_no:
            match = find_student_by_owner_and_number(student_no)
        else:
            match = require_manual_identity_choice(row.name)

        detect_duplicate_rows(row)
        detect_name_mismatch(row, match)
        store_preview_row(row, match, issues)

    return persistent_roster_preview()
```

```python
def confirm_roster(import_id, expected_revision, decisions, submission_id):
    with teaching_repository.write_transaction() as tx:
        replay_or_validate_submission(tx, submission_id)
        batch = tx.require_roster_preview(import_id, expected_revision)

        require_all_identity_conflicts_resolved(batch, decisions)

        for row in batch.selected_rows:
            student = create_or_link_student(tx, row, decisions)
            append_membership_if_missing(tx, student, batch.class_id)

        # 未在本次表格出现的学生不自动退班
        tx.mark_roster_confirmed(batch)
        return tx.save_submission_result()
```

```python
def create_assessment(confirmed_paper_revision, class_ids, selected_students):
    require_confirmed_paper(confirmed_paper_revision)

    with teaching_repository.write_transaction() as tx:
        assessment = tx.create_assessment(confirmed_paper_revision)
        tx.insert_assessment_classes(assessment, class_ids)
        tx.insert_participants_with_identity_snapshots(
            assessment, selected_students, attempt_no=1,
        )
        return assessment
```

固定行为：

- 学号按字符串保存，保留 `0012`。
- 姓名不是主键；无学号或同名冲突必须人工指定身份。
- 转班保留历史归属，不修改旧参测记录。
- 补考新增人次；报告默认选每名学生最新人次，可显式改选，每份报告每名学生只选一个人次。
- 名单导入不自动删除或退班，退班是独立操作。

**验收：**前导零、同名学生、重复行、转班、补考及旧参测身份不被当前名单改变。

#### T10/T40：原卷解析、校对和知识点标注

不能直接将现有 DOCX 文本解析器视为保真解析器。新增解析保留原件及富内容。

```python
def parse_original_paper(asset):
    blocks = []

    for element in iterate_docx_body_in_original_order(asset):
        block = parse_paragraph_table_formula_image(element)
        block.source_locator = original_block_locator(element)
        blocks.append(block)

    preserve_unhandled_objects_as_visible_issues(blocks)
    proposed_items = detect_question_boundaries(blocks)

    return {
        "allBlocks": blocks,
        "items": proposed_items,
        "unassignedBlockIds": find_unassigned_blocks(blocks, proposed_items),
        "issues": collect_issues(blocks),
    }
```

```python
async def propose_item_knowledge(paper_snapshot, selected_model):
    allowed_knowledge = knowledge_repository.active_subject_points(
        paper_snapshot.subject_id,
    )

    reply = await model.generate({
        "items": paper_snapshot.scored_leaf_items,
        "allowedKnowledge": allowed_knowledge,
        "allowNewCandidates": True,
    })

    result = validate_mapping_reply(reply)
    require_existing_ids_are_from_allowed_set(result)
    return pending_proposal(result, paper_snapshot.edit_revision)
```

AI 建议只能：

- 关联已有知识点；
- 提出待确认新知识点；
- 提醒知识点标注存在歧义。

不输出评分点，不据此判断学生掌握情况。

```python
def confirm_paper(paper_id, draft_id, expected_revision, submission_id):
    with publication_coordinator:
        with teaching_repository.write_transaction() as tx:
            replay_or_validate_submission(tx, submission_id)
            paper = tx.require_current_draft(paper_id, draft_id, expected_revision)

            require_unique_full_question_numbers(paper)
            require_item_tree_without_cycles(paper)
            require_only_leaf_items_are_scored(paper)
            require_positive_max_score_for_every_scored_leaf(paper)
            require_confirmed_knowledge_for_every_scored_leaf(paper)
            require_same_subject_knowledge(paper)
            require_sum_of_leaf_scores_matches_total(paper)
            require_all_source_blocks_assigned_or_explicitly_excluded(paper)
            require_no_unresolved_content_loss(paper)

            tx.seal_paper_revision(draft_id)
            tx.update_current_confirmed_pointer(paper_id, draft_id)
            tx.increment_edit_revision(paper_id)
            return tx.save_submission_result()
```

固定行为：

- 题号使用完整路径，如 `16(1)`，不能只保存 `(1)`。
- 共享题干及大题容器不计分。
- 原卷分析不要求先将题目录入题库。
- 图片复制字节及尺寸；公式保留 OMML，导出重新建立图片关系。
- 无法转换的对象保留原件定位；教师补录等价文本或图片后才可确认。
- DOCX 段落位置不能假称固定页码。
- 修改已确认原卷建立新修订，旧施测继续引用旧卷。

**验收：**共同材料、合并表格、两级小题、行内和独立公式、配图均有对应；遗漏可见；父子重复计分被拒绝。

#### T60：成绩导入、确认和修正

XLSX 使用公式视图和缓存值视图读取，不执行公式。`data_only`读取的是工作簿已有缓存值，不能当成重新计算的结果。[官方读取说明](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html)

```python
def parse_score_cell(raw, cached_value, max_score_units):
    if raw.is_formula:
        require_numeric_cached_value(cached_value)
        raw = cached_value

    if raw.is_blank:
        return ScoreCell(status="missing", score_units=None)

    if raw.matches_absent_marker:
        return ScoreCell(status="absent", score_units=None)

    if raw.matches_exempt_marker:
        return ScoreCell(status="exempt", score_units=None)

    require_not_boolean_or_excel_error(raw)
    value = Decimal(normalize_decimal_text(raw))
    require_at_most_two_decimal_places(value)

    units = exact_integer(value * 100)
    require(0 <= units <= max_score_units)

    return ScoreCell(status="recorded", score_units=units)
```

```python
def build_score_preview(assessment, file, mapping):
    require_mapping_to_exact_scored_leaf_ids(mapping)

    rows = parse_selected_sheet(file, mapping)
    participants = snapshot_current_participants(assessment)

    matrix = make_full_participant_item_matrix(
        participants,
        assessment.confirmed_paper.scored_leaves,
        rows,
    )

    detect_duplicate_students_and_item_columns(matrix)
    detect_unknown_student_and_question_numbers(matrix)
    detect_attendance_numeric_conflicts(matrix)
    audit_optional_total_column(matrix)

    return persist_preview_with_original_row_column_locations(matrix)
```

```python
def confirm_scores(import_id, expected_revision, acknowledged_issues, submission_id):
    with teaching_repository.write_transaction() as tx:
        replay_or_validate_submission(tx, submission_id)

        preview = tx.require_score_preview(import_id, expected_revision)
        tx.require_assessment_revision_unchanged(preview)
        tx.require_active_score_revision_equals(preview.base_score_revision_id)

        require_no_blocking_issues(preview)
        require_missing_data_explicitly_acknowledged(preview, acknowledged_issues)

        revision = tx.insert_draft_score_revision(
            participant_snapshot=preview.participants,
            base_revision_id=preview.base_score_revision_id,
        )

        tx.insert_full_score_matrix(revision, preview.matrix)
        tx.seal_score_revision(revision)
        tx.set_active_score_revision(preview.assessment_id, revision)
        tx.mark_import_confirmed(import_id)

        return tx.save_submission_result(revision)
```

成绩修正：

```python
def correct_scores(base_revision_id, changes, expected_assessment_revision):
    base = load_immutable_score_snapshot(base_revision_id)
    matrix = copy_full_matrix(base)
    apply_validated_changes(matrix, changes)

    return confirm_new_score_revision(
        matrix=matrix,
        participant_snapshot=base.participant_snapshot,
        expected_assessment_revision=expected_assessment_revision,
    )
```

固定行为：

- 缺列或空白经明确确认后保存为 missing，不能补零。
- 缺考、免考与数值同时出现时阻断确认。
- 全部小题有效且填写了总分时，总分不符阻断确认。
- 存在 missing 时，可选总分只作提示，不用总分反推小题得分。
- 新增补考人次后，旧成绩修订仍使用旧名单快照。
- 修正产生新完整版本，旧报告不自动改写。

**验收：**有效 0、空白、缺考、免考、两位小数、超满分、公式无缓存、重复映射、并发确认和中途回滚分别验证。

#### T70：学情分析及证据

```python
def analyze(snapshot, selected_attempts):
    require_one_attempt_per_student(selected_attempts)
    results, evidence = [], []

    for participant in selected_attempts:
        for knowledge in snapshot.paper_knowledge_points:
            items = snapshot.scored_items_for(knowledge.id)
            cells = snapshot.scores_for(participant.id, items)

            valid = [c for c in cells if c.status == "recorded"]
            losses = [
                c for c in valid
                if c.score_units < snapshot.max_score_units(c.item_id)
            ]

            if losses:
                observation = "needs_consolidation"
            elif not valid:
                observation = "no_evidence"
            elif len(valid) < len(items):
                observation = "incomplete"
            else:
                observation = "full_credit"

            results.append(make_result(
                participant, knowledge, observation,
                expected_count=len(items),
                valid_count=len(valid),
                loss_count=len(losses),
            ))

            evidence.extend(make_all_item_evidence(
                participant, knowledge, items, cells,
            ))

    return results, evidence
```

```python
def build_analysis_input(assessment, score_revision_id, selected_attempts):
    score = load_confirmed_score_revision(score_revision_id)

    return freeze({
        "paperRevision": load_exact_paper_revision(score.paper_revision_id),
        "scoreRevision": score,
        "participants": score.participant_snapshot,
        "selectedAttempts": selected_attempts,
        "ruleCode": "any_loss_v1",
    })
```

计算在事务外进行，结果、证据和 `running → ready`在同一事务完成。

班级报告必须返回：

```text
选中学生人数
具有有效成绩人数
本次需巩固人数
信息不全人数
无有效依据人数
本次相关题全部满分人数
```

“需巩固比例”使用该知识点具有有效成绩的学生人数作为分母，分母为零返回 `null`。信息完整性单独展示，即使已有失分，也显示仍有 missing。

固定行为：

- 综合题失分关联全部已确认知识点，展示“具体错因待教师确认”。
- 不将各知识点的分数相加作为试卷总分，因为同题可能关联多个知识点。
- 教师备注不改原始成绩和规则结果。
- 报告证据可定位原题、满分、得分、状态和知识点修订。
- 相同固定输入可复算得到相同结果；旧报告可继续查看。

**验收：**独立验收者使用另一份简单实现或手工表复算，结果逐项一致；不能直接调用生产分析函数作为验收依据。

#### T50：题库知识点关联和 AI 补题

修改正式题目必须保留关联：

```python
def patch_question(question_id, content, metadata, expected_revision):
    with question_bank.write_transaction() as tx:
        old = tx.require_question(question_id, expected_revision)
        new_revision = tx.append_question_revision(content, metadata)

        tx.copy_knowledge_links(old.revision_id, new_revision.id)
        tx.update_current_pointer(question_id, new_revision.id)

        return tx.question_view(question_id)
```

专门修改关联时，创建新题目修订并替换关联。草稿内容或标注变化均递增 revision，重新进入 `needs_review`。

```python
async def generate_questions(job):
    frozen = job.frozen_input
    raw = await resolve_frozen_model(job.model_snapshot).generate(frozen.prompt)

    candidates = GenerateReply.validate(raw)
    require_known_knowledge_ids(candidates, frozen.allowed_knowledge)
    require_allowed_evidence_refs(candidates, frozen.allowed_evidence)
    require_no_arbitrary_asset_paths_or_urls(candidates)

    original = store_generated_original(raw)

    with question_bank.write_transaction() as tx:
        tx.require_current_lease_and_not_cancelled(job)

        import_batch = tx.create_generated_import_once(job.id, original)

        for candidate in candidates:
            draft = tx.create_draft(
                import_batch,
                candidate,
                review_state="needs_review",
                extraction_method="ai",
            )
            tx.save_draft_knowledge_candidates(draft, candidate.knowledge_ids)

        tx.save_generation_provenance(import_batch, job.model_snapshot)
        tx.mark_job_succeeded(job.id, import_batch.id)
```

随后固定进入：

```text
AI 草稿 → 教师校对题意/答案/解析/知识点
        → reviewed → 既有题库确认事务
        → 正式 questionRevisionId → 可选入练习
```

不能复用现有 organizer 的输出解析器作为新出题解析器：新题没有真实上传原文块，应使用独立 `GenerateReply`，但复用模型解析、任务基础、草稿和确认内核。

固定行为：

- AI 自检不等于教师审核。
- 生成原件明确标示 AI 来源，不伪造教材题来源。
- 旧 `knowledgeTags`保留兼容，不能自动成为正式知识点。
- 旧指纹保留，新增版本化派生指纹，纳入共享材料及资产真实字节散列。
- 首版 AI 新题以文字和公式为主；必要几何图由教师提供受管资产。

**验收：**改题后关联存在；旧修订不变；非法 JSON、截断、未知知识点和虚构证据拒绝；AI 草稿不能绕过确认进入正式练习。

#### T80：针对性练习、DOCX 和成绩回流

```python
def suggest_practice(analysis_run_id, constraints):
    report = load_ready_analysis(analysis_run_id)
    targets = require_selected_knowledge_points(report, constraints)

    candidates = find_confirmed_questions(
        subject=report.subject_id,
        knowledge_ids=targets,
        types=constraints.types,
        difficulty=constraints.difficulty,
    )

    candidates = exclude_original_questions_and_duplicates(candidates)
    candidates = stable_sort(
        candidates,
        by=("uncovered_target_count_desc", "constraint_match_desc", "question_id"),
    )

    selection, gaps = select_until_teacher_targets(candidates, constraints)
    return {"selection": selection, "gaps": gaps}
```

一题覆盖多个知识点只占一个题位。缺题返回实际缺口，教师主动点击 AI 补题；不自动放宽要求。

```python
def review_practice(practice_id, expected_revision, submission_id):
    with publication_coordinator:
        snapshots = load_exact_confirmed_question_and_knowledge_revisions(practice_id)
        verify_assets_and_rich_content(snapshots)

        with teaching_repository.write_transaction() as tx:
            replay_or_validate_submission(tx, submission_id)
            draft = tx.require_practice_draft(practice_id, expected_revision)

            require_teacher_confirmed_item_structure_and_max_scores(draft)
            tx.freeze_content_and_knowledge_snapshots(draft, snapshots)
            tx.mark_practice_reviewed(draft)
            return tx.save_submission_result(draft.revision_id)
```

```python
def export_practice(reviewed_revision, variant):
    document = new_practice_docx()
    emitted_materials = set()

    for item in reviewed_revision.items:
        emit_required_shared_material_once(document, item, emitted_materials)
        emit_stem_options_formulas_images(document, item)

        if variant == "teacher":
            emit_answer_and_explanation_or_not_provided(document, item)

    return store_verified_export(document, reviewed_revision.input_hash)
```

```python
def practice_to_assessment(reviewed_revision, class_ids, held_on, submission_id):
    with teaching_repository.write_transaction() as tx:
        replay_or_validate_submission(tx, submission_id)

        paper = tx.create_paper_from_practice_once(
            source_practice_revision_id=reviewed_revision.id,
        )
        tx.copy_scored_leaves_and_knowledge_snapshots(paper, reviewed_revision)
        tx.confirm_paper(paper)

        assessment = tx.create_assessment(paper, class_ids, held_on)
        tx.freeze_selected_participants(assessment)

        return tx.save_submission_result(assessment)
```

成绩模板包含学号、姓名、出勤及每个计分叶子列，另附固定试卷修订和题号映射说明。回流使用 T60 的成绩流程，再生成新学情报告。

**验收：**学生卷无答案和解析；共同材料正确；旧练习不随题库修改；重复施测转换不产生重复记录；回流准确关联原练习小题。

#### T90/F30：后台教案、学情驱动 AI 和旧稿兼容

现有 `LessonPlanData`和本地 `DraftEnvelope.schemaVersion=1`保持兼容。后台外层记录版本为 v2，不能把现有内容结构直接改成 v2。

后台教案需要选择班级和学科；旧稿导入要求补齐这些上下文，但保留原本地草稿。

```typescript
type EditorSession = {
  source: "local" | "server";
  documentId?: string;
  editRevision: number;               // 本地编辑、撤销、重做序号
  serverRevision?: number;            // 后台 CAS
  serverRevisionId?: string;
  acknowledgedEditRevision: number;
  syncState: "idle" | "saving" | "saved" | "failed" | "conflict";
};
```

每次成功后台保存追加内容修订，并更新当前指针；相同内容散列不重复追加。修订内容不原地改写，“审核”只改变审核状态。

**旧稿导入**

```typescript
async function importLegacyDraft(context) {
  const raw = legacyRepository.loadRaw();
  if (raw.failed) return showReadFailureWithoutOverwrite();
  if (raw.missing) return showNoDraft();

  validateDraftEnvelopeV1(raw.value);

  const result = await lessonApi.importLocal({
    submissionId: stableOperationId(raw.value, context),
    draft: structuredClone(raw.value),
    context,
  });

  // 保留原键，不删除本地旧稿
  await navigateWithSaveGuard(result.documentId);
}
```

后台缓存使用按 `documentId`分隔的新键，不能写入原单稿键。

**串行后台保存**

```typescript
async function saveServerDraft(envelope) {
  writeDocumentRecoveryCache(envelope, serverRevision);

  const saved = await lessonApi.save(documentId, {
    submissionId: stableOperationId(envelope),
    expectedRevision: serverRevision,
    data: envelope.data,
  });

  serverRevision = saved.revision;
  serverRevisionId = saved.revisionId;
  acknowledgedEditRevision = envelope.revision;

  // 用户已继续编辑时，只更新 ACK，不 hydrate 旧响应
  markAcknowledged(envelope.revision);
}
```

409 时暂停自动写入，保留本地输入并展示差异；读取失败不得创建空稿覆盖。

**AI 输入**

```python
def freeze_lesson_generation_input(command):
    lesson = load_exact_lesson_revision(command.lesson_revision_id)
    report = load_ready_analysis(command.analysis_run_id)

    return {
        "lesson": lesson.data,
        "classSummary": anonymized_report_summary(report),
        "weakKnowledge": selected_report_knowledge(report),
        "teacherRequirements": command.requirements,
        "durationMinutes": command.duration_minutes,
        "textbookEvidence": verified_selected_evidence(command),
        "questionSnapshots": verified_selected_questions(command),
        "modelSnapshot": resolve_chat_model(command.model_profile_id).snapshot,
    }
```

学生姓名、学号和人员 ID 不进入模型输入。默认用班级统计；需要个别练习时使用匿名对象和固定知识点集合。

AI 允许建议：

```text
coreCompetencies
keyPoints
teachingDesign
process
exercises
```

标题、课时、课型及教学反思继续由教师控制。`process`按完整字段接受，不使用数组索引路径。过程建议附带总课时预算、各环节分钟数、目标知识点、活动、检测及依据；界面显示结构化说明，接受时映射到既有过程字段。

**生成和应用**

```typescript
async function generateLessonProposal() {
  await flushDraft();

  const identity = freeze({
    documentId,
    baseServerRevision: serverRevision,
    baseRevisionId: serverRevisionId,
    baseEditRevision: store.revision,
    analysisRunId,
    modelProfileId,
  });

  const token = ++requestSequence;
  const job = await lessonApi.createProposal(identity);
  const terminal = await observeJob(job);

  if (!matchesCurrentDocumentAndRequest(identity, token)) return;
  if (terminal.state !== "succeeded") return showTaskState(terminal);

  const proposal = await lessonApi.getProposal(terminal.result.proposalId);
  showDiffAndEvidence(proposal);

  if (store.revision !== identity.baseEditRevision) disableApplyAsStale();
}
```

```python
def apply_lesson_proposal(proposal_id, selected_fields, expected_revision, submission_id):
    with teaching_repository.write_transaction() as tx:
        replay_or_validate_submission(tx, submission_id)

        proposal = tx.require_pending_proposal(proposal_id)
        lesson = tx.require_lesson_revision(expected_revision)

        require_proposal_base_matches(proposal, lesson)
        require_allowed_selected_fields(selected_fields)
        require_valid_evidence_ids(proposal)
        require_valid_duration_and_process(proposal)

        merged = merge_selected_fields(lesson.data, proposal, selected_fields)
        revision = tx.append_lesson_revision(merged, source="ai_accepted")
        tx.update_current_pointer(revision)
        tx.mark_proposal_applied(proposal)

        return tx.save_submission_result(revision)
```

前端应用期间短暂锁定编辑，先 flush，成功后才载入后端返回内容。首次部分应用后建议终结，未选字段不再自动应用。撤销产生新的编辑和保存版本。

**验收：**旧稿、规则填充、撤销重做、JSON、Word、打印全部回归；生成期间编辑使建议过期；切教案后旧响应不覆盖；应用失败保留原稿；仅选定字段改变。

#### F10/F20/F30：统一交互与请求竞态

```typescript
async function loadPreview(input) {
  const token = ++requestSequence;
  abortPreviousRequest();

  try {
    const result = await api.preview(input, currentAbortSignal);
    if (token !== requestSequence) return;
    renderPreview(result);
  } catch (error) {
    if (isAbort(error)) return;
    keepCurrentInputAndShowError(error);
  }
}
```

```typescript
async function observeJob(job) {
  while (!viewSignal.aborted) {
    const current = await workflowApi.get(job);
    if (!matchesCurrentView(job, current.attempt)) return;

    renderJobState(current);
    if (isTerminal(current.state)) return current;

    await abortableDelay(pollInterval(current));
  }
}
```

轮询间隔固定为：开始 2 秒，持续 30 秒后 5 秒；恢复页面按持久 job 身份继续查询。

统一行为：

- 导入页面依次展示文件、映射、预览、校对、确认，不能一上传就正式入库。
- 422 显示行列错误；409 保留当前输入。
- 知识点 metadata 与关联两个修订接口必须串行使用返回版本。
- 原卷和报告证据使用完整内容接口，不直接复用只返回未归属块的旧题库来源 DTO。
- 报告状态完全使用后台结果，前端不重新推断掌握情况。
- 旧修订导出迟到时，不能替换当前修订的产物展示。
- 本机缓存、后台保存及打开打印窗口分别使用准确文案。

### 五、验收数据、质量门槛和最终文档交付

#### 1. 固定学情验收样本

设三个计分小题：

| 小题 | 满分 | 关联知识点 |
|---|---:|---|
| Q1 | 2 | K1 |
| Q2 | 3 | K1、K2 |
| Q3 | 5 | K2 |

成绩与预期：

| 学生 | Q1 | Q2 | Q3 | K1 预期 | K2 预期 |
|---|---:|---:|---:|---|---|
| A | 2 | 2 | 5 | 本次需巩固 | 本次需巩固 |
| B | 2 | 3 | 空白 | 本次相关题满分 | 信息不全 |
| C | 缺考 | 缺考 | 缺考 | 无有效依据 | 无有效依据 |
| D | 0 | 3 | 5 | 本次需巩固 | 本次相关题满分 |

两知识点均有 3 名有效成绩学生：

- K1 需巩固人数为 2，比例为 `2/3`。
- K2 需巩固人数为 1，比例为 `1/3`。
- C 单独列为无有效依据，不能计作零分学生。
- A 的 Q2 同时影响 K1、K2，不能将重复知识点统计相加作为总失分。

#### 2. 必须覆盖的失败和并发场景

1. 同 submission 重放；同 submission 不同请求冲突。
2. 两个成绩导入同时确认，只允许基于当前版本的提交成功。
3. 确认中途异常，正式成绩和正式题目不出现部分写入。
4. 取消后模型迟到，旧 lease 无法发布。
5. 重试新 attempt 后，旧 attempt 不能覆写结果。
6. 知识点归档与新关联并发，不能产生非法新引用。
7. 改题干后正式知识点关联保留。
8. 新增补考人次不改变旧成绩和旧报告。
9. AI 生成期间编辑教案，旧建议禁止应用。
10. 保存旧版本在途时产生新编辑，旧响应不覆盖新输入。
11. 旧稿损坏、后台读取失败和缓存冲突均不被空稿覆盖。
12. 学生卷不包含答案、解析或教师说明。
13. 缺图片、公式转换失败、未归属原文均不能静默丢弃。
14. 四库备份、缺失文件、半完成恢复及旧格式恢复分别验证。

#### 3. 检查与证据

模块实现运行相关 pytest/Vitest；集成候选运行：

```powershell
$env:NODE_OPTIONS = "--no-experimental-webstorage"
npm.cmd run check
npm.cmd run test:api
npm.cmd run test:e2e
npm.cmd run test:chat
npm.cmd run template:verify
```

- 路由、保存、导出改动的 E2E 前必须重新 build。
- 浏览器使用隔离会话和 5174；API 使用测试数据和隔离端口；Qdrant 使用 16333。
- 不操作正式草稿、正式 `.local-data`或真实凭证。
- 中文 DOCX、公式、表格、长题干和图片须在 Word/WPS 实际查看。
- 前端覆盖 1440×900、1920×1080、390×844，教案另覆盖 1024×768。
- 功能、视觉、真实模型质量分别记录。
- 既有 R-14、R-18、R-19 等问题按台账如实报告；R-15 以最新关闭记录为准。
- 未执行项写明 `not_run`及原因，不能用构建通过代替业务验收。

首版性能验收样本为 200 名学生、100 个计分小题；在 8 核、16GB、SSD 的记录环境中，非模型成绩预览目标不超过 10 秒，分析目标不超过 3 秒。记录实测，不将模型生成耗时混入该指标。

#### 4. 阶段验收门槛

| 门槛 | 通过标准 |
|---|---|
| G0 公共基础 | 契约一致；幂等、迁移、任务取消和恢复测试通过 |
| G1 数据建立 | 知识点、名单、原卷和题库可以校对确认，来源完整 |
| G2 学情 MVP | 成绩导入确认，固定样本独立复算一致，证据可回查 |
| G3 练习闭环 | 选题及补题审核、DOCX、成绩模板、施测转换和回流完成 |
| G4 AI 教案 | 固定学情依据生成建议，选字段应用，旧教案能力全部保留 |
| G5 整体交付 | 独立验收、兼容、四库备份恢复及工程检查完成 |

真实 AI 教学质量未验收时，技术链路可以记录通过，但不能宣称题目或教学建议质量已通过。生成内容仍须教师审核。

#### 5. 文档交付

后续制作一份统一执行计划书，提供：

- Markdown 源文（本文）；
- 可编辑 DOCX（后续交付项）；
- 经渲染检查的 PDF（后续交付项）。

存放于现有教学闭环设计目录下，命名为“多Agent实施任务计划书_v2.0”。内容包括本计划、完整 API/DTO、各任务卡、伪代码、数据库增量差异、依赖图和验收矩阵。

旧八人任务书保留历史记录，新计划注明人员排期已被多 Agent 调度方式取代。当前任务进度只更新 `CURRENT_STATUS.md`；稳定决定写入 `PROJECT_GUIDE.md`，现行接口和路由分别更新 API、ROUTES。不另建竞争性的进度入口。本文中的接口是拟实施接口，未经实际实现和核验不得写成现行已可用接口。
