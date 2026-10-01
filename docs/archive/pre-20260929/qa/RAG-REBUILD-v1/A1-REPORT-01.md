# A1-REPORT-01 · RAG-REBUILD v1.0 独立验收结果卡（r1）

```text
任务 ID / 版本：RAG-REBUILD-v1 / A1-VERIFY v1（r1 验收）
负责人：独立验收者（只读产品代码；未改任何产品/测试/契约/锁文件；未执行任何 git 写操作）
候选 SHA：c2f31ec0a70fc9b9e9d38479b6c193416c19befb（工作树，194 个变更文件）
前端构建：BUILD_ID HTTZY44JQkMTS0U36wT00（= FROZEN-CANDIDATE.json 声明值）
冻结核对：验收开始时 194/194 sha256 全等，git status 无清单外路径，HEAD == baseCommit（本人重算）；
  验收结束时 193/194 —— 唯一差异见 §8「候选漂移声明」（`next-env.d.ts`，由被要求的 `npm run test:chat` 触发 Next 生成物重写，非人工改动）
结论：needs_revision
```

**结论一句话**：13 条高风险边界里，12 条通过；**1 条部分通过**（模型空间一致的「查询半边」未强制 digest 校验）。
另有 6 项独立发现（1 项数据/证据完整性问题、1 项检索质量缺陷、1 项功能缺陷、3 项口径不一致），
不构成「核心不变量被破坏」，但按验收标准不足以给 pass。

复现入口（全部只读或只写 A1 自有副本）：

```bash
cd apps/api && PYTHONPATH=<repo>/apps/api A1_DATA=<repo>/_work/rag-rebuild-v1/A1/data \
  uv run python <repo>/_work/rag-rebuild-v1/A1/scripts/t01_core.py     # 其余脚本同法
```

---

## 0. 资源与候选（先说清数据边界）

| 事项 | 结论 |
| --- | --- |
| 独立数据 | `_work/rag-rebuild-v1/A1/data`（来自 `migrate-isolated/data` 的**副本**）、`A1/data-mut`（可变副本，供删除/重建/题库写操作） |
| 真实服务 | Qdrant 16333（compose `zqky-rag-test`）、Ollama 11434（bge-m3 + qwen2.5:7b）、真实云端 deepseek（用户 `.env` 凭证） |
| 未触碰 | 冻结的 `migrate-isolated/data`、`_work/rag-rebuild-v1/<其他任务>/**`、`docs/qa/RAG-REBUILD-v1/`（除本报告）、正式 Qdrant 6333、`.local-data` |
| 例外（已按要求登记） | 浏览器联调时临时把测试 API 起在 **8000**（只因冻结候选构建的 Next rewrite 指向 8000），**验后已停止** |

---

## 1. 工程检查（冻结候选上重跑）

| 检查 | 命令 | 退出码 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| 类型检查 | `npm run typecheck` | 0 | 通过 | `_work/rag-rebuild-v1/A1/logs/typecheck-lint.log` |
| Lint（0 警告门槛） | `npm run lint` | 0 | 通过 | 同上 |
| 单测 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | 0 | **67 文件 / 560 用例全通过**（82.3s） | `logs/unit.log` |
| 后端测试 | `cd apps/api && uv run python -m pytest -p no:cacheprovider --tb=short -ra` | 0 | **546 passed**（53.9s） | `logs/pytest-summary.log` |
| 全量 e2e | `npx playwright test` | 0 | **138 passed**（5.5m） | `logs/e2e.log` |
| 聊天集成 | `npm run test:chat` | 1 | **13 passed / 1 failed**，唯一失败 = `tests/integration/chat-live.spec.ts:62`（`从服务获取模型` 旧 selector，超时） | `logs/test-chat2.log` |

- e2e 期间 8000 无服务，`[WebServer] ECONNREFUSED 127.0.0.1:8000` 属预期噪声（用例用 `page.route` 打桩），**不影响 138 passed**。
- `test:chat` 第一次运行失败于 fixture 端口（8002 被我的实例占用）；停掉后重跑得上述结果。**R-15 既有失败核对成立，且确认只有它**。

---

## 2. 逐条高风险边界

每条给：我的命令 / 触发条件 / 原始证据 / 结论。所有脚本在 `_work/rag-rebuild-v1/A1/scripts/`，
结果卡在 `_work/rag-rebuild-v1/A1/evidence/`。

### 2.1 唯一索引权威 → **pass**

