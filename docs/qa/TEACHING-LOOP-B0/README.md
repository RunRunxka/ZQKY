# TEACHING-LOOP B0 批次证据（公共契约与基础设施）

- 批次：**B0（CTRL + T00-a + T00-b）**，依 [多Agent实施任务计划书 v2.0 §二.3](../../design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md)
- 起点：`main@301fc356493db21d187ab85f32fd49dfffdc51ef`（工作区，HEAD 未变；`docs/PLAN.md` 用户未提交修改原样保留，`docs/design/` 为用户设计输入）
- 日期：2026-09-30（本地时间）
- 任务卡（范围/文件归属/契约/验收）：[TASK-CARD.md](TASK-CARD.md)
- 独立验收任务卡：[V00-TASK-CARD.md](V00-TASK-CARD.md)；冻结指纹：[FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)（55 个候选文件 sha256）
- 候选停止写入时刻：见冻结记录与 V00 报告的对账；**独立验收后如再做修复，须重新冻结并说明**

## 1. 本批交付（对照 B0 完成条件）

| 计划 B0 条目 | 交付 |
| --- | --- |
| 类型契约 | `apps/api/app/contracts/teaching_loop.py`（`RevisionIdentity`/`ScoreCell`/`Observation`/`JobView`/`AssetRef`/`RichContentV2`/`canonical_hash`/错误详情）+ `apps/web/src/contracts/teaching-loop.ts` 双侧一致 |
| 错误契约 | 信封 `details = {currentRevision?, issues?, fields?}`；`AppError.details` 与统一处理器；前端 `ApiError.details` 保留 |
| 版本契约 | `revision`（乐观锁） vs `revisionId`（固定修订）冻结；提交幂等 `(ownerId, operation, submissionId)` |
| 任务契约 | `app/repositories/jobs` + `app/services/jobs`：claim/租约（90s、心跳 20s）/取消/同库同事务发布/重启收敛/重试保留冻结输入/并发上限 2 重任务 + 1 模型任务；路由 `GET/POST /api/v1/workflow-jobs/...` |
| 资产契约 | `AssetStore`（内容寻址、只增不改、读取重算散列、路径穿越拒绝）+ `file_assets` 登记仓储 |
| 迁移契约 | `app/core/migrations/`（四库追加式清单 + `schema_migrations` 散列登记）+ 启动门控（恢复状态 → 体检 → 迁移 → 收敛） |
| 前端公共客户端 | `api-client` 三缺口（details / 取消语义 `isAbortError` / `apiRequestBlob`）+ `workflow-jobs-api.ts`（含 `observeJob` 2s/5s 轮询与 attempt 守卫） |
| 四库备份 | `scripts/rag/backup.py` v3：四库 + 受管资产，缺库/缺原件拒绝完整性通过，恢复后四库完整性 + `file_assets` 逐文件对账；v2/legacy 只读兼容 |

**未做（按范围）**：任何业务表与业务页面（知识点 CRUD、名单/原卷/成绩/学情/练习/教案后端）、真实模型调用、Qdrant 变更、e2e。B1—B7 需用户另行授权。

## 2. 文件清单

详见 [FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)（55 个文件与逐个 sha256）。摘要：

- 后端新增 26 个：契约 1、启动门控 1、迁移 6、目录/仓储 10（knowledge/teaching/jobs/assets）、服务 6、路由与 schema 2。
- 后端修改 11 个既有文件：`main.py`、`core/config.py`、`core/exceptions.py`、`core/sqlite.py`、`textbook_catalog/{schema,catalog}.py`、`question_bank/{schema,catalog}.py`、`AGENTS.md`、`tests/conftest.py`、`tests/test_backup_restore.py`。
- 后端测试新增 6 个：`test_migrations.py`、`test_startup_gates.py`、`test_jobs_engine.py`、`test_submission_commands.py`、`test_assets.py`、`test_workflow_jobs_api.py`；既有 `test_backup_restore.py` 按 v3 契约扩写。
- 前端新增 3 个（`contracts/teaching-loop.ts`、`services/workflow-jobs-api.ts` + 测试）、修改 3 个（`contracts/api.ts`、`services/api-client.ts` + 测试）。
- 脚本 1 个（`scripts/rag/backup.py`）；文档 4 个（`docs/API.md`、`PROJECT_GUIDE.md`、`CURRENT_STATUS.md`、`api/AGENTS.md`）+ 本目录任务卡与证据。

