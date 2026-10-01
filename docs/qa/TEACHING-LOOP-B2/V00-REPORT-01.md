# TEACHING-LOOP B2 · V00 独立验收报告 01

- 批次：**TEACHING-LOOP B2**（CTRL + T40 + T50 + F10-KP + T30-b）
- 验收者：独立验收 Agent（V00，只读产品代码；自建探针与证据）
- 候选：B2 工作树，起点 `main@0f4b8cb190c2265d819b90e5d6df4e3954ad1906`；冻结指纹
  `docs/qa/TEACHING-LOOP-B2/FROZEN-CANDIDATE.json`（revision r1，83 文件）
- 日期：2026-10-01；报告版本：v1.0（对应候选 r1）
- 探针目录：`docs/qa/TEACHING-LOOP-B2/V00-probes/`；证据：`docs/qa/TEACHING-LOOP-B2/V00-probes/evidence/`
- 边界遵守：未改 `apps/**`、`scripts/**`、现行文档、实现者测试、冻结记录；未提交/推送；未读写正式
  `.local-data` 与 `.env`；模型一律受控替身、不联网、未启动 Qdrant；未占用 8000/8001/5174。

## 0. 结论摘要

| 项 | 结论 | 一句话 |
| --- | --- | --- |
| 指纹对账 | **pass** | 83/83 文件 sha256 与冻结记录逐一一致（0 不一致、0 缺失），无 `postVerificationDocChanges` |
| V1 迁移与分期 | **pass** | 87/87：三路径升级、幂等、回滚、`foreign_key_check`、分期 CHECK、20 个触发器、B0/B1 散列未漂移 |
| V2 T40 导入与草稿 | **pass** | 59/59：自建 DOCX（合并表格/图片/OMML/未知对象）块序定位、图片字节、整表替换与 16 类错误定位 |
| V3 T40 确认与不可变 | **pass** | 44/44：闸门逐项拒绝→成功、重放、绕过服务直写 16 条全被拒、改确认卷建新修订且旧修订逐字节不变 |
| V4 T40 AI 建议与 reader | **pass** | 32/32：四类非法零建议、发布期 stale 零残留、apply/reject/stale、reader 只放已确认（含损坏库纵深） |
| V5 T50 关联与生成 | **pass** | 32/32：关联整表替换/清空/回 needs_review、生成链 11 类拒绝零残留、冻结快照、检索、改题复制/替换 |
| V6 T50 统一任务 | **pass** | 14/14：attempt/六态、model 名额=1 严格串行、取消（queued 立即/running 迟到不发布）、重启收敛、旧 checkpoint 重选 |
| V7 T30-b 施测 | **pass** | 33/33：真链路（名单→原卷确认→施测）、归属未覆盖定位→带依据且历史未改、人次/回滚/快照/幂等 |
| V8 F10-KP 页面 | **pass**（组件级） | 自建 9/9：教材依据不可用≠没有依据、六态/取消/重试/attempt 守卫/卸载停轮询；浏览器视觉引用 CTRL E2E r3 |
| V9 声明抽查 | **fail**（文档级） | 17/19：2 处 `docs/API.md` 事实与代码不一致（错误码名、`CLASS_ARCHIVED` 状态码）；产品行为无缺陷 |
| V10 变异实验 | **pass** | 11/11：3 处变异证明断言有牙齿；还原后 83 文件哈希复算一致、候选零污染 |

**V9 的 2 处 fail 均为文档事实错误（不含产品行为缺陷）**，最小复现见 §10.2/§10.3；不阻塞 V1–V8/V10 的通过结论。
除此之外未发现阻塞 fail，也未发现数据损坏、越权写入或半批发布。

---

## 1. 候选身份与写入停止核对（报告开头项）

### 1.1 逐文件 sha256 复算

命令（仓库根，Python 3.12）：

```
python -c "import json,hashlib,os; j=json.load(open('docs/qa/TEACHING-LOOP-B2/FROZEN-CANDIDATE.json',encoding='utf-8')); \
bad=[(r) for r,e in j['files'].items() if not os.path.exists(r) or hashlib.sha256(open(r,'rb').read()).hexdigest()!=e]; \
print('declared',j['fileCount'],'actual',len(j['files']),'mismatch',bad)"
```

- 退出码：0
- 输出：`declared fileCount 83 actual entries 83 / missing: 0 / mismatch: 0 / OK count 83 / postVerificationDocChanges None`
- **结论：83/83 一致、0 缺失、0 不一致**；冻结记录未声明 `postVerificationDocChanges`，无按记录口径的特殊处理。

复算结果另存：`H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\baseline-hashes.json`
（V10.D1 在全部变异实验之后再次复算，仍 83/83 一致，见 §11）。

### 1.2 候选构成摘要（按冻结清单分类）