- 命令：`python A1/scripts/t01_core.py`（t01-b1 段），退出码 0
- 触发条件：真实候选上的 `/textbook-index/status` + `catalog_state` 全表列扫描 + Qdrant `/aliases` + 该数据目录的 `model-config.json`
- 结果：`active_generation_id` 与 `/status.activeGenerationId`、`generation.generationId` 三处同值；`catalog_state` 单行 id=1；
  **全表扫描无第二个 `index/collection/embedding/generation` 指针列**；Qdrant `/aliases` 为空数组；`model-config.json` 无索引代字段；
  `index_generations` 中 ready 代恰好 1 个且等于 active；collection 名唯一、无 alias 复用。
- 证据：`evidence/t01-b1-single-pointer.json`（10/10）

### 2.2 模型空间一致 → **fail（查询半边）**

- 通过部分：索引代的 `profile_id` 就是查询用的 profile（`/status.activeProfileId` 同值）；定位请求体**没有任何** profile/model 字段，
  客户端无法换模型空间；指向不存在索引代的快照 → 409 `RAG_SCOPE_CHANGED`（不是错误结果）。
  证据：`evidence/t03-b2-model-space.json`（6/6，命令 `python A1/scripts/t03_modelscope.py`，退出码 0）。
- **失败部分（缺陷 D1）**：`model_manifest_digest` 在**查询路径完全没有校验**。
  `_work/rag-rebuild-v1/A1/scripts/t04_digest_gap.py`（退出码 0，证据 `evidence/t04-digest-gap.json`）实测：
  1. 本机 bge-m3 digest 与 profile 登记一致（前提成立）；
  2. 把 profile 的 `model_manifest_digest` 改成 `0…0`（模拟同名 tag 换了权重）后，`HybridRetriever._embed_query(tampered, "等差数列的通项公式")`
     **仍然成功返回 1024 维向量**，不抛 `EMBEDDING_MODEL_CHANGED`；
  3. 写入路径是**有**校验的（`DocumentIndexer.require_digest` 在 `index_chunks` 每批嵌入前后各调一次，全仓 2 处调用点）；
  4. `apps/api/app/services/rag_v2/**` 整体不含 `require_digest` / `manifest_digest` 字样。
- **最小复现（交总控）**：`cd apps/api && PYTHONPATH=$PWD uv run python ../../_work/rag-rebuild-v1/A1/scripts/t04_digest_gap.py`
  → 第 2 项 PASS（即"未阻止错误查询"成立）。
- 影响：教材与查询向量会落在不同权重空间而不报错（结果静默失真，或分数塌到 0 后只剩 BM25 命中）。
  对照 `docs/PLAN.md` §4.2「同名 tag 的 digest 改变必须视为模型改变」与验收矩阵 E03「阻止错误写入**和查询**」。

### 2.3 重建失败/取消保留旧索引 + 删除不复活 → **pass**

- 命令：`python A1/scripts/t07a_rebuild_failure.py`（退出码 0）、`t07b_delete_during_rebuild.py`、`t07c_rebuild_recheck.py`（退出码 0）
- 触发条件（真实操作，非替身）：
  - 失败：`docker stop zqky-qdrant-test` → `POST /textbook-index/rebuilds` → 向量写入不可达；
  - 删除：真实全量重建（56 册、bge-m3、约 9 分钟）进行到一半时 `DELETE /textbooks/{id}`。
- 结果：失败任务 `state=failed, error_code=QDRANT_UNAVAILABLE`，目标代 `aborted`，`active_generation_id` **不变**，`rebuild_job_id` 释放；
  重建期间旧代继续可定位；重建期间删除的册在**新代**标 `skipped_deleted`、`expected_chunk_count=0`、Qdrant 中 0 个点、
  `deleted_at` 保持非空（未复活）；重建前已删除的册在新代中**没有任何行**（也不复活）；
  新代点数 9196 == 登记 ready 块数 9196；`G0→G1` 块数差额 266 == 两册被删册块数（157+109）。
- 证据：`evidence/t07a-rebuild-failure.json`(16/16)、`t07c-rebuild-recheck.json`(13/13)、`t07b-delete-during-rebuild.json`
- 说明：`t07b-delete-during-rebuild.json` 的 `pass=false` 只有 1 条 —— 是我自己把存活册数写死成 56（实际 55，因为 t06 先删过 1 册），
  **不是产品缺陷**；该文件已由 `t07c` 逐条复核并全通过。

### 2.4 范围不串库（最重要）→ **pass**

- 命令：`python A1/scripts/t01_core.py`（t01-b4 段）、`t03_modelscope.py`、白盒 `t02_whitebox_range.py`（均在 apps/api 下 uv 运行，退出码均 0）
- 真实数据：数学 A 版高二 3 册 / 数学 B 版高二 3 册（**册次标题完全相同**，故只能按 documentId 判定）；
  物理高二 3 册；化学/生物高二共 8 册。
