# TEACHING-LOOP B1 · V00 独立验收报告 02（r2 窄复验）

- 批次：TEACHING-LOOP B1（T10 + T20 + T30-a + CTRL）——**r2 窄复验**
- 候选：`main@301fc356493db21d187ab85f32fd49dfffdc51ef` 工作树，`FROZEN-CANDIDATE.json` **revision r2**
  （`previousRevision: r1`、`changedSincePrevious` 10 项；r1 记录见 `FROZEN-CANDIDATE-r1.json`）
- 验收者：独立验收 Agent（V00，只读产品代码）；时间：2026-09-30
- 范围：r1 的四条 fail（F1/F2/F3/F4）与 observation O1（及 O10/O11/O16 登记口径）的窄复验 + 受改动模块回归
- 结论摘要：**F1 pass / F2 pass / F3 pass / F4 pass / O1 pass**；r1 无遗留 fail；r2 复验未发现新 fail；
  受改动模块回归全绿（探针 190 项检查全部通过、B1 测试 178 例 exit 0、全量 test:api 1170 例 exit 0）
- 交付：本报告 + `V00-probes/evidence-r2/**`（r2 证据）；r1 证据已快照到 `V00-probes/evidence-r1-snapshot/**`（14 份，未被覆盖）

---

## 0. r2 基线核对

### 0.1 指纹复算

```
$ python docs/qa/TEACHING-LOOP-B1/V00-probes/v00_fingerprint.py
frozen revision=r2 declared fileCount=95 entries=95
matched=95 mismatched=0 missing=0
FINGERPRINT_OK 95/95            # 退出码 0（开工与收尾各一次，均一致）
```

### 0.2 差异集合对账（要求 4）

```
$ python - <<'PY'   # r1 哈希 vs r2 哈希逐文件比较
my diff count: 10        declared count: 10
diff==declared: True
mine-not-declared: []    declared-not-mine: []
```

10 项与 `changedSincePrevious` **不多不少**完全一致（其余 85 个文件与 r1 逐字节相同）：

| 文件 | 内容 |
| --- | --- |
| `apps/api/app/services/knowledge/service.py` | F1：`_resolve_parent` 增自指/环预检（`would_create_cycle`），`field` 按入参 |
| `apps/api/app/repositories/knowledge/points.py` | F1：`_require_parent` / `translate_integrity_error` 同形状 details |
| `apps/api/app/core/migrations/knowledge.py` | O1：`0003` 补 `adjust=_skip_existing_issues_column` |
| `apps/api/tests/test_knowledge_points.py`、`test_knowledge_imports.py` | 回归/新增用例 |
| `docs/API.md`、`docs/PROJECT_GUIDE.md`、`apps/api/AGENTS.md`、`docs/CURRENT_STATUS.md`、`docs/qa/TEACHING-LOOP-B1/TASK-CARD.md` | F2–F4 文档 |

### 0.3 写入者已停止 / 无残留

- 95 候选文件最大 mtime = **21:46:32**（r2 冻结写入），验收期 21:47–22:00 内 **0 写入**；
  `git status --porcelain` = 68 项（与 r1 收尾一致，r2 改动均落在此前已 dirty 的文件上）。
- 收尾：无 8000/8001/5173/5174/6333 监听、无 uvicorn 进程；探针临时数据根已清理。
- 探针纪律同 r1：先设 `ZQKY_DATA_DIR=<临时目录>` 再导入 `app.*`；不读写正式 `.local-data`
  （唯一例外为 `v1_migrations_probe` 的正式库 `schema_migrations` 只读对比，`mode=ro&immutable=1`）。

### 0.4 r2 证据目录

| 证据 | 内容 |
| --- | --- |
| `evidence-r2/v2r2_f1.json` | F1 复验（24 项） |
| `evidence-r2/v1r2_o1.json`、`v1r2_o1_digests.json` | O1 复验（13 项）+ 散列对账 |
| `evidence-r2/v9_doc_claims.json` | F2–F4 + 文档事实（19 项） |
| `evidence-r2/v1_migrations.json`、`v2_knowledge_points.json`、`v3_knowledge_imports.json`、`v4_knowledge_suggestions.json` | 受改动模块回归（r1 探针重跑） |
| `evidence-r2/v00r2_b1_targeted_tests.txt`、`test_knowledge_points.txt`、`test_knowledge_imports.txt` | 定向测试 |
| `evidence-r2/v00r2_full_testapi.txt` | 全量后端 |
| `evidence-r2/v00r2_doc_greps.txt` | 文档 grep 原文 |

