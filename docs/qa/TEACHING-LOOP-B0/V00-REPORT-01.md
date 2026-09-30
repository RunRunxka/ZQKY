# TEACHING-LOOP B0 · V00 独立验收报告 01

- 验收者：独立验收 Agent（V00，只读产品代码）
- 日期：2026-09-30（本地时间）
- 候选：`main@301fc356493db21d187ab85f32fd49dfffdc51ef` 工作树；冻结指纹 `FROZEN-CANDIDATE.json`
- 结论：**1 项 fail（V9：`question_jobs` 缺 §3.5 声明的 `(state, created_at)` 索引）**；
  其余 V1–V8、V10 **pass**；另有 6 条 `observation`（口径/文档）与 1 组 `not_run`（见 §4、§5）。
- 探针与证据：`docs/qa/TEACHING-LOOP-B0/V00-probes/`（脚本）与 `V00-probes/evidence/`（JSON/TXT 输出）

## 0. 指纹对账（报告开头项）

复算命令（55 个候选文件逐个 sha256，与冻结记录比对）：

```bash
cd "H:/备份xuexi/智启课源/apps/api" && uv run python ../../docs/qa/TEACHING-LOOP-B0/V00-probes/v10_hash_reconcile.py
# 退出码 0；证据：V00-probes/evidence/v10_hash_reconcile.txt / .json
```

| 项目 | 结果 |
| --- | --- |
| 冻结记录声明文件数 / 实际条目 | 55 / 55 |
| 逐字节一致 | **54** |
| 不一致 | **1**（仅为文档，见下） |
| 缺失 | 0 |

唯一差异（**冻结后文档变更，非产品/测试/脚本**，与 CTRL 变更通告一致）：

| 文件 | 冻结 sha256 | 实测 sha256 |
| --- | --- | --- |
| `docs/qa/TEACHING-LOOP-B0/TASK-CARD.md` | `f797e13f12fee3587481c968e6cdc869035e4d6a412ecddbc21d05b348424eb0` | `df1b0f69aa2451e2a1a6e965546552c6a45f8b3ee564d28c045417db70291e65` |

- 时间线证据：我的**首次**指纹复算（会话开始后第一次执行，结果 55/55 一致）时该文件仍与冻结记录一致；
  之后其磁盘 mtime 变为 `18:48:31`，内容为 CTRL 变更通告的两处口径补充
  （§3.4 第 5 条收敛范围=`RECONCILE_DOMAINS`；§6 kind 白名单位置）。我已按新版本文字核对 V9 的"收敛范围"声明（`v9.a7`）。
- 产品/测试/脚本文件：**0 个哈希不符**；V10 变异实验涉及的两个文件（`app/services/jobs/engine.py`、
  `app/repositories/jobs/repository.py`）在实验后复算仍与冻结记录一致（`v10_hash_reconcile.json`）。
- 未提交 Git、未切分支、未推送；`git rev-parse HEAD` 仍为 `301fc356…`。

## 1. 操作纪律与一处边界偏差（如实登记）

**偏差**：V2/V8/V9 探针会 `import app.main`，而 `app.main` 在**导入时**执行模块级 `create_app()`，
默认数据根是仓库 `.local-data`。最初两轮探针因此对**正式 `.local-data`** 建立了只读/迁移检查连接。

- 影响面（已核）：`.local-data` 内 **SQLite 数据文件未被修改**——4 个库文件 mtime 仍是 `18:28:02`/`18:29:54`
  （早于本次会话）、大小未变；`knowledge_jobs`/`workflow_jobs`/`*_submissions` 均为 0 行，`schema_migrations`
  仍只有各自 0001 基线；没有新增/删除任何数据文件。
- 会话期间在 `.local-data/knowledge|teaching` 下出现过 4 个 SQLite 运行时侧车文件
  （`*.sqlite3-wal` 均为 **0 字节**即 0 帧、`*.sqlite3-shm` 32KB 共享内存索引），由我的只读校验连接产生；
  已确认无进程占用（无 8000/8001/5173/5174/6333/16333 监听、无 python/node 进程）后删除，删除后复算
  `.local-data` 内**无任何** mtime ≥ 18:44 的文件。
