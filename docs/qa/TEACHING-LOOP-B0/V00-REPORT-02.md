# TEACHING-LOOP B0 · V00 独立验收报告 02（r2 窄复验）

- 验收者：独立验收 Agent（V00，只读产品代码）
- 日期：2026-09-30（本地时间）
- 候选：`main@301fc356493db21d187ab85f32fd49dfffdc51ef` 工作树，冻结记录 **r2**
  （`FROZEN-CANDIDATE.json`，`previousRevision: r1`；r1 记录保留在 `FROZEN-CANDIDATE-r1.json`）
- 范围：CTRL 点名的 5 项窄复验（F1 修复、O1 修复、V9 复跑、r2 指纹对账、回归），
  外加对 r2 改动的定点回归与变异复验（§5）
- 结论：**5/5 项全部 pass**；r1 的 1 项 fail（F1）与 6 条 observation 已逐条处置（§6）。
  本轮未发现新的 fail；新增 2 条 observation（§7）。
- 证据：`docs/qa/TEACHING-LOOP-B0/V00-probes/evidence/v00r2_*.json|txt`、`v10_r2-M*.json`、`v9_doc_claims_probe.json`

## 0. 必验项结论一览

| 必验项 | 结论 | 命令 / 退出码 | 关键证据 |
| --- | --- | --- | --- |
| ① V00-F1 已修 | **pass** | `uv run python ../../docs/qa/TEACHING-LOOP-B0/V00-probes/v00r2_f1_index_probe.py` / **0**（17/17） | `evidence/v00r2_f1_index_probe.json` |
| ② V00-O1 已修 | **pass** | `.../v00r2_o1_retry_error_probe.py` / **0**（16/16） | `evidence/v00r2_o1_retry_error_probe.json` |
| ③ V9 复跑 | **pass** | `.../v9_doc_claims_probe.py` / **0**（60/60） | `evidence/v9_doc_claims_probe.json` |
| ④ r2 指纹对账 | **pass** | `.../v00r2_fingerprint_probe.py` / **0**（55/55；差异集合 8 = 声明 8） | `evidence/v00r2_fingerprint_probe.json` |
| ⑤ 回归 | **pass** | `uv run python -m pytest <7 文件>` / **0**（108 passed）；`npm run test:api` / **0**（**1011 passed**） | `evidence/v00r2_regression_7files.txt`、`v00r2_testapi_full.txt` |

## 1. 指纹对账（必验项 ④）

```bash
cd "H:/备份xuexi/智启课源/apps/api" && uv run python ../../docs/qa/TEACHING-LOOP-B0/V00-probes/v00r2_fingerprint_probe.py
# 退出码 0
```

| 项目 | 结果 |
| --- | --- |
| r2 记录条目 / 磁盘实测 | 55 / 55 |
| 逐字节一致 | **55** |
| 不一致 / 缺失 | 0 / 0 |
| 自算 r1→r2 差异集合 | 8 项 |
| 记录 `changedSincePrevious` | 8 项 |
| **集合相等（不多不少）** | **True**（多余：`[]`；遗漏：`[]`） |

自算差异（= 声明差异，逐条一致）：`apps/api/app/core/migrations/question_bank.py`、
`apps/api/app/repositories/jobs/repository.py`、`apps/api/tests/test_jobs_engine.py`、
`apps/api/tests/test_migrations.py`、`docs/API.md`、`docs/CURRENT_STATUS.md`、
`docs/PROJECT_GUIDE.md`、`docs/qa/TEACHING-LOOP-B0/TASK-CARD.md`。
（r1 记录里的 `TASK-CARD.md` 冻结后变更已在 r2 记录中固化；本轮无"记录外"漂移。）

## 2. 必验项 ① V00-F1 已修（question_jobs 索引）

自建探针 17/17（不复用实现者用例；夹具与断言均为本轮独立构造）：