## 3. 验证（全部在候选上实跑）

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 后端全量（r1） | `npm run test:api` | **1007 passed**（基线 920，+87 例；退出码 0） |
| 后端全量（r2，含 V00 修复） | `npm run test:api` | **1011 passed**（退出码 0；日志 `_work/b0-smoke/testapi-r2.log`） |
| 后端定向（实现方声明） | `uv run python -m pytest tests/test_jobs_engine.py tests/test_submission_commands.py tests/test_workflow_jobs_api.py -q` | 58 passed（r2） |
| 后端定向（实现方声明） | `uv run python -m pytest tests/test_assets.py tests/test_backup_restore.py tests/test_textbook_ingest.py -q` | 72 passed（T00-b 结果卡；由我在全量 1011 中覆盖） |
| 前端单测 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | **76 文件 / 733 例通过**；本批变更范围新增 13 例（`api-client` +7、`workflow-jobs-api` 新文件 +6） |
| 根检查 | `NODE_OPTIONS=--no-experimental-webstorage npm run check` | 退出码 0（typecheck + lint 0 警告 + unit + build 通过） |
| 真实 v2 归档只读复验 | `uv run python scripts/rag/backup.py verify --path _work/rag-backups/rag-20260929-130007-pre-clean-generation` | rc 0（旧清单只读兼容未被破坏；实现方执行） |

口径说明：标注"实现方声明"的数字来自 T00-a/T00-b 的结果卡，由我在后端全量 1011 中输入覆盖；
其余检查由总控实跑。逐条命令、退出码与关键输出见 [EVIDENCE-COMMANDS.md](EVIDENCE-COMMANDS.md)。
**未执行**（`not_run`）：e2e（本批无页面/路由/布局/保存/导出改动，任务卡 §5 明确不跑）；
真实 Qdrant 的 v3 `create`/`restore` CLI 成功路径（CLI 无法注入替身，禁止连 6333）；真实模型调用；
真实 DOCX/XLSX 解析；真实数据根上的 v3 备份恢复演练。

## 4. 独立验收（V00）与 findings 处置

独立验收报告：[V00-REPORT-01.md](V00-REPORT-01.md)（探针与证据在 [V00-probes/](V00-probes/)）。
**结论：9 项 pass、1 项 fail、6 条 observation**；fail 与 observation 已在本批逐条处置（见下表），
修复后重新冻结为 **r2** 并做窄复验（[V00-REPORT-02.md](V00-REPORT-02.md)，见 §4.2）。

### 4.1 fail 与 observation 处置

| 编号 | 等级 | 内容 | 处置 |
| --- | --- | --- | --- |
| V00-F1 | **fail** | `question_jobs` 缺 §3.5 声明的 `(state, created_at)` 索引：`0002` 的 `adjust` 钩子只返回 12 条 ALTER，丢掉第 13 条声明的 `CREATE INDEX ...`；登记散列覆盖声明集合，漂移校验不揭示 | 修复（CTRL）：钩子改为**保留全部非 ALTER 声明**；新增迁移 **`0003_question_jobs_engine_state_index`** 给已应用 0002 的既有库补齐（0002 声明与散列不变，既有库不漂移）；新增 3 条用例（索引存在性、既有库补齐、钩子必须执行全部声明语句） |
| V00-O1 | observation | `retry` 后 `state=queued` 但 `error_code/error_json` 保留到下次 claim，UI 可能误读 | 修复（T00-a）：`retry` 同事务清空 error；新增用例（失败任务 retry 后 `error` 为空且冻结输入/指纹/attempt 保留）；首败证据：临时还原清错语句 → `assert 'MODEL_CONFIG_INVALID' is None` 失败 |
| V00-O2 | observation | `PROJECT_GUIDE §11` 未点名收敛范围只含 `knowledge`/`teaching` | 已补（本批文档） |
| V00-O3 | observation | `API.md` 资产归档路径未写 `files/` 前缀 | 已补：清单 `restorePath = assets/blobs/<sha256>`，归档路径 `files/assets/blobs/<sha256>` |
| V00-O4 | observation | 任务表索引命名与 §3.5 通配写法不一致（`idx_question_jobs_state` 为旧基线名） | 任务卡 §3.5 已逐表登记实际索引名与命名偏差 |
| V00-O5 | observation | 批次 README 的用例计数含实现方声明，验收未复跑全量 | README §3 已标注口径来源；总控在 r2 全量 1011 中输入覆盖 |
| V00-O6 | observation | `schemas/errors.py` 在任务卡 §2 归类为 CTRL 可改文件但实际未改动（`AppError.details` 走 `getattr`） | 口径记录，不构成问题 |

