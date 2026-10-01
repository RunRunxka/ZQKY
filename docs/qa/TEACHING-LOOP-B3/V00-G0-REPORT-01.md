# V00 · TEACHING-LOOP B3 / G0 独立验收报告（01）

- 任务：B3 / G0 独立复验（只读候选）· 验收对象 = B2 审查 11 项缺陷（RV01–RV11）+ 已披露 publish 异常 + 重建机制
- 起点：`main@0f4b8cb190c2265d819b90e5d6df4e3954ad1906` 工作区（未提交）；冻结指纹 `docs/qa/TEACHING-LOOP-B3/FROZEN-G0.json`
- 验收者：V00（只读）；**未改** `apps/**`、`scripts/**`、现行文档、实现者测试、冻结记录、审查目录
- 本次新增仅：`docs/qa/TEACHING-LOOP-B3/V00-probes/**` 与本报告
- 所有探针在导入 `app.*` 前设 `ZQKY_DATA_DIR` 指向临时目录；不读写正式 `.local-data`/`.env`；模型全部受控替身；不联网；不占端口

## 0. 结论一览

| 项 | 结论 | 探针 / 命令 | 退出码 | 证据 |
| --- | --- | --- | --- | --- |
| 指纹 106 文件 + `changedSinceB2` | **pass** | `python docs/qa/TEACHING-LOOP-B3/V00-probes/p00_fingerprint.py` | 0 | `V00-probes/p00_fingerprint.out.json`、`p00_fingerprint.final.json` |
| RV01 retry 真装配调度 / 幂等 / 重启 / 观察窗口 | **pass** | `p01_rv01_retry.py`（后端）+ `p09_frontend_hooks.cjs` / `p10_frontend_hooks.test.tsx`（窗口语义） | 0 / 0 / 0 | `p01_rv01_retry.json`、`p09_frontend_hooks.json`、`p10_frontend_hooks.log` |
| RV02 结构化处置 + 计分叶题面闸门 | **pass** | `p02_rv02_resolution.py` | 0 | `p02_rv02_resolution.json` |
| RV03 未归属块正文 + 受控资产接口 | **pass** | `p03_rv03_blocks_assets.py` | 0 | `p03_rv03_blocks_assets.json` |
| RV04 模型漂移守卫（四路径 + 缺指纹 + 凭证） | **pass** | `p04_rv04_drift.py` | 0 | `p04_rv04_drift.json` |
| RV05 整理中间批同事务租约 CAS | **pass** | `p05_rv05_lease.py` | 0 | `p05_rv05_lease.json` |
| RV06 确认复核已归档知识点（两域） | **pass** | `p06_rv06_archived_confirm.py` | 0 | `p06_rv06_archived_confirm.json` |
| RV07 改题学科关联集合核验 | **pass** | `p07_rv07_subject_links.py` | 0 | `p07_rv07_subject_links.json` |
| RV08 施测改日期归属重核 + 重确认 | **pass** | `p08_rv08_assessment_date.py` | 0 | `p08_rv08_assessment_date.json` |
| RV09/RV10 StrictMode / 迟到响应 / 观察代次 | **pass** | `p09_frontend_hooks.cjs`；`NODE_OPTIONS=--no-experimental-webstorage npx vitest run --config docs/qa/TEACHING-LOOP-B3/V00-probes/v00-vitest.config.ts` | 0；0（4/4 通过） | `p09_frontend_hooks.json`、`p10_frontend_hooks.log` |
| RV11 修订级标题快照（运行行为） | **pass** | `p11_rv11_titles_migration.py` | 1（见下） | `p11_rv11_titles_migration.json` |
| RV11 迁移 0005 在**含已确认修订**的 B2 旧库上回填 | **FAIL** | `p11_rv11_titles_migration.py`；最小复现 `p12_rv11_startup_repro.py` | 1；1 | `p11_rv11_titles_migration.json`、`p12_rv11_startup_repro.json` |
| 已披露：发布事务失败收敛（三域） | **pass** | `p13_publish_failure.py` | 0 | `p13_publish_failure.json` |
| 重建机制 `RebuildPlan`（数据承载库） | **pass** | `p14_rebuild_plan.py` | 0 | `p14_rebuild_plan.json` |
| 反向探针（审查目录 7 个，逐字节副本） | **pass（缺陷均不再复现）** | 见 §14 | 1/1/1/1/0/0/0 | `V00-probes/*.log`、`question_lease_probe.json`、`assessment_date_probe.json`、`ui_job_probe.log`、`p15_reverse_probes.json` |

