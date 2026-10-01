# V00 · TEACHING-LOOP B3 独立验收报告（01）

- 任务：B3 业务段（G0 无回归抽查 + T60 成绩后端 + F20-I 成绩工作区 + F10-QB + CTRL 集成）
- 候选：`docs/qa/TEACHING-LOOP-B3/FROZEN-B3.json`（**163 文件**，工作区磁盘字节 sha256；基线 commit `0f4b8cb190c2`，`revision=B3-final`）
- 判定者：独立验收（只读）。未改 `apps/**`、契约、迁移、测试、权威文档；新增仅本报告与 `V00-probes/**`；未提交 Git。
- 运行环境：Windows / `apps/api/.venv/Scripts/python.exe` 3.12.14；探针均先设 `ZQKY_DATA_DIR` 到临时目录，模型替身/不联网/不占端口（TestClient 进程内）；Playwright 使用 5174 既有构建 + spec 自起的临时端口真后端。
- 候选移动记录（CTRL 通知）：开工后有一次**仅文档**更新，旧版留存 `FROZEN-B3-before-docs.json`（162 文件）。独立复算：`+docs/qa/TEACHING-LOOP-B3/REPORT.md`、`~docs/CURRENT_STATUS.md`、无删除、`apps/**`/`tests/**` 零变化 → 与通知一致（p31）。

## 0. 结论一览

| 项 | 结论 | 关键证据 |
| --- | --- | --- |
| 指纹自核 163/163 + 差异清单 | **pass** | `p31_fingerprint_b3.py` exit 0；`p31_fingerprint_b3.json` |
| A1 正常链（上传→映射→PATCH→承认→确认→修订/矩阵） | **pass** | `p20_normal_chain.py` exit 0，70 checks / 0 failures |
| A2 失败路径（422 承认 / 三版本 409 / 越界 / 重放） | **pass** | `p21_failure_paths.py` exit 0，63 checks / 0 failures |
| A3 不可变 + 闸门 + 变异实验（≥1 处） | **pass**（含 1 条观察项） | `p22_immutability_gate.py` exit 0，20 checks / 0 failures |
| A4 修正（base=active、审计、并发双修正） | **pass** | `p23_corrections.py` exit 0，65 checks / 0 failures |
| A5 规模 200×100 / CSV / TABLE_TOO_LARGE | **pass** | `p24_scale_csv.py` exit 0，36 checks / 0 failures |
| B6 迁移 0006/0007（B2 旧库、散列不漂移） | **pass** | `p25_migrations.py` exit 0，28 checks / 0 failures |
| B7 闸门按该修订自己的快照 | **pass** | `p25_migrations.py`（同探针） |
| C8 契约镜像逐字段对比 | **pass**（附 5 条已登记镜像偏差） | `p26_contract_mirror.py` exit 0，493 checks / 0 failures |
| C9 e2e `assessments.spec.ts` 3/3 + 规模断言 + 非颜色证据 | **pass** | `p27_assessments_e2e.log` / `.rerun.log` exit 0；截图 3 张（已实际查看） |
| C10 边界反证（a–d） | **pass** | `p28_boundary_checks.py` exit 0，19 checks / 0 failures |
| D11 G0 无回归抽查 | **pass**（2 个 G0 探针 exit 1 系 stale 期望，已独立复算裁定） | `p01/p13/p04/p06/p12` exit 0；`p11/p16` 见 §D11；`p29_rv11_recheck.py` exit 0，17 checks / 0 failures |
| 附加：并发双确认 + 损坏读取 | **pass** | `p30_concurrency_corruption.py` exit 0，17 checks / 0 failures |

**阻塞性 fail：无。** 报告期内候选未移动（终验前复算仍 163/163；`p31`）。

---

## A. 成绩后端（T60）真实装配

装配口径：`ZQKY_DATA_DIR` 指临时目录 → `create_app()` 真 FastAPI + 真 `ScoreService` + TestClient；
班级/学生/施测/成绩全走真实 HTTP；已确认原卷由**自写 SQL** 种子（真表、真确认触发器，含知识点关联以满足 `ITEM_KNOWLEDGE_MISSING` 闸门）。不引用实现者测试夹具。