- 结果：
  - A 版 selection 的证据 `documentId`/`documentRevisionId` 全部落在允许集合内，与 B 版**零交集**；B 版同理；
  - 物理范围证据中**不含**任何化学/生物修订；
  - 单册范围（只选 1 册）证据只来自该册；
  - 负向对照（有力量）：把「光合作用的光反应与暗反应」问题放在**数学**范围 → 证据里不出现「光合作用」、无任何生物书册；
    同一问题放在生物范围 → 命中「光合作用」且全部来自生物册；
  - 空 `documentIds` → 422 `RAG_SCOPE_EMPTY`（明确拒绝，不回退全库）。
- 同一范围三处一致（白盒，真实 Qdrant + 真实 Embedding）：
  - Qdrant `search` 收到的 filter 与 `allowed_filter(scope)` 的 `to_qdrant()` **逐字段相等**；
  - BM25 侧 `catalog.list_chunks` 被读取的 chunk set 集合 ⊆ 范围；
  - 融合候选的 chunkSet/revision 全部在范围内；邻块扩展 span 全部在范围内；
  - **负向**：把化学册的候选塞进 `expand_spans` / `build_evidence` → 两者都抛 409 `RAG_EVIDENCE_UNAVAILABLE`（拒绝越界）。
- 证据：`t01-b4-scope-isolation.json`(14/14)、`t03-b4-power.json`、`t03-b4-single-book.json`、`t02-whitebox-range.json`(9/9)

### 2.5 范围变化被拒 → **pass**

- 命令：`python A1/scripts/t06_scope_change.py`（退出码 0，8002 可变副本）
- 触发条件与结果：
  - **改分类**（PATCH `volumeLabel` 生成新 metadata 修订）后用旧 `scopeSnapshot` 定位 / 详解 → 均 409 `RAG_SCOPE_CHANGED`；
  - **删除书册**后用旧快照定位 → 409 `RAG_SCOPE_CHANGED`；详解 → 409 `RAG_SCOPE_CHANGED`；
  - 仍含已删除册的 selection → 明确拒绝（不静默缩小范围）；去掉该册的新范围 → 正常定位且 `scopeHash` 变化；
  - **切换索引代**（t07b 真实重建发布 G1 之后）用 G0 快照定位 → 409 `RAG_SCOPE_CHANGED`；新代用新 selection → 正常且证据来自 G1。
- 证据：`evidence/t06-scope-change.json`(15/15)、`t07b-delete-during-rebuild.json`（换代段）

### 2.6 引用绑定不可变原文 → **pass**

- 命令：`python A1/scripts/t01_core.py`（t01-b6 段，退出码 0）
- 结果：数学 A 版高二真实检索返回的 **20/20 条**证据，`normalizedTextSha256` 与封存原文一致，
  且 `原文[charStart:charEnd] == evidence.text` **逐字节相同**（半开区间、Unicode 码点）；存在跨块合并证据（≥2 块）且块间连续（缝 ≤2 码点）；
  覆盖含 `$` 公式片段（`evidence/t01-b6-mathA-result.json` 存有全文样本）。
- 新代（重建后）重复同一核验 → 同样逐字节一致（t07b「新代证据仍与不可变原文逐字节一致」）。
- 详解引用侧：篡改 `charStart` / `evidenceId` / `normalizedTextSha256`，以及用**范围外**（物理）引用配数学快照 → 一律 409 `RAG_EVIDENCE_UNAVAILABLE`（t05a 4/4）。

### 2.7 失败不伪装成功 → **pass（必须项）+ 1 项口径问题**

- 命令：`python A1/scripts/t07a_rebuild_failure.py`、`t09_failure_modes.py`（退出码 0 / 1）
- 触发条件与结果：
  - `docker stop zqky-qdrant-test` → `/rag/stream` 报 **`QDRANT_UNAVAILABLE`**（不是 `no_evidence`）；
  - Embedding 指向不存在端口（11999）→ `/rag/stream` 报 **`EMBEDDING_UNAVAILABLE`**；`/embedding-models` 报 `available=false` + 原因 + 空列表（不冒充成功）；
  - 本地概括真实 HTTP 到不存在端口 → **`RAG_SUMMARY_UNAVAILABLE`(503)**，且服务层失败时**保留证据**、状态 `partial`、理由含「保留教材原文供核对」（替身注入，明确标注）；
  - 未装配（`create_app(bootstrap_textbooks=False)`，Host 用回环）→ `/rag/status`、`/rag/stream`、`/textbooks`、`PUT /teaching-settings` 全部 **503 `SERVICE_UNAVAILABLE`**；未实现路由仍 501。