存在 **1 项阻塞 fail（RV11 迁移 0005）** 与 6 条 observation；其余 12 项通过。**G0 不建议在修复该项前冻结**。

## 1. 指纹对账 / 差异核对 / 写入停止核对

### 1.1 指纹（106 文件 sha256 复算）

```
cd H:\备份xuexi\智启课源
python docs/qa/TEACHING-LOOP-B3/V00-probes/p00_fingerprint.py   # exit 0
```

实测（`p00_fingerprint.out.json`）：

```json
{"g0_fileCount": 106, "listed": 106, "hashed_ok": 106, "missing": [], "mismatch": [], "diff_matches_claim": true}
```

独立推导（不读 `changedSinceB2`，直接比对 B2 冻结清单 `docs/qa/TEACHING-LOOP-B2/FROZEN-CANDIDATE.json` 的 84 文件）：
`added=24 / changed=20 / removed=2`，与 `FROZEN-G0.json.changedSinceB2` **逐条一致**（`diff_matches_claim=true`）。
removed 两项为 `docs/qa/TEACHING-LOOP-B2/{TASK-CARD,V00-TASK-CARD}.md`（与声明一致）。

验收结束前重跑同一脚本（`p00_fingerprint.final.json`）仍为 `106/106，0 缺失，0 不一致` → 候选在本次验收期间**未被写入**。

### 1.2 写入停止核对

- 候选 106 文件的最新 mtime：`2026-10-01T18:31:03`（`apps/api/app/main.py`），早于本次验收开始（18:36）。
- 本次验收期间（18:36 起）`apps/**`、`scripts/**`、`tests/**` 下被修改文件数：**0**；`docs/**` 除 `V00-probes/**` 与外报告外：**0**。
- 审查目录 `docs/qa/TEACHING-LOOP-B2-REVIEW-20261001/` 26 个文件，最新 mtime `17:14:54`，**未修改**；反向探针以逐字节副本运行（副本 sha256 与原文件一一相等）。
- 本次只新建/写入：`docs/qa/TEACHING-LOOP-B3/V00-probes/**`（探针、日志、JSON、两份配置）与本报告。

## 2. RV01 · 公共 retry 真装配调度

命令（apps/api 下）：`.venv/Scripts/python.exe -X utf8 docs/qa/TEACHING-LOOP-B3/V00-probes/p01_rv01_retry.py` → **exit 0**；证据 `V00-probes/p01_rv01_retry.json`。

装配：`create_app`（真四库 + 真 JobEngine/JobStore）→ `build_question_bank_service`（受控模型替身）→ `_build_executor_registry(app)`（真注册表）→ TestClient 走**真实 HTTP** `/workflow-jobs/{id}/retry`。

| 场景 | 实测 |
| --- | --- |
| 失败 → retry → 新 attempt → 终态 | `failed` → retry `200 queued`（收据 attempt=1）→ `succeeded` attempt=2；provider 开始调用 1→2 |
| 仓库 retry 后未调度（模拟入队后调度异常）→ 再 retry | `queued`（attempt=1）→ retry `200` → `succeeded` attempt=2，调用 +1 |
| `running` → retry | `409 JOB_NOT_RETRYABLE`，无第二次执行 |
| 并发双 retry（两条都落在 queued） | 状态码 `[200, 409]`；attempt 1→2；调用次数 +1（只执行一次） |
| 注册表重复 `schedule`（queued + 已在跑窗口） | 两次均返回 True，attempt 1→2，只执行一次 |
| 重复点击（第一次已开始执行） | 第一次 `200`、第二次 `409`；只执行一次 |
| 重启后 `queued` | 新 app/新引擎下保持 `queued`（0.3s 窗口无自动重放），显式 retry 后 `succeeded` attempt=2，provider 调用 1 次 |

