# A1-REPORT-02 · RAG-REBUILD v1.0 独立验收（r2 窄复验）结果卡

```text
任务 ID / 版本：RAG-REBUILD-v1 / A1-VERIFY r2（窄复验：只复验 r1 点名的失败/缺口 + 回归确认）
负责人：独立验收者（只读产品代码；未改任何产品/测试/契约/锁文件；未执行任何 git 写操作）
候选 SHA：c2f31ec0a70fc9b9e9d38479b6c193416c19befb（工作树，204 个变更文件）
前端构建：BUILD_ID qAq9_vzcvKIFhfkQ7_7cy（= r2 记录声明值，我核对 .next/BUILD_ID 一致）
冻结核对：202/204 sha256 与记录一致；3 处漂移见 §1.0（均为总控自有文档与冻结工具自引用，非产品代码）
结论：pass（附条件）
```

**一句话**：r1 点名的 1 项 fail（D1）与 5 项缺陷（D2/D3/D4/D5/D6）+ 1 项口径（P1）**逐条修好并经我独立复现**；
新索引代上的关键不变量（唯一指针 / 范围不串库 / 引用逐字节 / SSE / 澄清幂等 / 题库语义 / 真实云端详解）**无回归**；
新增 4 条观察（1 条区域重叠缝的精确量化、1 条 README 口径、1 条冻结工具自引用、1 条仍是既有质量边界），均不阻塞。

---

## 0. 本次复验的环境与资源

| 事项 | 内容 |
| --- | --- |
| 独立数据 | `_work/rag-rebuild-v1/A1r2/data`（`migrate-v3/data` 的副本）、`A1r2/data-ingest`（摄取冒烟用副本） |
| 真实服务 | Qdrant 16333（`zqky-rag-test`）、Ollama 11434（bge-m3 + qwen2.5:7b）、真实云端 deepseek（用户 `.env`） |
| 受控替身 | 我自建的假 Ollama（`127.0.0.1:11440`，**同名 tag 换权重**：digest 与登记不符但返回合法 1024 维向量） |
| 我起的进程 | 测试 API 8001/8003/8004/8005/8006、浏览器用 8000、前端 5174、假 Ollama 11440 —— **全部已停止** |
| 未触碰 | `migrate-v3/data` 原目录、`migrate-isolated/**`、其他任务证据目录、正式 Qdrant 6333、`.local-data` |

---

## 1. 逐项复验结果

### 1.0 冻结核对与漂移（先说清"我验的是哪个候选"）

| 项 | 结果 |
| --- | --- |
| 清单长度 / BUILD_ID / HEAD | 204 条；`.next/BUILD_ID == qAq9_vzcvKIFhfkQ7_7cy`；HEAD == `c2f31ec` ✔ |
| sha256 逐文件重算 | **202/204 一致**，2 条不一致（下） |
| 清单外新路径 | 2 条（`docs/replica/AI_INTERACTIONS.md`、`docs/replica/PAGE_MATRIX.md`） |

漂移明细（**均非产品代码**，请总控在提交前对齐；证据 `_work/rag-rebuild-v1/A1r2/evidence/r2-frozen-verify-final.json`）：

1. `docs/CURRENT_STATUS.md`：记录里 `df8c94ef…`，实际 `33cca7e0…`（mtime 22:12，与冻结同一分钟）。
2. `docs/qa/RAG-REBUILD-v1/FROZEN-CANDIDATE.json`：**工具自引用**——`scripts/rag/freeze.py` 用
   `git status --porcelain -uall` 枚举文件，会把**清单自身**也列进去并在写盘前取哈希，因此该条**永远无法自洽**
   （r1 的清单没有这一条，r2 起出现）。建议 `freeze.py` 排除该路径。
3. `docs/replica/AI_INTERACTIONS.md` / `PAGE_MATRIX.md`：mtime 22:13，**晚于冻结**，故不在清单内（内容确与本批
   题库/教材页相关，像是冻结后补的矩阵更新）。
4. `apps/web/next-env.d.ts`：内容与清单**一致**（都是 `.next-test` 变体）；我重跑 e2e/test:chat 后 mtime 变化但
   字节未变；按你们 README 的说明，提交前会还原——**非缺陷**。

### 1.1 D1 查询路径模型身份核验 → **pass**

命令 / 退出码：
`cd apps/api && PYTHONPATH=$PWD A1_API=http://127.0.0.1:8004 uv run python ../../_work/rag-rebuild-v1/A1r2/scripts/r2_d1_digest.py` → **0**