- 补救：`_probe_common.py` 已按与 `apps/api/tests/conftest.py` 相同的手法，在导入任何 `app.*` 之前把
  `ZQKY_DATA_DIR` 指向会话级临时目录（显式设置优先），并在退出时清理；加固后重跑 V2/V8/V9 结果不变
  （20/20、27/27、58/59），且 `.local-data` 再无文件被动过。
- 结论：未损坏数据、未改候选，但**违反了"探针一律 tmp_path、不读写正式 .local-data"的操作约定**，
  按自查项登记，供队长评估是否需要更强的探针隔离规范（例如禁止探针导入 `app.main`）。

其余边界：未改 `apps/**`、`scripts/**`、任何现行文档与实现者测试；未联网；未连 6333/16333；
未新增 Git 提交；探针数据全部落在系统临时目录（含各自 `finally` 清理）。

## 2. 逐项结论（V1–V10）

运行约定：后端探针 `cd apps/api && uv run python ../../docs/qa/TEACHING-LOOP-B0/V00-probes/<脚本>`；
前端定向 `NODE_OPTIONS=--no-experimental-webstorage npx vitest run --config docs/qa/TEACHING-LOOP-B0/V00-probes/vitest.probe.config.ts`。

| 编号 | 结论 | 命令 / 退出码 | 关键输出（片段） | 证据 |
| --- | --- | --- | --- | --- |
| **V1** 迁移登记 | **pass** | `v1_migrations_probe.py` / **0** | 24/24；`v1.1d repeat apply leaves db file byte-identical`；`v1.2b failed migration left no table`；`v1.3a/b/c` 全部 `SCHEMA_MIGRATION_DRIFT`；`v1.4c/d/e` 旧库既有行**逐列字节**不变 | `evidence/v1_migrations_probe.json` |
| **V2** 启动门控 | **pass** | `v2_startup_gate_probe.py` / **0** | 20/20；垃圾文件/缺表/漂移均拒绝且文件字节不变、无新库；拒绝后文件可改名（句柄已释放）；缺文件放行且不创建；`incomplete` 数据根拒绝 `create_app`、`ready` 通过并建四库 | `evidence/v2_startup_gate_probe.json` |
| **V3** 任务协议 | **pass** | `v3_jobs_engine_probe.py` / **0** | 50/50；claim 1→2 换 token；未过期重复 claim `JOB_BUSY(409,retryable)`；过期可接管且旧 lease `complete`→`LEASE_LOST`、库内 `result_json` 为空；取消迟到不发布（publish 未调用、无业务行）；reconcile 只收敛 running 且幂等；retry 保留 frozen/snapshot/hash、attempt 不变；**并发上限**：heavy 峰值=2、model 峰值=1、变体 1/1，排队者 `lease_expires_at` 持续变化且 6 次接管全 `JOB_BUSY`、三个任务 attempt 全为 1 | `evidence/v3_jobs_engine_probe.json`、`v3_engine_{heavy,model,variant}.json` |
| **V4** 提交幂等 | **pass** | `v4_submission_probe.py` / **0** | 29/29；同键同 hash 重放不二次执行 apply；**改 payload → hash 变 → 409 `SUBMISSION_CONFLICT` 且业务表仍 1 行**；`REVISION_CONFLICT` 带 `details.currentRevision=7`；apply 抛错业务表与 submission 表皆无写入；非法 table 3 例全 422；`request_hash` 与冻结口径逐字节一致（含 `ensure_ascii=False`） | `evidence/v4_submission_probe.json` |
| **V5** 受管资产 | **pass** | `v5_assets_probe.py` / **0** | 42/42；内容寻址 `blobs/<sha256>`、重复写入幂等、无临时文件残留；篡改→`ASSET_CORRUPT`、缺失→`ASSET_MISSING`；14 种非法键（`..`/绝对路径/盘符/反斜杠/大小写/长度）全 `INVALID_ASSET_KEY(422)` 且无越界目录；`ref()` 键集合恰为 7 个 camelCase；坏行 `ASSET_ROW_CORRUPT`（`get`/`list_by_kind` 都不静默） | `evidence/v5_assets_probe.json` |
| **V6** 四库备份恢复 | **pass** | `v6_backup_restore_probe.py` / **0**；CLI 缺库：`uv run python ../../scripts/rag/backup.py create --data-dir <tmp> --into <tmp>` / **1（预期非 0）** | 48/48；四库+资产+教材/题库 blob create→verify→restore 全链路，恢复目录四库可读、`require_data_root_ready` 通过、恢复库与归档副本逐字节相同、`file_assets` 逐文件对账；缺教学库→清单 `status:"failed"`+点名缺哪个库+CLI rc=1+stdout 无"备份完成"；篡改资产→verify 失败且 restore 在写文件前拒绝；**教学库引用未归档 blob→restore 失败且 `restore-state.json: incomplete`（并拒绝启动）**；**删掉 `sqlite/teaching.sqlite3`（连清单条目一起）→ verify 报"完整清单缺少必需文件：teaching/teaching.sqlite3"**；v2/legacy 自建清单 verify+restore 通过且注明覆盖范围 | `evidence/v6_backup_restore_probe.json`、`v6_cli_missing_library.txt`、`v6_manifest.json` |
| **V7** 前端客户端 | **pass** | `npx vitest run --config …/vitest.probe.config.ts` / **0** | 10/10；409 `details.currentRevision`、422 `details.issues[{row,column,code}]` 到达 `ApiError.details`；`AbortError` 原样抛出且 `isAbortError` 为真（非 `SERVICE_UNAVAILABLE`）；`apiRequestBlob` 返回 `{blob,fileName}` 且 RFC5987 解码为 `学情导出.csv`、失败转 ApiError；`observeJob` 轮询 queued→running→succeeded、attempt 不符返回 null、abort 返回 null 且**不调用** cancel 接口 | `evidence/v7_vitest_output.txt` |
| **V8** 公共任务路由 | **pass** | `v8_workflow_jobs_api_probe.py` / **0** | 27/27；`JobView` 字段恰为 7 个 camelCase；未知 id 404 `JOB_NOT_FOUND`；非法域 422 且 `details.fields=["domain"]`；域未装配/已知域无仓储均 503 `SERVICE_UNAVAILABLE(retryable)`；取消幂等（重复取消不重写行）；`queued/running` retry 409、终态 retry 回 `queued` 且保留冻结输入/模型指纹/attempt | `evidence/v8_workflow_jobs_api_probe.json` |
| **V9** 声明抽查 | **fail** | `v9_doc_claims_probe.py` / **1** | **58/59**；API.md 四库路径/路由/404·422·503/取消幂等/租约 90s·心跳 20s/并发上限 2+1 与代码一致；备份 v3 四库+资产、AGENTS.md 迁移纪律、PROJECT_GUIDE §11 均一致；TASK-CARD §3.5/§3.6/§3.7 列清单 = 实际库结构（19/6/9 列）；**唯一 fail：`question_jobs` 没有 §3.5 声明的 `(state, created_at)` 索引**（详见 §3.1） | `evidence/v9_doc_claims_probe.json`、`v9b_question_jobs_index_probe.json` |
| **V10** 断言"有牙齿" | **pass** | 变异 ×3：`v10_mutation_runner.py`（M1/M2/M3）/ 均 **0**；对账 `v10_hash_reconcile.py` / **0** | M1 心跳间隔改错 → 实现方 2 例 + 我的探针 6 条断言失败（含官方回归例 `test_engine_slot_wait_keeps_lease_and_blocks_takeover`、`test_engine_heartbeat_loss_cancels_executor_and_publishes_nothing`）；M2 取消判定改错 → 1 例 + 2 条断言（`state=succeeded result={'late':…} publish_called=['called']`）；M3 retry 守卫改错 → 1 例 + 3 条断言；变异只在**我自己的临时副本**上执行（运行器以模块注入方式覆盖，候选文件全程未改），对账 54/55 一致（唯一差异即 §0 的文档变更） | `evidence/v10_M{1,2,3}-*.json`、`v10_hash_reconcile.{json,txt}` |