---

## 1. F1 已修（自指/环缺少可定位字段）—— **pass**

命令：`cd apps/api && ZQKY_PROBE_EVIDENCE_DIR=<evidence-r2> uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v2r2_f1_probe.py`；退出码 **0**（24/24）
证据：`evidence-r2/v2r2_f1.json`

r1 的两条最小场景（我自己重写，未复用实现者用例）：

| 场景 | 请求 | r2 实测 | 判定 |
| --- | --- | --- | --- |
| 自指（parentId） | `PATCH /knowledge-points/A {"expectedRevision":N,"parentId":"A"}` | 422 `KNOWLEDGE_PARENT_INVALID`，`details.issues[0].field="parentId"` | pass |
| 自指（parentCode） | `PATCH A {"expectedRevision":N,"parentCode":"A"}` | 422 `KNOWLEDGE_PARENT_INVALID`，`field="parentCode"` | pass |
| 成环（parentId） | `PATCH A {"parentId": C}`（A→B→C，C 为孙） | 422 `KNOWLEDGE_CYCLE`，`field="parentId"` | pass |
| 成环（parentCode） | `PATCH A {"parentCode":"C"}` | 422 `KNOWLEDGE_CYCLE`，`field="parentCode"` | pass |
| 中间节点环 | `PATCH B {"parentId": C}` | 422 `KNOWLEDGE_CYCLE`，`field="parentId"` | pass |
| 改父后新树环 | 树变为 A→C→B 后 `PATCH C {"parentCode":"B"}` | 422 `KNOWLEDGE_CYCLE`，`field="parentCode"` | pass |

兜底路径（要求"触发器等价兜底 + 仓储同形状"）：

- **仓储直写（绕过服务层预检）**：`KnowledgePointRepository.update_point(conn, A, parent_id=C)` → `AppError`
  `KNOWLEDGE_CYCLE`/422，`details.issues[0].field="parentId"`；直写自指 → `KNOWLEDGE_PARENT_INVALID`/422 同形状；
  两次拒绝后树与 `revision` 未变（无部分写入）。
- **裸 SQL（彻底绕过服务与仓储）**：`UPDATE knowledge_points SET parent_id=<descendant>` 仍被 DB 触发器
  `RAISE(ABORT,'KNOWLEDGE_CYCLE')` 拒绝；`SET parent_id = id`（自指）同样被拒（实测触发器先报，`CHECK(parent_id IS NULL OR parent_id<>id)`
  仍在 DDL 中，作为第二道）。
- **导入批内成环**：XLSX 两行互指父级 → 预览行 issues `KNOWLEDGE_CYCLE` + `field="parentCode"`；确认 →
  422 `KNOWLEDGE_IMPORT_BLOCKING_ISSUES` + `issues[].field="parentCode"` 且 `knowledge_points` 零新增（含同批正常行未写入）。

反向回归（防"预检过度拒绝"）：合法改父（跨层上移 C→A、跨分支 B→C）200 且父关系正确；未改父的普通改名 200；
缺父（parentCode）仍 422 + `field=parentCode`。r1 的 `v2_knowledge_points_probe.py` 重跑 **37/37**（r1 为 35/37）。

实现位置（只读核对）：`service.py:_resolve_parent`（`point_id` 非空时自指→`KNOWLEDGE_PARENT_INVALID`、
`would_create_cycle`→`KNOWLEDGE_CYCLE`，`field` 取实际入参）；`points.py:_require_parent` 与
`translate_integrity_error` 均带 `error_details(issues=[ErrorIssue(field="parentId", ...)])`。

## 2. F2–F4 已修（文档）—— **pass**

命令：`cd apps/api && ZQKY_PROBE_EVIDENCE_DIR=<evidence-r2> uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v9_doc_claims_probe.py`；退出码 **0**（19/19，r1 为 16/19）
证据：`evidence-r2/v9_doc_claims.json`、`evidence-r2/v00r2_doc_greps.txt`

