# A1 独立验收报告（RAG-QUALITY v1.1 · 图片清洗 / 紧凑首答 / 证据窗口 / 题库模型 / 备份恢复）

```text
任务：RAG-QUALITY-v1 / A1-VERIFY（独立验收者，只读产品代码）
验收对象：docs/qa/RAG-QUALITY-v1/FROZEN-CANDIDATE.json（98 文件 + sha256；BUILD_ID WXHZTQm_Ma2tbqT2sRCUY；基线 2f27841）
验收时间：2026-09-29 14:44 – 16:20（+0800）
本次判定：**needs_revision**（批次主体主张已独立复算通过；有 2 处需实现者修复的真实缺陷，见 §5 F1/F2）
```

判定口径：**只采信我自己重跑/重算得到的证据**；实现者报告中的数字凡未能复算的一律不采信，并要求给出替代证据。
所有写入只落在 `_work/rag-quality-v1/A1/**` 与本报告；未改任何产品代码、测试、文档、锁文件，未执行 git 写操作。

---

## 1. 结论摘要

| # | 必验边界 | 判定 | 一句话证据 |
| --- | --- | --- | --- |
| 1 | 图片清洗进入索引且原文不变 | **pass** | 我用 58 册源 markdown 独立重跑分块，10477/10477 点的 `text_sha256` 与 `indexTextSha256` 全部逐位复算一致（§4.1） |
| 2 | 不重复展示、原文默认不出现 | **pass** | 真实 SSE + 真实浏览器：知识点只在消息流出现一次，默认无 `.chat-rag-excerpt`，正文无 `> ` 原文块、无长 ev-id（§4.2、§4.8） |
| 3 | 预算与状态语义 | **partial** | 预算零越界（真实数据）；`partial/EVIDENCE_UNIT_TOO_LARGE`、`uncertain/EVIDENCE_TEXT_EMPTY` 只在替身层复现，真实数据未触发（§4.3） |
| 4 | 引用只用准入集合、越界整点拒绝 | **pass（替身）** | 定点重跑 11 例相关 pytest 全绿；真实数据上引用 ⊆ 准入集合（§4.4） |
| 5 | 图片地址不外泄 | **needs_revision** | 可见正文/预览/摘录均无泄漏；但**索引与清洗后文本有 3 个块仍含 `images/<hash>.jpg`**（块边界切断 `<img>` 标签，§5 F2） |
| 6 | 题库 AI 用当前聊天模型 | **pass** | 真实 qwen2.5:7b 与受控云端替身均走通；坏 profile 0 次上游调用；401/429/死端口错误分类正确；进行中切模型不影响冻结任务（§4.6） |
| 7 | 备份恢复真演练 | **pass** | create→verify→restore 全流程在 16333 上跑通，恢复目录被应用真实读取并答出教材首答（§4.5） |
| 8 | 数据锁与失败不伪装 | **pass** | API 持锁时备份 `DATA_LOCK_BUSY`（exit 2，零写入）；缺文件 → `status: failed` + 非零退出；`incomplete` → 应用拒绝启动（§4.5） |
| 9 | 历史兼容 | **pass（替身/前端）+ not_run（真实旧数据）** | 前端单测覆盖旧 v1/v2 可读、不误截、`readable` 缺失降级并标注；我的隔离库无历史旧数据可实测（§6） |
| 10 | 视觉与可访问性（三视口） | **pass** | 12 个页面×视口组合零横向溢出、零教材图片请求、键盘可达、`role=status` 存在、减少动画生效（§4.8） |
| 11 | 崩溃类回归 | **pass** | 我自己构造 20 例（含不等式+图片、400 图规模）全部 < 10 ms 完成，无死循环（§4.7） |

**需实现者处理的缺陷**：F1（`migrate_textbooks.py` 报告段 `NameError`，本批引入的回归，见 §5.1）、F2（3 个块的清洗后文本残留图片地址，见 §5.2）。
**不需要修复但需记录**：F3（无相关性闸门，R1 独立复现）、F4（错误码命名口径）、F5（单测偶发 flake）。

---

## 2. 冻结候选与资源核对