| 子项 | 结论 | 实测 |
| --- | --- | --- |
| F1① 全新库索引存在 | pass | `question_jobs`：`idx_question_jobs_engine_state(state, created_at)`；对照 `knowledge_jobs`/`workflow_jobs` 各有 `(state, created_at)`；重复 apply 返回 `[]`、索引仍只有一条（幂等） |
| F1② 既有库补齐 | pass | 夹具=手工旧表 + 执行 12 条 ALTER + 用**当前** 0002 散列登记 0002（索引缺失）；应用完整清单后 `applied_now == ["0003_question_jobs_engine_state_index"]`、索引出现、**0002 未被判漂移**、再次 apply `[]` |
| F1③ 0002 散列不变 | pass | `qb.MIGRATIONS[1].sha256 == 61e5595258709835d269b84c3b6d96594124ac818a5f67168c6af2bfe3fb9ee1`，且我用 `statement_digest()` **独立复算**同一常量（12 ALTER + 1 CREATE INDEX 的声明集合未变） |
| 附加 A（根因） | pass | 在"列不全"的旧表上，钩子现返回 **13** 条（12 ALTER + 1 索引），原缺陷（索引声明被丢）已消除 |
| 附加 B（0003 对象一致） | pass | `0003.statements == 0002` 声明集合里的同一条索引语句（结构一致、可重复执行） |
| 附加 C（登记值） | pass | 0003 登记散列 = `MIGRATIONS[2].sha256`；0001/0002 登记散列仍为原值 |

最小复现（一条命令，临时目录）：`uv run python ../../docs/qa/TEACHING-LOOP-B0/V00-probes/v00r2_f1_index_probe.py`。
证据：`evidence/v00r2_f1_index_probe.json`。

## 3. 必验项 ② V00-O1 已修（retry 清空上一轮错误）

自建探针 16/16：

- `failed`（`error_code=MODEL_CONFIG_INVALID`, `retryable=True`）→ `retry` 后
  **`state=queued`、`error_code=None`、`error=None`、`view().error == null`**；
- **直接读原始 DB 行**：`error_code`/`error_json` 均为 `NULL`（同一 UPDATE 落盘；行内不存在
  "已 queued 但仍带旧错误"的中间可观测态）；
- 保留 `frozen_input` / `model_snapshot` / `input_hash`（逐字节相等）与 `attempt`
  （下次 `claim` 才 +1），租约与 `cancel_requested` 清空；
- 其他终态同样成立：`cancelled`、`interrupted` retry → `queued` 且错误列为 NULL；
- 守卫未回归：`queued`/`running`/`succeeded` retry 仍 409 `JOB_NOT_RETRYABLE`，且被拒后任务行未被改写。

证据：`evidence/v00r2_o1_retry_error_probe.json`。

## 4. 必验项 ③ V9 复跑

```bash
cd apps/api && uv run python ../../docs/qa/TEACHING-LOOP-B0/V00-probes/v9_doc_claims_probe.py
# 退出码 0；== v9_doc_claims_probe: 60/60 passed; failed=[]; observations=[] ==
```

- r1 的唯一 fail（`v9.e5 question_jobs 具备 §3.5 声明的 (state, created_at) 索引`）已转 **pass**。
- 检查数 59 → **60**、observation 1 → **0**：`§11 收敛范围`项由"观察"变为**通过断言**
  （`PROJECT_GUIDE.md` 已写明"B0 的启动收敛范围只含知识点库与教学库"，与我实测
  `RECONCILE_DOMAINS == ('knowledge', 'teaching')` 一致）。
- 其余声明仍逐条一致：API.md 四库路径/路由/错误码/租约 90s·心跳 20s/并发 2+1、备份 v3 四库+资产、
  AGENTS.md 迁移纪律、§3.5/§3.6/§3.7 列清单（19/6/9）。

证据：`evidence/v9_doc_claims_probe.json`。

## 5. 必验项 ⑤ 回归（外加定点复核）