- **F2（`0003` 未登记）已修**：`v9.8` → `apiMdMentions0003=true / projectGuideMentions0003=true / agentsMdMentions0003=true / cardMentions0003=true`；
  printout：`docs/API.md:427` 结构表新增 `0003_knowledge_import_issues_column`（并注明 adjust 钩子）、
  `docs/PROJECT_GUIDE.md:487`「B1 为知识点库 `0002`+`0003`、教学库 `0002`」、`apps/api/AGENTS.md:10` 补 `0003` 说明。
- **F4（`/classes/{id}/restore` 未列）已修**：`docs/API.md:464` 与任务卡 `:97` 均在班级行以
  ``POST `/api/v1/classes/{id}/archive`、`/restore` `` 形式列出（与知识点 restore 的简写惯例一致）；
  路由实体 `apps/api/app/api/v1/roster.py:153`。我的 `v9.2b`（覆盖全部已注册路由，允许同一行简写）通过。
- **F3（PROJECT_GUIDE §12 可定位声明）已与实现一致**：`v9.17` → `would_create_cycle_defined=true`、
  `called_anywhere=true`（`service.py:1314`）、文档声明存在；`PROJECT_GUIDE.md:469` 措辞保持不变但现已被实现满足。

窄复验中我同步更新了自己探针的三处**判定口径**（透明披露，均不放松实质要求）：

1. `v9.2b`：允许"同一行简写"（`、`/restore``），与 r1 中对知识点 restore 的处理一致；
2. `v9.4`：可达性判定从"必须是契约常量"改为"有抛出/引用点或契约常量定义"（r2 文档改为列出**实际抛出集合**，
   其中 `KNOWLEDGE_LINK_NOT_FOUND` 等是服务层内联字面量）；
3. 新增 `v9.4b`：只定义未使用的码必须在文档标为**保留码**——实测 `definitionOnly=[KNOWLEDGE_LINK_INVALID, KNOWLEDGE_SUBJECT_UNKNOWN]`、
   `reservedMarked=true`（API.md 明确写"这两个码目前不会抛出"），O10 处置与代码一致。

## 3. O1 已修（`0003` 裸 ALTER 无 adjust 钩子）—— **pass**

命令：`cd apps/api && ZQKY_PROBE_EVIDENCE_DIR=<evidence-r2> uv run python docs/qa/TEACHING-LOOP-B1/V00-probes/v1r2_o1_probe.py`；退出码 **0**（13/13）
证据：`evidence-r2/v1r2_o1.json`、`evidence-r2/v1r2_o1_digests.json`

- **散列未变**：`0003_knowledge_import_issues_column` 的 `sha256 = ec0fdc9abcc7009ebe7a801927f21814c4fdeed809fda27c26e1f6873f76bb09`
  与 **r1 证据记录的散列逐字节相同**；声明集合仍是那一条 `ALTER`（`len(statements)==1`）；`0002` 散列亦未变
  （`6389e7c456b6…`）。→ "声明集合与散列不变"成立。
- **场景 A（列已存在 + 注册表缺 0003）**：r1 时抛 `sqlite3.OperationalError: duplicate column name: issues_json`；
  r2 实测 **不再抛错**、本次补登记 `["0003_knowledge_import_issues_column"]`、列保留、再次 apply 返回 `[]`（幂等）。
- **场景 B（列缺失 + 注册表缺 0003，真该补列）**：`apply` 返回 `["0003…"]`，列被真正 `ADD COLUMN`（钩子**没有**误跳过），
  列定义仍为 `issues_json TEXT NOT NULL DEFAULT '[]'`。
- **钩子两态直调**：列存在 → `()`；列缺失 → 原 `ALTER`。
- **常规新库全量**：`0001/0002/0003` 依次登记，`0003` 散列同为 r1 值。

我同步更新了自己 r1 探针里**唯一**一条与修复方向相反的断言（`v1_migrations_probe.py` 的 `v1.7b/v1.7c`：
r1 时断言"注册表缺 0003 且列已存在必须抛错（无自愈）"，现按修复后语义断言"不抛错且补登记"）——
这是期望值随修复更新，不是放宽要求；`v1.7d`（注册表已登记 0003、列被手工删除 → 不重补）保持原口径并仍 pass。
该探针重跑 **36/36**。

## 4. 回归（受改动模块）—— **pass**

### 4.1 我的探针（r1 探针重跑，证据写 `evidence-r2/`）