| 类别 | 文件数 | 说明 |
| --- | --- | --- |
| `apps/api/app/**`（后端产品代码） | 24 | 迁移 2、契约 2、路由 2、服务（papers/assessments/question_bank）13、仓储 2、schema/main 等 |
| `apps/api/tests/**`（实现者测试） | 14 | 含 B2 新增 8 个 + 被兼容性调整的既有用例 |
| `apps/web/src/**`（前端产品代码） | 38 | 知识点页面/功能 22、题库六态兼容 4、契约 3、服务 3、导航/壳/测试等 |
| `docs/**`（现行文档） | 6 | API / ROUTES / PROJECT_GUIDE / CURRENT_STATUS / B2 任务卡 ×2 |
| `tests/e2e/**` | 1 | `knowledge-points.spec.ts` |
| 合计 | **83** | |

### 1.3 写入停止核对

- 实现者（T40/T50/T30-b/F10-KP）声明已停止写入；本报告的所有断言均针对 §1.1 复算一致的同一批 83 个文件，
  未观察到验证期间的任何候选文件变化（V10.D1 在验证末端二次复算仍 83/83）。
- 本验收对工作区的**唯一新增**是 `docs/qa/TEACHING-LOOP-B2/V00-probes/**` 与 `V00-REPORT-01.md`；
  V10.D2 用允许清单核查 `git status --porcelain` 的 82 条条目：除冻结清单内文件、
  `docs/qa/TEACHING-LOOP-B2/V00-*`、既有未跟踪 `docs/design/**` 与 Git 忽略的 `_work/**` 之外，
  **零越界改动**（`offenders=[]`）。
- CTRL 的 E2E 日志 `_work/b2/e2e-b2-r3.log` 只读引用：末尾 `147 passed (6.0m)`，其中知识
  `knowledge-points.spec.ts` 9 例全部 `ok`（含三视口无溢出、reduced-motion 压制）。

---

## 2. V1 迁移与分期（pass）

**命令**（`cd apps/api`）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\v1_migrations_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\v1_migrations_probe.json"
```

- **退出码：0**；`87/87 passed`（证据：`…/V00-probes/evidence/v1_migrations_probe.json`）
- 关键输出摘录：
  - 新库：`applied=['0001…','0002…','0003_teaching_paper_tables','0004_teaching_assessment_tables']`（题库同）；
    二次应用 `[]`；`foreign_key_check=0 rows`；`quick_check=ok`。
  - 旧库（**真实构造**：只执行前置迁移的声明语句并写入与真实现同源 `schema_migrations` 行）：
    B0 路径（只登记 0001）与 B1 路径（登记到倒数第二条）都只增量应用 B2 迁移，升级后表齐备、外键全空、再应用幂等。
  - 中途失败：追加一条故意失败的迁移 → 抛 `sqlite3.Error`、首条语句已建的表**不存在**、失败迁移**未登记**、既有 4 条登记未损。
  - 分期 CHECK：`source_practice_revision_id` 非空 → `CHECK constraint failed: source_practice_revision_id IS NULL`；
    `source_file_id` 空 → `NOT NULL constraint failed`；`active_score_revision_id` 非空 → CHECK 拒绝；
    草稿 `total_score_units=0` 允许（容差）。
  - 触发器 20 个全部核对：`paper_confirm` 四分支（`NO_SCORED_ITEMS` / `PAPER_TOTAL_MISMATCH` /
    `ITEM_KNOWLEDGE_MISSING` / `SCORED_ITEM_MUST_BE_LEAF`）+ 合法草稿可确认；`freeze_paper_items|item_knowledge|
    source_blocks|issues` 的 UPDATE/DELETE/INSERT 全被 `IMMUTABLE_REVISION` 拒绝（含"UPDATE 改块归属"）；
    `immutable_paper_revisions_update/delete`；`no_direct_sealed_paper_revisions`；`paper_cycle_update` → `ITEM_CYCLE`；
    自引用被拒；`assessment_confirmed_paper_insert` → `PAPER_NOT_CONFIRMED`；`assessment_paper_fixed` → `ASSESSMENT_PAPER_FIXED`。
  - B0/B1 散列：`0001_teaching_baseline=bf78fb3f…`、`question_bank 0001/0002/0003` 与 B0 独立验收记录逐字一致；
    **另用 git HEAD（B1 提交）源码做逐语句比对**：`_BASELINE_STATEMENTS`/`_BUSINESS_STATEMENTS`
    （teaching）与 `_BASELINE_STATEMENTS`/`_ENGINE_STATEMENTS`（question_bank）**两侧 digest 相同、语句逐字相同**
    （`len=6/6`、`13/13`、`17/17`、`13/13`）→ B0/B1 声明未被 B2 改写。
- 未使用 CTRL 的 `test_b2_migrations.py` 作为依据（仅阅读其契约意图）；探针自带 DOCX/SQL 夹具与断言。

## 3. V2 T40 导入与草稿（pass）

**命令**（`cd apps/api`）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\v2_papers_import_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\v2_papers_import_probe.json"
```

