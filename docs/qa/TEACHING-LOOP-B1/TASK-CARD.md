# TEACHING-LOOP B1 任务卡（富内容基础 / 知识点后端 / 名单后端）

- 批次：**B1 = T10 + T20 + T30-a + CTRL**（依 [多Agent实施任务计划书 v2.0 §二.3](../../design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)）
- 版本：v1.0；建立：2026-09-30
- 起点：`main@301fc356493db21d187ab85f32fd49dfffdc51ef` 的**工作区**（B0 r2 交付未提交）。
  B0 基线以 [B0 FROZEN-CANDIDATE r2](../TEACHING-LOOP-B0/FROZEN-CANDIDATE.json) 为准（开工核对 55/55 一致，0 差异）。
- 批次完成条件：知识点库与教学库 B1 业务表登记并可用；知识点可人工/表格/AI 候选建立并确认；
  名单可导入并确认；富内容解析/渲染基础可用；独立验收 pass/not_run 逐项有据。
- 本批**不**实现：原卷（T40）、成绩（T60）、学情（T70）、练习（T80）、教案后端（T90）、正式施测创建（T30-b）、
  任何新增前端页面与导航；不改既有教材解析语义；不实现成绩/得分相关任何表。

## 0. B0 承接与 B0 文件回改

- 复用 B0：`app/repositories/jobs`、`app/services/jobs`、`app/services/submissions`、`app/services/assets`
  （`AssetStore`/`FileAssetsRepository`）、`KnowledgeCatalog`/`TeachingCatalog`、错误详情 `details`、迁移登记。
- 本批对 B0 文件的**回改**（只此几处，逐条说明理由与回归项）：

| 文件 | 改动 | 理由 | 回归项 |
| --- | --- | --- | --- |
| `app/core/migrations/knowledge.py`、`teaching.py` | 追加 `0002`（不改 `0001` 声明与散列） | B1 业务表登记 | `test_b1_migrations.py`（新）；`test_migrations.py` 中知识点库"仅基线"断言按两条迁移更新；正式数据根只读核对 0 漂移 |
| `apps/api/tests/test_migrations.py`、`test_startup_gates.py` | 迁移计数断言 `1 → 2` | 追加 0002 的连带更新（非产品行为变化） | 两文件全绿 |
| `app/main.py` | 装配 B1 服务与可选路由注册（`_include_optional_routers`） | 服务/路由归 CTRL；模块缺失时只记录原因（并行开发与裁剪部署安全） | 全量 `test:api`；本机装配冒烟（四服务 + 两路由） |
| `app/contracts/teaching_loop.py` | ①所有契约模型统一 `populate_by_name=True`；②`TableBlock.columnCount`（可选，`ge=1`） | ①**真实缺陷**：`error_details()` 因 `ErrorDetails` 未开构造别名而不可用（T10/T30-a 双双踩到，B0 未被发现）；②表格扁平单元格序列缺行边界，无法精确还原（T40/T50/前端消费所需）——加法式修改，旧数据可缺省 | `test_contracts_b1.py`（新）；T10/T30-a 全部套件；前端镜像 `teaching-loop.ts` 同步 |
| `apps/api/pyproject.toml`、`uv.lock` | 新增 `openpyxl==3.1.5`、`math2docx==3.1.0`（+传递依赖） | 计划书 §三.5 锁定版本 | 迁移/表格/富内容套件 |

- **不改** `KnowledgeCatalog`/`TeachingCatalog` 的 `REQUIRED_TABLES`：启动门控只要求 B0 基础表，
  合法"尚未应用 B1 迁移"的旧库必须能启动（B1 要求 §三.7）；新结构由迁移保证，另加测试证明。

## 1. 文件归属（未列入者不得写）

