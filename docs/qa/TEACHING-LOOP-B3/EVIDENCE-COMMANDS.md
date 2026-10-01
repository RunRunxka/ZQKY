# TEACHING-LOOP B3 证据与命令（CTRL 维护）

隔离口径：所有 Python 探针先设 `ZQKY_DATA_DIR` 到系统临时目录再导入 `app.main`；
正式 `.local-data` 只在"只读副本升级演练"中以只读连接 + backup API 复制后操作。测试端口 8001/5174 约定，
未启动真实服务（本文件记录的命令均为进程内/离线执行）。

## G0（前置修复）

| 命令 | 结果 |
| --- | --- |
| `uv run pytest tests/test_b3_g0_public.py -q` | 6 passed（publish 收敛/域错误码/取消优先/失权零写/指纹守卫/知识点引用） |
| `uv run pytest tests/test_rebuild_migration.py -q` | 5 passed（重建保数据与 FK、违规回滚、对账回滚、失败可重跑、散列覆盖计划） |
| `uv run pytest tests/test_migrations.py tests/test_b2_migrations.py -q` | 全通过（含 RV11 回填回归与「声明语句全部执行」不变量） |
| `uv run pytest tests -q`（全量） | **1365 passed, 1 failed = R-19**（`test_rag_sessions.py::test_ttl_memory_capacity_and_restart_are_explicit` 冷启动间歇；整文件重跑 14/14 通过，按台账定性） |
| 独立验收 V00-G0 | r1 `V00-G0-REPORT-01.md`（RV11 fail，其余 pass）→ 修复 → r2 `V00-G0-REPORT-02.md` **全项 pass**（106/106、差异恰 3 文件、p12 由 fail 转 pass） |

## 业务段（CTRL 侧）

| 命令 | 结果 |
| --- | --- |
| `uv run python ../../_work/b3/score_migration_probe.py` | 全新库 0001–0007 应用、成绩四表与触发器在位、封存闸门拒缺矩阵、矩阵/修订不可变、active 拒 draft、跨施测拒（复合 FK）；B2 旧库（含已确认卷/施测/参测数据）升级后数据逐行保留、FK 与触发器恢复、`foreign_key_check` 空、`integrity_check=ok`；`foreign_keys` 恢复为 1 |
| `uv run pytest tests/test_b3_score_migrations.py tests/test_b2_migrations.py tests/test_migrations.py tests/test_rebuild_migration.py tests/test_b3_g0_public.py -q` | 35 passed（含受控重建对账失败 → 回滚、不登记、可重跑） |
| 正式库只读副本升级演练 | 备份 API 复制 `.local-data/teaching/teaching.sqlite3` → 临时库应用 0006/0007：行数不变、复合外键恢复、`integrity_check=ok`、`foreign_key_check` 空；副本位于系统临时目录 |
| `read_score_sheet` 冒烟 | 公式视图 + 缓存视图双读、物理坐标保留、空单元格 `is_blank`、公式单元格 `formula='=B2+1'`（缓存缺失为空） |
| `uv run python -c "import app.api.v1.scores"`（装配前） | 报缺失属预期；`create_app()` 在 scores 模块缺失时降级为"成绩服务/路由未注册"警告，不影响其他模块 |

## 业务段实现者（结果卡要点）

| 任务 | 关键结果 |
| --- | --- |
| T60 成绩后端（12 个新文件，未改既有文件） | `uv run pytest tests/test_scores_*.py -q` → 33 passed, 1 skipped（skip 为当时不可行的 200×100 规模基线）；导入/确认/修正/规模四套（14+13+5+1 例）；样例矩阵 A/D 有总分、B/C `totalUnits=null`；三版本 409、承认 422 定位、重放幂等、并发双确认/双修正只前进一批、DB 触发器兜底不可变 |
| F20-I `/assessments` 工作区（新建 16 文件 + e2e） | `npm run typecheck` 0；eslint 0 警告；Vitest 3 文件 46 例全绿；`npm run build` 0；`npx playwright test tests/e2e/assessments.spec.ts` 3 passed（真隔离 FastAPI + 真浏览器；0/blank/absent 区分、矩阵总分规则、409 保留编辑、422 定位原表第 2 行 · 列 C） |
| F10-QB 题库前端增量 | `npm run typecheck` 0；eslint 0 警告；Vitest 15 文件 159 例全绿（新增 70 例：筛选/关联替换/旧标签分区/六态重试窗口/AI 校对链/`200+failures` 未确认） |

