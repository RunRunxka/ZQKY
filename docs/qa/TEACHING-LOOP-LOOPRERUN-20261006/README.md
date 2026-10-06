# 教学闭环复跑 2026-10-06

> 用户指示"过一遍闭环流程，测试文件在 `C:\Users\96022\Downloads\test`"后的复跑批次。
> 使用 10-04 留下的资料包与脚本，在当前 HEAD 上重跑核心闭环、浏览器专项与三组见证探针，
> 并把 10-04 首跑结论中**此前未入库**的四条产品问题（LOOP-01～04）与两条工具问题（QA-01/02）登记进仓库。
>
> 本批**只读产品代码**：没有修改任何产品文件；新增内容为本目录文档与精选证据。

## 1. 现场与运行方式

| 项 | 值 |
| --- | --- |
| 日期 | 2026-10-06（北京时间） |
| 分支 / HEAD | `main` @ `1f1b7b3`（`feat(lesson-plan): 增加恢复阻塞状态与生成意图保留机制`） |
| 开工工作区 | 本批开工时 `git status` 干净；同期另有 G7-B7C-LIVE 会话在同一仓库改动 `scripts/teaching-quality/*`、`apps/api/pyproject.toml`/`uv.lock` 与文档，非本批范围，本批没有触碰 |
| 后端运行时 | `apps/api/.venv`（CPython 3.12），生产 `create_app` |
| 前端运行时 | Node v26.2.0 + 仓库 `vitest@3.2.4`（jsdom，`NODE_OPTIONS=--no-experimental-webstorage`） |
| 测试资料 | `C:\Users\96022\Downloads\test`（10-04 MAT-v1 资料包，24 名虚构学生/2 班/4 知识点/6 计分叶）；**原脚本与首跑产物未改** |
| 真实模型 | 0 次调用；无正式数据根、无凭证读取 |
| 仓库写入 | 无（仅本目录文档与证据副本） |

五条腿的重跑方式：

1. **核心闭环**：`api-run/run_loop.py` 的字节副本 → `run_loop_rerun.py`（唯一改动：`heldOn` 由硬编码
   `2026-10-04` 改为 `ZQKY_LOOP_HELD_ON`，缺省当天）。独立数据根 `api-run/run06-head1f1b7b3/data`，
   真实 HTTP（TestClient），覆盖知识点 → 名单 → 原卷 → 施测 → 小题成绩 → 学情 → 题库 → 针对练习 →
   导出 → 新成绩回流 → 固定历史不变。
2. **原卷导入探针**：`audit/probe_paper_import_counterexamples.py` 副本（新建隔离目录
   `paper-gate-service-rerun-20261006`），真实 `PaperService` + 用户原卷 + 两条最小反例。
3. **教案前端探针**：`audit/cache-retry.test.tsx`、`audit/source-intent.test.tsx` 逐字节复制进仓库临时目录
   （`.probe-rerun-20261006/`，运行后已删除）以 jsdom + 真实组件重跑，9 例。
4. **浏览器专项**：仓库 `tests/e2e` 的 `assessments.spec.ts`、`knowledge-points.spec.ts`、
   `question-bank-real.spec.ts`（即 10-04 browser-run 同一组 15 例），跑在既有 G7 构建上，spec 自建隔离
   FastAPI 与临时数据根；端口 5174 由 `scripts/run-web.mjs` 拉起，跑完已释放。
5. **离线质量工具**：`audit/probe_quality_scopes.py` 副本重跑（`review_tool.py`）；finalizer 反例因
   源库已被系统清理**未重跑**，按工具字节未变单列（见 §3）。

## 2. 结果总览

