# A1 独立验收报告 r2（RAG-QUALITY v1.1 · 窄复验：F1/F2/F4/F5/冻结自校验）

```text
任务：RAG-QUALITY-v1 / A1-VERIFY r2（独立验收者，只读产品代码；不改 r1 报告）
验收对象：docs/qa/RAG-QUALITY-v1/FROZEN-CANDIDATE.json（104 文件 + sha256；BUILD_ID WXHZTQm_Ma2tbqT2sRCUY；基线 2f27841）
复验时间：2026-09-29 16:45 – 17:40（+0800）
本次判定：**pass（可交付，附条件）**
```

**判定含义**：r1 点名的 F1/F2/F4/F5 与冻结自校验**逐条独立复验通过**；未发现修完引入的回归；
遗留项（F6/R-19/R-1）均为**跨批既有**问题，已附最小复现与定性证据，不构成本批交付阻塞。
附条件：人工教学质量与真实云端供应商维持 `not_run`（§6）；e2e 与 UI 的构建口径见 §5.3；F6 的官方源目录影响未实测。

---

## 1. 结论摘要

| 复核项 | 判定 | 一句话证据 |
| --- | --- | --- |
| r2 冻结记录 | **pass** | 我重算 104 文件：`missing=0 hash_mismatch=0 size_mismatch=0`；`.next` BUILD_ID 与记录一致 |
| **F1** migrate 报告崩 | **pass（已修）** | 复现命令 `--limit 1` + 临时数据根 → **exit 0**、`完成：1 册已迁移 / 0 册失败`、报告 JSON 生成并含 `sourceRoot/requestedSource/requestedSourceZip` |
| **F2** 图片残片进索引 | **pass（已修）** | 我的最小复现输出 `</td><td>正四面体形</td></tr></table>`；v2 活动代 **10477/10477** 点独立重算一致且 `images/`、`src=`、`<img`、`![` **全部为 0**；12/12 自构造样例通过 |
| **F2 旁证**：旧代不被改写 | **pass** | v1 两代逐点用 v1 规则复算 10477/10477 一致（旧代的 3 处 `images/` 原样保留 = 历史不可变）；58/58 修订在 v2 代拿到**新 chunk_set_id**（指纹随版本变、不重用旧分集） |
| **F4** 错误码归一 | **pass（已修）** | 真实 import + 不存在 profile → HTTP 404 `MODEL_PROFILE_NOT_FOUND`「模型配置不存在。」，替身计数 **0 次上游调用**；成功路径仍走通 |
| **F5** 台账编号 | **pass** | `docs/CURRENT_STATUS.md:137` R-18 条目描述与事实一致（EmbeddingPanel 加载敏感、非本批引入、不加重试/不放宽断言）；R-16 确为其它批次占用 |
| **断言"有牙齿"** | **pass** | 变异验证：把常量改成 `rag-readable-v9` → 两处版本锚点用例**同时失败**（`assert 'rag-readable-v2' == 'rag-readable-v9'`）；不打补丁则通过 |
| 回归 | **pass（附 2 个既有间歇）** | unit 74 文件/712 例全通过；`test:chat` 14/14；pytest collect 920 → 919 passed / 1 failed（既有冷启动 flake，见 §5.1）；e2e 137 passed / 1 failed（= 台账 R-14，见 §5.2） |
| 前端对 v2 证据的接受度 | **pass** | 真实构建 + 真实 API：来源 6 条、出现「已省略图片」提示、摘录 683 字无图片语法、**无「未清洗历史原文」误标**、零溢出、零教材图片请求 |

---

## 2. r2 冻结记录与波及面

```bash
python _work/rag-quality-v1/A1/verify_freeze.py     # exit 0 → missing=0 hash_mismatch=0 size_mismatch=0；BUILD_ID 一致
```

**验收期间（我侧）记录漂移 2 处，均为非产品文件，如实声明**：