| 运行 | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 本批 7 个测试文件（6 + `test_backup_restore.py`） | `cd apps/api && uv run python -m pytest tests/test_migrations.py tests/test_startup_gates.py tests/test_jobs_engine.py tests/test_submission_commands.py tests/test_assets.py tests/test_workflow_jobs_api.py tests/test_backup_restore.py` | 0 | **108 passed**（r1 同口径 6 文件为 81；r2 新增 4 例 + `test_backup_restore.py` 23 例） |
| 后端全量（可选，我实跑） | `npm run test:api` | 0 | **1011 passed, 1 warning in 106.14s** —— 与 CTRL README 的 r2 计数一致 |

证据：`evidence/v00r2_regression_7files.txt`、`evidence/v00r2_testapi_full.txt`。

定点复核（超出必验清单，针对 r2 受影响的两处行为）：

| 复核 | 命令 / 退出码 | 结果 |
| --- | --- | --- |
| V3 任务协议（含 retry 语义） | `.../v3_jobs_engine_probe.py` / 0 | 50/50（与 r1 相同；retry 保留冻结输入/指纹/attempt、并发上限 2+1 等无回归） |
| V8 路由（retry 视图语义） | `.../v8_workflow_jobs_api_probe.py` / 0 | 27/27（我已把 v8.6e 从 r1 的"错误保留到 claim"改为 r2 口径"retry 即清空、视图 error 为 null"，断言随之通过） |
| 变异复验（r2 是否仍有牙齿） | `.../v10_mutation_runner.py --label r2-M1…M5` / 均 0（观察到预期失败） | M1 心跳间隔改错 → 2 例失败；M2 取消判定改错 → 1 例；M3 retry 守卫改错 → 1 例；**M4 还原 r1 缺陷（钩子丢索引声明）→ `test_adjust_hooks_execute_every_declared_statement` 失败 + 我的 F1 探针 1 条**；**M5 让 0003 不建索引 → `test_existing_database_already_on_0002_gains_index_from_0003` 失败 + 我的 F1 探针 2 条** —— r2 修复的两半（钩子保留 + 0003 补齐）都有回归断言守着 |

- 变异只在**我自己的临时副本**上执行（运行器以模块注入方式覆盖），候选文件全程未改。
- 探针基建修正（如实登记）：`v10_mutation_runner.py` 注入"迁移注册表类"模块时，原先只替换
  `sys.modules`，而 `app.core.migrations.REGISTERED_MIGRATIONS` 在导入期已绑定真模块，导致第一次 M4
  出现"实现者用例 0 失败"的**假阴性**；修正为注入后同步重指 `REGISTERED_MIGRATIONS[<库>]`
  （探针文件，非候选），重跑即得到上表的正确结论。
- 证据：`evidence/v10_r2-M{1,2,3,4,5}-*.json`。

## 6. r1 findings 处置核对（逐条）

| r1 编号 | r1 级别 | r2 状态 | 我的复核方式与结论 |
| --- | --- | --- | --- |
| V00-F1（question_jobs 缺索引） | fail | **已修** | §2：全新库/既有库/散列常量/根因 17/17 pass；V9 该断言转 pass；M4/M5 证明修复有回归保护 |
| V00-O1（retry 保留 error） | observation | **已修** | §3：16/16 pass（记录层 + 原始 DB 行 + 视图 + 冻结字段保留 + 守卫） |
| V00-O2（§11 未点名收敛范围） | observation | **已修** | `PROJECT_GUIDE.md:450` 写明范围；V9 该项由观察转为通过断言（60/60） |
| V00-O3（API.md 资产归档路径缺 `files/` 前缀说明） | observation | **已修** | `docs/API.md:328-329` 明确 `restorePath` 与归档路径、前缀只存在于归档内 |
| V00-O4（`question_jobs` 索引命名偏差未登记） | observation | **已修** | `TASK-CARD.md:97-98` 逐表写明实际索引名（含旧基线遗留名保留），`:102` 补 **T00-a-02** 偏差与修复记录 |
| V00-O5（本批用例计数未复跑核对） | observation | **已闭合** | 我实跑全量 `test:api` = **1011 passed**（退出码 0），与 CTRL 记录的 r2 计数一致 |
| V00-O6（§2 列 `app/schemas/errors.py` 为可改文件但未改动） | observation | 仍成立（低危） | 该文件仍无 diff；`AppError.details` 走 `getattr(exc, "details", None)`，功能口径不受影响。属"允许改"与"实际改"的表述差异，无需修复，保留登记 |