### A1 正常链 `p20_normal_chain.py`

命令（apps/api 下）：`.venv/Scripts/python.exe -X utf8 ../../docs/qa/TEACHING-LOOP-B3/V00-probes/p20_normal_chain.py` → **exit 0，70 checks / 0 failures**；证据 `p20_normal_chain.json`。

- 六人次 A/B/C/D/E/F × 三叶（Q1=200/Q2=300/Q3=500 单位）；XLSX 第 7 行为"学号 9999/姓名 冯"的未匹配行。
- 上传 201：state=reviewing、auto mapping 学号=A/姓名=B/Q1→C/Q2→D/Q3→E、resolvedRowCount=5、`SCORE_ROW_UNRESOLVED` 定位 row=7；上传时 missingCellCount=4（B 空白 1 + 未匹配行 3 叶，**观察项 §O-4**）。
- PATCH 修正：`{expectedRevision, rows:[{rowNo:7, participantId:F}]}` → revision=1/previewVersion=1/resolved=6/missing=1；再单元格校正第 7 行 C 列 1→1.5 → revision=2/previewVersion=2，行视图 text=1.5。
- 承认（本地推导 absent=[C]、missing={[B],1}，previewVersion 一致）→ 确认 200：confirmed、replayed=false、active=revisionId、施测 revision+1。
- 修订：1 条 v1 confirmed；participantSnapshot 6、itemSnapshot 3（Q1/Q2/Q3 满分 200/300/500）。
- 矩阵（含分页 2+2+2 全覆盖）：
  - A 全 recorded → totalUnits=900；D Q1=`recorded(0)`、totalUnits=800；
  - B 第 3 叶 missing → totalUnits=**null**；C 三叶全 absent → null；E 三叶全 exempt → null；F=650；
  - `missingCellCount=1`、`missingParticipantIds=[B]`、`absentClassIds=[班级]`，与承认范围一致（DB summary `acknowledged.missing.cellCount=1`、absences=[[C]]）。
- DB 落点：`student_item_scores`=18 行；四态 recorded=11 / missing=1 / absent=3 / exempt=3；D 的 Q1 `status=recorded, score_units=0`。

### A2 失败路径 `p21_failure_paths.py`

命令同上（文件名 p21）→ **exit 0，63 checks / 0 failures**；证据 `p21_failure_paths.json`。

- 422 `SCORE_ACKNOWLEDGEMENT_MISMATCH` 四类：missing `cellCount=2`（定位 field=cellCount）、missing 人次含 `nobody`（field=participantIds）、absences=[]（field=absences）、previewVersion 过期（field=previewVersion）；每次失败后 `score_revisions` 仍为 0（未写入）。
- 409 版本语义：
  - `expectedImportRevision` 过期 → `SCORE_IMPORT_REVISION_CONFLICT` + `details.currentRevision`（=当前 revision）；
  - 补录一人次推进施测后 `expectedAssessmentRevision` 过期 → `SCORE_ASSESSMENT_REVISION_CONFLICT` + `currentRevision=1`；
  - `baseScoreRevisionId` 不符（首版给 bogus / 确认时给过期 v1 / 上传显式给过期 v1）→ `SCORE_BASE_REVISION_CONFLICT`，`details.issues[].field=baseScoreRevisionId`（与 `docs/API.md` 的注记范围一致：`currentRevision` 标注在 import/assessment 两个冲突码上；见 §O-1）。
- 越界/非法（PATCH）：`999`（Q1 满分 2）→ 422 `SCORE_CELL_OVER_MAX`，issue `row=2, column=C`；`-1` → 422 `SCORE_CELL_INVALID`，issue `row=3, column=C`；失败后 revision 不递增。
- 重放：同 submissionId 同载荷 → 200 `replayed=true`、同 revisionId、`score_revisions` 仍 1、施测版本不变；换 submissionId 再确认 → 409 `SCORE_IMPORT_NOT_EDITABLE`。

### A3 不可变 + 闸门 + 变异 `p22_immutability_gate.py`