| 断言 | 结果 |
| --- | --- |
| 受控替身（同名 tag 换权重）：客户端收到 `EMBEDDING_MODEL_CHANGED` | PASS（SSE `error` 事件，见下"口径"） |
| **身份核验在嵌入之前**：替身收到 **0 次** `/api/embed` | PASS（`{"embed":0,"chat":0,...}`） |
| 替身确实能返回合法 1024 维向量（证明拒绝不是因为上游坏，测试有力量） | PASS |
| 白盒：篡改登记 digest → 抛 409 `EMBEDDING_MODEL_CHANGED` 且**不返回向量** | PASS |
| 白盒：整条 `retrieve()` 失败且 **Qdrant 检索次数 = 0**（零次向量检索） | PASS |
| 注册模型不在本机 → 同一码（不静默换模型） | PASS |
| 适配器无清单核对能力 → 同一码（不能证明身份就不检索） | PASS |
| 服务不可达 → `EMBEDDING_UNAVAILABLE`(503)，与"换权重"可区分 | PASS |
| 正常 profile → 仍返回 1024 维查询向量 | PASS |

证据：`A1r2/evidence/r2-d1-digest.json`（10/10）、`r2-calls-fake-ollama.json`

> **口径记录（非缺陷）**：流已开始（`message.start` 由 `start()` 先发）后的失败按既有 SSE 契约以 `error` 事件回传，
> 因此"409"体现为**错误码**而不是 HTTP 状态；HTTP 409 只可能出现在流开始前（范围类错误）。若总控要求 HTTP 409，
> 需把身份探测提前到 `start()`（会给每轮增加一次本地 HTTP 探测量）。我按"客户端必须拿到 `EMBEDDING_MODEL_CHANGED` +
> 零次嵌入 + 零次检索"判定通过。

### 1.2 D2 AI 整理只用本机 Ollama 模型名 → **pass**

命令 / 退出码：
`cd apps/api && PYTHONPATH=$PWD A1_API=http://127.0.0.1:8004 uv run python ../../_work/rag-rebuild-v1/A1r2/scripts/r2_d2_organizer.py` → **0**

| 断言（受控替身上游，可计数 `/api/chat`） | 结果 |
| --- | --- |
| 传聊天 profileId（UUID 形态）→ 拒绝 `ORGANIZER_MODEL_MISSING` | PASS |
| **UUID 分支：上游 `/api/chat` 调用次数 +0** | PASS |
| 传不在场的模型名 → 拒绝，且 `/api/chat` **+0** | PASS |
| 省略 `modelProfileId` → 解析服务端默认并**真的调用**本机上游（+2） | PASS |
| 空串 → 等价服务端默认（+2） | PASS |
| 上述被拒/失败路径**不改动任何草稿** | PASS |
| 真实本机 Ollama（8001）：`/rag/status.summarization.model` = `qwen2.5:7b`（前端取值来源） | PASS |
| 真实：显式传本机模型名 → 至少一次 `succeeded`，产出**pending** 建议 | PASS |
| 真实：省略 → 服务端默认同样可用 | PASS |
| 真实：整理后草稿内容**一字未改** | PASS |

证据：`A1r2/evidence/r2-d2-organizer.json`（14/14）
前端接线已核对：`apps/web/src/features/question-bank/model-profile.ts` 明确定义
「只能传本机模型名、空串=服务端默认、取值来自 `/rag/status.summarization.model`、不可用时禁用并给原因」，
与后端契约一致（对应单测 `model-profile.test.ts` 已入候选并通过）。

### 1.3 D3 块级正文/习题划分（region v3，58 册）→ **pass（含精确残留量化）**

命令 / 退出码：
`cd apps/api && PYTHONPATH=$PWD uv run python ../../_work/rag-rebuild-v1/A1r2/scripts/r2_d3_region.py` → **0**

| 断言（我的独立计算，口径 = Σ body 块字符 / Σ 全部块字符） | 结果 |
| --- | --- |
| 索引代使用 `regionRulesVersion = zqky-region-v3` | PASS |
| 存活册数 = **58**（较 r1 的 57 多 1 册，即从归档补回的 A 版必修第一册） | PASS |
| **58/58 册 body ≥ 50%**（min = **56.48%**，max = 100%） | PASS |
| 我 r1 点名的两册已修复：A 版选择性必修第一册 **47.6% → 64.1%**、第二册 **43.5% → 56.5%** | PASS（逐册同口径前后对比，57 册可比） |
| 我 r1 举证的正文块（`## 1.1.2 空间向量的数量积运算`）现在 `region=body` | PASS |
| Qdrant 每册点数 == 登记块数；`region=body` 过滤后 == body 块数 | PASS |
| 与总控自报数字的一致性：A 版必修第二册 63.6%、物理必修第一册 82.0%、生物学必修1 82.1% | **逐条一致** |