| 归属 | 新建 | 修改 |
| --- | --- | --- |
| **CTRL（总控）** | `app/contracts/knowledge.py`、`app/contracts/roster.py`、`app/services/publication.py`、`app/services/tabular.py`、`apps/web/src/contracts/knowledge.ts`、`apps/web/src/contracts/roster.ts`、`apps/api/tests/test_b1_migrations.py`、`apps/api/tests/test_tabular.py`、`apps/api/tests/test_publication.py` | `app/core/migrations/{knowledge,teaching}.py`、`app/main.py`、`apps/api/pyproject.toml`、`apps/api/uv.lock`、`apps/api/AGENTS.md`、`docs/API.md`、`docs/PROJECT_GUIDE.md`、`docs/CURRENT_STATUS.md`、`docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md`（T30-a/T30-b 阶段依赖登记）、`docs/qa/TEACHING-LOOP-B1/**` |
| **T10** | `app/services/rich_content/{__init__,blocks,formulas,parser_docx,renderer_docx}.py`；`apps/api/tests/rich_content_support.py`、`apps/api/tests/test_rich_content_parser.py`、`apps/api/tests/test_rich_content_renderer.py` | 无 |
| **T20** | `app/repositories/knowledge/{points,imports}.py`；`app/services/knowledge/{__init__,service,imports,evidence,suggestions}.py`；`app/api/v1/knowledge.py`；`apps/api/tests/{test_knowledge_points,test_knowledge_imports,test_knowledge_suggestions}.py` | 无 |
| **T30-a** | `app/repositories/teaching/{classes,students,roster}.py`；`app/services/roster/{__init__,service,imports}.py`；`app/api/v1/roster.py`；`apps/api/tests/{test_roster_classes,test_roster_imports}.py` | 无 |
| **V00** | `docs/qa/TEACHING-LOOP-B1/V00-REPORT-*.md`、`V00-probes/**` | 无（只读产品代码） |

共享文件（契约、迁移、main.py、pyproject/uv.lock、文档、Git）一律由 CTRL 独占；实现者需要改动时提交建议。

## 2. 冻结契约（实现者按此编码；类型定义不得复制第二份）

Python：`app/contracts/knowledge.py`、`app/contracts/roster.py`（B1 冻结）；`app/contracts/teaching_loop.py`（B0 冻结，含 `RichContentV2`/`ContentBlock`/`AssetRef`/`ErrorIssue`/`JobView`/`canonical_hash`）。
前端镜像：`apps/web/src/contracts/{knowledge,roster}.ts`（本批不建页面，仅保持类型单一来源）。

要点（逐条有测试）：
1. **知识点**：`code` 学科内唯一；`id` 稳定身份、`revisionId`/`version` 不可变修订；`revision` 乐观锁；
   更新必须核 `expectedRevision`，空白默认不修改、`clearFields` 才清空；归档保留历史引用、新使用禁选归档。
2. **父树**：父节点须同库同科且本批内可引用；跨学科、自指、环、缺父节点都必须给出**可定位**错误
   （`details.issues[].field` = `parentCode`/`parentId`），环由 DB 触发器兜底（`KNOWLEDGE_CYCLE`）。
3. **别名**：同知识点内去重；同名/同别名跨知识点只提示（返回 `warnings`），**绝不自动合并**。
4. **导入**：表头六个字段 `subjectCode/code/name/description/parentCode/aliases`；预览持久化（批次 + 行 + issues）；
   `create/update/ignore` 三类动作；失败**整批回滚**；确认幂等（`submissionId` 重放返回原结果）。
5. **AI 候选**：只生成 `source="ai"` 的待确认批次（同一确认流程），不写正式表；候选依据必须在允许集合内
   （既有知识点 id 或输入证据 id）；非法 JSON/未知引用/截断/模型配置失效/取消迟到都有明确行为；
   **候选写入与任务 succeeded 在知识点库同一事务**；教材读取失败不得当"没有依据"（报 `TEXTBOOK_EVIDENCE_UNAVAILABLE`）。