| 探针 | r2 结果 | r1 结果 | 结论 |
| --- | --- | --- | --- |
| `v1_migrations_probe.py` | 36/36 | 36/36（v1.7b 期望语义更新后） | pass（含正式库 0 漂移复核） |
| `v2_knowledge_points_probe.py` | **37/37** | 35/37 | pass（F1 两条断言转绿） |
| `v3_knowledge_imports_probe.py` | 38/38 | 38/38 | pass（无回归） |
| `v4_knowledge_suggestions_probe.py` | 23/23 | 23/23 | pass（service.py 改动无回归） |
| `v9_doc_claims_probe.py` | **19/19** | 16/19 | pass（F2–F4 三条断言转绿） |
| `v2r2_f1_probe.py`、`v1r2_o1_probe.py` | 24/24、13/13 | — | pass（新增窄复验） |

合计 r2 探针检查 **190 项，全部 pass**。v5–v8（名单/富内容/施测）涉及文件均不在 r2 diff 内，
r1 结论（38/38、26/26、18/18、19/19）继续有效，未重复执行。

### 4.2 实现者测试与全量

| 命令 | 结果 | 证据 |
| --- | --- | --- |
| `uv run python -m pytest tests/{test_knowledge_points,test_knowledge_imports,test_knowledge_suggestions,test_roster_classes,test_roster_imports,test_rich_content_parser,test_rich_content_renderer,test_b1_migrations,test_contracts_b1,test_tabular,test_publication,test_migrations,test_startup_gates}.py -q` | **退出码 0**，进度点 178、无 F/E（r1 为 176） | `evidence-r2/v00r2_b1_targeted_tests.txt` |
| 两个被改动测试文件单跑 | 各 17 例、exit 0 | `evidence-r2/test_knowledge_{points,imports}.txt` |
| `uv run python -m pytest -q`（全量后端） | **退出码 0**，进度点 **1170**、**0 F / 0 E**；**R-19 本轮未出现** | `evidence-r2/v00r2_full_testapi.txt` |

- 全量 1170 例与 `docs/CURRENT_STATUS.md` 声明的"1170 passed"一致（我实测同为 1170）。
- r2 改动文件不含任何前端文件 → `npm run typecheck`/vitest/e2e/test:chat 本轮 not_run（r1 已跑 typecheck exit 0 +
  2 个前端文件 19 例 pass，当时证据仍适用）。

## 5. 遗留 fail 认定（要求 6）

- r1 的 4 条 fail 认定 **全部关闭**（F1→§1、F2/F3/F4→§2），逐条以我自己的探针复现通过。
- 我 r1 报告中没有其它 fail 认定（其余 17 项均为 observation）。
- r2 窄复验**未发现新 fail**：受改动模块（迁移/知识点服务与仓储/导入）在我的探针、实现者测试与全量回归下均通过。

## 6. observation（r2）

- **O-r2-1**：`0003` 的 `adjust` 钩子在 `apply_migrations` 进入 `BEGIN IMMEDIATE` **之前**求值（读
  `PRAGMA table_info`），理论上存在"求值后、执行前他人加列"的 TOCTOU 窗口。当前部署为单进程 FastAPI +
  数据根 OS 排他锁，实际不可达；仅登记。
- **O-r2-2**：r1 observation 的处置说明主要落在**批次 README**（`docs/qa/TEACHING-LOOP-B1/README.md`，含
  O1–O17 全表）与 API.md（O10/O11），任务卡 §8 登记风险类（O4→§8.8、O6/O7/O8→§8.7、F1→§8.9）。
  `CURRENT_STATUS.md` 的措辞"O4/O6/O7/O10/O11/O16 已按边界登记在任务卡 §8 与批次 README"中，
  对 O10/O11/O16 的落点表述不够精确（O16 实际只在 README；O10/O11 在 API.md）。
  另：README 与 `EVIDENCE-COMMANDS.md` **不在 95 文件候选**内，不受指纹保护——仅供参考，不作为候选事实。
- **O-r2-3**：`KNOWLEDGE_LINK_NOT_FOUND`(404) 已在 API.md 登记且确有抛出点
  （`service.py` 内联字面量），但同族其它错误码都在 `contracts/{knowledge,roster}.py` 定义常量，本码没有；
  命名登记不一致（不影响行为与文档正确性）。