`「块不跨区」` 我用**生产路径**（`ImmutableSource.region_spans`）逐块核验 10,482 块，结论需要加限定：
**1156 块（11.0%）在"重叠缝"处跨界，最大缝 121 字符（= overlapChars 120 + 1），无实质跨区**（详见 §4 R2-A）。
证据：`r2-d3-region.json`（11/11）、`r2-d3-sample-1-1-2.json`、`r2-d3-cited-compare.json`、`r2-d3-seam.json`

### 1.4 D4 空跑证据作废 + 跳过计入失败 → **pass**

命令 / 退出码：`python - <<'PY' …（见报告末尾复现段）…` → **0**；证据 `A1r2/evidence/r2-d4-void-log.json`（4/4）

| 断言 | 结果 |
| --- | --- |
| 原空跑日志改名 `real-books-report-VOID-empty-pass.log`，**488 字节、仍含原 `PASS 4/4`**（原字节保留） | PASS |
| 新日志 `real-books-report-v14.log` 的四册块级 body 率 = 64.1 / 63.6 / 82.0 / 82.1 —— **与我的独立测量逐条一致** | PASS |
| 把源目录换成空目录运行 → **退出码 1** + 打印 `FAIL …（跳过计失败）`（"空跑通过"已不可能） | PASS |
| 代码层：缺失/重复的引用样本也计入 `cited_failures` | PASS |
| 作废声明诚实性：README §2 第 1 行与 §4 D4 行都已写明"该日志与那组数字作废" | PASS |

> 说明：脚本现在指向的 `_work/rag-rebuild-v1/source-md` **当前没有 md**（v14 那次运行的临时来源已清理），
> 因此现在直接跑它是 **exit 1**——这正是修复后的正确行为，而不是缺陷。

### 1.5 D5 迁移来源可复现（`--source-zip`）→ **pass**

命令 / 退出码：
`cd apps/api && uv run python ../../scripts/rag/migrate_textbooks.py --dry-run --source-zip "F:/人教版教材.zip" --staging <A1r2>/staging` → **0**

| 断言 | 结果 |
| --- | --- |
| `--dry-run --source-zip` 识别 **58 册**（含此前缺失的 `人教A版必修第一册`，列在第 1 项） | PASS |
| 解出的暂存目录含 **58** 个 `.md`；支持 `--staging` 显式指定；默认按运行独占 | PASS |
| README §3.1 的更正与事实一致：源目录已无 md、归档 58 册、57 册与目录散列逐字节一致、"只有 OCR JSON"只对**当时的目录**成立、并发共用暂存会把 58 截成 56 | PASS |

证据：`A1r2/evidence/r2-d5-source-zip.log`（含命令与 58 行清单）

### 1.6 D6 `/chat` 能力边界面板 → **pass**

命令 / 退出码：`node _work/rag-rebuild-v1/A1r2/scripts/r2_visual.mjs` → **0**（24/24）
环境：前端 5174（冻结构建）+ 测试 API 8000（A1r2 数据；**仅因构建 rewrite 指向 8000，用后已停止**）

| 断言 | 结果 |
| --- | --- |
| RAG 行存在且显示真实状态徽标：**「已实现 · 就绪」** | PASS（截图肉眼确认） |
| 面板整段文本**不再出现「规划中」** | PASS |
| 逐项明细显示：检索可用（向量+词法）/ 本地概括可用（qwen2.5:7b）/ 原文访问可用 / 任教范围已就绪 | PASS（截图） |
| 保留 **「人工教学质量：尚未验收」** | PASS |
| 注入 `/capabilities` + `/rag/status` 双 503 → 显示 **「状态未知」+「读取失败」+ 重试**，不回落成"规划中/可用" | PASS |
| 其余行按真实状态：附件「暂未接入」、MCP/Skills「未接入」 | PASS |

证据：`A1r2/screenshots/chat-capability-panel.png`、`chat-capability-panel-failed.png`、`A1r2/evidence/r2-visual.json`

### 1.7 P1 `/rag/status` 上游可达性探测 → **pass**

