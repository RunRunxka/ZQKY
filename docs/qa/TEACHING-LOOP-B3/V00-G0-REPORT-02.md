# V00 · TEACHING-LOOP B3 / G0 独立复验报告（02 · r2 窄复验）

- 任务：CTRL 修复 r1 唯一阻塞 fail（RV11 迁移 0005）后的**窄复验**
- 复验对象：`FROZEN-G0.json`（**r2**，106 文件，冻结于 `2026-10-01T19:31:40`）；r1 记录 `FROZEN-G0-r1.json`
- 只读边界：未改 `apps/**`、`scripts/**`、现行文档、实现者测试、冻结记录、审查目录；本次新增仅 `V00-probes/**` 与本报告
- 所有探针在导入 `app.*` 前设 `ZQKY_DATA_DIR` 指向临时目录；模型受控替身；不联网；不占端口

## 0. 结论一览

| 复验项 | 结论 | 命令 / 证据 |
| --- | --- | --- |
| 1. r2 指纹 106/106 + r1→r2 差异 = 恰好 3 文件 | **pass** | `python docs/qa/TEACHING-LOOP-B3/V00-probes/p17_r2_fingerprint.py`（19:35:40 运行：106/106、diff=3 文件、103 未变）；`p17_r2_fingerprint.after-move.json`、`p18_r2_timeline.json` |
| 2a. r1 最小复现 `p12` | **pass**（原 fail 已关闭） | `p12_rv11_startup_repro.py`（19:32:45：exit 0 / verdict pass） |
| 2b. 自建变体（两已确认 / 一草稿+一已确认 / 带 items+knowledge+blocks+issues 子行 / title_snapshot 部分已存在） | **pass** | `p16_rv11_r2_migration.py`：exit 0 |
| 3. RV11 判据全项（含触发器逐字恢复、FK/integrity、失败回滚可重跑、坏 0006 注入、散列不变） | **pass** | `p11_rv11_titles_migration.py`：exit 0；`p16_*`：exit 0 |
| 4. 无产品回归：RV01 与 publish 收敛重跑 | **pass**（同数；并发状态码存在两种合法时序，见 §5） | `p01_rv01_retry.py`（3 次均 exit 0）、`p13_publish_failure.py`（exit 0） |
| 5. r1 报告是否仍有成立的 fail | **无新增 fail**；r1 唯一 fail（RV11 迁移）已关闭 | 本报告 §2–§4 |
| 附加：CTRL 改动的两个测试文件 | 19 passed / exit 0（补充证据，非替代品） | `pytest tests/test_b2_migrations.py tests/test_migrations.py -q` |

**候选移动提示（重要）**：r2 冻结后，业务段（T60）于 `19:35:56` 改写了同一文件 `apps/api/app/core/migrations/teaching.py`（新增 0006/0007），并新增 `app/contracts/scores.py`、`app/services/tabular.py`、`web/src/contracts/scores.ts`。因此**当前工作区已不等于 r2 候选**；本报告全部结论锚定在 r2 冻结字节（最后一次 106/106 复算通过于 19:35:40，所有探针证据 ≤ 19:35:25，早于该改写）。若 G0 结论需要在业务候选上成立，应由 CTRL 重新冻结并（按需）再验。

## 1. 指纹对账

```
cd H:\备份xuexi\智启课源
python docs/qa/TEACHING-LOOP-B3/V00-probes/p17_r2_fingerprint.py
```

- 19:35:40 运行（r2 冻结字节）：`fileCount=106, listed=106, hashedOk=106, missing=[], mismatch=[]`。
- r1→r2 差异（由两份清单逐条比对，独立于 CTRL 声明）：

```json
{"added": [], "removed": [],
 "changed": ["apps/api/app/core/migrations/teaching.py",
             "apps/api/tests/test_b2_migrations.py",
             "apps/api/tests/test_migrations.py"],
 "unchangedCount": 103, "equalsExpectedChanged": true}
```