| 文件 | 变化 | 归因 |
| --- | --- | --- |
| `apps/web/next-env.d.ts` | 288 → 296 B | Next 自动生成文件；由我按约定执行的 `npm run test:chat`（内含 `next build`）重写，非手工编辑 |
| `docs/qa/RAG-QUALITY-v1/README.md` | 11866 → 12095 B（17:18） | 总控在我复验窗口内的台账更新（line 130 加 r2 指引）；我未写该文件 |

> 口径建议（重复 r1，r2 仍未处理）：`next-env.d.ts` 是自动生成物却在冻结清单内，任何 build/typecheck 都会打破"逐字节自校验"。建议从清单排除，或冻结后统一还原。

复验结束时的复核留痕（同一脚本、同一漂移）：`evidence/freeze-verify-r2-end.log`（`hash_mismatch=2` 即上表两项；`missing=0`；BUILD_ID 仍一致）。

**波及面（用哈希证明 r1 结论仍然有效，故未重跑）**：以下 r1 已验文件在 r1→r2 之间**逐字节未变**：
`scripts/rag/backup.py`、`app/core/data_lock.py`、`app/core/rag_budget.py`、`rag_v2/{evidence,presenter,retrieval,service,summary,explain}.py`、
`question_bank/organizer.py`、`textbook_ingest/indexer.py`、`document_parsing/chunking.py`（比对 r1 清单 sha256，全为"一致"）。
r2 增量 = `migrate_textbooks.py`（F1）+ `text_projection/**`、`schemas/rag_v2.py`、前端 `rag-v2.ts`（F2 版本升版）+ `model_runtime.py`（F4）+ 8 处测试断言 + `tests/fixtures/text-projection-samples.json`。

---

## 3. F1：migrate 报告 `NameError`（已修）

```bash
cd apps/api && ZQKY_QDRANT_URL=http://127.0.0.1:16333 uv run python ../../scripts/rag/migrate_textbooks.py \
  --source "_work/rag-quality-v1/A1/source-md-r2" --data-dir "_work/rag-quality-v1/A1/r2-dataroot" --limit 1 \
  --report "_work/rag-quality-v1/A1/evidence/migrate-r2-report.json"
# exit 0；OK [1/1] … 202586 字符 / 272 块 / 15.9s；完成：1 册已迁移 / 0 册失败
```

报告 JSON 实际内容：`sourceRoot=<settings.textbook_source_dir>`、`requestedSource=<--source 原值>`、`requestedSourceZip=null`、`generationId=3f9b9cb3…`、`generationChunkTotal=272`。
证据：`_work/rag-quality-v1/A1/evidence/migrate-r2.log`、`evidence/migrate-r2-report.json`。

口径小项（F7，低）：未传 `--report` 时默认写到 **`_work/rag-rebuild-v1/migration-report.json`**（上一批目录）；
我这次不带 `--report` 的复现因此写入了该文件（16:52，脚本默认行为，如实声明）。建议默认目录随批次目录走。

---

## 4. F2：截断标签残片（已修）——独立复验

### 4.1 我的最小复现 + 自构造样例（12/12 pass）

| 用例 | 结果 |
| --- | --- |
| r1 最小复现（块首残片 + 双引号） | `removedImageCount=1`，输出 `</td><td>正四面体形</td></tr></table>`，无 `images/` |
| 块尾截断（`<img src="…"` 无收尾） | 残留片段被删除 |
| URL 被切断 / 单引号 / 无引号 / 裸 `src="notes.txt"` | 全部删除 |
| **必须保留**：围栏代码里的 `<img>`、行内代码里的 `src=` | **原样保留**（未过度清洗） |
| 真实 3 处泄漏块的原文串 | 全部清洗干净 |

命令：`uv run python _work/rag-quality-v1/A1/probe_f2_r2.py`（exit 0）
证据：`_work/rag-quality-v1/A1/evidence/f2-cases-r2.json`

### 4.2 全语料逐块复算（不接受抽样）

用只读归档重解 58 册 md（`source-md-r2`）→ 独立重跑分块 → 按每个 payload **登记的清洗版本**复算：