- 证据：`evidence/t07a-rebuild-failure.json`(16/16)、`t09-failure-modes.json`(12 项，2 FAIL = 下述口径问题)
- **口径问题 P1**：Embedding 服务不可达时，`/rag/status.retrieval.available` 与 `summarization.available` 仍报 `true`
  （`providerUrl` 指向死端口）。状态只反映「装配 + 索引代就绪」，**不做上游可达性探测**，操作者会看到「检索可用」而每次请求都失败。
  同一时刻 `/embedding-models` 是如实报不可用的。`docs/API.md` 未定义 `available` 的确切含义，故记为口径问题而非硬缺陷。

### 2.8 定位与详解（SSE / 重启 / 模型 / 离线）→ **pass**

- 命令：`python A1/scripts/t01_core.py`（t01-b8a 段）、`t05a_explain.py`、`t05b_restart.py`（退出码均 0）
- 定位协议：事件编号自 1 严格递增；首事件 `message.start`；**定位成功后以 `wait-user` 收尾且不出现 `message.end`**（按真实协议断言）；
  `afterEventId=2` 续传编号从 3 起、序列与首次一致；跨会话恢复同轮 → 403 `RAG_SESSION_MISMATCH`；同轮换题 → 409 `RAG_TURN_CONFLICT`；`afterEventId` 越界 → `RAG_EVENT_CONFLICT`。
- 重启语义：重启后（进程内无任何会话）用**重启前冻结的 `scopeSnapshot` + `evidenceRefs`** 详解 → 成功并产出文本（不依赖 600 秒缓存）；
  同一 (sessionId, turnId) 且 `afterEventId>0` 续传 → **410 `RAG_TURN_EXPIRED`（不偷偷重跑）**；该轮的 reply/cancel 同样 410；重启后新轮次正常。
- 详解语义（真实 deepseek，用户 `.env` 凭证、`callable=true`）：
  使用请求指定的 profile（换另一个 profile 也成功且 `message.start.modelProfileId` 回显该值；不存在的 profile → 明确失败，不回落默认）；
  `Qdrant 停机时详解仍成功` → 证明**不触发检索**、不依赖向量库（X02）；
  `message.end.finishReason ∈ {stop,length,unknown}`。
- 证据：`t01-b8a-sse.json`(9/9)、`t05a-explain.json`(14/14)、`t05b-restart-explain.json`(6/6)、`t07a`（离线详解段）、
  答案原文 `evidence/t05a-explain-answer.txt`、`evidence/t07a-explain-offline.txt`
- 预算（`CONTEXT_TOO_LARGE` 不截断）：代码路径与单测覆盖（`build_explanation_request` 固定部分超限即 413、历史整条丢弃、原题/追问/证据不截断）。
  **我未在浏览器/HTTP 上构造一次真实 413**（`not_run`，见 §6）。

### 2.9 澄清提交幂等 → **pass**

- 命令：`python A1/scripts/t01_core.py`（t01-b9 段，退出码 0）
- 结果：首次提交 200 `accepted`；**同 submissionId 同载荷**重复提交 200 且结果一致；**同 submissionId 不同载荷** → 409 `IDEMPOTENCY_CONFLICT`；
  旧 `interactionId` 再提交 → `RAG_INTERACTION_EXPIRED`/`RAG_TURN_CLOSED`。
- 证据：`evidence/t01-b9-clarify.json`(5/5)

### 2.10 题库隔离与语义 → **pass**

- 命令：`python A1/scripts/t08a_question_bank.py`、`t10_organize.py`（退出码均 0）
- 源码级：`services/question_bank/**`、`repositories/question_bank/**`、`api/v1/question_bank.py` **没有任何** `vector_store/qdrant/collection` 引用；
  唯一与教材模块的耦合是 `MAX_UPLOAD_BYTES` 常量与 multipart 解析工具；自己的 SQLite + 自己的 blob 存储。
- 运行级：导入/校对/确认全过程前后，**生效索引代的教材 collection 点数完全不变**（9462 → 9462），未新建 collection。
- 语义：未归属原文块在导入详情中**可见**（含「本节小结」段）；缺答案草稿如实标注 + 警告，不编造；
  内容不变时 `reviewState=reviewed` 保留，**编辑内容后回到 `needs_review`**；
  重复指纹**不含答案与解析**（同题干不同答案 → 同指纹）；重复题默认 skip 并记录 `duplicateOfQuestionId`（不静默丢弃）；
  `edit_as_new` 在内容确实不同后才允许入库；确认入库单事务（一条 revision 不符 → 无半批写入）；同 submissionId 同载荷幂等、不同载荷 409。