观察窗口语义（前端，`workflow-jobs-api.ts` 真实实现）：
- `retryObservationWindow({attempt:2})` = `{minAttempt:2,maxAttempt:3}`；喂 2(queued)→3(succeeded) 被接受（onUpdate=[2,3]），返回终态 3；
- 喂 attempt=5（N+2）→ 返回 `null`（视为被更新尝试接管）；喂 attempt=1（早于 N）→ `null`；
- 精确窗口 `expectedAttempt=2` 遇 attempt=1 → `null`；终态后不再发请求；已 abort → `null`。
证据：`V00-probes/p09_frontend_hooks.json`（Node 探针，exit 0）与 `V00-probes/p10_frontend_hooks.log`（vitest，4/4 passed，exit 0）。

**结论：pass。**（observation-1 见 §15）

## 3. RV02 · 结构化问题处置与计分叶题面

命令：`.venv/Scripts/python.exe -X utf8 .../p02_rv02_resolution.py` → **exit 0**；证据 `p02_rv02_resolution.json`。

样本：程序化 DOCX 含未知对象（blocking `UNSUPPORTED_OBJECT`）。

| 输入 | 期望 | 实测 |
| --- | --- | --- |
| `resolution={"anything":1}` | 拒绝 | **422 INVALID_REQUEST**（schema：`kind` required / extra 禁止） |
| `status=resolved` 但无 `resolution` | 拒绝 | **422** |
| 内容损失码 + `kind=exclude, reason=…` | 拒绝 | **422 PAPER_ISSUE_RESOLUTION_INVALID**，`details.issues[0].field="kind"` |
| `supplement_text` 空文本 | 拒绝 | **422** |
| `supplement_text` 目标为公式块 | 拒绝 | **422**（"表格/公式/图片请用 supplement_asset"） |
| `supplement_asset` 键 `../../etc/passwd` | 拒绝 | **422**（非受管键） |
| `supplement_asset` 键 `blobs/aaaa…`（不存在） | 拒绝 | **422**（资产不可读） |
| 合法 `supplement_text` 到段落块 | 落地并真实变化 | **200**；DB `block_json.text` 与内容 API 均含补录文本 |
| 补录 + 知识点关联后确认 | 成功 | **200** `{state: confirmed, scoredLeafCount: 4, totalScoreUnits: 2100}` |
| 计分叶 `content={}` | 拒绝 | **422 ITEM_STEM_MISSING**（row=5，field=content） |
| 题面引用不存在的共同材料 | 拒绝 | **422 ITEM_MATERIAL_MISSING**（列出 `block-that-does-not-exist`） |

**结论：pass。**

## 4. RV03 · 未归属块正文与受控资产内容

命令：`.venv/Scripts/python.exe -X utf8 .../p03_rv03_blocks_assets.py` → **exit 0**；证据 `p03_rv03_blocks_assets.json`。

- 无题号 DOCX：`items=[]`，但段落块返回 `"这是一份没有题号的文档。"`、表格块返回单元格 `甲/乙`（可审阅）。
- 正常卷：9 段落 / 1 图片 / 1 表格 / 2 公式；公式含 `ommlXml`；合并表格 `colSpan=[2,1,1]`；图片块含受管键 `blobs/<64hex>`。
- 置为 `unassigned` 的块仍返回 disposition + 正文。
- 受控资产接口 `GET /papers/{id}/revisions/{rid}/assets/{key}/content`：
  - 被本修订引用 → **200**，`image/png`，字节以 `89504e470d0a1a0a` 开头；
  - 非受管键 `notes.txt` → **422 INVALID_ASSET_KEY**；路径穿越 → **422**；
  - 未被本修订引用的受管键 → **404 PAPER_ASSET_NOT_FOUND**；
  - 跨卷（另一份无图片修订）→ **404**；不存在的修订 → **404 PAPER_REVISION_NOT_FOUND**。

**结论：pass。**

## 5. RV04 · 模型配置漂移守卫

命令：`.venv/Scripts/python.exe -X utf8 .../p04_rv04_drift.py` → **exit 0**；证据 `p04_rv04_drift.json`。