命令 / 退出码（与 r1 同一脚本，指向"Embedding 死端口"实例）：
`cd apps/api && PYTHONPATH=$PWD A1_API=http://127.0.0.1:8003 uv run python ../A1/scripts/t09_failure_modes.py` → **0**

| 断言 | r1 | r2 |
| --- | --- | --- |
| `/rag/status` 检索项如实报不可用 | FAIL | **PASS** |
| `/rag/status` 摘要项如实报不可用 | FAIL | **PASS** |
| 其余 10 项（`EMBEDDING_UNAVAILABLE`、`/embedding-models` 如实、概括 503、替身保留原文、未装配 503×4、501） | PASS | **PASS** |

证据：`A1r2/evidence/t09-failure-modes.json`（12/12）；r1 对照 `A1/evidence/t09-failure-modes.json`

### 1.8 P2 / P3 文档口径 → **pass**

| 断言 | 结果 |
| --- | --- |
| `docs/API.md:230-231`、`docs/PROJECT_GUIDE.md:302-303` 已把口径写成「全部块都写入向量库…检索时用过滤器限定 `region=body`——即**只检索正文**，不是只索引正文」 | PASS（与我实测 9,462 = 7,681 body + 1,781 exercise 一致） |
| README §3.2 同步订正并给出 9,462/7,681/1,781 三个数字 | PASS |
| P3：README §4 明确「A/B 隔离判据一律用 `documentId`/`revisionId`，不用标题」 | PASS |

---

## 2. r1 已验、r2 **未重跑** 的项（及理由）

| r1 项 | r2 是否重跑 | 理由 |
| --- | --- | --- |
| B1 唯一指针 | **重跑**（t01-b1，10/10） | 新索引代 |
| B3 重建失败/取消保留旧索引、删除不复活 | **未重跑** | `textbook_index/service.py`、`textbook_catalog/**` 不在 r2 改动面（我按 mtime + 清单核对了改动文件列表）；相关路径由总控的全量重建（58 册成功）与 pytest 覆盖 |
| B4 范围不串库 | **重跑**（t01-b4，14/14） | 新索引代 + region 规则变更 |
| B5 范围变化 409 | **未重跑** | `rag_v2/scope.py`、catalog 未在改动面 |
| B6 引用不可变原文 | **重跑**（t01-b6，6/6；另在摄取冒烟中复验） | `evidence.py`、`regions.py`、`chunking.py` 均改了 |
| B7 失败不伪装成功 | **重跑**（P1 的 t09，12/12） | `summary.py` 改了状态探测 |
| B8 定位/详解/重启 | **重跑**（t01-b8a 9/9、t01-b9 5/5、t05a 14/14） | `rag_v2/service.py`、`evidence.py` 改了 |
| B9 澄清幂等 | **重跑**（t01-b9，5/5） | 同上（reply 在 service.py） |
| B10 题库隔离与语义 | **重跑**（t08a 22/22 + D2 14/14） | `question_bank/service.py`、`organizer.py`、`schemas/question_bank.py` 改了 |
| B11 历史兼容 | **未重跑** | `store.ts`/`chat-repository.ts`/`knowledge-catalog.ts`/`HistoryRegistrations.tsx`/`rag-history*` 均不在改动面 |
| B12 视觉与可访问性 | **重跑（15 组合 + D6 + a11y 抽样）** | `InfoPanel.tsx`、`chat.css` 改了 |

---

## 3. 回归确认（新索引代 / 真实链路）

| 检查 | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 核心不变量套件（B1/B4/B6/B8/B9 共 44 项） | `uv run python ../A1/scripts/t01_core.py`（A1_API=8001, A1_DATA=A1r2/data） | 0 | **44/44 PASS** |
| 真实云端模型详解（deepseek，用户凭证） | `uv run python ../A1/scripts/t05a_explain.py` | 0 | **14/14 PASS**（含篡改引用被拒、换 profile 生效、非存在 profile 明确失败） |
| 题库结构与语义 | `uv run python ../A1/scripts/t08a_question_bank.py` | 0 | **22/22 PASS**（第二次运行以触发重复题分支） |
| **真实摄取路径冒烟**（chunking/regions 改了 → 我另做了一条端到端） | 见下 | — | **PASS** |

摄取冒烟（`A1r2/data-ingest` 副本 + 8005，样本 `A1r2/sample-ingest.md`）：
`POST /textbook-imports` 201 → `PATCH`（改分类）200 → `POST /commit` 200 → job **succeeded**（2 块）→
新修订进入当前索引代（`state=ready`）→ 用它做 selection 定位：`status=ok`、2 points、1 条证据且
**与封存原文逐字节一致**，证据只取 `body` 块（习题块被正确排除）。
证据：`A1r2/evidence/r2-ingest-commit.json`、`r2-ingest-locate.json`