### 4.2 冻结修订与窄复验

- **r1**（记录保留在 [FROZEN-CANDIDATE-r1.json](FROZEN-CANDIDATE-r1.json)）：V00 复算 55 个文件中 **54 一致**；
  唯一差异是冻结后由 CTRL 做的 `TASK-CARD.md` 两处**口径补充**（非产品/测试/脚本），已提前通告并记录在
  V00 报告 §0。
- **r2（本批最终候选）**：V00-F1 与 V00-O1 修复后重新冻结；相对 r1 变化 **8 个文件**
  （产品/测试 4：`core/migrations/question_bank.py`、`repositories/jobs/repository.py`、
  `tests/test_migrations.py`、`tests/test_jobs_engine.py`；文档 4：`docs/API.md`、`PROJECT_GUIDE.md`、
  `CURRENT_STATUS.md`、`TASK-CARD.md`），逐一对账记录在 `FROZEN-CANDIDATE.json.changedSincePrevious`。
- **r2 窄复验（[V00-REPORT-02.md](V00-REPORT-02.md)）：5/5 pass，无新增 fail**——
  ① 新鲜库与"修复前既有库"两条路径都拿到 `idx_question_jobs_engine_state(state, created_at)`，`0002` 散列
  保持 `61e55952…` 未漂移；② `retry` 后库内 `error_code/error_json` 为 NULL、视图 `error` 为 null，
  冻结输入/指纹/attempt 保留；③ 文档声明探针 **60/60**；④ r2 指纹 **55/55**，差异集合与声明一致（不多不少）；
  ⑤ 7 个测试文件 **108 passed**，全量 `npm run test:api` **1011 passed** 由其本机复现。
  另外其变异实验 M4/M5 证明两半修复都有回归保护（还原钩子缺陷或删掉 0003 → 对应用例与探针失败）。
- **r2 之后的后验改动（已登记，仅文档）**：V00 r2 指出 `TASK-CARD §2` 文件清单仍写 `sql_*.py`（实际为
  `base.py`/`textbooks.py`/`question_bank.py`/`knowledge.py`/`teaching.py`）并漏记 `database_gate.py` 等归属；
  CTRL 修正该清单后，冻结记录以 `postVerificationDocChanges` 记录前后散列与理由（不触及 §3.5/§3.6/§3.7 断言内容）。
- **未获取的证据（如实登记）**：`0003` 在**真实数据根**上的补齐路径只有合成夹具覆盖——真实库演练需要写入授权，
  因此 `not_run`。正式 `.local-data` 的只读核对结果见 §7 第 7 条。


## 5. 首败与修复（本批真实缺陷，均已修复并留证据）