| collection | 代 | 点数 | payload 版本 | 源切片命中 | `indexTextSha256` 复算一致 | `images/` | `src=` | `<img`/`![` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `textbooks_3ff98a4b…` | `932d34c9` 批前 | 10482 | 缺失（raw-v0） | 10477 | 10477 | 6623 | 29 | 6601+27 |
| `textbooks_62373e59…` | `a6eb3569` | 10477 | rag-readable-**v1** | 10477 | 10477 | 3 | 3 | 3 |
| `textbooks_e2cfc638…` | `42e42518` | 10477 | rag-readable-**v1** | 10477 | 10477 | 3 | 3 | 3 |
| **`textbooks_6c9d991b…`** | **`90f3ec0b` 当前活动** | 10477 | rag-readable-**v2** | 10477 | **10477** | **0** | **0** | **0** |

- 命令：`uv run python _work/rag-quality-v1/A1/recompute_index_hash_r2.py <source-md-r2>`（exit 0）；证据：`evidence/recompute-index-hash-r2-full.json`
- 旧代保留 3 处 `images/`：这是**历史不可变**的正确表现（旧代不重建、不删）；新代清零。
- **同一版本映射双向成立**：v1 代用 v1 规则复算一致、v2 代用 v2 规则复算一致 → 升版没有偷偷改 v1 语义。
- 分块集不复用：58/58 修订在 v2 代拿到**新 `chunk_set_id`**，而每修订的原文切片散列集合与 v1 代**完全相同**（划分确定性 + 版本进指纹）。

### 4.3 真实链路（v2 代）与崩溃类回归

- 真实 `/rag/stream`（r2 隔离根 `3f9b9cb3…` / 272 块）：「用空间向量怎么求直线与平面所成的角？」→ `status=ok`、3 点 / 213 码点 / 6 条证据，**每条 `readable.version = rag-readable-v2`**、`removedImageCount` 1–4、封存切片仍含图片语法、19/19 检查通过（含 v1 时代的 `Literal` 收紧点被真实 v2 证据穿透验证）。
  证据：`evidence/rag-stream-q5-v2gen.txt`、`evidence/stream-check-q5.json`
- 崩溃类回归在 v2 扫描器上重跑：**20/20 pass**，最慢 8.7 ms（含不等式+图片、400 图规模）；证据：`evidence/projection-crash-r2.json`

---

## 5. 断言"有牙齿"与回归

### 5.1 变异验证（我自己构造，不改仓库）

读到的锚点：`test_document_parsing.py:949` 钉字面量 `TEXT_PROJECTION_VERSION == "rag-readable-v2"`；
`test_text_projection_samples.py` 要求 **fixture 的 version 等于常量**、且 24 组样例的**期望文本/映射/图片数逐组相等**；
新增 `test_samples_do_not_leak_image_addresses_in_cleaned_text`（不依赖常量的独立泄漏守卫）；前端 `text-projection.test.ts` 钉 `TEXT_PROJECTION_VERSION === 'rag-readable-v1'` 且保留 24 组逐组相等。

变异实验（`-p mutate_version_plugin`，只在进程内把常量改成 `rag-readable-v9`）：

```text
FAILED tests/test_document_parsing.py::test_text_projection_version_enters_policy_and_fingerprint
FAILED tests/test_text_projection_samples.py::test_samples_file_exists_and_is_versioned
E   assert 'rag-readable-v2' == 'rag-readable-v9'
```

不打补丁时这两例通过。→ **"改成常量比较"没有让用例恒真**；版本/规则漂移有独立锚点（字面量 + fixture 数据 + 逐例期望文本 + 泄漏守卫）。
残留口径（如实记录）：证据级断言（`readable.version == TEXT_PROJECTION_VERSION`）不再钉字面量，属设计取舍；前端只声明 v1 语义（`toBe('rag-readable-v1')`），v2 专属规则由后端承担。

### 5.2 回归数字