工程检查（全部在 r2 候选上重跑）：

| 检查 | 命令 | 退出码 | 我的结果 | 总控自报 |
| --- | --- | --- | --- | --- |
| 类型检查 | `npm run typecheck` | 0 | 通过 | 通过 |
| Lint | `npm run lint` | 0 | 0 警告 | 0 警告 |
| 单测 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | 0 | **69 文件 / 575 例通过** | 69 文件 575 例 |
| 后端 | `cd apps/api && uv run python -m pytest -p no:cacheprovider --tb=short -ra` | 0 | **574 passed** | 574 |
| e2e | `npx playwright test` | 0 | **138 passed**（5.6m） | 138 passed |
| 集成 | `npm run test:chat` | 1 | **13 passed / 1 failed**，唯一失败 = `chat-live.spec.ts:59`（R-15 旧 selector，45s 超时） | 13 + 1（R-15） |

证据：`A1r2/logs/{typecheck-lint,unit,pytest,e2e,test-chat}.log`

---

## 4. r2 新发现（不阻塞，交总控决定口径）

| ID | 严重度 | 发现 | 最小复现 / 证据 |
| --- | --- | --- | --- |
| **R2-A** | 低 | **「块不跨区」需要限定为「只在重叠缝处跨界」**：10,482 块中 **1,156 块（11.0%）**跨越了区边界，缝长 ≤ **121** 字符（= overlapChars 120 + 1）；净影响：**49,337 个 body 字符**（≈语料的 0.9%）落在 exercise 标签块内（**检索不到**），**45,602 个 exercise 字符**落在 body 标签块内（可能出现在证据的缝上）。建议 README 把该句写成"除重叠缝（≤121 字符）外不跨区"，或把 overlap 限制在区内 | `uv run python A1r2/scripts/r2_d3_region.py`（第 7 项）+ `A1r2/evidence/r2-d3-seam.json` |
| **R2-B** | 提示 | README §4.2(4) 写「真实云端聊天模型详解 `not_run`」，但该链路我在 r1 与 r2 都用用户真实 deepseek profile 亲测通过（`t05a` 14/14）。若原意是"云端模型的**教学质量**未评审"，建议改写措辞以免被读成"功能未验" | `A1r2/evidence/t05a-explain.json`、`A1/evidence/t05a-explain.json` |
| **R2-C** | 低（工具） | `scripts/rag/freeze.py` 把**清单自身**纳入哈希 → 该条永远无法自洽（r1 清单无此条，r2 起出现）。建议枚举时排除 `FROZEN-CANDIDATE.json` | `A1r2/evidence/r2-frozen-verify-final.json` 的第 2 条 mismatch |
| **R2-D** | 低（文档） | README 有**两个 `## 4.`**（"独立验收发现" 与 "已知质量边界"），章节号重复 | `grep -n "^## 4\." docs/qa/RAG-REBUILD-v1/README.md` |

另：README §4.2(1) 自报「30/58 册未识别出习题区（政治 8、英语 7、历史 5、地理 5、语文 5）」——
我按自己的口径复核**完全一致**（30 册 `exerciseChunks == 0`，学科分布逐项相同），登记诚实。

---

## 5. 附条件与未验范围

**附条件（不影响本轮 pass 判定，但不得当作已验收）**

1. **人工教学质量 `not_run`**：自动化只能证明"证据可核验、引用可追溯"。我目视抽样了 1 条真实详解（等差数列
   倒序相加，与教材表述一致）与 1 条真实知识点（「等差数列的通项公式推导」），**不构成质量结论**。
2. **AI 整理的真实模型输出质量**：形状合法、逐条 pending，但我只跑了 2 题 1 批的样本；本节报告的"可用"仅指
   链路与契约，不含内容正确率。
3. 本轮 **未重跑** r1 的 B3/B5/B7（限定项已由 t09 覆盖）/B11，理由见 §2；若总控在提交前又改了这些模块，需要重新划定复验范围。
4. 冻结记录与工作树存在 4 处漂移（§1.0）：提交前请确认 `docs/CURRENT_STATUS.md`、`docs/replica/*` 的
   内容是你本人在冻结后的预期编辑，并还原 `apps/web/next-env.d.ts`。

**未验（r2 明确 not_run）**