命令同上（文件名 p22）→ **exit 0，20 checks / 0 failures**；证据 `p22_immutability_gate.json`。

- 直连 sqlite 五种破坏写全部被拒且错误含 `SCORE_REVISION_IMMUTABLE`：UPDATE 已确认修订、DELETE 已确认修订、UPDATE/DELETE/INSERT 已确认修订矩阵行；失败后修订 version 仍 1、矩阵仍 9 行。
- 闸门：构造"3 人次×3 叶快照 + 8/9 矩阵单元"的草稿 → `UPDATE state='confirmed'` 被拒 `SCORE_MATRIX_INCOMPLETE`，草稿仍 draft。
- active 闸门：`UPDATE assessments SET active_score_revision_id='draft-complete'` → `SCORE_REVISION_NOT_CONFIRMED`。
- **变异 1（临时副本）**：复制临时库 → `DROP TRIGGER score_revision_confirm_gate` → 同一条不全确认 UPDATE **改为成功**（反证闸门就是拦截面）；原库闸门仍在、草稿仍 draft（变异不外溢）。
- **变异 2（服务层，观察项 §O-2）**：临时库 DROP 闸门 + 把仓储 `insert_matrix_in` 少写一格 → 确认仍 200 并落 5/6 行：**服务层不独立复核矩阵完整性**，完整性由 DB 闸门兜底；生产路径均由 `build_preview`（冻结快照×叶）生成完整矩阵，残余风险 = 绕开该路径的手工写入 + 闸门缺失。

### A4 修正 `p23_corrections.py`

命令同上（文件名 p23）→ **exit 0，65 checks / 0 failures**；证据 `p23_corrections.json`。

- base 校验：不存在 → 404 `SCORE_REVISION_NOT_FOUND`；NULL 掉 active 后修正 → 409 `SCORE_NO_BASE_REVISION`；过期 base → 409 `SCORE_BASE_REVISION_CONFLICT`。
- 修正 B 的 Q3 missing→recorded(3)：v2、base=v1、active=v2；v2 矩阵 4 人次、missing=0、B.totalUnits=800；审计 1 条：`old_status=missing / old_score_units=NULL / new_status=recorded / new_score_units=300 / reason=教师复核后更正 / seq=1 / (participant,item)` 与请求一致。
- 不可变：v1 仍 missing、totalUnits=null、矩阵未被改写。
- 请求校验（不新增版本）：重复条目 / 未变化值 → 422 `SCORE_CORRECTION_INVALID`；未知人次 → `SCORE_PARTICIPANT_UNKNOWN`；未知小题 → `SCORE_ITEM_UNKNOWN`；超满分 → `SCORE_CELL_OVER_MAX`；recorded 缺 scoreText、非 recorded 带 scoreText → 422 `INVALID_REQUEST`。
- 修正"当时的快照"：v1 后补录 G，再修正 → v3 快照 5 人次（含 G），G 三叶 missing/totalUnits=null；v2（4 人次）历史不受影响。
- 重放：同 submissionId **同载荷** → replayed=true 同修订；同 submissionId 不同载荷 → 409 `SUBMISSION_CONFLICT`（幂等键不允许换内容）。
- 并发双修正：`[(200, rev), (409, SCORE_ASSESSMENT_REVISION_CONFLICT)]` → 恰好一个新版本（共 4）、active=胜者、胜者审计 1 条、胜者写入值 ∈ {100,50}。

### A5 规模 / CSV / 超限 `p24_scale_csv.py`

命令同上（文件名 p24）→ **exit 0，36 checks / 0 failures**；证据 `p24_scale_csv.json`。