| 腿 | 结果 | 关键数字 |
| --- | --- | --- |
| 核心闭环 | **PASS** | 110 次 HTTP、577 条断言 0 失败、552 条独立 oracle 字段、初测需巩固 25 条 → 回流后 2 条、3 个导出工件下载 SHA 与台账一致、班级/学生改名后固定历史逐字节不变 |
| 浏览器专项 | **PASS** | 15/15（0 skip/0 flaky/0 unexpected），43.3s，exit 0；施测与成绩工作区 4 例（含 200 人次 × 100 叶规模与 390px 无横向溢出）、知识点页 9 例、真实 AI 补题与公共 retry 2 例；跑在既有 G7 构建 `49nH0q5IXMfFQTcg4mpIR` 上（HEAD 未变、源码零改动，未重新构建） |
| 原卷导入 | **两问题仍复现** | LOOP-01：第 8 题被填 18 分（分节合计）；LOOP-02：`15(1)`/`15(2)` 分值与题干分离（`own_block_ids` 为空） |
| 教案前端 | **部分修复** | 9 例中 6 过 3 败：显式清除在途核验已修；恢复缓存断言、切片坐标与固定教材变更两例仍失败 |
| 离线质量工具 | **一条复现、一条未重跑** | QA-02：7 类非法 scope 仍 `SCOPE_REVIEW_READY`；QA-01：finalizer 字节未变（SHA `a67b967…`），源库缺失未重跑 |

结论口径：**核心教学闭环在当前 HEAD 上仍然可跑通；整图未全通过**——原卷导入的两条内容归属问题
（LOOP-01/02）与教案来源面板的两条在途意图问题（LOOP-04 残余）在 HEAD 上原样存在，LOOP-03 属
"探针口径与已接受实现不一致"，需用户/总控裁定。

### 2.1 日期口径（不是回归）

原脚本把施测日期写死为 `2026-10-04`。今天（10-06）用原样日期重跑，`POST /assessments` 被
`422 PARTICIPANT_CLASS_UNCONFIRMED` 拦截：名单归属历史自导入当天（`joined_on = 今天`）起算，
不覆盖 10-04。这是 B2/T30-b 的**显式确认班级**闸门（`classConfirmed=true` + `classConfirmationNote`，
服务端不自动改归属），10-04 当天运行之所以通过只是因为"导入日 == 施测日"。
本轮按当天日期适配后通过；首跑（`run03`，10-04）与今日重跑（`run06`）都保留，未互相覆盖。

## 3. 六项 finding 的当前状态

| 编号 | 首跑结论（10-04） | 今日复跑 | 位置 |
| --- | --- | --- | --- |
| LOOP-01 | 分节合计被当作上一题满分 | **仍复现**（最小输入 `8.` → `二、多项选择题（共18分）` → `9.`，8 题 `maxScore=18`） | `apps/api/app/services/papers/imports.py`（`_fill_leaf_scores` 取自有块首个分值标记） |
| LOOP-02 | 独立括号子题创建后没有题干块 | **仍复现**（`15(1)`/`15(2)` 分值 4/6、`own_block_ids=[]`、`stemBlocks=[]`） | 同上（`_detect_specs` child 分支 `number_blocks[block.id]` 写父题号） |
| LOOP-03 | 恢复缓存写失败后没有公开保存重试入口 | **探针口径差异**：仓库已有公开"重试恢复缓存"控件（G4 批实现，`g4-recovery.test.tsx` 26 例自测通过）；探针要求"读取后台最新版本"后保存键直接可用，故断言仍失败 | `apps/web/src/features/lesson-plan/components/ServerControls.tsx` 等 |
| LOOP-04 | 显式清除在途教材后旧核验响应复活教材 | **显式清除已修**（该用例通过）；**切片坐标与固定教材两条用例仍失败**：核验在途时改 `切片终点`/`教材固定修订`，迟到的旧响应仍被采用 | `apps/web/src/features/lesson-plan/components/SourcePanel.tsx`（`verifySlice` 的 `verifyIntent` 只绑 `selection`/`value`，未含本地 `start/end/documentId`） |
| QA-01 | 只剩 14 例仍写 PASS15 | **未重跑**：离线源库（TEMP `zqky-b5-b6-quality-offline-third-nfyoaa05`）已被系统清理；`finalize_review_v3.py` 字节未变（SHA `a67b967…`），原反例照旧成立 | `docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/finalize_review_v3.py` |
| QA-02 | 非法真实模型范围仍得到 READY | **仍复现**：`boolean-sampleCount`/`duplicate-caseIds`/`unknown-caseId`/`string-caseIds`/`non-string-profile`/`NaN`/`Infinity` 共 7 类非法 scope 仍 exit 0 + READY（仅缺输入正确 exit 2） | 同目录 `review_tool.py`（字节未变，SHA `65c7ffd…`） |