**= 恰好 CTRL 声明的 3 个文件，不多不少；其余 103 个文件散列不变。**

- 移动后复算：`hashedOk=105`，唯一不一致为 `apps/api/app/core/migrations/teaching.py`
  （r2 清单 `f64815d1…`，当前 `84abbee7…`）；`p17_r2_fingerprint.after-move.json`（exit 1，符合"候选已移动"）+ `p18_r2_timeline.json` 记录时间线。r2 冻结字节的那次 106/106 结果保存在 `p17_r2_fingerprint.json`。
- 审查目录仍为 26 个文件、最新 mtime `17:14:54`，未修改。

## 2. 原最小复现与自建变体

### 2.1 原最小复现（r1 判 fail 的那条）

`p12_rv11_startup_repro.py`（在临时目录构造"含一条已确认修订的 B2 旧库"→ `create_app`）：

```
19:32:45 运行（r2 冻结字节）：EXIT=0，verdict=pass
{"startupError": null,
 "dbState": {"hasTitleSnapshot": true,
             "registeredMigrations": ["0001…","0002…","0003…","0004…","0005_teaching_paper_revision_titles"]}}
```

> 证据完整性：`p12_rv11_startup_repro.json` 已被 19:36:34 的"移动后"信息性重跑覆盖（该次同样 pass，且登记到 0007）；两次运行的时间线与结论记在 `p18_r2_timeline.json.p12Runs`。

### 2.2 自建变体 + 不变量（`p16_rv11_r2_migration.py`，exit 0）

旧库全部经**合法确认路径**造出已确认修订（draft + 计分叶 + 知识点 → `UPDATE … state='confirmed'`），三个形状：

| 形状 | 结果 |
| --- | --- |
| A. 两个已确认修订 + 一个草稿，且每修订带 `paper_items`/`paper_item_knowledge`/`paper_source_blocks`/`paper_issues` | `applied=["0005…"]`；两列齐备；全部行（含草稿）`title_snapshot="旧卷标题（当前值）"`、来源 `backfilled_from_paper`；子行 4 类逐行不变 |
| B. 一草稿 + 一已确认 | 同上（草稿行也按 `papers.title` 回填并标注来源） |
| C. `title_snapshot` 列已存在的部分状态 | 钩子过滤掉该 ALTER，仍完成另一列 + 回填 + 触发器恢复 |

三个形状共同满足（逐项记录在 `p16_rv11_r2_migration.json`）：

- `triggerVerbatim=true`：`sqlite_master` 中恢复后的触发器文本，与 0003 声明文本、与模块常量 `_IMMUTABLE_REVISIONS_UPDATE_TRIGGER` 在**空白与 `IF NOT EXISTS` 归一后逐 token 相同**（SQLite 存储时会自行剥掉 `IF NOT EXISTS` 与缩进，这是存储层行为，非文本差异）；
- 触发器语义仍在位：已确认修订 `UPDATE` → `IMMUTABLE_REVISION`；直接插已确认行 → `USE_CONFIRM_TRANSITION`；已确认修订的 `paper_items` 插入 → `IMMUTABLE_REVISION`；
- `foreign_key_check=[]`、`integrity_check=["ok"]`、`PRAGMA foreign_keys=1`；
- 迁移登记散列 = 当前 `Migration.sha256`；重复应用为空操作（`appliedAgain=[]`）。

## 3. RV11 判据全项