- `read_score_sheet` 自造 200 行 × 100 叶 XLSX（物理 201×102）：**0.128s**、max_row=201、max_column=102、末行末列（201,102）文本未被截断、表头完整。
- 真装配 200 人次 × 100 叶全链：上传解析 **1.023s**（201、resolved=200、missing=0）、确认 **0.932s**、矩阵首屏 **0.034s**；四页 50 行无重复覆盖全部 200 人次；每页 100 个 items；全 recorded 时 totalUnits 非空。数秒级要求满足（未出现分钟级/不收敛）。
- CSV 全链：上传 201、workSheet=`CSV`、物理行号=文件行号（2/3/4）、映射 3 叶；确认 200 后矩阵 A=900、B 的 Q3=missing、C 全 absent、missingCellCount=1。
- 超限：直读 XLSX 2002 行 / 601 列、CSV 2002 行 / 601 列全部 `TABLE_TOO_LARGE`；上传 2002 行 CSV → 422 `TABLE_TOO_LARGE`（"CSV 行数 2002 超过上限 2000；请拆分后重试。"）且不落批次。

---

## B. 迁移（0006 / 0007）

### B6 B2 旧库升级 `p25_migrations.py`

命令（apps/api 下）：`.venv/Scripts/python.exe -X utf8 ../../docs/qa/TEACHING-LOOP-B3/V00-probes/p25_migrations.py` → **exit 0，28 checks / 0 failures**；证据 `p25_migrations.json`。

- 自建 B2 旧库：monkeypatch 迁移前缀只应用 0001–0005，再种子已确认卷（draft→UPDATE 触发器路径）+ 一条草稿修订 + 班级/学生/归属 + 施测 + 2 参测人次（present/absent）；B2 期 `active_score_revision_id` 非空被 CHECK 拒绝。
- 应用 0006/0007：`applied=["0006_teaching_score_tables","0007_teaching_assessment_active_score_fk"]`；**全部既有表逐行保留**（before/after 全量 ORDER 化行转储相等）；`foreign_key_check=[]`、`integrity_check=["ok"]`、`PRAGMA foreign_keys=1`。
- 结构：成绩四表 + `score_revision_corrections` 就位且为空；9 个触发器（`score_revision_confirm_gate`、3×score_revisions/item_scores 不可变、`assessment_active_score_confirmed`、`assessment_confirmed_paper_insert`、`assessment_paper_fixed` 等）在位；assessments 复合外键 `(active_score_revision_id,id)→score_revisions(id,assessment_id)` 恢复；分期 CHECK 已移除。
- 散列：0001–0005 的登记散列前后逐字不变；与 `tests/test_b2_migrations.py::FROZEN_DIGESTS`（0001/0002）一致；并**只读**正式库 `.local-data/teaching/teaching.sqlite3`（`file:?mode=ro`）比对 0001–0005 散列一致（正式库登记含 0006/0007，`94dbbae1…`/`d550b603…`）。
- 升级库可用性：在升级后的库上真装配，读取施测 200、上传 XLSX 201、确认链 200（甲 recorded、乙 absent）。

### B7 闸门按修订自己的快照（同探针）

- 确认 v1（2 人次、missing=1）后经真实 API 补录 G；v1 仍可读、total=2、missing 口径与确认时逐字一致，未被判不全。
- DB 直连构造：`snap-own`（快照不含 G + 对应矩阵）→ 封存**放行**；`snap-with-g`（快照含 G + 少 G 矩阵）→ 封存被拒 `SCORE_MATRIX_INCOMPLETE`。证明闸门按修订自己的快照，不按当前参测集合。

---

## C. 契约镜像与前端

### C8 `p26_contract_mirror.py`（TS 侧用仓库 typescript 5.7.3 解析，非正则）

命令（apps/api 下）→ **exit 0，493 checks / 0 failures**；证据 `p26_contract_mirror.json`；辅助 `_mirror_ts_extract.cjs`。