## CTRL 集成修复（业务段，均有测试或实跑证据）

| 缺陷（由实现者实测报告） | 修复 | 证据 |
| --- | --- | --- |
| `tabular.read_score_sheet` 在 read-only 工作表上逐格 `.cell()` → O(行²×列)，200×100 不可收敛（F20-I 实测 50×100=200s；T60 实测 51×102=211s，外推 200×100 > 40min） | 改 `iter_rows` 一次性物化两本书（新增 `_grid_from_sheet`/`_materialize_cell_rows`），并补 CSV 支持（ZIP 魔数分派；物理行号=文件行号；无公式视图） | 200×102 实测 **0.13s**；`ZQKY_RUN_SCALE_BASELINE=1 uv run pytest tests/test_scores_scale.py -q` → `test_scale_baseline_two_hundred_participants` **2.13s** 通过；`tests/test_tabular.py` 新增 3 例（物理网格/双视图、200×102 线性守卫、CSV 与超限码）10 passed |
| `ScoreImportPatchRequest` 未在冻结契约（T60 暂放 `services/scores/dto.py`） | 并入 `app/contracts/scores.py`，删除 dto.py 并改两处导入（`api/v1/scores.py`、`services/scores/service.py`），包 `__init__` 同步去掉 dto 导入 | `uv run pytest tests/test_scores_*.py -q` 重跑通过；全量 `tests` 收集恢复 |
| `AssessmentView` 未暴露 `activeScoreRevisionId`（F20-I 只能按最高已确认版本"推断"） | 后端 `AssessmentRecord`/`_SELECT_ASSESSMENT`/契约视图 + TS 镜像补字段；`HistoryPanel` 改为权威字段优先、缺失时回退推断并在文案说明来源 | `tests` 相关全绿；assessments 单测 46 例通过 |
| 导航新增 `assessments` 后 `navigation.test.ts` 硬编码清单失败 | 同步测试期望值 | 13 passed |
| F20-I e2e 规模用例原为 200×10（100 叶不可行） | 阅读器修复后把 spec 规模用例提升为 **200 人次 × 100 叶** | 见下方终验记录 |

## 终验（CTRL 统一，2026-10-01）

| 命令 | 结果 |
| --- | --- |
| `uv run pytest tests -q`（全量后端） | 1405 用例收集；**第一轮全绿（exit 0）**；第二/三轮仅 R-19 失败（台账既有冷启动间歇：整文件 14/14、单跑 3/3 失败、机制为 jieba 首次加载 ≈350ms > TTL 50ms，非本批引入） |
| `ZQKY_RUN_SCALE_BASELINE=1 uv run pytest tests/test_scores_scale.py -q --durations=5` | `test_scale_baseline_two_hundred_participants` **2.13s 通过**（修复前外推 >40 分钟） |
| `uv run pytest tests/test_tabular.py -q` | **10 passed**（新增 3 例：物理网格与双视图、200×102 线性守卫、CSV 物理行与 TABLE_TOO_LARGE） |
| `NODE_OPTIONS=--no-experimental-webstorage npm run check` | **exit 0**：typecheck 0；lint 0 警告；unit **97 文件 / 927 例全绿**；build 成功（`npm run test:unit` 不带该变量时会因 Node 26 jsdom localStorage 出现 152 例假失败——文档既有口径） |
| `npx playwright test`（全量 e2e，9.0m） | **149 passed / 1 failed**；唯一失败为台账 **R-14**（`books-commit-safety.spec.ts:238` 双标签页并发写不同书，隔离 `--repeat-each=3` 定性见下） |
| `npx playwright test tests/e2e/assessments.spec.ts`（新 spec，含规模） | **3 passed（23.7s）**：0/blank/absent 区分、409 保留编辑、422 定位「原表第 2 行 · 列 C」；**200 人次 × 100 叶真实链**——上传解析 3.4s、确认 5.3s、矩阵首屏 50 行 **1105ms**、翻页 **1098ms**、`document.scrollWidth = innerWidth = 1440` |

### 独立验收 V00-B3（只读，报告 `V00-REPORT-01.md`）