共享实现单元级（`resolve_frozen_model` + 假仓储/凭证）：

```json
{"matchOk": true, "missingFingerprint": ["MODEL_FINGERPRINT_MISSING", 422],
 "missingProfileId": ["MODEL_FINGERPRINT_MISSING", 422], "drift": ["MODEL_CONFIG_DRIFT", 409],
 "credentialsInFingerprint": false, "credentialsInErrors": false}
```

四条真实执行路径（用 gated 知识点任务占住共享模型名额 → 目标任务排队 → 同 profile 改 model-B → 放行）：

| 路径 | 终态 | 错误码 | 上游开始调用 | 发布 |
| --- | --- | --- | --- | --- |
| `question:generate` | failed | MODEL_CONFIG_DRIFT | 0 | `question_imports=0`、`provenance=0` |
| `question:organize`（恢复/recovery） | failed | MODEL_CONFIG_DRIFT | 0 | 建议 0；checkpoint 前后均 1（未推进） |
| `teaching:paper_mapping` | failed | MODEL_CONFIG_DRIFT | 0 | `ai_proposals=0` |
| `knowledge:suggestion` | failed | MODEL_CONFIG_DRIFT | 0 | 零候选批次 |

- 旧行缺指纹（直接建任务行 `model_snapshot={"profileId":…}`）→ 经公共 retry 调度 → **failed + MODEL_FINGERPRINT_MISSING**，零调用。
- 落库 `model_snapshot_json`（三库）与任务视图均不含替身 API Key；错误消息不含凭证。

**结论：pass。**

## 6. RV05 · 整理中间批的同事务租约 CAS

命令：`.venv/Scripts/python.exe -X utf8 .../p05_rv05_lease.py` → **exit 0**；证据 `p05_rv05_lease.json`（仓储级故障注入：真 `QuestionBankCatalog.record_organize_batch` + 真 `JobStore` 租约）。

| 场景 | 建议写入 | checkpoint |
| --- | --- | --- |
| A 正常路径（当前有效租约） | 1 条建议 | `nextBatchIndex 0→1` |
| B 旧 attempt（过期后接管 attempt=2） | 0（`created=None`） | 1→1（不动） |
| C token 不匹配（同 attempt） | 0 | 0 |
| D 租约过期（注入 `now=2099`） | 0 | 0 |
| E interrupted 后迟到批次 | 0 | 0 |
| E succeeded 后迟到批次 | 0 | 0 |
| F 已请求取消 | 0 | 0 |
| G 未提供租约凭据 | 0 | 0 |
| H 正常两批 | 2 条建议 | `nextBatchIndex=2` |

**结论：pass。**

## 7. RV06 · 确认复核已归档知识点

命令：`.venv/Scripts/python.exe -X utf8 .../p06_rv06_archived_confirm.py` → **exit 0**；证据 `p06_rv06_archived_confirm.json`。

- 原卷：草稿绑定活跃知识点 → 归档 → 确认 = **409 KNOWLEDGE_ARCHIVED**（`details.issues[0].field="references[0].knowledgePointId"`）；该卷已确认修订数 0→0（零发布）。控制组（未归档）确认 200。
- 题库：草稿绑定活跃 → 归档 → 确认 = **409 KNOWLEDGE_ARCHIVED**；`questions.total` 不变（零发布）。控制组确认 200、生成 1 道题。
- 历史已确认关联在归档后仍可读：原卷 4 条关联（名称快照 `一次函数`）逐条不变；题库题目仍返回 `knowledgeLinks`（含 `knowledgeNameSnapshot`）。
- 注：确认前复核调用点位于 `PublicationCoordinator.publication(...)` 临界区内、写事务之前（`papers/service.py::confirm → _recheck_confirm_knowledge`、`question_bank/service.py::_recheck_confirm_links`）——这是**代码阅读**结论，外部行为证据是上面的 409 与零发布。

**结论：pass。**

## 8. RV07 · 改题学科时的关联集合核验

命令：`.venv/Scripts/python.exe -X utf8 .../p07_rv07_subject_links.py` → **exit 0**；证据 `p07_rv07_subject_links.json`。