- `scores.py` ↔ `scores.ts`：26 个 Python 模型 vs 25 个 TS 接口，差集**恰好** `ScoreImportPatchRequest`（web 侧在 `services/assessments-api.ts:294` 本地实现，文件头 11–15 行已披露"契约缺口…已在 F20-I 结果卡登记"）；用 TS 解析该本地接口与后端模型逐字段对比——字段名/类型一致。
- 逐字段（字段名集合、必填/可选、`| None`↔`| null`、类型类别、字面量枚举）对 25 个模型全部核对；`ScoreStatus` 跨契约枚举集合一致；`AssessmentView.activeScoreRevisionId`（可选、可空 string）与 `QuestionKnowledgeLinkView`（5 字段，role 枚举 primary|secondary）两侧一致（见 `p26_contract_mirror.json` observations 的逐字段转储）。
- 已登记镜像偏差 5 条（均记录在探针 observations，非 fail）：`ScoreColumnMapping.itemColumns` 后端可省略（default []）而 TS 必填；`AssessmentView.{classIds,participantCount,state}` 后端有默认而 TS 必填（方向均为 TS 更严格，响应始终含该字段）；`assessments-api.ScoreImportPatchRequest.rows` 本地 TS 允许 null 而后端 list 不接受 null（调用方 `hooks.ts:389` 始终构造数组，未发送 null）。**无任何"TS 可选 ↔ 后端必填"方向的反向缺口。**

### C9 e2e 与呈现

- 命令（仓库根）：`npx playwright test tests/e2e/assessments.spec.ts --reporter=list --output=docs/qa/TEACHING-LOOP-B3/V00-probes/_pw-assessments-out` → **exit 0，3 passed（14.4s）**；日志 `p27_assessments_e2e.log`（首轮）与 `p27_assessments_e2e.rerun.log`（复跑，EXIT=0）。
- spec 规模用例确证"200 人次 × 100 叶"：`prepareScaleScene(origin, scalePaper, 200, 100)`、`expect(leaves.length).toBe(leafCount)`、页面断言 `共 200 人次`、50 行/页、`第 1 页`→`第 2 页`；日志 `[scale] … 人次=200 叶=100：矩阵首屏 599ms；翻页 537ms`（首轮 556/542ms），annotation 记录。
- `scrollWidth <= innerWidth`：spec 第 831 行断言 `document.documentElement.scrollWidth <= innerWidth`，并打印逐级溢出诊断；实测 `scrollWidth=innerWidth=1440`。诊断显示 `.score-matrix`（7605px）位于 `overflow-x:auto` 的 `.score-matrix-wrap` 内滚动，document 级无横向溢出（首轮与复跑同）。
- 实际查看页面（截图，均在 `_pw-assessments-out/**`）：历史矩阵页可见文字化四态——`0 分`、`2.5 分`、`空白`、`缺考`、总分列`不展示总分（共 10 分；该人次含空白/缺考/免考）`；规模页 `已确认（不可变）· 人次 200 · 叶 100`、`第 2 页 · 共 200 人次 · 每页 50`；390px 页无横向溢出。
- 非颜色证据（代码）：`labels.ts` 定义 `STATUS_LABELS/STATUS_SHORT/STATUS_GLYPHS`（●/▢/✕/◇）与 `SCORE_STATUS_LEGEND`（4 条文字说明）；`ScoreStatusBadge.tsx` 渲染 **字形 + 文案 + `visually-hidden` 全称 + title**；`cellValueText` 对非 recorded 返回状态短名、绝不给 0；`HistoryPanel.tsx:251/304` 在矩阵页放图例并以 Badge 渲染每格；`ScorePanel.tsx:514` 亦放图例；`ScoreImportReview.tsx:389` 原表预览同样用 Badge。

### C10 边界反证 `p28_boundary_checks.py`

命令（apps/api 下）→ **exit 0，19 checks / 0 failures**；证据 `p28_boundary_checks.json`。

- (a) CSV：直读单表 `name=CSV`、物理 3×5、无公式视图、空白 `is_blank=True`；全链见 §A5。
- (b) 服务端**无** missing/absent 明细字段：`ScoreImportView` 无 `absentByClass/missingParticipantIds`（只有 `missingCellCount` 汇总），`ScoreImportRowView` 无行级 status/attendance；前端在 `ScoreImportReview.tsx` 用 `loadAllImportRows`（最多 20 页）+ `groupAbsencesByClass`/`deriveMissingAcknowledgement` 本地推导，服务端 422 `SCORE_ACKNOWLEDGEMENT_MISMATCH` 兜底；与 CTRL 边界声明一致。（服务端在 DB 内部持久化预览快照用于 422 比对与审计，但**不通过任何 API 字段暴露**——§O-3。）
- (c) 无"出勤校正"独立端点：assessments/scores 路由表 15 条（见探针 observation）无 attendance/correction 路径；`AssessmentUpdateRequest` 仅 title/type/heldOn；人次维护仅 `POST /assessments/{id}/participants`（新增/补录）；冲突文案指向"修正原表后重建预览"、UI 入口是"上传并创建待校对批次"（校正 = 重传文件）。
- (d) F10-QB 用例全部为替身：FROZEN 差异中的 9 个 QB 测试 + `question-bank-api.test.ts` 中，7 个交互/API 文件一律 `vi.stubGlobal('fetch', fetchMock)`，3 个为纯函数零 mock；全部文件无真后端/真进程/真浏览器（无 spawn、无 127.0.0.1、无 TestClient、无 uv run）。