- `CONTEXT_TOO_LARGE` 的真实 HTTP 413 构造；上游中途断流/客户端断开的上游关闭观测；扫描件 PDF → `DOCUMENT_NEEDS_OCR`；`.docx` 解析。
- `/question-bank/imports/[id]` 校对页三视口（r1 也未验）。
- 并发/多实例场景（除已知的迁移暂存目录并发截断，那是实现者自己实测并已登记）。

---

## 6. 我启动/停止的进程（收尾）

| 资源 | 动作 | 状态 |
| --- | --- | --- |
| API 8001（A1r2 数据）、8003（死 Embedding 端口）、8004（指向假 Ollama）、8005（摄取冒烟）、8006（题库）、8000（浏览器联调，已登记例外） | 逐个启动、逐个停止 | **已停止** |
| 前端 5174（冻结 `.next`） | `node scripts/run-web.mjs start 5174` | **已停止** |
| 假 Ollama 11440（我自己写的替身） | 启动/停止 | **已停止** |
| 测试 Qdrant 16333 | 未停（r2 全程运行，未执行 docker 操作） | **运行中（保持）** |
| 正式 Qdrant 6333 / Ollama 11434 | 未触碰 | 运行中 |
| 写入的数据 | `A1r2/{data,data-ingest,staging,evidence,screenshots,logs,scripts}` | 全部在我的证据目录内 |

---

## 7. 复现命令（按结论顺序）

```bash
# 冻结核对
python _work/rag-rebuild-v1/A1/scripts/verify_frozen.py            # 202/204 + 漂移清单

# D1 / D2（需先起 8004 指向假 Ollama 11440；假替身脚本在 A1r2/scripts/fake_ollama.py）
cd apps/api && PYTHONPATH=$PWD A1_API=http://127.0.0.1:8004 A1_DATA=../../_work/rag-rebuild-v1/A1r2/data \
  A1_EVID=../../_work/rag-rebuild-v1/A1r2/evidence uv run python ../../_work/rag-rebuild-v1/A1r2/scripts/r2_d1_digest.py
cd apps/api && PYTHONPATH=$PWD A1_API=http://127.0.0.1:8004 A1_DATA=…/A1r2/data A1_EVID=… \
  uv run python ../../_work/rag-rebuild-v1/A1r2/scripts/r2_d2_organizer.py

# D3（58 册区域）
cd apps/api && PYTHONPATH=$PWD A1_DATA=…/A1r2/data A1_EVID=… \
  uv run python ../../_work/rag-rebuild-v1/A1r2/scripts/r2_d3_region.py

# D4（空跑作废 + 退出码）
python _work/rag-rebuild-v1/A1r2/scripts/r2_d4_void_log.py

# D5（归档来源 58 册）
cd apps/api && uv run python ../../scripts/rag/migrate_textbooks.py --dry-run \
  --source-zip "F:/人教版教材.zip" --staging …/A1r2/staging

# D6 + 视觉（需 8000 + 5174）
node _work/rag-rebuild-v1/A1r2/scripts/r2_visual.mjs

# 回归与工程
cd apps/api && PYTHONPATH=$PWD A1_API=http://127.0.0.1:8001 A1_DATA=…/A1r2/data A1_EVID=… \
  uv run python ../../_work/rag-rebuild-v1/A1/scripts/t01_core.py
cd apps/api && PYTHONPATH=$PWD A1_API=http://127.0.0.1:8001 A1_DATA=… A1_EVID=… \
  uv run python ../../_work/rag-rebuild-v1/A1/scripts/t05a_explain.py
npm run typecheck && npm run lint && NODE_OPTIONS=--no-experimental-webstorage npm run test:unit
cd apps/api && uv run python -m pytest -p no:cacheprovider --tb=short -ra
npx playwright test && npm run test:chat        # 注意：会改写 next-env.d.ts（见 §1.0 第 4 条）
```

```text
A1 r2 结论：pass（附条件）
逐项：D1 pass / D2 pass / D3 pass / D4 pass / D5 pass / D6 pass / P1 pass / P2 pass / P3 pass
回归：t01_core 44/44、t05a 14/14、t08a 22/22、真实摄取冒烟 pass、工程检查 6 项一致
新发现：R2-A 区域重叠缝量化（低）、R2-B README 口径（提示）、R2-C 冻结工具自引用（低）、R2-D 章节号重复（低）
附条件：人工教学质量 not_run；AI 整理内容质量未评审；B3/B5/B11 未重跑（不在改动面）
```