- 改学科（math→chinese）且省略 `knowledgeLinks` → **422 KNOWLEDGE_REFERENCE_INVALID**，`details.issues[0].field="knowledgeLinks[0].knowledgePointId"`，文案要求显式替换/清空；题目仍为 math、关联未变、revision 未推进。
- 改学科 + 显式 `knowledgeLinks=[]` → **200**，`subjectId=chinese`、零关联。
- 改回 math + 显式替换为 math 知识点 → **200**，关联 = 新知识点。
- 显式提交异学科知识点 → **422 KNOWLEDGE_SUBJECT_MISMATCH**。
- 同学科改内容、省略关联 → **200**，revision 推进、旧关联复制保留、题干更新。

**结论：pass。**

## 9. RV08 · 施测改日期重核参测归属

命令：`.venv/Scripts/python.exe -X utf8 .../p08_rv08_assessment_date.py` → **exit 0**；证据 `p08_rv08_assessment_date.json`（真实 HTTP 链：班级/学生 → 原卷导入确认 → 施测创建 → PATCH → 重确认）。

- 创建（学生 joinedOn=2026-09-20、heldOn=2026-09-30、`classConfirmed=false`）→ **201**，姓名/学号快照 `张三/0007`。
- PATCH heldOn=2026-09-01（早于入班）→ **422 PARTICIPANT_CLASS_UNCONFIRMED**，`issues[0].row=0, field="classId"`，含人次与班级真实标识；日期未写入（仍 09-30）。
- `POST /assessments/{id}/participants`（既有 studentId/classId/attemptNo + `classConfirmed=true` + 依据）→ **200**：人次仍 1 条、`attemptNo` 不变、快照不变、只更新确认列与依据。
- 重确认后再 PATCH 同一失效日期 → **200**，`heldOn=2026-09-01`；`class_memberships` 前后**逐行相等**（`joined_on=2026-09-20, left_on=null`）。

**结论：pass。**

## 10. RV09 / RV10 · 前端 hook（StrictMode、迟到响应、观察代次）

两条入口都跑通：

1) Node + esbuild + jsdom 加载**真实** `hooks.ts` / `workflow-jobs-api.ts` / `contracts/teaching-loop.ts`（仅 mock `apiRequest`）：

```
node --no-experimental-webstorage docs/qa/TEACHING-LOOP-B3/V00-probes/p09_frontend_hooks.cjs   # exit 0
```

```
strictmode_off {"label":"succeeded:1","terminalCalls":1}
strictmode_on  {"label":"succeeded:1","terminalCalls":1}
late_retry_response_ignored {"pendingDuringRetry":"retry","pendingAfterReset":"none",
                             "stateAfterAdoptB":"B:succeeded:3","stateAfterLateRetry":"B:succeeded:3"}
late_cancel_response_ignored {"beforeLateCancel":"B:succeeded:3","afterLateCancel":"B:succeeded:3"}
late_failure_ignored {"state":"B:succeeded","error":"none"}
observation_epoch_guards_stale_update {"state":"B:5","terminals":[]}
window_accept_N_and_N1 {"updates":[2,3]} / window_reject_N2 {"rejected":null}
```

2) vitest（仓库要求的前端入口；因只读边界不能在 `apps/web/src` 下新建探针，使用自建配置 `V00-probes/v00-vitest.config.ts`，include 指向本目录，alias/setupFiles 与根配置一致）：

```
NODE_OPTIONS=--no-experimental-webstorage npx vitest run \
  --config docs/qa/TEACHING-LOOP-B3/V00-probes/v00-vitest.config.ts    # exit 0
Test Files 1 passed (1)   Tests 4 passed (4)
```

**结论：pass。**（未跑真实浏览器；见 §16）

## 11. RV11 · 修订级标题快照 + 迁移 0005 —— 部分 FAIL

命令：`.venv/Scripts/python.exe -X utf8 .../p11_rv11_titles_migration.py` → **exit 1**；证据 `p11_rv11_titles_migration.json`。

### 11.1 运行行为（通过）

