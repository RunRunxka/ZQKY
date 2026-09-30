# TEACHING-LOOP B0 任务卡（公共契约与基础设施）

- 批次：**B0**（依 [多Agent实施任务计划书 v2.0 §二.3](../../design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)）
- 版本：v1.0；建立日期：2026-09-30
- 起点：`main@301fc356493db21d187ab85f32fd49dfffdc51ef`（工作区现场：`docs/PLAN.md` 用户未提交修改，**必须保留**；`docs/design/` 未跟踪）
- 批次完成条件（计划书原文）：**类型、错误、版本、任务、资产及迁移契约冻结**
- 总控：本会话（CTRL）。实现 Agent：T00-a、T00-b（≤2）。独立验收：V00（只读）。
- 本批**不**启动 B1—B7 业务模块：不实现知识点 CRUD、名单/原卷/成绩/学情/练习/教案后端，不改任何前端页面与路由。

## 0. 本批范围与不做清单

**做**：四库（教材目录、题库、知识点库、教学库）统一迁移登记；任务引擎（租约/心跳/取消/同库提交/重启收敛/并发上限）；提交幂等（`(owner_id, operation, submission_id)` 复合身份）；受管资产服务；四库+资产备份恢复扩展；公共任务 HTTP 路由；错误详情（details.issues/currentRevision）与前端 API 客户端三个缺口（details、取消语义、Blob 下载）；共享契约 Python/TS 双侧冻结。

**不做**：任何业务表（知识点、班级、学生、原卷、成绩、报告、教案、练习）与业务路由；任何页面、导航、样式改动；真实模型调用；Qdrant 变更；对 `apps/api/.env`、正式 `.local-data`、`F:\人教版教材`、`F:\DeepTutor`、`F:\ZQKY_RAG` 的任何读写；推送、部署、合并 `feat/glass-theme`。

## 1. 起步核对（所有 Agent 开工前）

1. `git status --short`、`git rev-parse HEAD`：记录现场；**不**提交、不暂存、不切分支、不还原他人改动；`docs/PLAN.md` 的未提交修改原样保留。
2. 读根 `AGENTS.md`、`apps/api/AGENTS.md`、本卡、`docs/design/teaching-loop-v1/06-data-design.md` 相关表节。
3. 单测/接口只使用 `tmp_path` 临时目录；不连接 6333 正式 Qdrant、不读 `apps/api/.env`。
4. 一个文件同一时段只有一个写入者（见 §2 归属表）；发现需要改他人文件时，向总控提交建议，不自行修改。

## 2. 文件归属（精确到文件；未列入者不得写）

| 归属 | 新建文件 | 修改文件 |
| --- | --- | --- |
| **CTRL（总控）** | `apps/api/app/contracts/teaching_loop.py`；`apps/api/app/core/database_gate.py`；`apps/api/app/core/migrations/__init__.py`、`base.py`、`textbooks.py`、`question_bank.py`、`knowledge.py`、`teaching.py`；`apps/api/app/repositories/knowledge/{__init__,schema,catalog}.py`；`apps/api/app/repositories/teaching/{__init__,schema,catalog}.py`；`apps/api/app/schemas/teaching_loop.py`；`apps/api/app/api/v1/workflow_jobs.py`；`apps/api/tests/test_migrations.py`、`test_workflow_jobs_api.py`、`test_startup_gates.py`；`apps/web/src/contracts/teaching-loop.ts`；`apps/web/src/services/workflow-jobs-api.ts`（+`.test.ts`）；`docs/qa/TEACHING-LOOP-B0/**` | `apps/api/app/core/config.py`、`apps/api/app/core/exceptions.py`、`apps/api/app/core/sqlite.py`、`apps/api/app/main.py`、`apps/api/app/repositories/textbook_catalog/{schema,catalog}.py`、`apps/api/app/repositories/question_bank/{schema,catalog}.py`、`apps/web/src/services/api-client.ts`（+`api-client.test.ts`）、`apps/web/src/contracts/api.ts`、`apps/api/AGENTS.md`、`docs/API.md`、`docs/PROJECT_GUIDE.md`、`docs/CURRENT_STATUS.md` |
| **T00-a（实现）** | `apps/api/app/repositories/jobs/{__init__,repository}.py`；`apps/api/app/services/jobs/{__init__,engine}.py`；`apps/api/app/services/submissions/{__init__,service}.py`；`apps/api/tests/test_jobs_engine.py`、`test_submission_commands.py` | 无 |
| **T00-b（实现）** | `apps/api/app/services/assets/{__init__,store}.py`；`apps/api/app/repositories/assets/{__init__,file_assets}.py`；`apps/api/tests/test_assets.py` | `scripts/rag/backup.py`、`apps/api/tests/test_backup_restore.py`（仅追加/按新契约调整既有断言，逐条在结果卡说明） |
| **V00（验收，只读）** | `docs/qa/TEACHING-LOOP-B0/V00-REPORT-*.md`、`V00-probes/**` | 无（只读产品代码；探针自建在证据目录） |