- AI 整理（**真实本机 qwen2.5:7b**）：返回逐条 `pending` 建议，草稿在被应用前**一字未改**；`base_draft_revision` 不符 → 拒绝；
  正确 revision → 应用且回到 `needs_review`；同一建议不能重复应用；`accept=false`（忽略）不改草稿。
- **功能缺陷 D2（交总控）**：前端把「默认聊天模型 profileId」（UUID，如 `63b3ffdc…`）作为 `modelProfileId` 传给
  `POST /question-imports/{id}/organize`，而后端 `OllamaOrganizerModel` **把该字段直接当 Ollama 模型名**发给本机 `/api/chat`。
  实测：传默认 profileId → `state=failed, errorCode=ORGANIZER_MODEL_MISSING, suggestionCount=0`（如实失败，但**功能在用户真实配置下不可用**——
  用户的默认聊天模型是云端 deepseek，本机 Ollama 没有该名字的模型）；传 `qwen2.5:7b` 才成功。
  最小复现：`python A1/scripts/t10_organize.py` 第 2 项。
- 真实模型输出质量观察（非断言）：两条建议的 JSON 形状合法，但第一条把「解析」文本同时塞进 `stemMarkdown` 与
  `explanationMarkdown`（重复）——这正是「建议必须人工校对」的设计价值所在。
- 证据：`t08a-question-bank.json`(22/22)、`t10-organize.json`(12/12)、`t10-organize-job.json`、`t08a-qdrant-counts.json`

### 2.11 历史兼容 → **pass**

- 命令：`python A1/scripts/t11_boundaries.py`；浏览器级 `node A1/scripts/history-compat.mjs`、`legacy-chat.mjs`（退出码 0）
- 结果：
  - 旧浏览器本地登记：`/knowledge-bases`「历史登记」列出旧条目并明示「**不参与真实检索**」；旧入口链接仍是
    `/knowledge-bases/[kbName]`（URL 编码正确）；详情页可打开且明示「解析与索引为显式模拟…真实检索服务未接入」。
  - 旧 v1 聊天消息（`rag` 形状含 `subject/citations/explanations`，无任何 v2 字段）：出现在会话列表、正文可读、不报「数据格式不受支持」；
    打开旧会话**不发起任何** `/rag/stream|reply|cancel|explain` 请求（不猜造 v2 引用、不偷偷重跑）。
  - 单测侧另有：旧轮缺范围快照时「继续本轮」如实拒绝；续传回传该轮冻结快照而非当前选择（`rag-history.test.ts` 3/3）。
- 证据：`evidence/t15-history.json`、`t15b-legacy-chat.json`、`t11-known-boundaries.json`
- 课程引用未被本批改动（未改 `courses-store`/`course-session` 相关代码；相关单测与 e2e 全绿）。

### 2.12 视觉与可访问性 → **pass**

- 命令：`node A1/scripts/visual-a1.mjs`（退出码 1，2 项失败见下）；截图 `A1/screenshots/*.png`（**我自己生成并逐张看过关键页**）
- 覆盖：`/knowledge-bases`、`/knowledge-bases/libraries/[id]`、`/question-bank`、`/settings#embedding`、`/chat` × 三视口（1440×900 / 1920×1080 / 390×844）= 45 组。
- 结果：**45/45 无横向溢出**（`scrollWidth-clientWidth ≤ 1` 且无 offender）；错误注入（5 组 503）**全部出现 `role="alert"`**；
  键盘 Tab 10 次可达 ≥5 个可聚焦元素且焦点 outline 可见（3 个页面全通过）；
  `prefers-reduced-motion: reduce` 下 3 个页面的过渡/动画时长全部 ≤50ms。