```
beforeTitle=Original Title  afterTitle=Original Title  paperTitleNow=NEW DRAFT Title
revisions: confirmed → title_snapshot="Original Title"  source="revision"
           draft     → title_snapshot="NEW DRAFT Title" source="revision"
```

即：已确认修订的标题不随新草稿改名而变（内容 API + DB 快照一致），新草稿快照随 `papers.title` 更新。

### 11.2 迁移 0005 在纯草稿旧库上（通过）

自建 B2 旧库（逐条执行 0001–0004 登记语句 + 真 `schema_migrations` 行 + `papers`/两条 `paper_revisions`），仅含草稿行：

```
pendingBefore=["0005_teaching_paper_revision_titles"]  applied=["0005_teaching_paper_revision_titles"]
columnsAdded=["title_snapshot","title_snapshot_source"]
rows: rev-1/rev-2 → title_snapshot="旧卷标题（当前值）", source="backfilled_from_paper"
shaMatches=true  secondApplyNoop=true  foreign_keys=1
```

### 11.3 迁移 0005 在**含已确认修订**的 B2 旧库上（FAIL）

实测：

```
{"applied": null,
 "error": "IntegrityError: IMMUTABLE_REVISION",
 "columnsAdded": [], "rows": [{"id":"rev-1","state":"confirmed"},{"id":"rev-2","state":"draft"}],
 "registered": false}
failures=["B2: 含已确认修订的 B2 旧库上迁移 0005 失败（IntegrityError: IMMUTABLE_REVISION）；
          真实用户库升级会卡在启动迁移"]
```

**最小复现**（命令、输入、期望、实测、首败行号）：

```
cd H:\备份xuexi\智启课源\apps\api
.venv/Scripts/python.exe -X utf8 "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B3\V00-probes\p12_rv11_startup_repro.py"   # exit 1
```

- 输入：临时数据目录内预置 B2 版 `teaching/teaching.sqlite3`（0001–0004 已登记；`papers` 一行 + `paper_revisions` 两条，其中 `rev-1.state='confirmed'`；库中已存在 0003 的 `immutable_paper_revisions_update` / `no_direct_sealed_paper_revisions` 触发器），随后 `create_app(Settings(data_dir=…))`。
- 期望：启动成功，0005 登记，`title_snapshot` 有值且 `title_snapshot_source='backfilled_from_paper'`。
- 实测：`create_app` 抛异常，启动失败（`p12_rv11_startup_repro.json`）：

```
File "app/main.py", line 226, in _build_local_runtime
    app.state.teaching.migrate()
File "app/repositories/teaching/schema.py", line 21, in migrate
    apply_migrations(connection, database=DATABASE)
File "app/core/migrations/__init__.py", line 147, in apply_migrations
    tx.execute(statement)
sqlite3.IntegrityError: IMMUTABLE_REVISION
```

- 首败行号：`apps/api/app/core/migrations/__init__.py:147`（执行 0005 的 `_TITLE_BACKFILL` UPDATE；语句位于 `app/core/migrations/teaching.py:436-438`）。
- 成因（代码定位）：0005 的回填 `UPDATE paper_revisions SET title_snapshot=… WHERE title_snapshot=''` 会命中 `state='confirmed'` 的行，而 0003 已登记触发器 `immutable_paper_revisions_update BEFORE UPDATE ON paper_revisions WHEN OLD.state='confirmed'` 直接 `RAISE(ABORT,'IMMUTABLE_REVISION')`（`app/core/migrations/teaching.py:314`）。`_skip_existing_title_columns` 只过滤 ALTER，回填语句总会执行（`teaching.py:447-455`）。迁移事务回滚 → 未登记 → 应用启动失败。
- 影响：任何"教学库中存在已确认原卷修订 + 0005 未应用"的环境（真实用户库升级、备份恢复后的旧库）都会在启动迁移处确定性地失败；这是 G0 判据"迁移 0005 在有数据的 B2 旧库上回填 + 来源标注 + 失败回滚"的直接不满足。

### 11.4 失败回滚与可重跑（通过）