## 7. observation（r2 新增/残留）

1. **`TASK-CARD.md §3.5` 的 `app/core/migrations/sql_*.py` 文件名仍与实际不符**（§2 文件归属表写
   `sql_textbooks.py`/`sql_question_bank.py`/`sql_knowledge.py`/`sql_teaching.py`，实际是
   `textbooks.py`/`question_bank.py`/`knowledge.py`/`teaching.py`；`AGENTS.md` 与我的 V9 检查用的是实际名）。
   r1 未登记，本轮补记：属文档笔误，建议随下次文档维护订正（不影响任何行为）。
2. **`0003` 补齐路径只有合成夹具覆盖**：我拒绝再次打开正式 `.local-data`（r1 已登记过该边界偏差），
   因此"真实既有库首次应用 0003"只由自建夹具（§2 F1②）与实现者用例覆盖；若队长希望有真实现场证据，
   需要另行授权只读/迁移一次正式库。

## 8. not_run（本轮未执行及原因）

| 项目 | 原因 |
| --- | --- |
| 真实 Qdrant 的 v3 `create`/`restore`、真实模型/供应商外呼、真实 DOCX/XLSX 解析 | B0 范围外且需凭证/隔离实例；r2 的 8 个变更文件不含这些路径 |
| `npm run check`（typecheck/lint/unit/build）、e2e | 按任务卡与分工由 CTRL 负责；本轮只做后端回归与前端（r2 未改前端，故未重跑 V7） |
| V7 前端定向 vitest 重跑 | r2 未改 `apps/web/**`（指纹差异集合不含前端文件），按窄复验原则不重跑（r1 结论 10/10 仍适用） |
| 正式 `.local-data` 上的迁移/索引补齐验证 | 遵守只读边界，不做（见 §7.2） |

## 9. 我最不确定的一处

**"既有库补齐"的真实性强度**：F1② 用自建夹具（手工 12 条 ALTER + 手工登记 0002）证明"只新增 0003、
0002 不漂移、索引出现"，并有两处变异（M4/M5）证明断言有效；但**没有任何真实世界库**参与该路径验证——
我按边界不打开正式 `.local-data/question-bank/question-bank.sqlite3`（若它当前已登记 0002，则下次启动会走
0003 补齐路径）。若队长需要"真实库一次补齐"的证据，建议授权一次受控的只读/迁移演练（拷贝到临时目录后验证），
我可以按同样口径补做。

## 10. 现场与纪律

- 隔离：所有探针在导入 `app.*` 前把 `ZQKY_DATA_DIR` 指向会话级临时目录（r1 偏差已修正的做法），
  并在结束时清理；本轮复算 `.local-data` 内**无任何** mtime ≥ 18:44 的文件（含侧车文件）。
- 端口/进程：无 8000/8001/5173/5174/6333/16333 监听；无我启动的进程残留；`%TEMP%\zqky-v00*` 已清空。
- 候选：未修改任何候选文件（§1 对账 55/55）；未提交、未暂存、未切分支；`git rev-parse HEAD`
  仍为 `301fc356493db21d187ab85f32fd49dfffdc51ef`；`git status` 条目数与开工时一致。
- 新增内容仅 `V00-REPORT-02.md` 与本轮探针/证据（`V00-probes/**`）；未改权威文档。