| 编号 | 现象与首败 | 修复 |
| --- | --- | --- |
| T00-a-01 | `JobEngine.run_job` 先 claim 后等并发名额，心跳在拿到名额后才启动：排队超过 `lease_seconds` 的任务租约过期，可被第二个执行者按"过期接管"领取 → 同一 job 两个执行者。回归用例 `test_engine_slot_wait_keeps_lease_and_blocks_takeover` 在旧顺序下失败：`AssertionError: 等待条件超时`（4s 内排队任务 `lease_expires_at` 从未变化） | 心跳提前到名额等待之前（claim → 载入冻结输入 → 启动心跳 → 竞速取名额 → 执行）；失权即取消等待、归还名额、不执行不发布 |
| CTRL-01 | `app/core/sqlite.connect` 先切 WAL 再设 `busy_timeout`：多进程（应用/CLI/并行测试）首次打开同一库时抛 `database is locked`（B0 四库共享同一数据根后暴露） | 先 `busy_timeout` 再 `journal_mode` |
| CTRL-02 | 启动门控体检垃圾文件时 `connect()` 的 WAL PRAGMA 直接抛错，连接对象未关闭 → Windows 上文件句柄泄漏（临时目录删不掉） | 门控改用不设 WAL 的专用打开方式，`finally` 关句柄；`test_startup_gates` 断言拒绝后文件可删 |
| CTRL-03 | 后端测试套件导入 `app.main` 时模块级 `create_app()` 会对**正式** `.local-data` 建库/迁移（既有行为；并行跑测试时还互相抢写锁） | `tests/conftest.py` 在导入 `app.main` 前把 `ZQKY_DATA_DIR` 指向会话级临时目录（显式设置优先）；`app.main` 运行期行为不变 |

其他记录：实现方 T00-b 开发中修正过一处 WAL 事务可见性断言写法（跨连接读未提交事务）与一处错误文案笔误，详见其结果卡。
另：独立验收发现的 V00-F1（索引声明被 adjust 钩子丢弃）与 V00-O1（retry 保留旧错误字段）不在实现者自检范围内，
由 CTRL/T00-a 在本批修复，逐条处置见 §4.1。

## 6. 与既有能力的兼容

- 教材目录/题库迁移改为经登记表执行，DDL 与旧版**逐字一致**（冻结为 0001 基线），既有库首次运行只是登记、不改数据；
  `question_jobs` 用 `ALTER TABLE ADD COLUMN` 补列，旧读写路径不变（题库原有五态枚举未改）。
- 备份 v2/legacy 清单仍可 verify/restore（只覆盖当时的教材目录与题库）；新备份为 v3 四库 + 资产。
- 前端 `api-client` 只增不改：原 `apiRequest` 调用方语义不变（`details` 是新增可选字段）。
- 启动收敛范围**只含知识点库与教学库**：题库组织任务的五态与旧 UI 视图未迁移，B2 迁移题库任务时纳入（避免旧界面出现不认识的状态）。

## 7. 遗留与边界（如实登记）

1. `verify_backup` 对 v3 只按清单逐文件校验，不重新推导教学库资产引用；内部不一致归档会在 `restore` 阶段以 `incomplete` 拒绝（契约口径，见 T00-b 结果卡）。
2. 任务 kind 白名单在 `app/main.py` 硬编码（`JOB_KINDS`）；新增任务类型属总控级变更（改一行 + 文档）。
3. `retry`/`claim` 对 `succeeded` 返回 409 `JOB_NOT_RETRYABLE`（结果已发布不允许重跑；契约 §3.4.6）。
4. `AssetStore.store_original` 对"同名但内容不符"的既有文件执行原子重写修复（内容寻址不变量的实现方式），不是"只报错"。
5. `import app.main` 时的模块级 `create_app()` 运行期仍会对默认数据根建库/迁移（应用自身行为）；测试已隔离到临时目录。
6. 本批没有真实服务/模型/Qdrant 证据；"构建与自动化通过"不等于业务、视觉或真实模型质量通过。
7. **正式 `.local-data` 的只读核对（CTRL，只读不写）**：`textbooks`＝`0001`；`question_bank`＝`0001`+`0002`
   （`question_jobs` 19 列、旧索引 `idx_question_jobs_state`，**`0003` 尚未应用**）；`knowledge`/`teaching`＝各自 `0001` 基线。
   这是**合法的"待应用迁移"状态**：下次启动应用会自动补 `0003` 索引。开发早期的测试运行（在 `conftest` 隔离修正之前）
   确实对正式数据根执行过迁移登记与 `0002` 补列——**业务数据行零改动**（题库表无新增/修改行，教材目录仅登记）；
   测试隔离修正后不再发生；本说明为如实披露，不构成缺陷。
8. **未获取的真实库证据**：`0003` 的既有库补齐在真实 `.local-data` 上未演练（需写入授权），只有合成夹具覆盖。