注入 `BEFORE UPDATE OF title_snapshot` 触发器令回填失败后：两列未新增、未登记、`pending` 仍列出 0005、`foreign_keys=1`；移除触发器后重跑成功且来源标注正确（`migration_rollback` 段）。

**结论：RV11 的运行时行为 pass；迁移 0005 在含已确认修订的旧库上 FAIL（阻塞）。**

## 12. 已披露项 · 发布事务失败后的终态收敛

命令：`.venv/Scripts/python.exe -X utf8 .../p13_publish_failure.py` → **exit 0**；证据 `p13_publish_failure.json`（同一公共引擎/仓储实现分别在 teaching/question/knowledge 三个 JobStore 上跑一遍）。

| 场景 | teaching / question / knowledge 实测 |
| --- | --- |
| publish 抛 `AppError` | `failed` + 保留 `error_code`；`finished_at` 有值、lease 清空；publish 内业务行**回滚**（探针表 0 行） |
| publish 抛非 AppError | `failed` + `JOB_FAILED` + 固定文案"任务结果发布失败，本次写入已回滚。"；业务行回滚 |
| 正常 publish（对照） | `succeeded`，业务行保留 |
| 取消优先 | `complete`（cancel_requested=1）→ `cancelled`；`fail_if_current_lease` → `cancelled`（不写 error） |
| 失权零写入 | 过期旧租约 + 接管（attempt=2）后调用 → 当前记录保持 `running/attempt=2/error NULL`，新持有者未被覆盖 |
| 无永久 running | 收敛后不存在 `running` |

**结论：pass（三域一致）。**

## 13. 重建机制 · RebuildPlan（数据承载库演练）

命令：`.venv/Scripts/python.exe -X utf8 .../p14_rebuild_plan.py` → **exit 0**；证据 `p14_rebuild_plan.json`。

- 成功：2 行数据完整搬运，新定义生效（`CHECK(amount>=0)` + 复合外键），索引 `idx_items_owner` 重建，迁移登记，`PRAGMA foreign_keys=1`。
- 外键问题行（孤儿行）：`foreign_key_check` 报 1 行 → 失败并整体回滚（DDL/数据/登记都不变），`foreign_keys` 仍 1。
- 对账不符（verifications 计数非 0）：失败回滚、未登记；修正后**可重跑**成功。
- 指纹：`RebuildPlan` 文本变化改变 `Migration.sha256`（已登记即冻结）。

**结论：pass。**

## 14. 反向探针（审查目录 7 个，逐字节副本）

副本放置于 `docs/qa/TEACHING-LOOP-B3/V00-probes/`（与审查目录同深度，`parents[4]`/`'../../../..'` 仍指向仓库根），sha256 与原文件逐一相等；**原目录未改**。汇总见 `p15_reverse_probes.json`。

| 探针 | 退出码 | 缺陷是否复现 | 观察 |
| --- | --- | --- | --- |
| `papers_probe.py` | 1 | **否** | 先打印 `responseContainsOriginalText=true, dbContainsOriginalText=true`（块正文已返回）；随后在 `PaperDraftPatchRequest.model_validate({'resolution':{'anything':1}})` 处被 schema 拒绝（`kind` required / extra forbidden）→ 无法到达原"任意 JSON 放行"断言（首败行 87） |
| `papers_content_probe.py` | 1 | **否** | 同上（首败行 53） |
| `question_jobs_probe.py` | 1 | **否** | "绑定活跃→归档→确认"得 409 `KNOWLEDGE_ARCHIVED`，原断言期望 200（首败行 56） |
| `question_model_probe.py` | 1 | **否** | 漂移场景任务终态为 `failed`，原断言 `record.state == "succeeded"` 失败（首败行 52） |
| `question_lease_probe.py` | 0 | **否** | JSON：`staleBatchSuggestionCreated=false`、`suggestionsAfterStaleBatch=0`、`checkpointAfterStaleBatch={}`、`interruptedBatchSuggestionCreated=false` |
| `assessment_date_probe.py` | 0 | **否** | JSON：`bugReproduced=false`（改日期被拒绝且要求显式确认流程） |
| `ui_job_probe.cjs` | 0 | **否** | `strictMode.bugReproduced=false`（strict 模式 view=succeeded、terminalCalls=1）、`lateRetry.bugReproduced=false`（afterLateRetry=new-B） |