原卷两条的旁证（与首跑一致）：按原样确认 → `422 ITEM_KNOWLEDGE_MISSING`；只给计分叶补知识点后再确认 →
`422 PAPER_ISSUE_BLOCKING`，仍有 22 条 open blocking，**原卷无法直接确认**，也没有产生正式成绩。

## 4. 未执行项（明确 not_run）

- `npm run check`（typecheck/lint/unit/build）、全量 e2e（174 例，本批只跑其中 3 个 spec / 15 例）、
  10-04 的样本 4 页与 390px 截图核查：**本批未执行**；最近一次同 HEAD 门禁证据见
  [G7/B7-C 状态](../CURRENT_STATUS.md)（check r2/r3 全绿、e2e 174/174）。
- 真实模型备课（`LESSON_PROPOSAL_INVALID` 首跑结论）、真实 RAG 检索、Word/WPS 原生排版：**未执行**。
- QA-01 的在线复现需要重跑 b6-quality 离线用例生成（属另一批授权范围），本轮不做。

## 5. 证据台账

本目录 `evidence/`（由批次会话精选 `git add -f`）：

| 文件 | SHA256（前 16） | 说明 |
| --- | --- | --- |
| `CORE-LOOP-RESULT-run06.json` | `a4fc47163be3ecaa` | 核心闭环完整结果（110 HTTP、577 断言、导出 SHA、边界声明） |
| `CORE-LOOP-IDS-run06.json` | `ae7ea0e0c83e82a4` | 本轮新建实体 ID（4 知识点/2 班/原卷/施测/练习…） |
| `PAPER-IMPORT-COUNTEREXAMPLES-rerun.json` | `258b08854f33e97c` | 原卷最小反例 + 原卷确认闸门（LOOP-01/02） |
| `COMPONENT-PROBES-rerun.json` | `1c8fc01fa96b80dd` | 两份教案组件探针 9 例结果（LOOP-03/04） |
| `QUALITY-SCOPE-rerun.json` | `3b595a70da1bc9b0` | 7 类非法 scope 的工具返回（QA-02） |
| `BROWSER-SPEC-15-rerun.json` | `15f936ea5e7e28b3` | 浏览器专项 15/15 完整 JSON（playwright 1.58.2，43.3s，0 skip/flaky） |
| `run_loop_rerun.py` | `ccc713d673dd3d43` | 本轮核心闭环驱动（`run_loop.py` 副本 + 日期适配） |
| `FIRST-RUN-REPORT-20261004.txt` | `fcac6c0d51821afa` | 10-04 首跑结论原件（LOOP-01～04/QA-01/02 的来源） |
| `FIRST-RUN-SUMMARY-20261004.json` | `dcb4c55e9875d1b8` | 10-04 首跑汇总（核心 PASS、浏览器 15/15、真实模型 `LIVE_LESSON_FAILED`） |
| `FIRST-RUN-PRESERVATION-20261004.json` | `b6135863dceab73f` | 10-04 保全声明（HEAD `b7f99ab`、3172 文件零漂移、原卷 SHA 未变） |
| `CORE-LOOP-RESULT-run08.json` | `2bbf260006ad79ed` | 第二轮核心闭环（110 HTTP/577 断言，与 run06 逐项一致） |
| `PAPER-IMPORT-COUNTEREXAMPLES-rerun3.json` | `58b335149d4c0234` | 第二轮原卷最小反例（含替身原卷标注） |
| `QUALITY-SCOPE-rerun2.json` | `3b595a70da1bc9b0` | 第二轮 QA-02（与第一轮逐字节相同，证明工具确定性） |
| `BROWSER-SPEC-15-rerun2.json` | `42d595d6b5d231a5` | 第二轮浏览器专项 15/15 完整 JSON |
| `CORE-LOOP-RESULT-run09-postfix.json` | `1c2775fc322c0b9a` | **修复后**核心闭环（109 HTTP/577 断言，PASS） |
| `PAPER-IMPORT-COUNTEREXAMPLES-postfix.json` | `b90a542419fd9bbd` | **修复后**原卷最小反例（8 题不再被填 18 分、子题拿到题干） |
| `BROWSER-SPEC-15-postfix.json` | `527745f445f00847` | **修复后**浏览器专项 15/15 完整 JSON |