实现方测试复跑（记录为"实现方声明已复跑"，不替代上述独立探针）：

```bash
cd apps/api && uv run python -m pytest tests/test_migrations.py tests/test_startup_gates.py \
  tests/test_jobs_engine.py tests/test_submission_commands.py tests/test_assets.py \
  tests/test_workflow_jobs_api.py -q
# 退出码 0；--collect-only 计数 81，-q 输出 81 个通过点（无 F/E）
# 证据：V00-probes/evidence/v0_implementer_tests_baseline.txt
```

## 3. fail 明细与最小复现

### 3.1 V9 fail：`question_jobs` 缺 §3.5 声明的 `(state, created_at)` 索引

- 期望（TASK-CARD §3.5）：三张任务表统一 `索引：idx_*_jobs_state(state, created_at)、idx_*_jobs_kind(kind, state)`。
- 实测（新建库与"旧库采纳"两条路径都一样）：

  | 表 | 实际索引 |
  | --- | --- |
  | `knowledge_jobs` | `idx_knowledge_jobs_state(state, created_at)`、`idx_knowledge_jobs_kind(kind, state)` |
  | `workflow_jobs` | `idx_workflow_jobs_state(state, created_at)`、`idx_workflow_jobs_kind(kind, state)` |
  | `question_jobs` | **只有** `idx_question_jobs_state(kind, state)`（旧基线遗留名）；**(state, created_at) 不存在** |