| 项 | 结果 |
| --- | --- |
| 清单 | `files_in_manifest=98 changedFileCount=98`，`missing=0` |
| 哈希 | 97/98 逐字节一致；**唯一不一致**：`docs/qa/RAG-QUALITY-v1/README.md`（清单 10580 B / 实 11866 B，冻结后 8 秒被追加 §6） |
| 产品代码 | 98 项中全部产品代码、测试、脚本、契约在验收开始与结束时**两次核对一致**（未发生验收期改动） |
| 前端构建 | `apps/web/.next/BUILD_ID = WXHZTQm_Ma2tbqT2sRCUY`（与冻结一致） |
| 正式 Qdrant 6333 | 只读；三代点数 `10482 / 10477 / 10477`，验收前后一致（未写入） |
| 测试 Qdrant 16333 | 只写入（我的隔离演练）；验收后保留运行；collection 全部为 `textbooks_*` |
| 隔离数据根 | `_work/rag-quality-v1/A1/dataroot`（58 册源 md 中实入 2 册数学，898 块） |

命令与退出码：

```bash
python _work/rag-quality-v1/A1/verify_freeze.py            # exit 0（唯一 HASH/SIZE 行 = README.md）
cat apps/web/.next/BUILD_ID                                # WXHZTQm_Ma2tbqT2sRCUY
curl -s http://127.0.0.1:6333/collections/{c} | …          # 10482 / 10477 / 10477
```

证据：`_work/rag-quality-v1/A1/evidence/freeze-verify.log`、`freeze-verify-end.log`

> **口径问题（点名）**：`docs/qa/RAG-QUALITY-v1/README.md` 自身在冻结清单内，却在冻结后被改。冻结记录因此**无法逐字节自校验**——
> 后续审计者看到的第一个"不一致"就是批次自己的 README。建议：冻结清单排除批次文档，或冻结后不再改文档。

---

## 3. 工程检查（在冻结候选上由我重跑）