| 检查 | 我的结果 | 退出码 |
| --- | --- | --- |
| `uv run python -m pytest`（collect **920**，48 文件） | **919 passed / 1 failed**（两次全量运行一致） | 1 |
| 失败项 | `tests/test_rag_sessions.py::test_ttl_memory_capacity_and_restart_are_explicit` | — |
| 定性 | **既有冷启动敏感 flake（非本批引入）**：该文件在 r1/r2 清单中均**未改动**；单用例冷启动 5/5 失败、**整个文件 14/14 通过**、**基线树（`git archive 2f27841`）单用例同样失败** | — |
| 机制量化 | `start` 3.4–4.4 ms，`drain` **465–477 ms**（其中 jieba 首次加载 ≈350 ms）> 该用例 TTL **50 ms** → 第二轮不再 `RAG_CAPACITY`（"DID NOT RAISE"）；同进程若已有先行用例预热则通过 | — |
| `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | **74 文件 / 712 例全通过**（R-18 本次未复现） | 0 |
| `npm run test:chat` | **14 passed / 0 failed**（重建 `.next-test`，BUILD_ID → `Hv0U6DSWnktbdGSMrt3ME`） | 0 |
| `npx playwright test`（全量 e2e） | **137 passed / 1 failed**（8.3 min） | 1 |
| 失败项 | `tests/e2e/books-commit-safety.spec.ts:238` = 台账 **R-14**（`strip(second)` 120 s 内仍为 1；失败快照显示页面**内容完整可读、笔记仍在**、带「强制重新生成」按钮，无数据丢失迹象）。**书籍/课程目录零改动**（清单内无 books 文件）→ 与本批 diff 面无交集 | — |

> 与实现者数字的差异，如实登记：**pytest** 我方 919/920（实现者 920/0）——差异即上述 R-19 类 flake；
> **e2e** 我方 137/138（r1 我方 138/138、实现者 r1 137/1）——差异即 R-14 的间歇性，r2 我方复现了一次，签名与台账一致。
> 两者都**不建议**用"加等待/加重试/放宽断言"处理。

### 5.3 构建口径声明

- e2e 跑在冻结 `.next`（`WXHZTQm_Ma2tbqT2sRCUY`，**r1 期构建，不含 r2 前端改动**）上 → e2e 未覆盖 r2 的 `rag-v2.ts` 运行时 guard；该点由 §5.4 的 UI 复核在新构建上覆盖。
- UI 复核跑在 `npm run test:chat` 重建的 `.next-test`（r2 源码，代理到 8001）。

### 5.4 前端对 v2 证据的接受度（三视口回归的定点复核）

真实构建 + 真实 API（v2 活动代）+ 真实提问：

```text
来源条目 6 条 ✔｜出现「已省略图片」提示 ✔（该提示依赖服务端 readable.removedImageCount ⇒ 前端确实读进了 v2 readable）
展开摘录 683 字且 0 处 ![ / images/ / <img ✔｜面板整体 0 处图片语法 ✔
未出现「未清洗历史原文」标注 ✔（v2 证据没被当成历史回退）｜页面级零横向溢出 ✔｜零教材图片请求 ✔
```

命令：`node _work/rag-quality-v1/A1/r2-ui-v2-evidence.mjs http://127.0.0.1:5174 …`（exit 0）
证据：`_work/rag-quality-v1/A1/evidence/r2-ui-v2.log`、`shots/chat-v2-evidence-1440x900.png`、`shots/r2-ui-v2-evidence.json`

---

## 6. 新发现（均为跨批既有，附最小复现）

### 6.1 F6（中高，**既有**）`migrate_textbooks.py` 会**搬走（删除）源目录里的教材文件**

- 事实：`migrate_textbooks.py:373` 把**原始源文件路径**当 `staged_path` 传给 `IngestService`，
  而 `BlobStore.stage_file()` 是**移动语义**（`os.replace`，跨卷退化为复制+`source.unlink()`）。
- 最小复现（我 16:52 跑的）：源目录放 1 个 md → 运行 `migrate_textbooks.py --source <该目录> --limit 1`
  → **运行前 1 个文件，运行后 0 个文件**；exit 0、`完成：1 册已迁移`、内容仅存于受管 blobs（catalog 侧无损）。
- 与本批脚本自述冲突："只读源目录：原件由入库链路复制进受管 blobs，**源目录一个字节都不写**"（基线同样如此）。
- 定性：**基线提交 `2f27841` 同一行为**（`git show 2f27841:... | grep staged_path` 相同）→ 非本批引入；但本批改过该文件，
  建议单开小卡修（改复制语义或先落 staging），并同步修正文档口径；官方流程目前只用 `--source-zip` 暂存目录，故此前未暴露。
- 副作用（对验收）：它让我 r1 暂存的语料丢了 3 册，导致我第一次 r2 复算只覆盖 55/58 册（9308/10477 命中）；
  我发现后重新解档 58 册（`source-md-r2`）重跑，**报告 §4.2 的数字均为 58 册完整语料的结果**。
- 证据：`evidence/repro-consume.log`（运行前后文件数）、`apps/api/app/services/textbook_ingest/blobs.py:102-118`。

### 6.2 R-19（中，**既有**）`test_rag_sessions` TTL 冷启动 flake

见 §5.2 量化证据。建议台账 R-19：把该用例 TTL 余量放宽（或先预热分词器），**不改产品行为**。

### 6.3 F7（低，口径）migrate 默认报告路径落在上一批目录 `_work/rag-rebuild-v1/`。

---

## 7. 未验范围（r2）

| 项 | 原因 |
| --- | --- |
| 人工教学质量、真实云端供应商 | 与本批无关，维持 `not_run`（不宣称） |
| r1 已验的备份恢复/数据锁/预算与准入/历史兼容/三视口视觉 | **未重跑**：相关文件 r1↔r2 逐字节一致（§2 哈希表），无波及面；如需可随时补跑 |
| F6 对**官方**只读源目录（`F:/人教版教材/markdown`）的实际影响 | 未对该目录做写入实验（其当前无 `.md`）；我用自建副本复现了同一行为，并用基线树证明既有 |
| R-1（无相关性闸门） | 本批不修，r1 已独立复现，维持开放 |
| r2 前端改动在全量 e2e 中的覆盖 | e2e 构建为 r1 期 `.next`；由 §5.4 UI 复核补上（未重跑三视口全页矩阵） |
| `restore-state`/锁/门禁等 r1 边界在 r2 的再确认 | 同上，文件未变，未重跑 |

---

## 8. 我启动/停止的进程与资源

| 资源 | 用途 | 状态 |
| --- | --- | --- |
| `uvicorn --port 8001`（`ZQKY_DATA_DIR=…/r2-dataroot`，`ZQKY_QDRANT_URL=16333`） | F4、v2 真实 `/rag/stream`、UI 复核 | **已停止** |
| `python _work/…/mock_upstream.py --port 18099` | F4 的受控替身（计数用） | **已停止** |
| `node scripts/run-web.mjs start 5174`（`ZQKY_TEST_BUILD=1`） | v2 证据 UI 复核 | **已停止** |
| `pytest` / `vitest` / `next build`（test:chat）/ `playwright test` 子进程 | 回归 | 已结束 |
| 测试 Qdrant **16333** | 按要求保留运行（我新增 collections：迁移 1 个 + 恢复演练 1 个，均在隔离实例） | **保持运行** |
| 正式 Qdrant **6333** | 全程只读；四个代点数 10482 / 10477 / 10477 / 10477 未变 | 未写入 |

写入范围：仅 `_work/rag-quality-v1/A1/**` 与本报告。**未改**产品代码、测试、权威文档、锁文件；未执行 git 写操作（`git archive` 仅读取对象库）。
附带声明：一次不带 `--report` 的 migrate 复现按脚本默认写入了 `_work/rag-rebuild-v1/migration-report.json`（§3）。