- 根因（首败行号）：`apps/api/app/core/migrations/question_bank.py:191-195`
  `_skip_existing_columns()` 只返回 12 条 `ALTER TABLE ADD COLUMN`，把声明集合里的第 13 条
  （`_ENGINE_STATEMENTS` 末尾，question_bank.py:186-188 的
  `CREATE INDEX IF NOT EXISTS idx_question_jobs_engine_state ON question_jobs(state, created_at)`）
  在执行前丢掉；而登记散列（`Migration.sha256`）覆盖的是**声明集合**，所以漂移校验也不会揭示
  这条从未执行的语句（`v9b.1`/`v9b.3`/`v9b.6`）。
- 最小复现（单条命令，全部在临时目录）：

  ```bash
  cd apps/api && uv run python ../../docs/qa/TEACHING-LOOP-B0/V00-probes/v9b_question_jobs_index_probe.py
  # 退出码 0（探针本身断言的是"缺陷确实存在"）：
  #   v9b.2 全新题库库：question_jobs 没有 (state, created_at) 索引
  #   v9b.3 hook 返回 12 条（全部 ALTER）；声明集合共 13 条（12 ALTER + 1 CREATE INDEX）
  #   v9b.5 既有库路径：ALTER 补齐了 12 列，但 (state, created_at) 索引同样缺失
  ```

  等价的最短 Python 复现：

  ```bash
  cd apps/api && uv run python -c "
  import tempfile, pathlib
  from app.repositories.question_bank.catalog import QuestionBankCatalog
  from app.core.sqlite import connect
  db = pathlib.Path(tempfile.mkdtemp()) / 'qb.sqlite3'
  QuestionBankCatalog(db).migrate()
  con = connect(db)
  print({r['name']: [i['name'] for i in con.execute(f'PRAGMA index_info(\"{r[\\\"name\\\"]}\")')]
         for r in con.execute('PRAGMA index_list(question_jobs)')})
  "
  # 期望：含 ['state','created_at'] 的索引；实测：只有 {'idx_question_jobs_state': ['kind','state'], …}
  ```

- 影响：题库任务的按状态扫描（`reconcile_interrupted`/列表）缺该索引；**冻结 DDL 与库内实际结构不一致**，
  且漂移校验覆盖了这条从未执行的语句，后续不会自动察觉；B2 迁移题库任务时需要以新增迁移补齐。
  非数据正确性缺陷（查询结果不受影响），定级为 fail（契约/结构不符），建议由队长安排修复方向：
  让 adjust 钩子在返回 ALTER 之外保留索引语句（或改用 `CREATE INDEX IF NOT EXISTS` 独立语句不经钩子过滤），
  **注意需按迁移纪律新增迁移、不得改写已登记 SQL**。
- 附带命名偏差（observation，非 fail）：`question_jobs` 的 `(kind, state)` 索引名是旧基线的
  `idx_question_jobs_state`，而 §3.5 的偏差记录只提到 kind/ALTER，未登记该命名差异。

## 4. observation（口径/文档，不判 fail）

1. **retry 后错误字段保留**：`retry`（repository.py:468-488）只把状态置回 `queued` 并清租约/取消标志，
   `error_code/error_json` 保留到下次 `claim` 才清空（`claim` 中 `error_code = NULL`）。因此
   `JobView` 会短暂呈现 `state=queued` 且 `error` 非空（V8 实测：`error_code=MODEL_CONFIG_INVALID`）。
   契约与 API.md 未规定此组合；建议明确"queued 视图是否展示上次错误"，避免 UI 误读。