| 检查 | 我的结果 | 退出码 | 与实现者报告 |
| --- | --- | --- | --- |
| `npm run typecheck` | 通过 | 0 | 一致 |
| `npm run lint`（`--max-warnings=0`） | 通过 | 0 | 一致 |
| `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | 第 1 次 **711/712**（1 例加载敏感 flake，见 F5）；第 2 次 **712/712（74 文件）** | 1 → 0 | 与"712 例"一致（需重跑才复现全绿） |
| `cd apps/api && uv run python -m pytest` | 853 例（collect 853，逐点全为 `.`，无 F/E） | 0 | 一致 |
| `npx playwright test`（全量 e2e） | **138 passed / 0 failed**（5.6 min）；`books-commit-safety.spec.ts:238`（台账 R-14）**本次通过** | 0 | 未复现 R-14；R-14 确为"跨批间歇"而非恒定失败 |
| `npm run test:chat` | **14 passed / 0 failed** | 0 | 一致（R-15 已修掉） |
| 定点 pytest（预算/准入/历史/幂等/详解） | `test_rag_v2_answer_quality` 11 例 + `reply_is_idempotent`/explain 5 例全绿 | 0 | — |

证据：`_work/rag-quality-v1/A1/eng-pytest.log`、`eng-typecheck-lint.log`、`eng-unit-run2.log`、`eng-unit-chat.log`、`eng-e2e.log`、`evidence/pytest-collected.log`、`evidence/pytest-targeted.log`、`evidence/pytest-reply-explain.log`

**构建产物说明（如实登记）**：`npm run test:chat` 按脚本约定重建了 `apps/web/.next-test`（BUILD_ID 由 `onW50z6JKsRwt56jZY8Kx` → `05-nCTbUgymaM4CL36PgD`，源码树相同）；
冻结的 `.next`（`WXHZTQm_Ma2tbqT2sRCUY`）未被重建，e2e 与视觉检查都跑在冻结源树的构建上。视觉检查用 `.next-test`（该构建按 `test-chat.mjs` 的既有约定内联代理到 8001），未改任何产品代码。

---

## 4. 逐维度详细结果

### 4.1 真实 Qdrant（6333 只读 + 16333 写入）

**核心复算（不接受复述）**：我用**只读归档** `F:/人教版教材.zip` 解出 58 册 markdown 到 `_work/rag-quality-v1/A1/source-md`，
独立跑 `parse_document → chunk_document(DEFAULT_CHUNK_POLICY) → retained_for_manifest`，建立 `sha256(原文切片) → 块` 索引，
再 scroll 三个 collection 的全部 payload 对账：

| collection | 点数 | `textProjectionVersion` | 原文切片在源索引命中 | 重算 `sha256(project_readable(raw).text)` == `indexTextSha256` | `point_id_for(...)` 复算一致 |
| --- | --- | --- | --- | --- | --- |
| `textbooks_62373e59…`（冗余代） | 10477 | `rag-readable-v1` ×10477 | 10477 / 10477 | **10477 / 10477** | 10477 / 10477 |
| `textbooks_e2cfc638…`（当前活动） | 10477 | `rag-readable-v1` ×10477 | 10477 / 10477 | **10477 / 10477** | 10477 / 10477 |
| `textbooks_3ff98a4b…`（批前） | 10482 | 字段缺失 ×10482 | 10477 / 10482（其余 5 点为旧划分） | 旧代不适用（恒等投影，`indexTextSha256` 缺失） | 10477 / 10477 |

- `text_sha256` 仍等于原文切片散列：10477/10477（证明"清洗只产生派生文本、原文散列不动"）。
- 新代 8683 个点清洗确实改变了索引文本（`indexTextSha256 != text_sha256`），1794 个点未变（原文无图片）。
- 6621 个原文切片含图片语法；**其中 3 个块清洗后仍含 `images/` 路径**（见 F2）。

命令：`uv run python _work/rag-quality-v1/A1/recompute_index_hash.py`（exit 0）
证据：`_work/rag-quality-v1/A1/evidence/recompute-index-hash.json`

**16333 写入演练**：用 `scripts/rag/migrate_textbooks.py --source <staged md> --data-dir <隔离根> --only math --limit 2`
真实入库 2 册（321,905 + 356,670 字符 / 427 + 471 块，`OK [1/2] [2/2]`），bge-m3 真实 1024 维、真实 Collection 发布。

### 4.2 真实 `/rag/stream`（本机 Ollama 11434 + Qdrant 16333 + 真实数据）

4 次真实请求（3 次隔离根 + 1 次恢复目录），SSE 事件序列完整：`message.start → rag.result → text.delta → wait-user`。

| 问句 | status | 首答码点 | 证据条数 | 我的核对 |
| --- | --- | --- | --- | --- |
| 集合的表示方法有哪些？ | ok | 107 | 6 | 19 项检查全过 |
| 交集可以用Venn图怎么表示？ | ok | 142 | 6 | 全过；6 条封存切片含图片语法，6 条 readable 均已去除（`removedImageCount` 1–2） |
| 一般现在时的第三人称单数形式怎么变化？（**范围外**） | **ok** | 36 | 6 | 命中数学"随机事件"，无任何相关性闸门 → **R1 独立复现** |
| 什么是空集？（恢复目录） | ok | 78 | 6 | 全过 |

自动核对项：点数 ≤3、单点 ≤90 码点、合计 ≤250、每点 ≤2 引用、证据 ≤6、单条原文 ≤6000、原文总量 ≤16000、单条清洗后 ≤1600、
每条含 `readable`、引用 ⊆ 准入集合、可见正文/预览/`text.delta` 无 `![`/`images/`、渲染正文无长 ev-id、`presentation.bodyCharCount` 与重算一致、`compact-v1/brief`。
**封存切片允许含图片语法**（`evidence[].text`），实测 6/6 含图片语法而 readable 全净 —— 与设计一致。

命令：`uv run python _work/rag-quality-v1/A1/real_rag_stream.py --base-url http://127.0.0.1:8001 … --tag q1-natural`
核对：`uv run python _work/rag-quality-v1/A1/check_stream_file.py <SSE 记录> <输出.json>`（exit 0）
证据：`evidence/rag-stream-q{1,2,3,4}-*.txt`、`evidence/stream-check-q{1,2,4}.json`、`evidence/rag-result-q{1,2,3,4}-*.json`

**定位轮过期语义（真实）**：客户端保持 SSE 打开约 60 s 后收到 `error{RAG_TURN_EXPIRED, retryable:true}`（"本轮已过期，请重新发送题目。"），
**没有偷偷重跑**；同时 `wait-user` 已给出追问卡。后端重启后由既有 `evidence[].documentRevisionId + locator` 发起详解的路径，
只在替身层验证（`test_explain_streams_without_touching_retrieval_and_rebuilds_refs` 等 5 例全绿，见 §4.4），真实数据未做（§6 not_run）。

### 4.3 预算与状态语义

- 真实数据：4 次请求 19 项预算检查**零越界**（上表）。
- `partial + EVIDENCE_UNIT_TOO_LARGE`、`uncertain + EVIDENCE_TEXT_EMPTY`、`no_evidence + NO_MATCH`：**真实数据未能触发**，仅在替身层复现：
  `test_q3_over_long_protected_unit_is_partial_with_reason_not_missing_evidence` 断言 `partial` / `EVIDENCE_UNIT_TOO_LARGE` / `evidence==[]` /
  文案含"超长公式"且**不含**"没有找到足够依据"，且不调用概括模型（`env.summarizer.calls == []`）。
- 从 payload 反推：新代建清单时已排除"清洗后为空"的块（10477 块全部非空），因此在**新代上 `EVIDENCE_TEXT_EMPTY` 基本不可达**；
  该状态码存活的意义主要在旧代/历史路径。这是我从代码 + 10477 个 payload 反推的结论，非实测。

### 4.4 准入集合与越界引用（替身）

- `test_q5_excluded_evidence_reference_is_rejected_as_a_whole_point`：越界点**整点拒绝**（保留"合法点"），
  `violation_codes` 含 `REF_NOT_ADMITTED`，且被排除的 id **从未进入模型上下文**（断言 prompt 里不含该 id）。
- `test_q5_service_second_check_uses_admitted_set`：服务端二次校验同样只认准入集合。
- `test_q4_hundred_points_are_capped_and_over_long_point_is_rejected`：100 点 → ≤3 点 / ≤250 码点，超长单点整点拒绝，最多修正一次（`corrected==1`，2 次请求）。
- 真实数据侧：4 次请求的 `引用 ⊆ 准入集合` 全过。
- 定点重跑 11 例 + 5 例（幂等/详解）全部通过（exit 0）。

### 4.5 备份恢复与数据锁（全部真跑，16333 隔离）

| 场景 | 期望 | 实测 | 退出码 |
| --- | --- | --- | --- |
| API 持有数据根锁时 `create` | 拒绝、零写入 | `DATA_LOCK_BUSY`（报出持有者 pid/标签 `api`），备份目录为空 | 2 |
| 无 API 时 `create` | 成功 | 15 文件 + 1 collection 快照 + `status: complete`，活动代 `2d2f40f1…` | 0 |
| `verify` | 通过 | 清单校验通过（15 文件 / 1 collection） | 0 |
| `restore`（16333） | 成功 | `textbooks/catalog.sqlite3`、`textbooks/{blobs,normalized,staging}`、`question-bank/question-bank.sqlite3`、`restore-state.json`；collection → `…__restored_77f36d8ded`（898 点） | 0 |
| 恢复根被应用读取 | 能读活动代与文档 | `GET /textbooks` 2 册；`/textbook-index/status` 活动代 `ready`/898 块/2 册；`qdrantAvailable: true`；**并用恢复根真实答出教材首答**（§4.2 q4） | — |
| `--isolated-qdrant 6333` | 拒绝 | "恢复拒绝指向正式 Qdrant 端口 6333…绝不覆盖正式 collection" | 2 |
| 缺 `--isolated-qdrant` | 拒绝 | "恢复必须显式指定隔离 Qdrant" | 2 |
| 目标目录已存在 | 拒绝 | "恢复目标已存在，拒绝覆盖" | 2 |
| 清单路径穿越（`restorePath=../../escape.txt`） | 拒绝 | "restorePath 不在教材/题库运行目录内"；目标目录未被创建 | 2 |
| 被引用文件缺失 | `failed` + 非零 + 不打印"完成" | `verify` 报"缺失文件"exit 1；`restore` 前置校验拒绝、不打印完成 | 1 / 2 |
| 破损数据根上 `create` | `status: failed` + 非零 | manifest `status=failed` + 4 条缺失明细，打印"备份失败，已保留失败记录" | 1 |
| `restore` 一份 `status: failed` 的备份 | 拒绝 | "清单 status=failed，只有 complete 才能恢复" | 2 |
| `restore-state.json = incomplete` | 应用拒绝启动 | uvicorn `Application startup failed`，报"数据根处于恢复未完成状态（status=incomplete），已拒绝启动以免覆盖未恢复的数据" | 3 |

命令：`uv run --directory apps/api python ../../scripts/rag/backup.py {create|verify|restore} …`；`python _work/rag-quality-v1/A1/restore_refusals.py`
证据：`evidence/backup-{lock-test,create,verify,restore,broken}.log`、`evidence/restore-refusals.json`、`evidence/restore-from-failed.log`、`_work/rag-quality-v1/A1/backup-drill/**`
备注：启动闸门的拒绝信息里**只有自然语言，没有 `DATA_RESTORE_INCOMPLETE` 字样**（该 code 只在 HTTP 响应体现）；判定依据是"拒绝启动 + 明确原因"。

### 4.6 题库 AI 使用当前聊天模型（真实本地模型 + 受控替身）

受控替身：`_work/rag-quality-v1/A1/mock_upstream.py`（OpenAI 兼容 `/v1/chat/completions`，按 model 名切换正常/401/429/慢/非 JSON，并逐请求落 JSONL）。

| 场景 | 实测 |
| --- | --- |
| 本地 profile（真实 Ollama qwen2.5:7b） | `state=succeeded`，suggestionCount 1–2（一次运行因本地模型输出非法 JSON 而 1 批失败：`ORGANIZER_INVALID_JSON`，**原文保留、草稿不变**，如实失败不伪装） |
| 云端替身 profile | `state=succeeded`，2 条建议，替身日志确认 `model=mock-ok` 两次请求 |
| profile 不存在 | HTTP 404 `code=NOT_FOUND`「模型配置不存在。」，**0 次上游调用**（替身日志计数不变） |
| 401 | `errorCode=AUTH_REQUIRED`，文案不含"内容无效" |
| 429 | `errorCode=RATE_LIMITED` |
| 死端口 | `errorCode=UPSTREAM_UNAVAILABLE`，不冤枉试题内容 |
| 替身返回非 JSON | 批级 `ORGANIZER_INVALID_JSON`（原文保留），**不是**任务级上游故障 |
| 进行中切模型（替身慢 4 s，任务飞行中把 profile 改指 `mock-after-switch`） | 改模型**确实生效**（`profileModelAfterJob=mock-after-switch`），但该任务全部请求仍是 `mock-slow`，`state=succeeded` → **冻结生效** |
| 人工草稿不被覆盖 | 整理后草稿 `stem="人工改写的题干（A1）"`、`revision=1` 不变；界面文案"AI 只给出待校对建议，永不直接覆盖人工草稿" |

命令：`python _work/rag-quality-v1/A1/qb_ai_test.py`、`python _work/rag-quality-v1/A1/qb_freeze_test.py`
证据：`evidence/qb-ai-report.json`、`evidence/qb-freeze-report.json`、`evidence/mock-upstream*.jsonl`、`evidence/qb-ai-test*.log`

### 4.7 崩溃类回归（我自己构造）

20 例输入串行计时，含：实现者最小复现（对照）、**含不等式 + 图片 + 图注**、HTML `<img>`/`<picture>`、引用式图片（定义被文字链接共用）、
转义与嵌套括号、行内代码/围栏代码里的假图片、行内/显示公式、超长 alt、文件名式 alt、泛化占位 alt、表格单元内嵌图、
只有图片无正文、未闭合方括号、连续不等号与尖括号、**400 个图片节点**、8.7k 字符大表格。

结果：**20/20 pass，0 fail**；最慢 7 ms（400 图）与 2 ms（大表格）；全部满足"来源映射坐标不越界"；
设计允许保留的图片语法（代码保护区字面示例、仍被文字链接使用的引用定义、非法 Markdown）单独标注、不计为泄漏。

命令：`uv run python _work/rag-quality-v1/A1/probe_projection_crash.py`（exit 0）
证据：`_work/rag-quality-v1/A1/evidence/projection-crash.json`

### 4.8 人工视觉与可访问性（我自己看截图 + 实测）

工具：Playwright（msedge，`reducedMotion: 'reduce'`）对 `/chat`（真实 RAG 首答 + 来源两级展开 + 追问卡）、`/knowledge-bases`、
`/question-bank`、`/question-bank/imports/<id>`（校对台）、`/settings#embedding` 实测。

| 项 | 1440×900 | 1920×1080 | 390×844 |
| --- | --- | --- | --- |
| 页面级横向溢出 | 无 | 无 | 无（`scrollWidth == innerWidth`） |
| 教材图片网络请求 | 0 | 0 | 0 |
| 可见正文 `![` / `images/` / 长 ev-id | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 来源面板（展开后）同上 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| `role="status"`/`alert` | 3 | 3 | 3（检索/概括/原文/范围/人工质量 + 等待提示） |
| 键盘 Tab 前进 | 焦点移动 6 个不同控件，含可见焦点环 | 同 | 同 |
| `prefers-reduced-motion: reduce` | 生效；采样 400 个元素**无任何动画/过渡**（`animationName=none`、`transitionDuration≈0`） | 同 | 同 |
| 追问卡（教材追问 + 选项） | 存在 | 存在 | 存在 |
| 来源两级折叠 | "查看教材依据（6 条）" → 6 个「展开摘录」；默认 `aria-expanded=false` 且 **DOM 中无 `.chat-rag-excerpt`** | 同 | 同 |
| 图片提示 | 面板显示"已省略图片，未识别图中内容。" | 同 | 同 |

- 图片请求断言：全流程只出现 3 个**第一方静态图标**（`/provider-icons/{qwen-color,ollama,openai}.svg`，模型选择器用），**没有任何 `images/` 教材图片请求**。
- `/settings` 390 宽有 3 个导航链接文本超出视口，但 `.settings-index` 是 `display:flex; overflow:auto; white-space:nowrap` 的横向条带（`settings.css:165`），
  **页面级 `scrollWidth` 仍为 390**，即可在条带内横向滚动到达——按"不新增页面滚动"判为 pass，并如实记录该条带行为。
- 校对台：草稿编辑 / 未归属原文 / 拆分 / AI 整理（模型不可用时给可读提示并禁用按钮，不发上游）全部渲染正常；两视口零溢出。
- `/settings#embedding`：当前模型 bge-m3 / 1024 维 / 索引代 / state=ready / 块 898 / 教材 2 / 任教范围已就绪；候选含"非 Embedding 模型"标注。

证据（可自行查看）：`_work/rag-quality-v1/A1/shots/*.png`（chat/knowledge-bases/question-bank/question-bank-review/settings × 三视口）、`shots/visual-report.json`、`evidence/visual-check.log`

---

## 5. 需要实现者处理的缺陷（最小复现）

### 5.1 F1（本批引入的回归 · 高）`scripts/rag/migrate_textbooks.py` 报告段 `NameError`，迁移成功后退出码 1 且不写报告

- 触发条件：任何一次 `migrate_textbooks.py` 运行（无论是否传 `--report`）。
- 实测：两册真实入库成功（`OK [1/2] …427 块`、`OK [2/2] …471 块`）之后，构建报告时抛异常：

```text
Traceback (most recent call last):
  File "…/scripts/rag/migrate_textbooks.py", line 275, in migrate
    return _migrate_locked(args, settings, tasks=tasks, skipped=skipped)
  File "…/scripts/rag/migrate_textbooks.py", line 426, in _migrate_locked
    "sourceRoot": str(source_root),
NameError: name 'source_root' is not defined
MIGRATE_EXIT=1
```

- 根因：本批为加数据根排他锁把函数体抽成 `_migrate_locked(args, settings, *, tasks, skipped)`，
  但报告字典仍引用 `migrate()` 的局部变量 `source_root`（基线 `2f27841` 中该变量在同一函数作用域内，故基线无此问题）。
- 影响：① 运维看到的是"迁移失败"（exit 1），实际数据已写入；② `--report` 报告永远不生成；③ 收尾的 `close()` 全部跳过。
- 最小复现：

```bash
cd apps/api && uv run python ../../scripts/rag/migrate_textbooks.py \
  --source <任一含 md 的目录> --data-dir <临时目录> --limit 1
# 期望：打印 OK 后正常收尾；实际：NameError + exit 1，报告未写
```

- 证据：`_work/rag-quality-v1/A1/evidence/migrate.log`（我这次的完整输出）。

### 5.2 F2（本批核心主张的窄口 · 中）块边界切断 `<img>` 标签 → 3 个块的"清洗后文本"仍含 `images/<hash>.jpg`

- 触发条件：源 markdown 里**单行 HTML 表格**长度超过分块上限（1200 码点），切点落在 `<img …>` 标签内部。
- 实测（当前活动代 10477 点中 3 点，0.03%）：块首不是 `<img` 而是 `src="images/….jpg"/></td>…`，
  清洗器认不出"被截断的标签"，于是**图片地址留在索引文本（BM25 + 向量）与 `readable.text` 里**，可经来源预览/展开摘录显示给用户、并进入概括/详解的模型输入。
  另有 3 个块残留 `src="…` 属性片段（无路径）。
- 最小复现：

```python
from app.services.text_projection import project_readable
raw = 'src="images/8a174688….jpg"/></td><td>正四面体形</td></tr></table>'
project_readable(raw).text        # 期望：不含 images/；实际：原样保留
# 源头成因（真实数据）：人教版化学选修第二册 ord=80，父行 1223 码点，块起点 70016 落在 <img 标签内部
```

- 建议方向（不代实现者决定）：投影前把块的**上下文**（或整篇/整行）交给扫描器判定跨边界的图片节点；
  或分块时禁止在 `<img`/`<picture` 标签内部切分（把"未闭合 HTML 标签"当作不可切分单元）。
- 证据：`_work/rag-quality-v1/A1/evidence/cleaned-image-syntax.json`（6 例明细）、`evidence/probe-chunk-boundary`（成因探针输出见会话/脚本 `probe_chunk_boundary.py`）。

### 5.3 F3（已登记 R1 的独立复现 · 中）无相关性闸门：范围外问题返回 `ok`

- 我在**自己的隔离语料**（高一数学 2 册）上复现：问"一般现在时的第三人称单数形式怎么变化？" → `status=ok`，给出数学知识点"随机事件表示"，证据 6 条全为数学教材。
- 与实现者登记一致（他们 10 个边界问题全部 `ok`）。两者语料不同、结论相同 → 缺口真实存在，且**不因语料规模而消失**。
- 证据：`evidence/rag-result-q3-outofscope.json`、`evidence/rag-stream-q3-outofscope.txt`。

### 5.4 F4（口径 · 低）缺少 profile 的错误码名称

`modelProfileId` 指向不存在的 profile 时返回 **HTTP 404 `code=NOT_FOUND`**「模型配置不存在。」（0 次上游调用，符合卡片要求），
而 `organizer.JOB_LEVEL_ERROR_CODES` 里的名字是 `MODEL_PROFILE_NOT_FOUND`（用于任务落库路径）。建议统一口径，便于前端区分"配置不存在"与"其他 404"。

### 5.5 F5（工程 · 低）单测加载敏感 flake（新增观察，非本批文件）

第 1 次全量 `test:unit` 出现 1 例失败：`apps/web/src/features/model-settings/embedding/EmbeddingPanel.test.tsx:166`
（`findByRole('radio', {name:/bge-m3 · 1024 维/})` → `toBeChecked` 未及时成立）；该文件单独跑 5/5 通过、第 2 次全量 712/712 通过。
归属**不在本批 98 文件清单内**，属既有测试在高并发收集/执行下的竞态。建议纳入台账（可称 R-16），与 R-14 同类管理。

---

## 6. 未验范围（not_run，明确列出）

| 项 | 原因 |
| --- | --- |
| 人工教学质量（样本/信度） | 卡片默认 not_run；本批只做机器可判定项，未做人工评分 |
| 真实数据触发 `no_evidence/NO_MATCH`、`uncertain/EVIDENCE_TEXT_EMPTY`、`partial/EVIDENCE_UNIT_TOO_LARGE` | 我的隔离语料无"清洗后为空"的命中（新代建清单已排除）也无超长受保护单元；仅在替身层复现 |
| 真实数据发起"详解"（`POST /rag/explain/stream`，含取消关闭上游、超预算保留输入） | 时间与端口预算；替身层 5 例已通过（`test_rag_v2_explain.py`），真实链路未跑 |
| 澄清提交幂等（真实 `/rag/reply`） | 替身层 `test_reply_is_idempotent_and_relocates_inside_the_frozen_scope` 通过；真实链路未跑（未构造真实澄清问答） |
| 历史兼容的真实旧数据行为（旧 v1/v2 消息、`readable` 缺失降级、`/knowledge-bases/[kbName]` 旧登记只读且不参与检索） | 我的隔离库只有新消息、无旧登记；仅有前端单测（`rag-history.test.ts`、`Message.compact-rag.test.tsx`、`message-projection.test.ts`）+ 代码阅读证据 |
| 题库与教材向量库"完全隔离"的行为级验证 | 只做了静态核对：16333 全部 collection 均为 `textbooks_*`，题库只用自己的 sqlite/blobs，未见第二套向量库 |
| R2（1600 紧于 6000 导致邻块退化）、R4（历史草稿缺 `cleanedTextEmpty` 标记） | 未独立重测；采信实现者登记，未做反证 |
| R3（强杀 running 任务的闸门自愈） | 未构造强杀场景；本次未跑 `rebuild_index.py`（避免动 16333 以外资源与重建耗时） |
| 三索引代的历史口径逐点核对（`932d34c9` 的旧划分/旧清洗与代码同构） | 只核对了点数、`textProjectionVersion` 缺失、point id 复算与"原文切片可在源里找到 10477/10482" |
| 题库 AI 的云端真实供应商 | 替身（本地自建 OpenAI 兼容服务）代替，未使用任何真实云端凭证 |

---

## 7. 我启动/停止的进程与资源（验收后状态）

启动过（并已全部停止）：

| 资源 | 用途 | 状态 |
| --- | --- | --- |
| `uvicorn app.main:app --port 8001`（`ZQKY_DATA_DIR=_work/rag-quality-v1/A1/dataroot`，`ZQKY_QDRANT_URL=16333`） | 真实 `/rag/stream`、题库 AI、恢复根读取、备份锁测试 | **已停止** |
| `uvicorn`（`ZQKY_DATA_DIR=…/backup-drill/restored-01`，端口 8001） | 恢复目录可读性 + 真实首答 | **已停止** |
| `uvicorn --port 8011`（`restore-state=incomplete`） | 启动闸门拒绝启动验证 | 自行退出（exit 3） |
| `node scripts/run-web.mjs start 5174`（`ZQKY_TEST_BUILD=1`） | 三视口视觉与交互实测 | **已停止** |
| `python _work/rag-quality-v1/A1/mock_upstream.py --port 18099` | 题库 AI 的受控云端替身 | **已停止** |
| `npx playwright test` / npm 构建等子进程 | 工程检查 | 已完成退出 |

保持运行（未动）：测试 Qdrant **16333**（`zqky-qdrant-test`，按要求保留）；正式 Qdrant **6333**（只读，未写入，三代点数不变）。

写入位置：`_work/rag-quality-v1/A1/**`（证据、脚本、隔离数据根、备份演练产物、截图）与本报告。未触碰正式 `.local-data`、正式 Qdrant、权威文档与 Git。