外部原始资料（只读，未改）：`run_loop.py` `93cb05a9fb06aa81`、`probe_paper_import_counterexamples.py`
`a6400c1bf53988f8`、`cache-retry.test.tsx` `e17532d198bcf83b`、`source-intent.test.tsx`
`88880573a32ae5e9`、`probe_quality_scopes.py` `10acd222db12d732`；
仓库内工具 `finalize_review_v3.py` `a67b967db179011f`、`review_tool.py` `65c7ffd7524aa69c`。

## 6. 第二轮复跑（同日 18:20–18:25）

用户要求"再跑一遍"时发现：`C:\Users\96022\Downloads\test` 除 `inputs/`（15 份材料）外，
驱动脚本（`api-run/*.py`、`audit/*.py`、两份组件探针、浏览器产物）与首跑原始产物已被清理，
回收站内也没有（`$Recycle.Bin` 无对应项）。仓库侧留存与本轮重建如下：

| 需要的东西 | 来源 |
| --- | --- |
| 核心闭环驱动 | 仓库 `evidence/run_loop_rerun.py`（12:5x 复跑时留存的逐字节副本，SHA `ccc713d6…`） |
| `runtime.py`（隔离 app 工厂） | **重建**：按 12:5x 记录的原文重写（本批 `harness-20261006/runtime.py`，SHA `8bfb658e…`） |
| 原卷导入探针 | **重建**，两条最小反例逐字保留；原"用户原卷"`测试试卷.docx` 已删，代之以仍存在的 `inputs/闭环测试_一元一次方程原卷.docx` 并在结果里标注 |
| QA-02 探针 | **重建**，scope 输入与 `review_tool.py` 都在仓库内，保持只读 |
| 教案组件探针（LOOP-03/04） | **无法逐字恢复**（原件已删、内容只部分留档）→ 本轮不重跑，结论仍以 12:5x 那次为准 |

第二轮结果（与第一轮一致，无翻转）：

- 核心闭环 `run08-head1f1b7b3`：**PASS**，110 HTTP、577 断言 0 失败、552 oracle 字段、
  需巩固 25→2、模型 0，与 `run06` 逐项相同。
- 原卷导入最小反例：仍然 `8.` 题 `maxScore=18`；`15(1)/15(2)` 分值 4/6、自有块 0。
  （替身原卷本身无 blocking，故 `asImported` 之后补知识点即确认成功——这条与本轮结论无关，
  是因为原用户原卷已被删除、换成了干净的学习闭环原卷。）
- QA-02：7 类非法 scope 的返回与第一轮**逐字节相同**（同工具、同输入，输出 SHA 均为
  `3b595a70da1bc9b0`）。
- 浏览器专项：再次 **15/15**（0 skip/flaky，45.7s）。
- 仓库自有 `g4-recovery` + `g4-source-intent`：55/55 通过（用于交叉确认 LOOP-03 现行设计成立）。