---

## D. G0 无回归抽查（重跑上一轮探针）

| 探针 | 覆盖 | exit | 结果 |
| --- | --- | --- | --- |
| `p01_rv01_retry.py` | RV01 真装配 retry：失败→retry→终态、并发/重复只执行一次、重启后 queued 不自动重放 | 0 | 与 G0 r2 同形（终态 succeeded、attempt+1、provider +1） |
| `p13_publish_failure.py` | publish 收敛三域（teaching/question/knowledge） | 0 | AppError→failed+保留码；内部异常→failed+固定文案；正常 succeeded；取消优先 cancelled；失权零写入 |
| `p04_rv04_drift.py` | 冻结模型指纹漂移四条路径 + 旧行缺指纹 + 凭证边界 | 0 | 漂移 `MODEL_CONFIG_DRIFT`、零调用；缺指纹 `MODEL_FINGERPRINT_MISSING`；无凭证泄漏 |
| `p06_rv06_archived_confirm.py` | 知识点归档后确认被拒（原卷+题库） | 0 | 409 `KNOWLEDGE_ARCHIVED`、零新增修订/题目；历史关联仍可读；控制组可确认 |
| `p12_rv11_startup_repro.py` | RV11 在 B2 旧库上的启动迁移 | 0 | verdict=pass |
| `p11_rv11_titles_migration.py` | RV11 A/B/C | **1** | A/B 行为全过；B1/C 唯一不符是探针把 applied/pending/retry 硬编码为 `["0005…"]`（B3 已增 0006/0007）→ s. §D11 |
| `p16_rv11_r2_migration.py` | RV11 r2 三形状 + F2 | **1** | 三形状除 `applied==["0005…"]` 外全部子不变量为真（triggerVerbatim / 子行不变 / 0005 散列 / FK / integrity / 冻结语义 / 二次应用空）；F2 仅 `applied==[]` 过期（实际正确应用 0006/0007）；JSON 证据 `p16_rv11_r2_migration.json` |
| `p29_rv11_recheck.py` | 用同一旧库构造器按 B3 口径复算 B1/C | 0 | 17 checks / 0：pending/applied/retry=`[0005,0006,0007]`、两列/回填/来源/散列/幂等/触发器/FK/integrity、失败回滚 + 可重跑全部成立 |

**D11 裁定**：p11/p16 的 exit 1 是**探针期（G0）硬编码迁移清单**在 B3 迁移集下过期，不是产品回归。裁定依据是逐项读数（`p16_rv11_r2_migration.json` 全部子不变量为真）+ 用 B3 口径独立复算（`p29`，17/17）；未修改历史探针/报告来"关闭"它们。

---

## 阻塞性 fail

无。

## 观察项（非 fail）