6. **名单**：学号文本保留前导零；无学号/同名/姓名不符/重复行进人工核对；确认必须给出每行 `link|create|ignore`
   且 `link` 必须带 `studentId`；未出现的学生不自动退班；转班保留旧归属；整批回滚；409/422 用 `details.issues` 定位行。
7. **施测**：只冻结契约（`AssessmentCreateRequest`/`ParticipantSnapshot`/`ConfirmedPaperRevisionView`/`ConfirmedPaperReader`）；
   真实创建 = T30-b；未实现接口 501 `FEATURE_NOT_IMPLEMENTED`，不返回模拟成功。

## 3. 迁移与结构（已登记，编号固定）

| 库 | 迁移 | 内容 |
| --- | --- | --- |
| 知识点库 | `0002_knowledge_business_tables` | 设计 5 表（`subjects`/`knowledge_points`/`knowledge_point_revisions`/`knowledge_aliases`/`textbook_knowledge_links`）+ 3 索引 + 4 触发器（环检测、修订不可变）+ **补齐** `knowledge_imports`/`knowledge_import_rows`（+2 索引） |
| 知识点库 | `0003_knowledge_import_issues_column` | `knowledge_imports` 补 `issues_json`（批次级问题独立落列；0002 只给了 mapping/warnings，实现者一度塞进 `mapping_json` 保留键，按"只追加迁移"纠正） |
| 教学库 | `0002_teaching_business_tables` | 设计 3 表（`classes`/`students`/`class_memberships`，含 `ux_active_membership` 部分唯一索引、`ix_membership_student`）+ **补齐** `roster_imports`/`roster_import_rows`（+4 索引） |

偏差记录（已在迁移文件注明）：`roster_import_rows` 保存可查询的 `name`/`student_no`；
`knowledge_imports.file_asset_id` 是**跨库逻辑引用**（EXT，指向教学库 `file_assets`，由服务核验）；
批次级 issues：知识点导入独立列（0003），名单导入由行 issues 派生（T30-a 口径，不落库）；
施测三表不在本批（依赖 T40 的 `paper_revisions`）。

## 4. HTTP 接口（全部 `/api/v1` 前缀；错误信封与 B0 一致）

### 知识点（T20）

| 方法与路径 | 说明 |
| --- | --- |
| GET `/knowledge-points` | 列表：`subjectId` 必填？否，可筛；`status`、`parentId`、`q`（名称/别名/编码模糊）；分页 `{items,total,offset,limit}` |
| POST `/knowledge-points` | 人工建立（201）；同 `(subjectId, code)` 冲突 409 `KNOWLEDGE_CODE_CONFLICT` |
| GET `/knowledge-points/{id}` | 详情（含别名、当前修订、教材依据数） |
| PATCH `/knowledge-points/{id}` | 更新（`expectedRevision`；`clearFields`）；改名=追加修订 |
| POST `/knowledge-points/{id}/archive`、`/restore` | 归档/恢复（`expectedRevision`） |
| POST `/knowledge-imports` | multipart：`file` + `subjectId` + 可选 `mappingJson`/`sheetName`；返回预览视图 |
| GET `/knowledge-imports`、GET `/knowledge-imports/{id}` | 批次列表 / 详情（含行与 issues） |
| PATCH `/knowledge-imports/{id}` | 改映射 / 行动作（`expectedRevision`） |
| POST `/knowledge-imports/{id}/confirm` | 确认（`expectedRevision`+`submissionId`+`actions`）；重放返回原结果 |
| POST `/knowledge-suggestion-jobs` | AI 候选（`modelProfileId`+`subjectId`+`materials`/`textbookEvidence`）→ 202 `JobView` |
| GET `/knowledge-points/{id}/textbook-links`、POST（`expectedRevision`+区间）、DELETE `/{linkId}` | 教材依据（可选关联；区间经教材目录核验并冻结标题） |

### 名单（T30-a）