通用：任何文件写入前先读当前版本；`*.pyc`/`__pycache__`、构建产物、`_work/` 不提交。

## 3. 冻结契约（CTRL 交付后即冻结；实现方按此编码，不得自行改字段名）

### 3.1 外部 JSON 约定

外部 JSON 一律 camelCase；内部 Python/SQL snake_case。列表统一 `{items,total,offset,limit}`（本批仅任务视图不使用列表）。时间：UTC ISO-8601（秒精度，`Z` 结尾，沿用 `app/core/sqlite.now_iso`）。分数禁止浮点（`scoreUnits = 分数×100` 整数，B3+ 使用）。

### 3.2 错误信封（`app/schemas/errors.py` + `app/contracts/teaching_loop.py`）

```
{ code, message, requestId, retryable, details? }
details = { currentRevision?: number, issues?: [{ row?: number, column?: string, field?: string, code: string, message: string }], fields?: string[] }
```

- 422 行列错误：`details.issues`；409 版本冲突：`details.currentRevision`。
- 同 submissionId、不同请求 → `409 SUBMISSION_CONFLICT`；重放已成功提交 → 先返回原结果（不报冲突）。
- 既有题库确认语义不变：HTTP 200 + `failures` 非空 = 整体未确认。

### 3.3 RevisionIdentity 与 ScoreCell / Observation（仅类型冻结）

```
RevisionIdentity = { id: string, revision: number, revisionId: string }
ScoreCell = { participantId, itemId, status: "recorded"|"missing"|"absent"|"exempt", scoreUnits: number|null }
Observation = "needs_consolidation"|"full_credit"|"incomplete"|"no_evidence"
```

语义：`revision` 是可变实体编辑锁（乐观锁整数）；`revisionId` 是固定内容修订身份（不可变）；两者不得混用。B3+ 的分数/学情实现必须遵守"有效 0、空白、缺考、免考严格区分；综合题不分摊失分"。

### 3.4 JobView / 任务状态机（本批成为运行实现）

```
JobView = { jobId, domain: "knowledge"|"question"|"teaching", kind, attempt, state,
            result: object|null, error: ApiErrorEnvelope|null }
state ∈ queued | running | succeeded | failed | cancelled | interrupted
```

固定行为（实现与测试共同锁定）：