- **退出码：0**；`59/59 passed`（证据：`…/evidence/v2_papers_import_probe.json`）
- 自建样本 DOCX（`v00_support.build_sample_docx`，非实现者 helper 的复制）：前导共同材料 2 段 + 两级小题
  `16.`/`16(1)`/`16(2)` + 行内 OMML + 独立 OMML + 真实 PNG + 横向 `gridSpan` 与纵向 `vMerge` 合并表格 +
  独立计分题 `17.` + 空段落 + 纯未知对象段落 + 未知对象+题号 `18.`。
- 关键输出摘录：
  - 拆题 `{16,16(1),16(2),17,18}`；`16` 容器不计分、`16(1)=4`、`16(2)=6`、`17=5`、合计 1500 单位；
    `16(1)/16(2)` 的 `parentItemId` = `16`；`18` 未识别满分**不计分、不给假 0 分**。
  - 块顺序/定位与原件 body 一致：`['p1','p2','p3','p4','p5','p6','p6-1','p7','t8','p9','p10','p10-1','p13']`；
    类型序列含 `formula/image/table`；`t8.blockStart=8` 且 `tableColumns=3/tableRows=2`。
  - 图片：块引用 `blobs/b3a677…`，从受管资产根读出的字节与我生成的 PNG **完全相等**，尺寸 120×60；
  - OMML：子树逐节点（tag/属性/text/children）与原始 `m:oMath` **完全相同**且 `m:oMath` 标签原样（未做 LaTeX 往返）；
    可见文本 `x+1` 未丢；
  - 合并表格：`columnCount=3`，`得分表` 只出现一次且 `colSpan=2`，`题号` `rowSpan=2`，共 4 个起始格，首行 `isHeader`。
  - 未知对象问题两类都落库：`block_id=None`（纯对象段落，locator 定位）与 `block_id=…:p13`，均 `blocking`；
    `ITEM_SCORE_MISSING` 同判 blocking。
  - 草稿 PATCH：整表替换（删除 18）、知识点 `human` 写入、总分保持 1500、标题更新、`papers.revision` 0→1、
    被删题目的块归属被清空并记 `PAPER_BLOCK_ITEM_RESET`；复用已删除 `itemId` 建新题成功。
  - 错误路径 16 项全部 422/409 且带定位：`ITEM_QUESTION_NO_DUPLICATE(row=3,questionNo)`、`ITEM_CYCLE(parentItemId)`、
    `ITEM_PARENT_INVALID`、`SCORED_ITEM_MUST_BE_LEAF`、负分/三位小数（schema 拒绝）、`ITEM_SCORE_INVALID(maxScore)`、
    容器带分、`PAPER_REVISION_STALE(currentRevision)`、`KNOWLEDGE_REFERENCE_INVALID`（未知/跨学科/已归档）、
    `ITEM_ORDINAL_DUPLICATE`、`ITEM_ID_INVALID`、`PAPER_BLOCK_INVALID`、`PAPER_ISSUE_NOT_FOUND`；
    失败后题数与修订未被污染；阻断问题缺 `resolution` → 422 `PAPER_ISSUE_BLOCKING`，带 `resolution` 可解决。

## 4. V3 T40 确认与不可变（pass）

**命令**（`cd apps/api`）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\v3_papers_confirm_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\v3_papers_confirm_probe.json"
```

- **退出码：0**；`44/44 passed`（证据：`…/evidence/v3_papers_confirm_probe.json`）
- 关键输出摘录（每项失败路径都断言"仍为 draft 且 revision 未变"）：
  - 未归属块 → 422 `PAPER_BLOCK_UNASSIGNED`（`rows=[3]`）；缺知识点 → 422 `ITEM_KNOWLEDGE_MISSING`（`rows=[2]`）；
    无计分叶 → 422 `NO_SCORED_ITEMS`；总分不符（绕过服务直改草稿总分）→ 422 `PAPER_TOTAL_MISMATCH`；
    blocking 问题直改回 `open` → 422 `PAPER_ISSUE_BLOCKING`；过期 → 409 `PAPER_REVISION_STALE(currentRevision=7)`。
  - 闸门全过：确认成功（`state=confirmed`、`totalScoreUnits=1500`、`scoredLeafCount=3`）；同 `submissionId`
    重放 `replayed=True` 且结果一致；`currentState=confirmed`、`papers.revision` +1；同 `submissionId` 不同载荷
    → 409 `SUBMISSION_CONFLICT`；新 `submissionId` 重复确认 → 409 `PAPER_NOT_EDITABLE`。
  - **绕过服务直写**（独立 sqlite3 连接，16 条）：items 的 UPDATE 题号/分值、DELETE、INSERT；knowledge 的
    UPDATE/DELETE/INSERT；blocks 的 UPDATE 归属/DELETE/INSERT；issues 的 UPDATE/DELETE/INSERT；修订的
    UPDATE 总分/改回 draft、DELETE —— **全部被 `IMMUTABLE_REVISION` 拒绝**，随后旧修订快照 digest 不变（`6420b6c9…`）。
  - 旧施测真链路：`POST /assessments`（班级+学生+归属齐备）用旧修订成功创建；
    改已确认卷 → 自动新建 `version=2` draft 且复制 13 个块行，旧修订仍 `confirmed` 且 digest 不变；
    旧施测详情仍指 `paperRevisionId` = 旧修订。

## 5. V4 T40 AI 建议与 ConfirmedPaperReader（pass）

**命令**（`cd apps/api`；探针不经 TestClient，避免把 JobEngine 名额信号量绑到别的 loop）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\v4_papers_proposals_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\v4_papers_proposals_probe.json"
```