| 判据 | 结论 | 证据 |
| --- | --- | --- |
| 迁移在含已确认修订的 B2 旧库上成功（此前 fail） | **pass** | `p12`（exit 0）、`p16` 三形状（exit 0） |
| 旧修订标题不随新草稿改名而变 | **pass** | `p11`：`beforeTitle=Original Title`、改名后 `afterTitle=Original Title`、`paperTitleNow=NEW DRAFT Title`；DB 快照 confirmed=`Original Title`(source=revision)、新草稿=`NEW DRAFT Title`(source=revision) |
| 来源标注 | **pass** | 回填行 `title_snapshot_source='backfilled_from_paper'`；运行期写入为 `revision` |
| `foreign_keys` / `integrity_check` | **pass** | `p16`：`foreign_keys=1`、`foreign_key_check=[]`、`integrity_check=ok`（三个形状） |
| 失败回滚 + 可重跑 | **pass** | `p11`：注入 `BEFORE UPDATE OF title_snapshot` 触发器 → `IntegrityError: BLOCKED`，两列未加、未登记、pending 仍列 0005、`foreign_keys=1`；移除触发器后重跑成功、来源正确 |
| 注入坏 0006 验证 0005 不受影响 | **pass** | `p16`：坏 0006（`SELECT * FROM v00_does_not_exist`）→ 0005 已应用并登记、0006 未登记、pending=`["9001_v00_bad"]`、回填结果完好；换好 0006 后只补跑 0006，0005 不重跑、数据不变 |
| 声明集合/散列不变（无漂移） | **pass** | `p16`：声明文本（2 ALTER + 回填）与 r1 验收时读取的文本**逐字相同**，条数=3；当前 0005 散列 `a06f042ab0b769d4fec9e9a5f172a1e6a6d5f75875301b6a26517b0fa6756961`；另一库预登记同散列后 `apply_migrations` **不报** `SCHEMA_MIGRATION_DRIFT` 且零重复执行 |
| 验收入口 `p11`（r1 曾 fail 的整条探针） | **pass** | `p11_rv11_titles_migration.py`：exit 0，`failures=[]`（r1 时 exit 1） |

> 散列不变的口径说明：`Migration.sha256` 由 `statements` 计算（`adjust` 不参与），r2 只改了钩子，声明三条文本未动；我逐字比对了 r1 验收时读取到的三条文本。**我未保留 r1 源码字节**（工作区被覆盖、无 r1 备份），因此"与 r1 注册散列相等"这一点由"声明文本逐字相同 + 同散列登记不报漂移"支撑，而非直接对 r1 散列读数；CTRL 已用正式库只读对比确认，我未读取正式库。

## 4. 无产品回归抽查（与 r1 同数）

### 4.1 RV01 真装配 retry（`p01_rv01_retry.py`，3 次均 exit 0）

| 场景 | r1 | r2（3 次） |
| --- | --- | --- |
| 失败 → retry → 终态 | failed→200 queued(1)→succeeded(2)，调用 1→2 | 同 |
| queued 未调度 → 再 retry 补调度 | queued→200→succeeded(2)，调用 +1 | 同 |
| running → 409 | 409 `JOB_NOT_RETRYABLE` | 同 |
| 并发双 retry | `[200,409]`，attempt+1，调用+1 | 共 4 次运行：1 次 `[200,200]`（未放宽断言时报 fail，见 §5-1）、2 次 `[200,409]`、1 次 `[200,200]`；每次 attempt+1、调用+1、终态 succeeded |
| 注册表重复 schedule | True/True，只执行一次 | 同 |
| 重复点击 | 200/409，只执行一次 | 同 |
| 重启后 queued | 不自动重放；显式 retry 后 succeeded(2) | 同 |

### 4.2 publish 失败收敛（`p13_publish_failure.py`，exit 0）

teaching / question / knowledge 三域数值与 r1 完全同形：`AppError` → `failed`+保留码、业务行回滚；非 AppError → `failed`+`JOB_FAILED`+固定文案、业务行回滚；正常发布 `succeeded`+业务行保留；取消优先 → `cancelled`；失权零写入（接管后 attempt=2、`running`、error NULL）；无永久 running。

### 4.3 附加（CTRL 改动的测试，补充证据）

```
cd apps/api && .venv/Scripts/python.exe -m pytest tests/test_b2_migrations.py tests/test_migrations.py -q -o addopts=''
→ 19 passed, exit 0
```