1. **租约**：`claim` 时 `attempt+1`，生成新 lease token，`leaseExpiresAt = now + 90s`；心跳每 **20s** 续租（测试可注入更短周期）；租约丢失后旧 lease **不能发布**。
2. **续租即停**：心跳失败（失权/被接管）→ 取消执行器，不发布结果。
3. **同库提交**：`complete` 在同一 SQL 写事务内执行 `require_current_lease` → `require_not_cancelled` → `publish(tx)` → 置 `succeeded` + `result_json` + `finished_at`。事务内不得有网络/解析/推理。
4. **取消**：`cancel` 置 `cancel_requested`；`queued` 任务立即置 `cancelled`；运行中任务在其下次探测/发布点停止，**已取消的任务即使执行器迟到也不发布**；终态任务取消是幂等空操作。
5. **重启收敛**：启动时把遗留 `running` 全部置 `interrupted` 并清租约；**不自动重新调用模型**。
   B0 的收敛范围是**知识点库与教学库**（`RECONCILE_DOMAINS`）：题库组织任务仍是既有五态流程与旧 UI 视图，
   纳入收敛会在旧界面上出现未知状态；B2 迁移题库任务时一并纳入（契约 §6 已登记）。
6. **重试**：仅终态 `failed|interrupted|cancelled` 可重试 → 置 `queued`，**保留冻结输入与模型指纹**，attempt 在下次 claim 时递增；`queued|running` 重试 → 409 `JOB_NOT_RETRYABLE`。
7. **模型配置失效**：显式失败（错误码由域实现给出），不偷偷换模型；模型指纹（`modelSnapshotJson`）在创建任务时冻结。
8. **页面停止观察不取消任务**；只有 cancel 接口取消。
9. **并发上限**：同时最多 **2** 个后台重任务，其中最多 **1** 个模型生成任务（模型任务同时占用两个名额）。队列等待不丢任务。
10. **文件产物**：相同导出输入的成功产物可重用；失败不登记成功文件（B4+ 使用，本批只冻结规则）。

### 3.5 任务表 DDL（迁移登记内容，CTRL 冻结）

统一字段（`knowledge_jobs`、`workflow_jobs` 新建；`question_jobs` 用 `ALTER TABLE ADD COLUMN` 补齐）：

```
id TEXT PRIMARY KEY, owner_id TEXT NOT NULL DEFAULT 'local', kind TEXT NOT NULL,
state TEXT NOT NULL CHECK(state IN ('queued','running','succeeded','failed','cancelled','interrupted')),
frozen_input_json TEXT NOT NULL DEFAULT '{}', input_hash TEXT NOT NULL DEFAULT '',
model_snapshot_json TEXT NOT NULL DEFAULT '{}', attempt INTEGER NOT NULL DEFAULT 0,
lease_token TEXT NULL, lease_expires_at TEXT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0,
checkpoint_json TEXT NOT NULL DEFAULT '{}', result_json TEXT NULL, error_code TEXT NULL,
error_json TEXT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
started_at TEXT NULL, finished_at TEXT NULL
索引：`idx_*_jobs_state(state, created_at)`、`idx_*_jobs_kind(kind, state)`；实际命名逐表为
`idx_question_jobs_engine_state`（题库，B0 新增；旧基线遗留的 `idx_question_jobs_state(kind, state)` 保留）、
`idx_knowledge_jobs_state`/`idx_knowledge_jobs_kind`、`idx_workflow_jobs_state`/`idx_workflow_jobs_kind`
```

偏差记录：`kind` **不加** CHECK（新任务类型不应要求重建表，改由应用层白名单校验）；`workflow_jobs` 原设计无 attempt/lease/取消/结果列，本批按计划书 §二.2 补齐。SQLite `ALTER TABLE` 不能加 CHECK，既有 `question_jobs` 以应用层枚举校验。 **T00-a-02（V00 独立验收发现，已修）**：`0002` 的 `adjust` 钩子最初只返回 ALTER 语句，把声明集合里的 `CREATE INDEX ... idx_question_jobs_engine_state` 一起丢掉（语句从未执行；登记散列覆盖声明集合，故漂移校验也不揭示）。修复为「钩子保留全部非 ALTER 声明」，并**新增 `0003_question_jobs_engine_state_index`** 给已应用过 `0002` 的既有库补齐索引（`0002` 的声明与散列保持不变，既有库不漂移）；`test_migrations.py` 增加该索引存在性与"钩子必须执行全部声明语句"的不变量用例。这也是本批唯一被判 fail 的独立验收项。