| 方法与路径 | 说明 |
| --- | --- |
| GET/POST `/classes`、GET/PATCH `/classes/{id}`、POST `/classes/{id}/archive`、`/restore` | 班级 CRUD（`schoolYear`+`code` 用户内唯一 409 `CLASS_CODE_CONFLICT`） |
| GET `/classes/{id}/students` | 该班活跃成员（含归属历史） |
| GET `/students`（`q` 模糊）、GET `/students/{id}`、POST `/students`（无学号显式建档） | 学生身份 |
| PATCH `/students/{id}`、POST `/students/{id}/transfer` | 改名/改学号（乐观锁）、转班 |
| POST `/classes/{id}/roster-imports` | multipart 名单上传 + 预览 |
| GET `/roster-imports`、GET `/roster-imports/{id}`、PATCH `/roster-imports/{id}`、POST `/roster-imports/{id}/confirm` | 批次/预览/校对/确认（幂等） |

施测（`POST /assessments` 等）**不注册路由**：由 B0 通配占位返回 501 `FEATURE_NOT_IMPLEMENTED`，文档标注 planned（T30-b）。

## 5. 装配点（CTRL 实施；实现者提供工厂，签名固定）

```python
# T20
def build_knowledge_service(
    catalog: KnowledgeCatalog, *,
    asset_store: AssetStore, file_assets: FileAssetsRepository,
    evidence: TextbookEvidenceReader, coordinator: PublicationCoordinator,
    model_resolver: Callable[..., ChatModelHandle] | None,
    job_engine: JobEngine | None,
) -> KnowledgeService: ...

# T30-a
def build_roster_service(
    catalog: TeachingCatalog, *,
    asset_store: AssetStore, file_assets: FileAssetsRepository,
    job_engine: JobEngine | None,        # 预留（本批不用）
) -> RosterService: ...
```

- 服务挂 `app.state.knowledge_service` / `app.state.roster_service`；未装配时路由 503 `SERVICE_UNAVAILABLE`（不返回空列表）。
- AI 候选必须走 B0 任务引擎：`engine.store("knowledge").create(kind="suggestion", frozen_input=…, model_snapshot=…)`
  → `engine.schedule("knowledge", job_id, executor, uses_model=True)`；执行器在**事务外**调用模型，
  返回 `JobOutcome(result=…, publish=…)` 在知识点库同一事务写候选批次与 succeeded。
- `PublicationCoordinator`（`app/services/publication.py`）注入知识点服务：确认导入、归档、教材依据发布都在
  `coordinator.publication(operation=…)` 内"核验外部修订 → 本库短事务"；锁内不得调用模型/解析文件。
- 表格读取统一用 `app/services/tabular.py`（`read_table`），不得各自实现 XLSX/CSV 解析。

## 6. 验收条件

| 编号 | 条件 | 责任 | 证据 |
| --- | --- | --- | --- |
| A1 | B1 迁移：新库/既有 B0 库两条路径重复应用幂等；中途失败回滚；`0001` 散列不变 | CTRL | `test_b1_migrations.py` |
| A2 | 合法"仅 B0 结构"的旧库能通过启动门控；迁移后新表齐备 | CTRL | `test_b1_migrations.py` |
| A3 | 富内容解析：段落/表格（合并单元格）/图片（真实字节+散列+尺寸+块位置）/OMML/未知对象可见问题；共享材料分组 | T10 | `test_rich_content_parser.py` |
| A4 | 富内容渲染：学生版无答案与解析、共同材料只出一次、图片重建 relationship（不复用旧 rId）、OMML 原样、LaTeX 经 math2docx；转换失败保留原件定位并报错 | T10 | `test_rich_content_renderer.py` |
| A5 | 知识点 CRUD/父树/别名/归档/历史名称；同 code 冲突、跨学科父、环、缺父可定位 | T20 | `test_knowledge_points.py` |
| A6 | 表格导入：预览持久化、映射、动作、整批回滚、重放、空白不清空/显式清空 | T20 | `test_knowledge_imports.py` |
| A7 | AI 候选：非法 JSON/未知引用/截断/配置失效/取消迟到/不自动入库；同库事务提交；教材读取失败不当无依据 | T20 | `test_knowledge_suggestions.py` |
| A8 | 名单：0012 前导零、无学号/同名/重复行/姓名不符、确认决策校验、未出现不退班、转班保留旧归属、重放、整批回滚 | T30-a | `test_roster_imports.py` |
| A9 | 班级/学生 CRUD 与乐观锁；学号唯一冲突 409；归档班级行为 | T30-a | `test_roster_classes.py` |
| A10 | 路由装配：未装配 503、非法参数 422 带 `details.issues`、plan 施测 501 | CTRL+T20/T30-a | 各路由测试 |
| A11 | 工程检查：定向 pytest + 全量 `test:api` + `npm run check` 全绿 | CTRL | EVIDENCE-COMMANDS |
| A12 | 独立验收 V00：逐项 pass/fail/not_run（含变异实验证明断言有牙齿） | V00 | `V00-REPORT-01.md` |