重建 harness 位于 `C:\Users\96022\Downloads\test\harness-20261006\`；第二轮证据见下表 `…-run08`/`…-rerun2`/`…-rerun3` 行。

## 7. 修复记录（同日 18:40–19:15，LOOP-01/02）

按用户"帮我修掉"的指示，本批修掉两条**原卷导入**问题；LOOP-03/04 未动，理由见下。

| 问题 | 改动 | 行为变化 |
| --- | --- | --- |
| LOOP-02 | `_detect_specs` child 分支：子题号块登记成 `full`（完整子题路径）而非 `current_root.question_no`（父题号） | 独立成段的 `（1）` 及其后续正文归 `15(1)`；父容器不再吸收子题内容。与既有复合写法 `16(1)` 口径一致 |
| LOOP-01 | 新增 `_SECTION_HEADING` 正则与 `is_section_heading_block`；`_assign_blocks` 里分节标题作**结构边界**：关闭上一题归属，自己记 `unassigned` | 分节标题里的「共 N 分」不再是上一题满分；标题也不再混进上一题题干。该块由教师指定归属或排除（与其它非题目文本同一口径） |

同一最小输入的修复前后对比：

- 修前：`8.` → `maxScore=18`（错）；`15(1)/15(2)` 分值 4/6 但 `ownBlocks=[]`。
- 修后：`8.` → 无分值 + `ITEM_SCORE_MISSING`（要求教师确认）+ 分节标题 `PAPER_BLOCK_UNASSIGNED`；
  `15(1)/15(2)` 各自 `ownBlocks=[b1]/[b2]`、题干含题号与正文、无 issue。

新增回归用例 2 条（`apps/api/tests/test_papers_import.py`），样本构造器加两个开关；相关套件与全量后端：

- `pytest tests/ -k "paper or import"`：157 通过；
- 全量 `pytest`：126 文件 1921 例收集，完整一轮 exit 0。

修复后复跑（同样本、叠加本批修复）：

- 核心闭环 `run09-postfix`：**PASS**，109 次 HTTP、577 条断言 0 失败、552 oracle 字段、需巩固 25→2、模型 0
  （与 run06/run08 唯一差异是后台任务轮询少 1 次）；
- 浏览器专项：**15/15**（44.7s）；
- 学习闭环原卷（无分节标题）不受影响，仍 0 issue。

未动的三条与理由（**同日 19:30 用户已按建议裁定**）：

- **LOOP-04 残余**：保留现行语义——`g4-source-intent.test.tsx` 的两条刻意用例锁定"改切片坐标/固定教材属于
  下一段准备、不算取消在途核验"；已采纳证据自带教材修订与区间坐标，且现在**在面板上写明分工**
  （新增一行说明：参数是「下一段待核验」，已核验证据列在下方、各自标注修订与区间、撤回走整体清除），
  配套新用例 `states on screen that the form holds the next slice…`。不做"改参数即作废"：
  那会让手一抖就静默丢掉正在等的核验，而且作废路径不报错。
- **LOOP-03**：保留"先点重试恢复缓存、再保存"的现行设计——多一次点击，换来"保存键可用即已有一份
  读回校验过的完整恢复包"这一保证；故障瞬时恢复后自动解锁会让正文只留在内存里（标签页崩了即丢）。
  待用户嫌点击麻烦时再评估"下次编辑时自动重试恢复包写入"的折中。
- **QA-01/02**：离线质量工具（位于 `docs/qa/...` 证据区），本轮未动，留待下一次质量批。

改动文件（未提交）：

- 后端：`apps/api/app/services/papers/imports.py`、`apps/api/tests/papers_support.py`、
  `apps/api/tests/test_papers_import.py`（LOOP-01/02 修复与两条回归用例）；
- 前端：`apps/web/src/features/lesson-plan/components/SourcePanel.tsx`（LOOP-04 口径说明一行）、
  `apps/web/src/features/lesson-plan/g4-source-intent.test.tsx`（说明文案用例一条）。

配套门禁：教案模块单测 14 文件 342 例通过；`npm run check` 全绿——typecheck、lint 0 警告、
单测 **128 文件 1484 例**通过、生产构建成功（构建 `sBZJ0fQ7zQuuZSbRpWLTT`，`next-env.d.ts` 已恢复原字节）；
新构建上 `tests/e2e/lesson-plan.spec.ts` **9/9** 通过（含四视口不溢出与损坏草稿保护）。

## 8. 独立验收与提交（同日 19:40–19:55）

用户要求"让独立验收者复核后提交，只提交项目代码"。独立验收者（只读产品、自写探针）结论：**pass**。

它自己构造的证据：纯函数最小反例 38 项、端到端 DOCX→解析→落库 10 项、HEAD 与工作区行为对照、
`pytest tests/test_papers_import.py` 15 通过、`pytest -k "paper or import"` 157 通过、
前端 `g4-source-intent` 30 通过 / `g4-recovery` 26 通过。四个命题（子题归属、分节边界、不误伤、
前端仅文案且语义不变）逐项自证通过。

验收者另记两条**不阻塞**边界，作为后续可选项（本批不改，改会作废已验证字节）：

1. 节标题不重置 `_detect_specs` 的 `current_root`：节标题之后冒出的独立 `（1）` 仍会挂到节前的父号
   （HEAD 对照确认非本批回归；该块会带告警、闸门会拦）。根治需在 `_detect_specs` 遇到节标题时置
   `current_root = None`。
2. `（三）个同学参加了比赛。` 这类以括号中文序号开头的正文会被判为分节标题（本批新增的行为），
   后果是显式告警 + 闸门要求教师处理，不是静默丢失；若样本频发，可给括号形态加后续语义校验。

提交：`bfea753`（分支 `main`），只含 5 个项目文件、117 insertions：
`apps/api/app/services/papers/imports.py`、`apps/api/tests/papers_support.py`、
`apps/api/tests/test_papers_import.py`、`apps/web/src/features/lesson-plan/components/SourcePanel.tsx`、
`apps/web/src/features/lesson-plan/g4-source-intent.test.tsx`。
按用户指示，**本目录（含 evidence/）与 `docs/`、`docs/qa/` 的文档改动一律不入库**，保留在工作区；
另一个会话的 `scripts/teaching-quality/*`、`apps/api/pyproject.toml`、`uv.lock` 未被触碰。未推送。

## 9. 模型口径批（同日 21:00–22:30，用户裁定）

用户裁定：**教案生成与 RAG 的 LLM 不使用本地模型，统一使用"全局默认问答模型"**（云端）。
两条子规则：教案生成"只允许云端档案、未选时默认用全局默认档案"；RAG 概括"走默认云端模型，
未配置默认档案就明确不可用，绝不回退本机"。

**A. 教案生成（只允许云端 + 默认全局默认）**

| 面 | 改动 |
| --- | --- |
| 后端硬规则 | `services/lesson_generation/preparation.py`：解析出的档案落在注册表 `is_local` 供应商（Ollama/vLLM/LM Studio）时，生成请求 422 `LESSON_MODEL_NOT_CLOUD`，**不发任何模型请求** |
| 档案身份下发 | `api/v1/model_views.py`：连接视图加 `isLocal`，档案视图加 `isDefault`（对照全局默认档案）；`model_catalog.py`、`model_profiles.py` 三个调用点传入默认档案 id |
| 前端 | `contracts/model-settings.ts` 加 `isLocal`/`isDefault`；`SourcePanel.tsx` 的"模型档案"只列云端档案，未显式选择时自动选中 `isDefault`，已存本机档案时显示明确占位项 |

**B. RAG 知识点概括（改走默认云端模型）**

- `services/rag_v2/summary.py`：`KnowledgeSummarizer` 由"本机 Ollama `/api/chat` + 固定
  `qwen2.5:7b` + `num_ctx`/`num_predict`"改为**「全局默认问答档案 → ChatModelHandle → provider」**：
  协议由档案决定（openai-chat / openai-responses / anthropic-messages），同步调用经独立线程桥接
  provider 的异步 `complete`；输出预算取档案 `maxOutputTokens`（夹在 256–2048），提示词预算按档案
  `contextTokens`（未声明用 8192）推导并与 6000 字符证据上限取较小者。
- 判定与状态：**默认档案未配置、或默认档案是本机部署 → 503 `RAG_SUMMARY_UNAVAILABLE`**（问答侧转
  partial 并保留证据，绝不回退本机）；`status()` / `probe()` 改为**配置级检查**（不向云端发推理调用，
  因此"探测通过"只代表配置就绪，已在 state/detail 文案中写明）；截断判定改用 provider 归一的
  `finish_reason=length`，`usage` 只作诊断字段。
- `services/model_runtime.py`：`ChatModelHandle` 增加 `context_tokens`（来自档案 `contextTokens`）。
- `main.py`：装配改为 `resolve_default_profile=(读 model 配置的 defaultChatProfileId) + resolve_handle`。

**测试**：新增 `tests/summary_support.py` 概括替身台（真实 provider + MockTransport，与生产同路径）；
4 个原有测试文件按新口径重写/适配——`test_rag_v2_summary.py`（含"未配置默认/默认本机/云端可用"
三态与 503 转换）、`test_rag_v2_summary_budget.py`（档案预算与截断）、`test_rag_v2_status_probe.py`
（配置级探测）、`test_rag_v2_answer_quality.py`（脚本化概括输出）；另在 `test_lesson_generation_validation.py`
与 `test_model_catalog.py` 增加本机档案拒绝、云端放行、`isLocal`/`isDefault` 标记用例。

**门禁（本批最终）**：后端 `pytest` 全量 **1924 passed / 1 skipped**（exit 0）；前端 `typecheck` + `lint`（0 警告）
+ 单测 **128 文件 1484 例** + 生产构建（`__2rXajplseOuw-WelpEd`）全通过，`next-env.d.ts` 已恢复原字节。
首轮 `check` 的 2 例失败（`lesson-workspace` 分页 `role=alert`、`g2-session` 409）隔离复跑与全量复跑均通过，
按"观察到一次、未复现"的间歇记录，不拼绿。

**独立验收**：pass_with_conditions。验收者自写探针（A1–A4、B1–B5 全过）：
A1 `ollama/vllm/lm_studio/llama_cpp` 四类本机档案全部 `LESSON_MODEL_NOT_CLOUD` 且模型请求 0 次（拒绝点在
`build_request` 之前）；A2 同现场换 `deepseek` 放行且请求 1 次；A3 三处视图标记 + 默认档案切换/删除后
`isDefault` 跟随；A4 五个 vitest 渲染探针（下拉只列云端、自动选中默认、保留教师已选、本机档案占位）；
B1 未配置/本机/空 id 全部 503 且 0 请求、解析失败转 503 而非 500；B2 三协议互通与三种截断形态；
B3 预算随档案窗口收缩（2048 窗口→1433、窗口小于预留→0）；B4 `status()/probe()` 0 请求；
B5 整点拒绝/只修正一次/不回显题目原文/失败分级逐一复测。

验收者记下三条**非阻塞**发现（本批不改，留台账）：

1. 未知/空 `providerId`（自建 custom 连接）按"非本机"放行——沿用"仅显式本机供应商被拒"的口径，需确认措辞；
2. openai-responses 的 `status=incomplete` 缺 `incomplete_details.reason` 时不判截断（与 base.py"未知值不伪装成 stop"一致）；
3. `KnowledgeSummarizer.status()` 只捕 `AppError`，非 AppError 会穿透；生产链路
   `RagV2Service._summarizer_status` 有 `except Exception` 兜底，用户可见结果仍是不可用，属文案层。

**提交**：`22f5b8a`（main），16 个项目文件、551 insertions：
后端 `model_views.py` / `model_catalog.py` / `model_profiles.py` / `lesson_generation/preparation.py` /
`model_runtime.py` / `rag_v2/summary.py` / `main.py`；测试 `summary_support.py`（新）+ 4 个概括测试文件
+ `test_lesson_generation_validation.py` + `test_model_catalog.py`；前端 `contracts/model-settings.ts` +
`SourcePanel.tsx`。**docs/qa 与本目录证据、其它会话改动一律未提交**（用户指示），未推送。

## 10. 真实环（同日 23:10–23:35，用用户正式凭证）

用户要求"走一遍"真实环：用**正式 `apps/api/.env` 的云端凭证**真发一次 RAG 概括与一次教案生成。

**RAG 知识点概括 —— 跑通**（正式数据根 + 正式教材）

- 链路：Ollama `bge-m3` 向量 → Qdrant 检索（正式索引代 `90f3ec0b…`，58 册 / 10477 块）→ **deepseek-flash 概括**。
- 实证：后端日志 `POST https://api.deepseek.com/chat/completions → 200`；页面「本地概括 deepseek-flash」
  「检索 就绪」「任教范围 已就绪」；回答给出 3 个知识点（并集 / 交集 / 区别）与**教材依据 6 条**。
- 结论：新概括路径在真实环境可用，模型身份来自「全局默认问答模型」。

**教案生成 —— 两次超时后跑通**（隔离数据根 + 正式模型配置/凭证）

- 面板按新规则工作：模型下拉**只列云端档案**（deepseek-v4-pro / deepseek-flash），**全局默认 deepseek-flash 自动选中**（`isDefault` 生效）。
- 前两次真实生成 `UPSTREAM_TIMEOUT`（"等待模型响应超时"）：云端**确实被调用**（两条 `POST api.deepseek.com → 200`），
  但产品 `lesson_generation/service.py:122` 的 `asyncio.wait_for(..., config.timeoutSeconds)` 默认 **30 秒**等不及——
  该档案是 `reasoningEnabled=true / effort=max`，一次完整教案 JSON 要约 **90 秒**。这是**从产品 UI 复现**了
  [G7-B7C-LIVE 登记的 LIVE-FINDINGS](../TEACHING-LOOP-G7-B7C-20261005/b7c/LIVE-FINDINGS-v1.md)（非流式 30 秒默认等待）。
- 在与正式配置隔离的演示根里把该档案推理关闭后重新发起 → **生成成功**：候选通过契约校验，逐字段差异
  （核心素养 / 教学重点 / 教学设计 / 教学过程）→ 勾选 4 项采用 → "已采用所选字段，该候选已终结"，正文更新、后台稿已保存。
- 成本：4 次真实调用（含两次上游实际已生成但客户端已超时 + 1 次成功生成 + 1 次 RAG 概括），deepseek-flash 价位下为**分币级**。

**真实环顺带观察（未改，建议登记）**

1. 教案生成的 30 秒非流式等待对 `reasoning` 档模型不够（同上 LIVE-FINDINGS）；当前无配置项可调。
2. 「教师要求」为空时，面板前置检查不提示，后端只回"教案请求字段不符合契约。"，教师看不出该填哪一项。
3. 前端端口必须落在后端白名单（`ZQKY_ALLOWED_ORIGINS`，默认 5173/5174），否则 403 `FORBIDDEN_ORIGIN`。

**环境还原**：自起的 API/前端与 Qdrant 容器已全部停止（跑之前 Qdrant 是停的），Ollama 未动，端口无监听；
正式数据只留了一条 RAG 问答会话（正常使用），教案相关写入全在隔离根；隔离根内是正式模型配置副本（无密钥）。

## 11. 下一动作建议

1. LOOP-01/02 **已修复**并跑通闭环（本批 §7）；如需入库，按仓库惯例单独提交这一小批
   （`apps/api/app/services/papers/imports.py` + 两条回归用例），独立验收者可复核最小反例。
2. LOOP-04 残余与 LOOP-03 属**产品口径**选择，请用户裁定后再动产品与对应测试：
   要么接受现行语义并改用例口径，要么改产品并同步改 `g4-source-intent`/`g4-recovery` 的锁定用例。
3. QA-01/02 属离线质量工具，可在下一次质量批内一并收紧（严格 scope 类型校验、按 manifest 全集核对计数）。