### 3.6 提交幂等表 DDL（知识点库、教学库新建；题库 B2 再迁）

```
(owner_id TEXT NOT NULL, operation TEXT NOT NULL, submission_id TEXT NOT NULL,
 request_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY (owner_id, operation, submission_id))
```

`request_hash` = 规范化 JSON（`sort_keys=True, ensure_ascii=False, separators=(',',':')`）的 sha256。语义：同键同 hash → 返回原结果；同键不同 hash → 409 `SUBMISSION_CONFLICT`；`expected_revision` 不符 → 409 `REVISION_CONFLICT` + `details.currentRevision`；以上判定与业务写入在同一事务。

### 3.7 受管资产（`file_assets`，教学库）

```
id TEXT PRIMARY KEY, owner_id TEXT NOT NULL DEFAULT 'local',
kind TEXT NOT NULL CHECK(kind IN ('roster','score_sheet','paper','export','attachment')),
blob_key TEXT NOT NULL, sha256 TEXT NOT NULL CHECK(length(sha256)=64),
original_name TEXT NOT NULL, media_type TEXT NOT NULL, byte_size INTEGER NOT NULL CHECK(byte_size>=0),
created_at TEXT NOT NULL
```

- 文件本体：`<assets_root>/blobs/<sha256>`（内容寻址、原子落盘、只增不改、**读取时重算 sha256**）。
- `blob_key` 必须形如 `blobs/<64位小写hex>`；任何越出受管根的路径（`..`、绝对路径、盘符）一律拒绝，**原件与模板不覆盖**。
- `AssetRef`（契约）：`{assetId, kind, blobKey, sha256, mediaType, byteSize, originalName}`。

### 3.8 数据根与四库

```
<data_dir>/textbooks/catalog.sqlite3        教材目录（唯一索引权威在库内，不复制）
<data_dir>/question-bank/question-bank.sqlite3
<data_dir>/knowledge/knowledge.sqlite3      本批只建：schema_migrations、knowledge_submissions、knowledge_jobs
<data_dir>/teaching/teaching.sqlite3        本批只建：schema_migrations、command_submissions、file_assets、workflow_jobs
<data_dir>/assets/blobs/<sha256>
```

连接一律走 `app/core/sqlite.connect`（外键/WAL/busy_timeout）；**迁移登记**为每库 `schema_migrations(id, sha256, applied_at)` 表，逐条迁移一个事务、失败整体回滚且不登记；已登记迁移的 SQL 散列不符 → `SCHEMA_MIGRATION_DRIFT` 拒绝启动（fail closed）。**幂等**：重复迁移不改变既有内容；**损坏保护**：既有库不可读/结构不符 → 明确报错拒绝启动，**不得按空库重建**。

### 3.9 公共任务路由（CTRL）

| 方法与路径 | 说明 |
| --- | --- |
| GET `/api/v1/workflow-jobs/{jobId}?domain=knowledge\|question\|teaching` | 返回 `JobView`；未知 id → 404 `JOB_NOT_FOUND`；domain 非法 → 422 `INVALID_REQUEST` |
| POST `/api/v1/workflow-jobs/{jobId}/cancel`（body `{domain}`） | 协作式取消，幂等；返回 `JobView` |
| POST `/api/v1/workflow-jobs/{jobId}/retry`（body `{domain}`） | 仅终态可重试；`queued/running` → 409 `JOB_NOT_RETRYABLE`；返回 `JobView` |

## 4. 验收条件（B0 门槛）