- **退出码：0**；`32/32 passed`（证据：`…/evidence/v4_papers_proposals_probe.json`）
- 关键输出摘录：
  - 非法 JSON / 截断(`length`) / JSON 非对象 / 未知知识点 / 未知题目 / 证据越界 / 无既有也无新候选
    → 任务 `failed` + `error_code=PAPER_PROPOSAL_INVALID` + **`ai_proposals` 零行**（逐例 `proposals=0->0`）。
  - 发布期冻结失败：用受控 `asyncio.Event` 卡住模型调用 → 教师改草稿 → 放行 → 任务**未 succeeded 且零建议**；
    另用**真实执行器 + 真实发布回调**直接跑一轮，捕获 `AppError PAPER_PROPOSAL_STALE(409)` 且零建议写入。
  - 合法建议：`pending`、新知识点候选、证据齐全、`stale=False`；**候选不建正式知识点**（`knowledge_points` 2→2）。
  - 应用：选择与建议不符 → 422（`field=knowledgePointId`）；选择非计分容器 → 422（`field=itemId`）；
    stale → 409；应用成功写入 `source=ai_confirmed / role=primary`；重复应用/reject 后应用 → 409。
  - 冻结输入含 `allowedItemIds`/`allowedKnowledgePointIds`/`sha256:` 指纹且**无凭证字样**。
  - reader：draft → 422 `ASSESSMENT_PAPER_INVALID`；不存在 → 404 `PAPER_NOT_FOUND`；确认后返回**真实**标题/学科/
    总分/计分叶（与库一致 1500/3）；**损坏库纵深**（移除确认触发器后造"已确认"零总分/无计分叶修订）→ 均 422。

## 6. V5 T50 关联与生成（pass）

**命令**（`cd apps/api`；经真 HTTP + 长驻 TestClient portal，后台任务才会跑完）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\v5_question_links_generation_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\v5_question_links_generation_probe.json"
```

- **退出码：0**；`32/32 passed`（证据：`…/evidence/v5_question_links_generation_probe.json`）
- 关键输出摘录：
  - 生成链 11 类拒绝，每例都核 `imports/drafts/provenance/questions/links` 增量为 0：
    `GENERATION_INVALID_JSON`、`GENERATION_OUTPUT_TRUNCATED`、`GENERATION_CANDIDATE_COUNT_MISMATCH`、
    `GENERATION_UNKNOWN_KNOWLEDGE`、`GENERATION_UNKNOWN_EVIDENCE`（虚构证据）、`GENERATION_FORBIDDEN_REFERENCE`
    （URL / 绝对路径 `/etc/passwd/data` / 盘符路径 `C:\data\paper.docx`）、`GENERATION_ASSET_INVALID`、
    `GENERATION_ASSET_NOT_REGISTERED`；材料含 URL 在建任务前 422 `GENERATION_MATERIAL_INVALID`（零上游调用）；
    学科不一致 422 `KNOWLEDGE_SUBJECT_MISMATCH`（零上游调用）。
  - 成功链：202 → succeeded + `candidateCount=1`；批次 `needs_review`、候选 `extractionMethod=ai`、
    草稿关联 `source=ai` 且带学科/名称快照；**候选未进正式表**（`questions`/`links` +0）；
    `question_import_provenance(source=ai, job_id, sha256: 指纹)` 无凭证。
  - 草稿关联：提供即整表替换（A→B）、两条（primary+secondary）、`[]` 清空；**关联变化强制回 `needs_review`**
    （即使请求显式给 `reviewed`），内容/关联不变的第二次 PATCH 可标记 `reviewed`。
  - 确认入库：草稿关联冻结为 `question_knowledge_links`（`subject_id_snapshot=math` + 名称快照 + 角色）；
    `GET /questions?knowledgePointId=` 命中该题、未知知识点返回空。
  - 改题：改内容（缺省）→ 新修订并**复制**旧正式关联；显式 `knowledgeLinks` → 整表替换；
    旧修订 2 条关联未被改动；直写 UPDATE/DELETE `question_knowledge_links` 均 `IMMUTABLE_REVISION`；
    正式修订写入版本化派生指纹 `derived-v1`。

## 7. V6 T50 统一任务（pass）

**命令**（`cd apps/api`）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\v6_question_job_engine_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\v6_question_job_engine_probe.json"
```