- 结论 **可交付、无阻塞 fail**：163/163 指纹一致（`p31`，并核对文档-only 移动）；
  A1 正常链（70/0）、A2 失败路径（63/0）、A3 不可变+闸门+**变异实验**（20/0）、A4 修正（65/0）、
  A5 规模/CSV/超限（36/0，读取 200×100=0.128s、全链上传 1.02s/确认 0.93s）、
  B6/B7 迁移（28/0，含 0001–0005 散列不漂移与"按修订自身快照"闸门）、C8 契约镜像（493/0）、
  C9 e2e 3/3（其环境实测首屏 599ms/翻页 537ms、`scrollWidth=innerWidth=1440`）、
  C10 边界反证（19/0：CSV 可用、预览明细无 API 字段、无出勤校正端点、F10-QB 全 stub）、
  D11 G0 无回归（p11/p16 为**过期探针期望**，用 B3 口径独立复算 `p29` 17/0 判非回归）。
- 其观察项（非 fail）：base 冲突不带 `currentRevision`（与 docs 注记范围一致）；矩阵完整性由 DB 闸门兜底
  （服务层变异实验证实，生产路径不可达）；预览明细在 DB `summary_json` 内部持久化但不出 API；
  上传时 missing 含未匹配行叶；契约 5 条已登记偏差；e2e 首轮 libuv 退出噪声；document 级无溢出 vs 表内滚动。

### V00 后处置（r2 窄改，2026-10-01）

- 采纳 C8 的唯一镜像差项：`ScoreImportPatchRequest` 并入 `apps/web/src/contracts/scores.ts`，
  `services/assessments-api.ts` 改为引用契约类型并再导出（删除第二份本地形状，文件头注明 r2 已并入）。
- 定向验证：`npm run typecheck` 0；`npx eslint` 两文件 0 警告；assessments 单测 46/46 通过。
- 重新冻结：`FROZEN-B3-r1.json`（163）→ **r2（163，r1→r2 差异恰 2 文件）** → 定版 `FROZEN-B3.json`；
  请求 V00 窄复验（`V00-REPORT-02.md`）。

### 冻结时序（流程教训，B4 起沿用）

- **先冻结产品、再写文档**：本批两次冻结记录被"冻结后 10 秒写了 `EVIDENCE-COMMANDS.md`/`REPORT.md`"判为
  **清单登记过期**（V00 复算 161/163，差异恰为这两个文档；产品逐字节未动）。处置：按 V00 建议重算两文档散列
  并重新冻结 —— `FROZEN-B3-r2.json`（163）→ `FROZEN-B3-r3.json`（163）→ **`FROZEN-B3-r4.json` = 定版
  `FROZEN-B3.json`（163，r3→r4 差异仍恰为这两个文档：把 r3 结论写回文档后才做的最终冻结）**，
  复算 **163/163 自洽**（V00 `p36`/`p37` 独立复核）。
  B4 起把"最后一步 = 冻结"写进流程：冻结前不再改任何进入清单的文件。
  **本批逐次修订一律以冻结记录里的 `FROZEN-B3.json.revisionHistory` 为准**（正文不再硬编码"定版 = rN"——
  本批曾因"每次把结论写回文档 → 记录又落后一轮"连续多轮返工，改此口径后终止；产品与测试自 r2 起零字节变化，
  r2→定版差异恰为 3 个文档：本文件、`REPORT.md`、`docs/CURRENT_STATUS.md`）。

### 本批修复的集成缺陷（真因与证据）

1. **`read_score_sheet` 超线性**（F20-I 与 T60 各自实测报告）：改为 `iter_rows` 一次性物化两本书（`_grid_from_sheet` / `_materialize_cell_rows`），并补 CSV 支持（ZIP 魔数分派；物理行号=文件行号；无公式视图）。200×102 实测 0.13s。
2. **100 列矩阵把文档撑到 7607px**（新规模用例暴露）：单元格内 `.visually-hidden`（绝对定位、包含块在滚动容器之外）逃出 `overflow-x: auto` 裁剪。修法：`.score-matrix-wrap` 与 `.score-matrix` 建立包含块（`position: relative`）；修复后 `scrollWidth = innerWidth = 1440`，诊断链（table→html 每级宽度与 overflow）保留在 spec 的溢出断言里。
3. **契约三处缺口**：`ScoreImportPatchRequest` 并入 `app/contracts/scores.py`（删 `services/scores/dto.py`）；`AssessmentView.activeScoreRevisionId` 补进后端契约/仓储/TS 镜像，`HistoryPanel` 改为权威字段优先并保留旧后端回退；`QuestionDetail.knowledgeLinks`（`QuestionKnowledgeLinkView`）补进 `contracts/question-bank.ts`。
4. **导航单测清单**：`services/navigation.test.ts` 期望值随 `/assessments` 登记同步（此前全量 check 唯一失败项）。