| 编号 | 条件 | 责任 | 证据形式 |
| --- | --- | --- | --- |
| A1 | 重复迁移无内容变化；同一迁移重复 apply 不重复登记 | CTRL | pytest `test_migrations.py` |
| A2 | 中途迁移失败可恢复：失败迁移整体回滚、不登记，修复后重跑成功 | CTRL | pytest（注入坏语句） |
| A3 | 已登记迁移 SQL 散列被改动 → `SCHEMA_MIGRATION_DRIFT` 且拒绝 | CTRL | pytest |
| A4 | 既有库损坏（非 SQLite/结构不符）→ 启动拒绝，不重建空库 | CTRL | pytest `test_startup_gates.py` |
| A5 | 同 submission 重放返回原结果；同键不同请求 409；版本不符 409+currentRevision | T00-a | pytest `test_submission_commands.py` |
| A6 | 任务 claim/心跳/续租/失权不发布/取消（含迟到结果）/重启收敛/重试保留冻结输入/并发上限 | T00-a | pytest `test_jobs_engine.py` |
| A7 | 路由行为：视图字段、404/422/409、取消幂等、重试语义 | CTRL | pytest `test_workflow_jobs_api.py` |
| A8 | 资产：内容寻址、重复写入幂等、篡改检测、缺失报错、路径穿越拒绝 | T00-b | pytest `test_assets.py` |
| A9 | 四库备份 create→verify→restore 全链路；缺库/篡改原件/半完成恢复拒绝；旧 v2/legacy 清单仍可 verify/restore | T00-b | pytest `test_backup_restore.py` |
| A10 | 错误详情：422 issues 行列、409 currentRevision 能到达前端 `ApiError.details` | CTRL | pytest + vitest |
| A11 | 取消语义：AbortError 原样抛出且 `isAbortError` 可用；Blob 下载返回 `{blob, fileName}` 且失败转 ApiError | CTRL | vitest |
| A12 | 全套工程检查：`test:api`、`test:unit`（NODE_OPTIONS）、`typecheck`、`lint`、`build` | CTRL | 命令+退出码 |

独立验收（V00）另做：迁移中途失败的真实注入复现、任务取消迟到结果的独立探针、备份缺库/篡改的独立构造、前端取消/Blob 的独立复现；逐项 `pass/fail/not_run`。

## 5. 测试资源与结果格式

- 后端：`cd apps/api && uv run python -m pytest tests/<file> -q`；全量 `npm run test:api`。全部使用 `tmp_path`；不建正式数据目录、不读 `.env`。
- 前端：`NODE_OPTIONS=--no-experimental-webstorage npm run test:unit`（Node 26 必须）；`npm run typecheck`、`npm run lint`。
- 本批不跑 e2e：无页面/路由/布局/保存/导出改动（若实际改动超出，则先 `npm run build` 再跑相关 e2e 并如实报告）。
- 结果格式（每个实现 Agent 提交）：

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

## 6. 已知风险与预先登记

- 既有用例 `test_backup_restore.py` 以两库/`schemaVersion:2` 为断言基准；扩展为四库后需按新契约调整（T00-b 逐条说明），旧 v2/legacy 清单兼容必须保留专门用例。
- `question_jobs` 现表在真实题库库中已存在：迁移用 `ALTER TABLE ADD COLUMN`；对全新库先走 0001 基线再 `ALTER`。
- 迁移冻结后，业务表增量（B1+）一律**新增迁移**，不得改写已冻结的基线 SQL；迁移内容由总控登记。
- 启动收敛的域范围：B0 只含 `knowledge`/`teaching`；题库组织任务在 B2 迁移到新任务协议时一并纳入
  （原因：`question_jobs` 的五态枚举与既有前端 `OrganizeJobView` 视图尚未迁移，提前写入
  `interrupted` 会让旧界面出现未知状态）。
- 任务 kind 白名单在 `app/main.py`（`JOB_KINDS`）；新增任务类型属总控级变更。
- 既有 R-18/R-19 间歇用例与本批无关，按 `docs/CURRENT_STATUS.md` 台账如实报告，不"修"不删。