- **退出码：0**；`14/14 passed`（证据：`…/evidence/v6_question_job_engine_probe.json`）
- 关键输出摘录：
  - organize 经统一引擎：`succeeded` + `attempt=1` + `suggestionCount=2`；冻结输入 `contractVersion=2`、
    `modelProfileId`、`sha256:` 指纹、批次快照；公共任务视图状态在六态集合内且 attempt 一致。
  - **model 名额并发上限 = 1**：两个并发模型任务共 4 次模型调用，事件轨迹
    `[(start,1),(end,1),(start,2),(end,2),(start,3),(end,3),(start,4),(end,4)]` —— 严格串行、无重叠。
  - 取消：`queued` → `POST /workflow-jobs/{id}/cancel` 立即 `cancelled` 且零上游调用；
    `running` 期间取消（模型调用在飞）→ 终态 `cancelled` 且该任务 `question_suggestions` **0 行**（迟到不发布），
    上游调用数未额外增加（只影响在飞那一次）。
  - 重启收敛：库里造 `running` → `reconcile_interrupted()` → `interrupted` 且**不重叫模型**（provider 调用数不变）；
    再次 reconcile 幂等；显式 `recover_organize_jobs()` → `succeeded` 且 `attempt>=2`、建议 ≥1。
  - 旧语义 checkpoint（`contractVersion=1`）→ `failed` + `ORGANIZER_MODEL_RESELECT_REQUIRED` +
    provider **零调用**；checkpoint 只写 `needsModelReselection=true`、**不回写伪造指纹**；旧冻结输入未被改写；
    显式 recover 同样只标重选。

## 8. V7 T30-b 施测（pass）

**命令**（`cd apps/api`）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\v7_assessments_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\v7_assessments_probe.json"
```

- **退出码：0**；`33/33 passed`（证据：`…/evidence/v7_assessments_probe.json`）
- 关键输出摘录：
  - **真链路**：CSV 名单导入（T30-a 真 API，2 行预览）→ 确认**建档 + 归属**（`createdStudent/createdMembership` 均真）
    → T40 原卷确认 → `POST /assessments` 201、`participantCount=2`、`paperRevisionId` 指已确认修订；
    参测姓名/学号 = 服务端真值（张伟/V0001、李娜/V0002），`attempt_no` 均为 1。
  - 幂等：同 `submissionId` 同载荷重放 `replayed=True` 且不重复建（仍 2 行）；不同载荷 409 `SUBMISSION_CONFLICT`。
  - 闸门 10 项：draft/不存在卷 → `ASSESSMENT_PAPER_INVALID`；`2026-02-30` → `ASSESSMENT_HELD_ON_INVALID(heldOn)`；
    空名单 → 422；班级不存在 → `PARTICIPANT_INVALID(classIds[0])`；行班级越范围 → `PARTICIPANT_CLASS_SCOPE(classId)`；
    班级重复 → 422；学生不存在 → `PARTICIPANT_INVALID(studentId)`；客户端伪造 `nameSnapshot`/`studentNoSnapshot`
    字段 → 422（extra=forbid，快照只从服务端读）。
  - 归属未覆盖：转班后对旧班 + 次日施测 → 422 `PARTICIPANT_CLASS_UNCONFIRMED(row=0)`；带
    `classConfirmed + classConfirmationNote` 重提 → 201 且 `class_confirmed=1` 与依据落库；
    `class_memberships` 逐行 digest 前后相同（**不改归属历史**）；`classConfirmed=true` 无依据 → 422。
  - 人次：同学生跨班重复 → 422 `PARTICIPANT_INVALID(classId)`；重复人次 → 409 `PARTICIPANT_ATTEMPT_CONFLICT`；
    补考缺省 → 新增 `attempt 2`，首次记录 digest 逐字节不变；批量补录含非法行 → 422 且**整批回滚**。
  - 快照冻结：学生改名后既有施测快照仍是旧名；`PATCH /assessments/{id}` → `revision+1`；过期 → 409
    `ASSESSMENT_REVISION_STALE(currentRevision)`。

## 9. V8 F10-KP 页面（pass，组件级；浏览器视觉引用 CTRL E2E）

**命令**（仓库根；自建配置只收集 V00 探针用例，不改产品配置）：

```
NODE_OPTIONS=--no-experimental-webstorage npx vitest run \
  --config docs/qa/TEACHING-LOOP-B2/V00-probes/frontend/vitest.v00.config.ts