- 我亲眼确认的页面（不是"截图存在"）：
  - `/question-bank`：导入批次列表含状态 chip（待校对/已确认入库）、草稿数、**未归属原文**数、大小与时间，内容真实；
  - `/knowledge-bases`：基础库按「年级·学科·版本」分卡，显示书册数与「已就绪」数（高一·数学·人教A版 1 册、高二·数学·人教A版 3 册…），与后端一致；
  - `/chat` 390×844：空态 + 输入框 + 建议 chips，无溢出（该页 body 文本仅 152 字属**空态正常**，我在报告里按"可接受"处理，未计为缺陷）；
  - `/chat` RAG 全流程：状态条逐项显示「检索/本地概括/原文访问/任教范围/**人工教学质量 尚未评审**」，
    显示「本轮范围：高二 · 数学 · 人教A版 · 3 册」，随后出现 **教材追问卡**（选项 + 自由输入 + 忽略/继续）——
    即 SSE 以 `wait-user` 收尾的真实界面证据。
- 交互（浏览器级，真实 API）：选「RAG 模式」→ 发送 → 前端发起 **`/api/v1/rag/stream`**（非普通聊天）；
  **单选后不自动提交**（无 `/rag/reply`）；点「继续」→ `/rag/reply` **200**，本轮继续推进不悬挂。
  证据：`evidence/t14-chat-rag.json`、`t14b-chat-cards.json`（4/4）、`t13-visual.json`
- **UI 缺陷 D6（低）**：`/chat` 右侧信息面板「对话能力边界」把「教材检索（RAG）与来源引用」硬编码标为 **规划中**，
  而同一页面已提供可用的 RAG 模式、后端 `/capabilities` 已报 `rag: ready` → 文案自相矛盾。
  位置：`apps/web/src/features/chat/InfoPanel.tsx:48`。

---

## 3. 按维度分列（必须区分）

| 维度 | 结论 | 依据 |
| --- | --- | --- |
| 工程检查 | **pass** | §1：typecheck/lint/unit(560)/pytest(546)/e2e(138) 退出码 0；test:chat 仅 R-15 既有失败 |
| 受控测试替身 | **pass** | 概括失败替身保留原文+partial；未装配服务 503；范围外候选拒绝；单测替身全绿（`t09`、`t02`） |
| 真实 Qdrant（16333） | **pass** | 9462 点、按修订/region 过滤点数与 SQLite 逐册对账一致；停机 → `QDRANT_UNAVAILABLE`；重建写入失败 → aborted |
| 真实本地 Embedding（bge-m3） | **pass** | 查询向量 1024 维、真实检索命中；`EMBEDDING_UNAVAILABLE` 语义正确；**但见 D1（digest 未核）** |
| 真实本地知识点概括（qwen2.5:7b） | **pass** | 真实证据下产出知识点：`status=ok`、1 条 `RagPoint`（标题「等差数列的通项公式推导」+ 教材原文级 summary）、20 条证据、`reason=null`；不可达时 503 且保留原文（`t07a` 真实检索全链路、`t09` 白盒）。证据：`evidence/t01-b6-mathA-result.json` |
| 真实所选聊天模型详解 | **pass** | 真实 deepseek（用户 `.env`）：message.start→text.delta*→message.end、引用回传、篡改引用被拒、断网（Qdrant 停机）仍可详解 |
| 人工教学质量 | **not_run** | 未做人工评审。我只做了 1 条目视抽样（等差数列倒序相加推导，教材依据与推导一致），**不构成质量结论** |
| 人工视觉 | **pass（含 1 项低缺陷）** | §2.12：45 组截图我自己看过关键 4 张；D6 文案矛盾 |

---

## 4. 独立发现（去重后，交总控决定）

| ID | 严重度 | 发现 | 最小复现 | 证据 |
| --- | --- | --- | --- | --- |
| **D1** | 中 | 查询路径不校验 `model_manifest_digest`（写入路径校验）；同名 tag 换权重后查询静默使用错误向量空间 | `cd apps/api && PYTHONPATH=$PWD uv run python ../../_work/rag-rebuild-v1/A1/scripts/t04_digest_gap.py` | `evidence/t04-digest-gap.json` |
| **D2** | 中 | 题库 AI 整理在用户真实配置下不可用：前端传聊天 profileId（UUID），后端当 Ollama 模型名用 | `python A1/scripts/t10_organize.py`（第 2 项） | `evidence/t10-organize.json` |
| **D3** | 中高 | 正文/习题划分仍有 2/57 册 body 占比 < 50%（数学 A 版选择性必修第一册 **47.6%**、第二册 **43.5%**）；被划为 exercise 的块里含明确正文（如 `## 1.1.2 空间向量的数量积运算`、定理证明、探究与发现），这些内容**检索不到** | `python A1/scripts/t12_region_check.py`；样本见 `evidence/t12-region-independent.json` 的 `books` | `evidence/t12-region-independent.json` |
| **D4** | 中 | README §2 缺陷#1 引用的证据 `B1-FIX-REGION/real-books-report.log` 是**空跑通过**：脚本读到「无 markdown」直接 `return`（不记失败），随后仍打印 `PASS 4/4 本`。其声称的「四册 body 63.7%–82.3%」在冻结候选上**无法复现**（我实测 47.6% / 50.2% / 70.5% / 70.6%） | `cat _work/rag-rebuild-v1/B1-FIX-REGION/real-books-report.log`；脚本 `verify_real_books.py:26-29` | 同 D3 + 该日志 |
| **D5** | 中 | 迁移源路径**已无 markdown**：`F:\人教版教材\markdown` 现含 0 个 `.md`，`migrate_textbooks.py --dry-run` 报「没有可迁移的教材」→ 迁移**不可从配置路径复现**；而归档 `F:\人教版教材.zip` 含 **58** 册 md（其中 57 册与目录 `original_file_sha256` 逐字节一致，未迁移的那 1 册= A 版数学必修第一册）。即「那册只有 OCR JSON 无 markdown」的解释与归档不符 | `uv run python ../../scripts/rag/migrate_textbooks.py --dry-run`；`python A1/scripts/t11_boundaries.py` | `evidence/t11-source-state.json`、`t11-known-boundaries.json` |
| **D6** | 低 | `/chat` 信息面板把已实现的 RAG 标为「规划中」 | 打开 `/chat` → 右侧「对话能力边界」 | `screenshots/chat-rag-4-after-continue.png`、`apps/web/src/features/chat/InfoPanel.tsx:48` |
| **P1** | 口径 | `/rag/status` 的 `available` 只表示装配+索引代就绪，不探测上游可达性（Embedding 死端口时仍报 available=true） | `python A1/scripts/t09_failure_modes.py` | `evidence/t09-failure-modes.json` |
| **P2** | 口径 | `docs/API.md` 写「只索引 `body` 区」，实际是**索引全部块**（含 exercise）。实测该代 collection 9462 点 = **7681 body + 1781 exercise**，检索时靠 Qdrant `region=body` 过滤。检索结果层面成立（按 region 过滤后每册点数 == body 块数），但文档措辞与实现不符 | `python A1/scripts/t12_region_check.py` | 同 D3 |
| **P3** | 口径 | 数学 A/B 版高二 3 册的**册次标题完全相同**，因此「A 版结果中不得出现 B 版书册标题」这类**按标题**的判据在本批真实数据上不可判定，只能按 documentId/revisionId 判 | `python A1/scripts/t01_core.py`（t01-b4 段） | `evidence/t01-b4-scope-isolation.json` |

---

## 5. 实现者「已知边界」核对真实性

| 登记项 | 核对结论 |
| --- | --- |
| 迁移覆盖 57 册（源 58 目录中 `人教A版数学必修第一册` 无 markdown） | **结果成立，原因不成立**：57 册与目录一致，`chunkTotal=9462` 与迁移报告一致；归档 zip 中该册**有** md（519387 字节），且当前源目录整体没有 md（见 D5） |
| 年级归属为规则推断（必修→高一、选修/选择性必修→高二） | **核对成立**：57 册实际归属与规则**完全一致**（无额外偏差），`学生读本` 有显式特例（→高二） |
| `chapter_path` 章节标签在真实教材上不完全准确（行号准确） | **核对成立且更严重**：物理必修第一册中含「滑动摩擦力」的 12 个块里有 11 个顶层章节被挂到「探究弹簧弹力与形变量的关系」（与实现者所述例子一致）；`chapter_path` 存在明显复用（单一路径覆盖多个块）。**但 README 所述影响方向写反了**：实测相邻块常共享（错误的）章节路径 → 邻块扩展会在**实际不同小节**的边界处合并，即"更宽松"而非"更保守"（`evidence/t11-chapter-path.json`） |
| 规则拆题属启发式；AI 整理真实模型形状未联调 | **已联调（我做的）**：真实 qwen2.5:7b 输出形状合法、逐条 pending；但见 D2（模型选择链路在用户配置下不可用）与输出质量观察（解析被重复写进题干） |
| 单步耗时超租约（90 秒）才会失权；单册远低于该值 | **核对成立**：迁移报告 57 册用时 4.7–17.6s（max 17.6s）；真实全量重建 56 册成功无失权 |
| 正文/习题划分修复（README 缺陷#1：修复后 body 63.7%–82.3%） | **不成立**：见 D3/D4 |

---

## 6. 未验范围（明确 not_run，不用「应当通过」代替）

1. **人工教学质量**：未做人工评审（1 条目视抽样不计）。知识点概括/解题的教学正确性无结论。
2. **真实 `CONTEXT_TOO_LARGE`(413)**：未在 HTTP/浏览器上构造真实超限请求（仅代码路径 + 单测覆盖 + 离线详解成功样例）。
3. **上游中途断流 / 客户端断开即关闭上游**：未做网络级观测（未见实现者提供可观测点；上游关闭逻辑按代码阅读成立，未独立实测）。
4. **扫描件 PDF → `DOCUMENT_NEEDS_OCR`**、**`.docx` 解析**、**同名模型 digest 改变后的写入拦截**（E03 写入半边）：
   未在真实文件/真实换模型上触发。
5. **E06 的"迟到 worker 无权发布"**：未构造（重建失败/删除不复活已单独验过）。
6. **BM25 负 IDF 语料**、**RRF 并列稳定性**：仅单测覆盖，未独立构造。
7. **`/question-bank/imports/[id]` 校对页三视口**：本卡 12 条未要求（同类页面 `/question-bank` 已验）；未截图。
8. **题库 AI 整理真实模型的"形状多样性"**：只跑了 1 次 2 题样本（1 批）。

---

## 7. 我启动/停止的进程与资源（收尾状态）

| 资源 | 动作 | 最终状态 |
| --- | --- | --- |
| 测试 API（A1 数据副本） | 先后起在 **8001**（只读）、**8002**（可变）、**8003**（Embedding 死端口）、**8000**（浏览器联调，已按要求登记例外） | **全部已停止** |
| 测试前端 5174（冻结 `.next` 构建产物） | `node scripts/run-web.mjs start 5174` | **已停止** |
| 测试 Qdrant 16333 | 按验收要求 `docker stop` 后 `docker start`（t07a） | **运行中（保持）**，`zqky-qdrant-test` Up |
| 正式 Qdrant 6333 / Ollama 11434 | 未停止、未配置写入 | 运行中（未触碰） |
| 其它 | `npm run test:chat` 会重建 `.next-test`（distDir 独立，`.next`/BUILD_ID 不变）；未执行任何 git 写操作 | — |
| 写入的数据 | `A1/data`（副本，被 t08a/t10 写题库、t11 只读）、`A1/data-mut`（副本，被 t06/t07b 删除书册、t07a/t07b 两次重建创建新代与 collection） | 均在 `_work/rag-rebuild-v1/A1/**` 内 |

---

## 8. 候选漂移声明（必须由总控处理）

**事实**：验收结束时重跑冻结清单，`apps/web/next-env.d.ts` 的 sha256 与 `FROZEN-CANDIDATE.json` 不一致
（期望 `1862ac4b…`，实际 `e6150b1f…`），其余 193 个文件全等，`git status` 无清单外新路径。

**原因**（已定位，不是我改的代码）：该文件是 Next 自动生成物（文件头写明 "This file should not be edited"）。
验收开始时它引用 `./.next/dev/types/...`；我按任务卡执行 `npm run test:chat`（内部 `next build` + `ZQKY_TEST_BUILD=1` → distDir `.next-test`）后，
Next 把它重写为 `./.next-test/types/...`。文件 mtime 20:47 = 该命令执行时刻；`.next/BUILD_ID` 仍是冻结值 `HTTZY44JQkMTS0U36wT00`（未被改动）。

**影响与建议**：
- 冻结清单对该生成物不稳定（任何一次 `next build` 都会改它）；建议总控在集成时把 `next-env.d.ts` 从冻结清单中剔除，
  或在冻结前最后一步统一用 `npm run build`（默认 distDir）生成后再取哈希。
- 我**没有**恢复该文件（属产品路径文件，且恢复=改产品文件，超出验收者权限），也未执行任何 git 写操作。

## 9. 给总控的下一步建议

1. **D1**：在查询路径（`HybridRetriever._embed_query` 或 `RagV2Service._locate`）接线 `require_digest`（或改为 `catalog.require_profile_digest`），
   失败用 `EMBEDDING_MODEL_CHANGED`(409)。实现者改后需**重新冻结候选**（v2）再复验。
2. **D3/D4**：先修证据链（`real-books-report.log` 必须把"跳过"计入失败），再决定是否为 region 规则加新守卫
   （例如对单册 body 占比 < 50% 也降级并告警），并在 README 用可复现的数字替换 63.7%–82.3%。
3. **D5**：确认 `F:\人教版教材\markdown` 的 md 去向（是否被外部流程清理）；迁移报告应登记「源不可复现」这一事实，或改为从 `F:\人教版教材.zip` 复现。
4. **D2**：明确唯一的"整理模型"契约（是 Ollama 模型名，还是 model-config profileId → 解析为 Ollama 模型名），前后端对齐。
5. **D6/P1/P2**：文案与文档口径修正（RAG 能力边界、`/rag/status.available` 语义、API.md 的索引范围措辞）。
6. 复验范围建议：D1 需重跑 `t04`；D3 需重跑 `t12`；D2 需重跑 `t10`；其余为文档/文案，重跑 `t13`/`t01-b8` 即可。

```text
A1 验收结论：needs_revision
通过：唯一指针 / 重建失败与取消 / 范围不串库（含三处同一范围）/ 范围变化被拒 /
      引用不可变原文 / 失败不伪装成功（必须项）/ 定位与详解（含重启与离线）/
      澄清幂等 / 题库隔离与语义 / 历史兼容 / 视觉与可访问性
未通过：模型空间一致（查询路径 digest 未校验）
独立发现：D1..D6 + P1..P3（见 §4）
```