新回归 `test_title_snapshot_backfill_handles_confirmed_revisions` 走合法确认路径造旧库，断言回填、来源、触发器恢复后仍 `IMMUTABLE_REVISION`、`foreign_key_check` 空、`integrity_check=ok`；`test_adjust_hooks_execute_every_declared_statement` 改为"每条声明语句必须被执行、允许追加辅助语句"。

## 5. observation

1. **并发 retry 的第二种合法时序**：r1 单次运行观察到 `[200,409]`；r2 首次运行（未放宽断言）观察到 `[200,200]` 并报 fail，放宽后 3 次运行得到 2×`[200,409]` + 1×`[200,200]`，全部 exit 0。`[200,200]` 是路由文档化的幂等路径（第二条请求仍看到 `queued`，注册表 `is_tracking` 直接返回当前视图）；两者都满足"只执行一次"（attempt +1、上游调用 +1、终态 succeeded）。**这是 r1 报告表述需要修正的一处（非产品回归）**：判据应写成"全部 ∈ {200,409} 且恰好一次执行"，而不是"恰好一个 200"。
2. **触发器"逐字一致"的口径**：SQLite 存储时剥掉 `IF NOT EXISTS` 与缩进，因此"逐字"只能在 token 级（空白归一）成立；r2 模块常量的 token 序列与 0003 声明完全一致，恢复后语义可验（三种冻结触发器均按原样生效）。
3. **候选在复验期间移动**：业务段 19:35:56 改写 `teaching.py`（0006/0007）并新增业务文件；r2 的 G0 结论只对冻结字节成立。补充信息（**非冻结候选**）：19:36 再跑 `p12` 仍 pass，且旧库能一路迁到 0007——r2 的 0005 修复在当前工作区仍在位。
4. `test_adjust_hooks_execute_every_declared_statement` 的判据由"钩子输出 == 声明集合"放宽为"每条声明都被执行"；这是 CTRL 说明的正确不变量，但"钩子不得**多出**副作用语句"这一面不再由该测试覆盖，改由 `p16` 的 DROP/CREATE 结构与语义检查兜底。
5. r1 报告 §15 的 6 条 observation 中，与本批相关的第 2 条（`model_runtime.__all__` 未导出新函数）在 r2 仍未变；其余未受本次 3 文件改动影响。

## 6. not_run

- 真实大模型 / 真实上游、真实 Word/WPS 与人工视觉、Qdrant/Ollama、正式 `.local-data` 迁移（正式库未读写）。
- 全量 `test:api` / `npm run check` / build / Playwright e2e（按边界不跑；本节只跑了 CTRL 改动的两个测试文件作为补充）。
- 真实浏览器视觉、F20 五步链、T60 成绩导入等业务段内容（且业务段已在复验后开始写入）。
- 多进程/多 worker 下的 retry/租约竞态。
- r2 变更的**跨文件**影响面：本次窄复验只覆盖 3 个改动文件的 G0 语义与两项回归重跑；未复核 r2 是否影响题库/原卷其它路径（改动仅限迁移文件与两个测试文件，`teaching.py` 的其它部分 diff 未逐行审查——见"最不确定"）。

## 7. 最不确定的一处

**r2 的 `teaching.py` 是否只动了我复验到的那一处。** 我按文件散列与行为验证（`p11/p12/p16` + 新回归测试）确认"0005 修复成立、声明散列不变、触发器/回滚/幂等正确"，但**没有逐行 diff r2 的 `teaching.py` 与 r1 版本**：r1 源码字节未保留，我搜索过仓库、`H:\备份xuexi` 与 `__pycache__`（`teaching.cpython-312.pyc` 已按移动后源码重生成；`teaching.cpython-314.pyc` 是 9 月 30 日的 G0 前版本，且无 3.14 解释器可解），没有任何 r1 副本可供比对。因此若该文件内还有非 0005 的静默改动，本次窄复验不会发现；现有缓解证据是 0005 三条声明文本逐字一致 + 散列登记不报漂移 + `test_migrations.py`/`test_b2_migrations.py` 19 passed（含 0001–0004 的逐库 migrate 与漂移检测）。