```

- **退出码：0**；`Test Files 1 passed (1) / Tests 9 passed (9)`；
  日志证据：`H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\v8-vitest-independent.log`
- 自建用例（真组件 + 模块边界受控 mock；不是实现者用例的复制）：
  - `V8.1` 503 `TEXTBOOK_EVIDENCE_UNAVAILABLE` → 显示「教材依据暂不可用（服务未就绪）」+「这里是有依据但读不到，
    和「没有依据」不同」，**且不显示**「没有教材依据」；`V8.2` 成功 0 条 → 显示「没有教材依据」且不显示"暂不可用"；
    `V8.3` 其它读取错误 → 带错误码的失败横幅（不伪装成空）。
  - AI 候选：`V8.4` queued/running 文案与取消入口 → 点取消走 `cancelJob` → 终态「已取消」+ 重试；
    `V8.5` 重试走 `retryJob` 并接管新 attempt（显示"第 2 次尝试"）；`V8.6` `interrupted/failed` 显示「已中断/失败」
    + 重试、`succeeded` 显示「已完成」且无取消/重试；`V8.7` 观察被新 attempt 取代返回 `null` → 停止观察并显示说明
    （不把旧 attempt 当本轮结果）；`V8.8` **组件卸载 → 观察 signal 全部 abort**（停止轮询且未取消任务）；
    `V8.9` 六态文案映射逐项（排队中/生成中/已完成/失败/已取消/已中断）。
- 视觉/浏览器边界（不重复 CTRL 的构建与 E2E，只读引用 `_work/b2/e2e-b2-r3.log`）：
  `knowledge-points.spec.ts` 9 例全 `ok`，含「三视口无横向溢出；390px 页面级溢出 ≤1px」与
  「prefers-reduced-motion 下过渡被压制」；**我本人未做真实浏览器视觉复核**（见 §12 not_run）。

## 10. V9 声明抽查（**fail**，文档级，2 处）

**命令**（`cd apps/api`）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\v9_docs_declarations_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\v9_docs_declarations_probe.json"
```

- **退出码：1**；`17/19 passed`（2 fail + 1 observation；证据：`…/evidence/v9_docs_declarations_probe.json`）
- 通过的声明核对（机械抽取 + 代码/DB 对照）：
  - V9.1/V9.2 路由：从 `docs/API.md` B2 节抽出的 **20 条**方法与路径全部真实存在；B2 新增路由（原卷/施测/生成）
    在文档中均有声明（双向零差异）。
  - V9.3 迁移 id（`0003_teaching_paper_tables`、`0004_teaching_assessment_tables`、`0004_question_knowledge_links`）已登记。
  - V9.4 触发器家族 ×20 与真实库逐一一致；V9.5 分期 CHECK 与 DDL 一致；V9.6 `paper_confirm` 无
    `PRACTICE_NOT_REVIEWED` 分支；V9.7 六态 + attempt 与 `JobState`/`OrganizeJobView`/`GenerationJobView` 一致；
    V9.8 `RECONCILE_DOMAINS` 含 `question`。
  - V9.11 `ROUTES.md`（已实现/ready）与 `navigation.ts`（`status:'ready'`、`path:'/knowledge-points'`）一致且页面存在；
    V9.12 租约 90s（`JobStore` 默认）与 `PROJECT_GUIDE §13` 一致；V9.13 §13 六条稳定决定逐条与代码行为一致；
    V9.14 B2 任务卡关键事实与代码一致。

### 10.1 fail 级别说明（2 处，均为 `docs/API.md` 事实错误，无产品行为缺陷）

**F-V9-1（V9.9）：B2 节声明了 3 个代码中不存在的生成错误码**

- 最小复现：

  ```
  grep -n "GENERATION_INVALID_EVIDENCE\|GENERATION_UNSAFE_REFERENCE\|GENERATION_TRUNCATED" -r apps docs
  ```

  期望：文档声明的错误码都能在代码里找到同名常量。
  实测：这 3 个名字**只出现在 `docs/API.md:545-546`**；代码里的真实名字是
  `GENERATION_UNKNOWN_EVIDENCE` / `GENERATION_FORBIDDEN_REFERENCE` / `GENERATION_OUTPUT_TRUNCATED`
  （`apps/api/app/services/question_bank/generation.py:74,77,78`），我在 V5 用真 HTTP 逐条复现了真实码。
- 预期：文档与代码同名；实际：文档使用旧命名。**首败位置：`docs/API.md:545`**。