日志：`V00-probes/{papers_probe,papers_content_probe,question_jobs_probe,question_model_probe,question_lease_probe,assessment_date_probe,ui_job_probe}.log`。

**结论：pass —— 7 个原诊断探针均不再复现缺陷。**

## 15. observation

1. **模型名额排队期的任务状态是 `running`**（`run_job` 先 `claim` 再等名额）。这是引擎既有语义，观察窗口按 `attempt` 判定不受影响；但若前端把 `running` 展示为"已开始调用模型"，在名额排队时不准确（本次探针里目标任务的"排队"表现为 `running`）。
2. `app/services/model_runtime.py` 的 `__all__` 未列出 `resolve_frozen_model` / `fingerprint_of_handle` / `model_fingerprint`，不影响使用（各处显式 import），仅影响 `from … import *` 类用法与可读性。
3. RV01 的"重复点击/并发 retry 只执行一次"在**单进程事件循环**内由路由体无 `await` 的原子性 + `is_tracking` 保证；多 worker/多进程部署下的同任务竞态本次未覆盖（也超出本批边界）。
4. RV02 的"任意 JSON 被拒"目前由 pydantic schema 承担（`INVALID_REQUEST`），与语义化拒绝码 `PAPER_ISSUE_RESOLUTION_INVALID` 并存；前端若要据此显示字段级提示，需同时处理两类码。
5. RV06 的"在同一发布临界区内复核"是代码阅读结论（复核调用点在 `coordinator.publication(...)` 内、写事务前）；外部可观察证据是 409 与零发布，未做锁内/锁外的时序注入。
6. 自建"B2 旧库"时，为插入已确认行，我临时卸下 `no_direct_sealed_paper_revisions` 触发器并在插入后**原样恢复**（模拟确认路径写入的结果）；库内触发器状态与真实 B2 库一致（`immutable_*` 触发器在 0003 建立，未被动过）。

## 16. not_run（未执行及原因）

- **真实大模型 / 真实上游**：所有探针与四路径均用受控替身，无网络请求。真实模型教学质量、真实 provider 兼容性未评。
- **真实 Word/WPS 打开与人工视觉**：DOCX 全部为程序化样本（`tests/papers_support` 构造器），未用 Word/WPS 打开或渲染页比对。
- **Qdrant / Ollama 教材 RAG**：未启动、未连接。
- **正式数据迁移**：未读写正式 `.local-data`；迁移仅在临时目录构造的旧库上验证（RV11 的失败因此只覆盖"临时旧库 + 启动路径"，未在正式库上复现）。
- **全量 `npm run check` / `test:api` / Playwright e2e / build**：按本次边界不跑（G0 前端 unit 811 例与 typecheck/lint 由 CTRL 组织，我未复核其结果）。除 §14 反向探针外，未复跑实现者测试文件。
- **真实浏览器视觉与 F20 五步成绩流**：业务段范围，未执行。
- **多进程/多 worker 下的 retry、取消、租约竞态**：未执行。
- **T60 成绩导入 / T40 真实原卷人工审阅**：业务段范围，未执行。

## 17. 最不确定的一处

**RV11 迁移 0005 失败的影响面判定。** 失败本身是确定性的、可最小复现（临时旧库 + `create_app`），但"真实用户库是否已含已确认原卷修订"我无法确认——按只读边界我没有读取正式 `.local-data`，也没有在正式库上跑任何迁移。因此：若正式教学库当前没有任何已确认修订，这条失败的暴露面会推后到"第一次确认原卷之后、0005 应用之前"的任何升级/恢复场景；反之它会立刻让应用启动失败。无论哪种情况，它都直接违反 G0 判据"迁移 0005 在有数据的 B2 旧库上回填 + 来源标注 + 失败回滚"（我的数据承载旧库演练即失败），故按阻塞 fail 上报，请总控安排修复（最小改动方向：回填前按列/行绕过不可变触发器，例如使用受控重建或在同一迁移内临时重建触发器，并补一条"含已确认修订的旧库"回归）。