## 7. 测试资源与结果格式

- 全部使用 `tmp_path` 隔离数据根；**独立探针/脚本必须先设 `ZQKY_DATA_DIR` 再导入 `app.main`**（conftest 只保护 pytest 进程）。
- 模型一律受控替身（参照 `tests/test_question_bank.py` 的 `FakeLLMProvider`/`make_handle`/`FakeResolver`）。
- XLSX 样本用 openpyxl 现造（`tmp_path`），DOCX 样本用 python-docx 现造（含共享材料/两小题/合并表格/图片/行内+独立公式）。
- 真实模型、真实 Word/WPS 排版、真实 Qdrant 均 `not_run`（本批无此环境），分开记录。
- 结果格式（每个实现者）：

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

## 8. 预先登记的风险

1. `ux_active_membership` 只保证"同一 (班级, 学生) 只有一条活跃归属"，**不阻止**同一学生同时在两个班活跃（设计原文如此）；
   业务层不额外收紧，界面在 B2+ 提示。
2. 施测三表与 `paper_revisions` 的复合外键/触发器随 T40 登记；T30-b 完成前 `POST /assessments` 保持 501。
3. `knowledge_imports.file_asset_id` 是跨库逻辑引用（EXT）：AI 批次的原始输出先登记为教学库 `file_assets`
   （kind=attachment），再写知识点批次；两步之间失败会留下未被引用的资产登记（只增不改，可从备份恢复核对）。
4. 富内容 LaTeX→OMML 依赖 `math2docx==3.1.0`（+ latex2mathml/mathml2omml-as），只用于**新题导出**；
   原卷 OMML 原样保留，不反向转 LaTeX（本批不做 OMML→LaTeX）。
5. DOCX 视觉排版（Word/WPS 实际打开）本机无法自动验证：结构级断言 + `not_run` 说明，不把 XML 存在当排版通过。
6. B0 已登记迁移的声明与散列一律不得改写；B1 只追加 `0002`/`0003`（已核对正式数据根 0 漂移）。
7. 名单确认的身份冲突：**DB 唯一约束在写入时兜底**（同学号两行都 create → 409 `STUDENT_NO_CONFLICT` +
   `details.issues[].row` 定位 + 零写入），与 422 预检阻断并存——两者都禁止假成功；
   同名（两行都无学号）`link 到既有学生 + create 新学生` 是**教师显式消歧**，允许（姓名不是主键）。
8. `publish` 抛错时任务停 `running`（B0 引擎契约"异常向上抛、同事务回滚"），失败不落 succeeded；
   收敛路径是租约过期/重启 `reconcile` → `interrupted`，可重试。B1 不改引擎语义，登记为已知边界。
9. 预检与兜底两条路径的错误详情形状必须一致（V00 F1：自指/环曾缺 `details.issues[].field`，已要求实现者补齐）。
10. 台账既有间歇项（R-14/R-15/R-18/R-19）不属本批范围，按 `docs/CURRENT_STATUS.md` 口径记录。