**F-V9-2（V9.10）：B2 施测节把 `CLASS_ARCHIVED` 标注为 409，实际是 422**

- 最小复现（探针内已自动化）：建班 → 学生建档 → 归档该班 → `POST /assessments`（班级范围为该归档班）。
- 期望（按 `docs/API.md:564` 的分组）：409 `CLASS_ARCHIVED`。
- 实测：**422** `CLASS_ARCHIVED`；代码位置 `apps/api/app/services/assessments/service.py:622-633`
  （`status_code=422`）。注：`docs/API.md:471` 处**名单域**的 `CLASS_ARCHIVED(409)` 是对的
  （`app/services/roster/service.py:189-190`），与本条无关。**首败位置：`docs/API.md:564`**。
- 影响面：仅文档口径；我的 V7 未把 `CLASS_ARCHIVED` 状态码当作契约断言，故不影响 V7 结论。

### 10.2 observation（不计 fail）

- `apps/api/AGENTS.md` 仍只有 B1 段落（"施测三表留 T30-b（依赖 T40 的 `paper_revisions`）"），B2 已落地
  teaching `0003/0004` 与 `assessments`；该文件**不在 B2 任务卡的文件归属表内**（属文档漂移，不是产品不一致）。

---

## 11. V10 变异实验（pass）

**命令**（`cd apps/api`）：

```
uv run python "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\v10_mutations_probe.py" \
  --evidence "H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-B2\V00-probes\evidence\v10_mutations_probe.json"
```

- **退出码：0**；`11/11 passed`（证据：`…/evidence/v10_mutations_probe.json`）
- 三处变异（全部作用于副本/内存，产品文件零写入）：
  - **A 触发器分支**：从复制出的 `paper_confirm` DDL 删除 `ITEM_KNOWLEDGE_MISSING` 分支（912→681 字节），
    建变异库。原始库对"总分对、缺知识点"的草稿**拒绝**（`IntegrityError: ITEM_KNOWLEDGE_MISSING`），
    变异库**接受** → V1.F3/V3.4 的断言确实能发现该分支缺失。
  - **B 生成校验**：把 `scan_forbidden_reference` 的副本改成恒返回 `None`（源文件未改，`V00 变异` 只存在于副本）。
    同一含 URL 的回复：原始实现抛 `GENERATION_FORBIDDEN_REFERENCE`，变异副本产出 1 条候选 → V5.6/7/8 的断言有牙齿。
  - **C 启动收敛**：把 `RECONCILE_DOMAINS` 的内存副本去掉 `question`。先在题库库造 `running` 再 `create_app`：
    原始配置 → `interrupted`（日志 `启动任务收敛（running → interrupted）：{'question': [...]}`）；
    变异后 → 仍 `running` → V6.8 的断言有牙齿。
- 还原与复算：变异实验后 **83/83 文件 sha256 与冻结记录一致**（`mismatch=[]`）；
  `git status --porcelain` 82 条条目中，除冻结清单内文件、`V00-probes` 新增、既有 `docs/design/**` 与忽略的
  `_work/**` 外 **零越界**（`offenders=[]`）→ 候选未污染。

---

## 12. 观察（observation）

1. **OBS-1（原卷域 publish 失败后任务停在 `running`）**：AI 建议任务在"发布期冻结失败"时，业务写入确实零残留
   （`ai_proposals` 零行、旧修订不变），但任务行停在 `running`，直到下次启动 `reconcile` 才转 `interrupted`
   （我的探针实测 `state=running code=None`，另用真实执行器捕获到 `AppError PAPER_PROPOSAL_STALE(409)`）。
   这与 README §5.3 预先登记的边界一致（"T50 的 publish 失败收尾只在 question 域"），故**不判 fail**；
   建议 CTRL 在 B3 或引擎级变更时统一各域的发布失败收尾（否则原卷建议失败会长时间显示"进行中"）。
2. **OBS-2**：`apps/api/AGENTS.md` 未同步 B2（见 §10.2）。
3. **OBS-3**：`docs/API.md` T50 节声明的三个错误码名与代码不一致（F-V9-1）；建议按代码实际名修订，
   或（若刻意保留旧名）在代码里增加别名常量并在文档注明映射。
4. **OBS-4（口径提示，非缺陷）**：`KnowledgePointView` 的字段是 `id`（不是 `pointId`），
   而 `PaperItemKnowledgeView` 用 `knowledgePointId`；探针已按各自契约取值，此处仅作跨模块口径提示。
5. **OBS-5（未判 fail 的草稿语义）**：草稿"内容/关联一变即强制回 `needs_review`"（任务卡 §6.1 明示），
   因此标记 `reviewed` 需要第二次内容不变的 PATCH；我的 V5 按此正向复现，特此登记以免被误读为缺陷。