2. **PROJECT_GUIDE §11 未点名收敛范围例外**：§11 只写"重启遗留 `running` 收敛为 `interrupted`"，
   未说明启动收敛只覆盖 `knowledge`/`teaching`（`RECONCILE_DOMAINS`，题库组织任务留待 B2）。
   同一口径在 TASK-CARD §3.4.5（更新版）与批次 README §5 有明确说明，建议 §11 补一句。
3. **API.md 资产归档路径表述**：文档写"受管资产以 `assets/blobs/<sha256>` 入清单"，
   实际归档路径是 `files/assets/blobs/<sha256>`（清单 `restorePath` 才等于 `assets/blobs/<sha256>`）。
   建议加"归档目录前缀 `files/`"以免读者按归档路径找文件时困惑。
4. **`question_jobs` 索引命名**：见 §3.1 末尾（`idx_question_jobs_state` vs §3.5 的 `idx_*_jobs_kind`）。
5. **实现方 README 的用例计数**：README 记"后端全量 1007 passed（+87 例）"；我按验收范围只复跑了本批
   6 个新增/扩写测试文件（81 例全通过，退出码 0；证据 `v0_implementer_tests_baseline.txt`），
   **未复跑全量套件**，因此未核对 1007/+87 的口径。
6. **`schemas/errors.py` 未在冻结清单但被 TASK-CARD §2 列为 CTRL 可改文件**：实际未改动（工作树无该文件 diff），
   `AppError.details` 走 `getattr(exc, "details", None)`，与 API.md 的错误信封口径一致；仅记录口径差异，
   不构成问题。

## 5. not_run（未执行项与原因）

| 项目 | 原因 |
| --- | --- |
| 真实模型/供应商调用（含真实 DOCX/XLSX 解析、人工教学质量） | B0 范围外（批次明确不做业务模块与真实调用）；无凭证，也未尝试 |
| 真实 Qdrant 的 v3 `create`/`restore` CLI 成功路径 | 需可达的隔离 Qdrant 实例（不得连 6333）；本轮用自建 Fake 替身完成 6①/6③/6④/6⑤，**未**验证真实快照上传/点数对账 |
| `npm run check` / `npm run build` / e2e | 按任务卡 §5 与总控分工，构建与全量工程检查由总控负责；本轮只做前端定向 vitest（V7） |
| 后端全量 `npm run test:api` | 同上（范围外）；本批 6 个测试文件已复跑（81 passed） |
| 跨连接凭证隔离 / 旧配置迁移 / `.env`-JSON 失败补偿 / 推理与正文拆分 / SSE 中途失败与取消 / 模型发现来源 / 专用认证过期与取消 | **本批候选未触及这些代码路径**（`git status` 中无 `providers/`、`chat.py`、`secrets.py`、`model_*` 改动），B0 范围外；故不适用/未执行 |
| "默认预算耗尽时是否假成功" | B0 无预算/token 概念（不适用）；同类"不假成功"不变量已独立验证：引擎失败路径（V3.9）、发布回滚（V3.9b）、提交回滚（V4.4）、备份缺库/篡改/半完成恢复（V6②③④）、未装配 503 与 501 占位（V8）均如实失败，未发现伪造成功 |

## 6. 我最不确定的一处

`question_jobs` 索引缺失的"严重度"判断：我按"§3.5 冻结结构未落地 + 漂移校验掩盖"判为 fail，
但它在 B0 阶段**没有任何功能/数据影响**（题库任务 B2 才纳入统一引擎，`question_jobs` 当前无写入方），
也可能被队长判定为"可并入 B2 的一次新增迁移"而降级为 observation。请队长在"是否必须在本批修复"
上做决定；如果降级，建议同时在 §3.5 偏差记录补一句（避免读者以为索引已存在）。

## 7. 运行资源与现场

- 端口：无 8000/8001/5173/5174/6333/16333 监听；无我启动的进程残留（`tasklist` 无 python/node）。
- 临时目录：探针自带 `finally` 清理；我额外清理了变异运行器的临时副本目录，`%TEMP%\zqky-v00*` 已为空。
- 候选文件：未修改（§0 对账）；未提交、未暂存、未切分支；新增内容仅
  `docs/qa/TEACHING-LOOP-B0/V00-REPORT-01.md` 与 `V00-probes/**`。
- 未写权威文档（`docs/API.md`、`PROJECT_GUIDE.md`、`CURRENT_STATUS.md`、TASK-CARD、FROZEN-CANDIDATE.json 均只读）。