- **O-r2-4**：r1 的 O12（`RequestValidationError` 的 `details.fields` 元组 repr）与 O16（`textbook.ts` 同名
  `JobView`）仍为 HEAD 既有、r2 未改，按边界保留（README 已登记为"不属本批"）。
- **O-r2-5**：r2 任务卡 §8.7/§8.8 与我的 r1 O6/O7/O8/O4 一致（同学号冲突由 DB 唯一约束兜底、同名 link+create
  视为教师显式消歧、publish 失败停 `running` 属 B0 引擎契约）——登记口径与实测行为一致，我复核通过。
- **O-r2-6**（审计用）：本轮我对自己的探针做了 4 处期望/口径更新（`v1.7b/v1.7c` 期望翻转、`v9.2b` 允许简写、
  `v9.4` 可达性口径、新增 `v9.4b`）；r1 证据已快照在 `evidence-r1-snapshot/`，可直接对照，未覆盖。

## 7. not_run（r2）

| 未执行项 | 原因 |
| --- | --- |
| 真实大模型调用 / 真实 Word·WPS 排版 / 真实 Qdrant | 同 r1（无环境与授权）；r2 未触及这些面 |
| 正式数据根写入演练（`0002/0003` 补齐） | 仍需用户写入授权；本轮只做 `schema_migrations` 只读对比（四库 0001 散列 0 漂移，证据在 `evidence-r2/v1_migrations.json`） |
| 前端 `npm run typecheck` / vitest / e2e / `test:chat` / `npm run check` 全串 | r2 的 10 个改动文件不含任何 `apps/web/**`（差异集合可证）→ 无前端变更可验 |
| B0 面（凭证隔离、.env/JSON 补偿、SSE 中途失败、模型发现、认证过期、预算耗尽） | 不在 r2 diff 内；全量后端 1170 例通过作为不回归证据 |
| 超深父链（>3 层）/ 既有脏数据下的环检测行为 | 窄复验只覆盖 3 层链与两节点环；`would_create_cycle` 的 `MAX_PARENT_DEPTH=512` 与"遇既有环即拒"分支未覆盖（见 §8） |

## 8. 我最不确定的一处

**F1 修复把 `would_create_cycle` 从死代码变成活路径**：现在每次改父都要沿父链上溯判断成环，
而我只验证了 3 层链与两节点环、以及"合法改父不被误拒"的少量组合。`MAX_PARENT_DEPTH=512`
上限与"上溯途中发现既有数据已损坏成环即拒绝写入"（`points.py:617` 分支）这两条边界我没有构造数据触发；
若历史上存在脏数据（手工改库、旧版本写入），拒绝写入的错误码/定位字段形状是否与正常环一致也未被验证。
建议：待有正式库写入授权时，用一份含深层链与人工环的副本做一次专项演练（不必在本批内完成）。

---

## 附：r2 结论速览

| 项 | 结论 | 依据 |
| --- | --- | --- |
| F1 自指/环可定位（V2 原 2 fail） | **pass** | 24/24；HTTP 四种入参 + 仓储直写 + 裸 SQL 触发器 + 导入环零写入 + 合法改父回归；`v2` 探针 37/37 |
| F2 `0003` 登记（V9） | **pass** | API.md:427 / PROJECT_GUIDE:487 / AGENTS.md:10 / 任务卡 / CURRENT_STATUS 均登记；`v9.8` pass |
| F3 §12 可定位声明（V9） | **pass** | `would_create_cycle` 有调用点（service.py:1314）；`v9.17` pass |
| F4 `/classes/{id}/restore`（V9） | **pass** | API.md:464 + 任务卡:97（同一行简写）；`v9.2b` pass |
| O1 `0003` adjust 钩子 | **pass** | 13/13；两场景 + 钩子两态 + 散列与 r1 一致；`v1` 探针 36/36 |
| 回归（受改动模块） | **pass** | v1 36/36、v2 37/37、v3 38/38、v4 23/23；B1 测试 178 例 exit 0；全量 1170 例 exit 0（0 F/0 E，无 R-19） |
| 指纹/差异对账 | **pass** | r2 95/95；实测 diff = `changedSincePrevious` = 10 项；验收期 0 写入 |
| 遗留 fail | 无 | r1 4 条 fail 全部关闭，无新增 |