6. **OBS-6（正式数据根）**：验证窗口内（15:00 之后）`H:\备份xuexi\智启课源\.local-data` 下无任何文件 mtime 更新
   （`find -newermt "2026-10-01 15:00"` 为空），即我的探针未触碰正式库；CTRL 披露的 13:37 迁移应用在此窗口之前，
   与代码登记的 B2 迁移 id 一致（属已登记迁移，未判 fail），但**正式数据迁移演练本身仍 not_run**。
7. **OBS-7（台账间歇项）**：R-14/R-15/R-18/R-19 按 `docs/CURRENT_STATUS.md` 既有口径记录为"未关闭/跨批间歇、
   非本批引入"；我的 V00 未复现它们（未跑全量 e2e/全量 unit，见 §13），也未"修"或放宽任何断言。

## 13. not_run（明确未执行及原因）

| 项目 | 原因 |
| --- | --- |
| 真实模型调用（AI 建议 / AI 补题 / 知识点 AI 候选 / 整理） | 无授权凭证；全部为受控替身，质量与真实模型无关（替身通过 ≠ 质量通过） |
| 真实 Word/WPS 排版检查 | 本机无法自动验证；只做结构级断言（块序/定位/图片字节/OMML 子树/合并表格形状），不把 XML 存在当排版通过 |
| 真实 Qdrant / 真实教材检索链路 | 未启动、不联网；B2 范围不含 RAG 变更 |
| 正式数据迁移演练（对 `.local-data` 应用/回滚） | 硬边界禁止读写正式数据根；仅只读确认验证窗口内无写入 |
| 全量 `npm run test:api` / `npm run check` / `npm run build` / `npm run test:e2e` | 由 CTRL 组织（我按任务卡禁令不跑 build/e2e）；只读引用 `_work/b2/e2e-b2-r3.log`（147 passed） |
| 实现者测试的复跑 | 未复跑；我的结论来自自建探针（实现者测试的通过不作为验收依据） |
| 真实浏览器视觉复核（1440×900 / 1920×1080 / 390×844 / reduced-motion 的**人工**观感） | 我未做浏览器截图级复核，仅引用 CTRL 的 E2E 断言；组件级文案/状态/轮询行为由 §9 自建用例覆盖 |
| 2000 人上限压力、硬件触摸、真实网络抖动 | 不在本批验收范围 |

## 14. 我最不确定的一处

**原卷域"发布失败后任务停在 `running`"是否会在真实使用中造成可见问题**。我的证据是：业务写入零残留、
`AppError PAPER_PROPOSAL_STALE(409)` 被真实抛出、任务状态停在 `running` 直到下次启动收敛；
README §5.3 明确登记了"publish 失败收尾只在 question 域"，所以我按登记边界记为 observation 而非 fail。
但"任务长期显示进行中、且错误码未落库"对界面体验的影响，需要 F20/前端轮询口径确认——
如果前端把 `running` 当作"还在生成"并无限轮询，这一差异就会从"边界登记"升级为可感知缺陷；
我无法在没有真模型与真前端的条件下判定它的实际发生率。

## 15. 资源释放与边界声明

- 无本批启动的常驻进程/端口：`netstat` 中 8000/8001/5174/6333 无监听；`uvicorn/python` 无残留；
  三个 `node.exe` 为宿主工具进程（创建时间 14:53:58，早于我全部探针，且命令行指向宿主 runtime），非我启动。
- 所有探针的临时数据根都在系统临时目录（`zqky-v00b2-*`），未在仓库内落任何临时库/样本。
- 未修改产品代码、未改实现者测试、未改现行文档、未改冻结记录、未提交/推送、未改 `.env`。
- 探针与证据产物清单（全部在允许范围内新建）：
  - `docs/qa/TEACHING-LOOP-B2/V00-probes/{v00_support.py,v1_migrations_probe.py,v2_papers_import_probe.py,v3_papers_confirm_probe.py,v4_papers_proposals_probe.py,v5_question_links_generation_probe.py,v6_question_job_engine_probe.py,v7_assessments_probe.py,v9_docs_declarations_probe.py,v10_mutations_probe.py,baseline-hashes.json}`
  - `docs/qa/TEACHING-LOOP-B2/V00-probes/frontend/{v00-kp-independent.test.tsx,vitest.v00.config.ts}`
  - `docs/qa/TEACHING-LOOP-B2/V00-probes/evidence/{v1..v7,v9,v10}_*.json` 与 `v8-vitest-independent.log`
  - 本报告 `docs/qa/TEACHING-LOOP-B2/V00-REPORT-01.md`

**最终判断：候选 r1 的产品实现（V1–V8、V10）在独立探针下未发现阻塞性 fail；V9 的 2 处 fail 为 `docs/API.md`
文档事实错误，需由总控安排修订（不改产品代码、不影响指纹对账）。**