- **O-1 三版本 409 的 `currentRevision`**：`expectedImportRevision` / `expectedAssessmentRevision` 均带 `details.currentRevision`；`baseScoreRevisionId` 冲突返回 `details.issues[].field=baseScoreRevisionId`（无 `currentRevision`）。这与 `docs/API.md` 的明确注记一致（`currentRevision` 标注在上述两个冲突码上）；V00 任务书"三版本…带 currentRevision"的括注按文档口径理解为前两者。若要求 base 冲突也带 currentRevision，属文档/口径变更（需 CTRL 决定），当前按文档判 pass。
- **O-2 矩阵完整性只有 DB 闸门兜底**：变异实验证明服务层不独立复核矩阵完整性（DROP 闸门 + 人为少写一格时确认仍 200）。生产路径（确认/修正）都从冻结快照生成完整矩阵，正常不可达；残余风险仅限"绕过服务的手工写入 + 闸门缺失"，闸门语义与触发器恢复已由 B6/B7 验证。
- **O-3 预览明细的服务端落点**：missing/absent 明细不作为 API 字段暴露（边界声明成立），但服务端确实把预览快照持久化进 `score_imports.summary_json` 用于 422 权威比对与审计。若文档"没有服务端字段"指"DB 中也不存"，则表述需加"不由 API 暴露"的限定；按接口/功能口径与 CTRL 声明一致。
- **O-4 上传时 missingCellCount 含未匹配行的叶**：A1 上传时 missing=4（B 空白 1 + 未匹配行 3），PATCH 消歧后=1，与"全矩阵显式 missing、不静默补 0"一致；前端承认推导基于原表行读法，确认必须与**当前**预览一致（422 兜底），无功能问题。
- **O-5 契约镜像已登记偏差 5 条**（C8）：TS 更严格 4 条 + 本地 rows 可空 1 条；均不影响响应解析与现有调用。
- **O-6 e2e 环境噪声**：首轮 e2e 结束后 node 打印 `Assertion failed: !(handle->flags & UV_HANDLE_CLOSING)`（libuv 退出期噪声），测试 3 passed；复跑同命令 EXIT=0 未复现，不影响结论。
- **O-7 “无横向溢出”的口径**：document 级 `scrollWidth=innerWidth=1440`；矩阵表本身 7605px，在 `.score-matrix-wrap{overflow-x:auto}` 内滚动（设计如此）。spec 的 offenders 列表会列出表内超宽元素，但断言只针对 document 级，与 CTRL 描述一致。
- **O-8 G0 探针 p11/p16 的 stale 期望**：见 §D11；建议后续批次对探针的迁移清单断言改为"包含 0005"而非"等于 0005"（探针属历史证据，未由本轮修改）。

## 未执行项（not_run）

- 后端全量 `uv run pytest tests -q`（1405 例）与 R-19 冷启动定性：**未重跑**（CTRL 终验数据供参考；本轮只跑定向探针与 5 个 G0 回归探针）。
- `NODE_OPTIONS=--no-experimental-webstorage npm run check`（97 文件/927 例 + build）与全量 e2e（149/1 = R-14）：**未重跑**；本轮只跑 `tests/e2e/assessments.spec.ts`（3/3）。
- G0 其余 RV（RV02/RV03/RV05/RV07/RV08/RV09/RV10）：**未重跑**（任务只要求 RV01/发布收敛/漂移/归档/RV11 的无回归抽查）。
- 真实大模型/真实上游、Ollama/Qdrant、真实 Word/WPS 与人工视觉走查：未涉及（B3 无 DOCX 导出验收项；成绩呈现已用真浏览器截图核对）。
- 正式 `.local-data` 的迁移/备份演练：仅**只读**打开 `schema_migrations` 做散列比对，未复制、未迁移、未写入。
- 多进程/多 worker 竞态（并发均为进程内线程 + TestClient）、真机跨浏览器矩阵（仅 spec 指定的 msedge 1440×900 与 390px 用例）。
- 学情分析（T70）与备份/恢复功能：B3 无实现（TASK-CARD §7 边界），不适用。
- 200×100 的**浏览器**首屏/翻页上限只按 spec 的宽松上界（20s/10s）判定，未做性能基准（实测 0.5–0.6s）。

## 结论（一行）

**可交付**：163/163 指纹一致（含"文档-only"移动复算），A1–A5、B6–B7、C8–C10、D11 全部通过（无阻塞 fail；p11/p16 为 G0 探针 stale 期望，已用 B3 口径复算裁定非回归）；附条件为：候选需保持当前 163 文件字节不变（否则本报告失效）、§O-2/O-3 两条残余风险按记录交由后续批次文档化。
