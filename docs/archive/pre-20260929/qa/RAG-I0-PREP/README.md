# RAG-I0-PREP v1 只读核对报告

| 项 | 值 |
| --- | --- |
| 批次 / 版本 | RAG-I0-PREP v1 |
| 实现者 | I-RAG（单一写入者） |
| 报告时间 | 2026-09-23（本机时区 +08:00） |
| 宿主仓库 | `H:\备份xuexi\智启课源`，分支 `main`，起点 `b16a825`（**本批未做任何 Git 写操作**） |
| 上游仓库 | `F:\ZQKY_RAG`，全程只读；教材 `F:\人教版教材\markdown` 未访问 |
| 本批未执行 | 启动模型、重建索引、跑评测、联网调用、解封 held-out、读 `.env` 值、跑 RAG 侧 pytest |

## 结论

**存在具体缺口。**

宿主侧**契约与接入准备已完成**（adapter 契约 + 合成数据契约测试，见 §6；凭证与环境未改动）。
但 RAG 侧仍有具体缺口，且核对期间上游工作树**正在被第三方写入**（§1.3），
因此**不得**据此进入 I1 的真实接入验收，也不得写「RAG 已接入 / 真实推理通过 / 教学质量通过」。

主要缺口（详见 §5）：① 仍无「可恢复版本交付物」（无 tag / remote / bundle）；② 冻结快照
`--verify` 现报 18 项漂移 + 源文件清单变化，且漂移集在核对期间继续扩大；③ 上游工作树存在
**并发写入者**，任何"冻结/一致"结论都只是时点观测；④ 宿主锁定环境与 RAG 声明的 Python/依赖
兼容性**未验证**；⑤ 并发/队列上限与实际停止能力**未见实现证据**；⑥ 人工质量评审仍 `not_run`。

---

## 1. 仓库状态实测

### 1.1 时点 T0（本会话开工第一次读取，与任务卡一致）

```
git rev-parse HEAD        -> a0f9adedd3511acd4ec1d5f19a1f263df407f8f0
git rev-parse HEAD^       -> 8ed22b868deb537e001ccd34b5955a190ab05754
git log -1 --format=%cI   -> 2026-09-22T23:23:49+08:00
git log -1 --format=%s    -> feat(evaluation): 补充人工评审工作包与段级/claim 指标取数入口
git branch --show-current -> master          （注意：分支名是 master，不是 main）
git status --porcelain    -> 7 项（见下）
```

```
 M docs/EVAL.md
 M docs/SCHEMA.md
 M docs/START_PROMPT.md
 M docs/STATUS.md
 M docs/qa/P8B-REVIEW-PROTOCOL.md
?? docs/START_PROMPT_P8B_HUMAN_REVIEW_V2.md
?? docs/qa/P8B-ROUND12-RULES-v2.md
```

**与任务卡 §0 一致**：HEAD `a0f9ade`（用户口述 `8ed22b8` 是其父提交，已实测确认）；
工作区 7 项不干净，逐项路径与任务卡登记完全相同。

### 1.2 补充实测（任务卡未登记的事实）

| 项 | 实测 |
| --- | --- |
| 分支 | `master`（任务卡只说了宿主是 `main`；上游分支名不是 main） |
| 提交时间地点 | `a0f9ade` 2026-09-22T23:23:49+08:00；`8ed22b8` 2026-09-22T19:42:10+08:00；`3b132df` 2026-09-19T20:02:40+08:00 |
| tag | `git tag -l` = **0 个** |
| remote | `git remote -v` = **0 条** |
| 暂存区 / stash | `git diff --cached --name-only` = 0 行；`git stash list` = 0 条 |
| 对象库 | `count-objects -v`：`count: 507`、`in-pack: 0`、`packs: 0`、`prune-packable: 0` |
| 归档件 | 仓库内（`.git` 外）无 `*.bundle` / `*.zip` / `*.pack` |

**两个新提交相对冻结时刻的进展**：冻结 manifest 记录的 `git_head` 是 `3b132df`
（2026-09-19），此后新增了 `8ed22b8`（P5 本地化执行策略与数据契约）与 `a0f9ade`
（人工评审工作包与指标取数入口）。即：**P5 之后的一部分实现已经进入提交历史**，
不再是"全部只存在于工作树"。但 tag / remote / bundle 仍全部缺失。

### 1.3 漂移：核对期间上游工作树**正在被第三方写入**

| 时点 | `git status --porcelain` 项数 | 说明 |
| --- | --- | --- |
| T0（本会话开工） | **7** | 与任务卡 §0 完全一致 |
| T1（撰写报告前，14:17:53 +08:00） | **11** | 新增 4 个未跟踪文件 |
| T2（报告初稿后，14:19:29 +08:00） | **12** | 又新增 1 个未跟踪文件 |
| T3（交验前最后一次，14:20:14 +08:00） | **13** | 再新增 1 个未跟踪文件；**交验时仍在增长** |

T1–T3 相对 T0 新增的 6 项（**全部不是本会话产生**；mtime 均在观察窗口内）：

```
?? src/evaluation/annotation_v2.py         mtime 2026-09-23 14:14:38  32739 B
?? src/evaluation/segment_metrics_v2.py    mtime 2026-09-23 14:16:15  16692 B
?? src/evaluation/claim_review_v2.py       mtime 2026-09-23 14:17:08  24743 B
?? src/evaluation/fullset_manifest.py      mtime 2026-09-23 14:17:28  13119 B
?? src/evaluation/quality_report_v2.py     mtime 2026-09-23 14:18:32  30002 B
?? tools/p8b_v2_packet.py                  mtime 2026-09-23 14:19–14:20
```

判定依据（该时间窗口内 **I-RAG 没有写入过 F: 的任何文件**）：

1. 这些文件位于 `src/evaluation/` 与 `tools/`，与本批可写范围（宿主 `apps/api/app/contracts/**`、
   `apps/api/tests/test_rag_adapter_contract.py`、`docs/qa/RAG-I0-PREP/README.md`）无交集；
2. 同一时刻出现 `src/evaluation/__pycache__/annotation_v2.cpython-314.pyc`
   （mtime `14:14:51`，42112 B）——**CPython 3.14** 编译产物，即有人用 RAG 自己的主环境
   `E:\miniconda3`（3.14.6）`import` 过该模块。本会话全部 Python 调用使用宿主
   `apps/api` 的 **CPython 3.12.14**，且**从未 import `F:\ZQKY_RAG` 下任何模块**；
3. 与上游 `docs/STATUS.md` §1 记录的 2026-09-23 任务（「P8B 12 题规则歧义裁定与下一批
   真人复核入口」；"v2 工作包和校验器尚待实现"）在**文件命名、主题与时间上完全吻合**；
4. `.zcode/` 存在（`F:\ZQKY_RAG\.zcode\agents`），说明上游存在独立的 agent 会话目录；
5. 观察窗口内文件数持续增长（7 → 11 → 12 → 13），说明写入**仍在进行**，不是一次性事件。

**影响（须写入交接）**：任何"上游冻结 / 与快照一致 / 清单为 N 项漂移"的结论都只是**时点观测**。
任务卡 §0 的"7 项漂移"在核对当天已不成立。若 I1 要在真实接入前确认候选身份，
必须先与上游确认**写入者停止**并重新取一次 HEAD + 指纹，不能沿用本报告或历史记录的数字。

### 1.4 `.env` 边界（只检查键名与是否空值，未读取值）

| 项 | 实测 |
| --- | --- |
| 文件 | `F:\ZQKY_RAG\.env` 存在（112 B，mtime 2026-09-18 22:55） |
| 键名 | 仅 `ZAI_API_KEY` 一个 |
| 是否空值 | 空值计数 = 0（即该键**非空**，存在历史登记的凭证） |

本会话只做 `grep -o '^[A-Za-z_][A-Za-z0-9_]*='`（只输出键名与等号，不输出值），
未 `cat`、未回显、未复制该文件内容。本地链路按上游 STATUS 记录不需要该密钥。

---

## 2. 冻结记录与现役配置逐项对照

冻结编号：**`P8-FREEZE-20260922-190500`**（来源：`F:\ZQKY_RAG\docs\CANDIDATE_FREEZE.md`；
用户 2026-09-22 决定「暂不安排人工评审，先冻结候选」；phase = `frozen_candidate_not_release`）。

对照方式：冻结记录表格的每一项 → 在 `configs/**` 的实际取值（`configs/` 下只有
`models.yaml` 与 `heading_rules.yaml` 两个文件）；`configs/**` 未承载的项下钻到代码的
**单一定义点**（`src/service.py` / `src/config.py` / `src/llm/prompts.py`）。

| # | 冻结记录项 | 冻结值 | 实际位置与实际值 | 一致性 |
| --- | --- | --- | --- | --- |
| 1 | 执行策略 | `local-only` | `configs/models.yaml` → `execution.policy: local-only` | **一致** |
| 2 | embedding provider / 维度 | `bge_m3_local`（1024 维） | `embedding.active: bge_m3_local`；`providers.bge_m3_local.dims: [1024]`、`model_id: ollama/bge-m3:latest` | **一致** |
| 3 | 检索方法 | `hybrid_weighted` | `src/service.py` provenance `"method": "hybrid_weighted"`（`configs` 无此字段） | **一致** |
| 4 | `alpha` | `0.5` | `configs/models.yaml` → `fusion.alpha: 0.5` | **一致** |
| 5 | `pool` | `50` | `configs/models.yaml` → `fusion.pool: 50` | **一致** |
| 6 | `top_k` | `50` | `src/service.py` `top_k: int = 50`（`configs` 无此字段） | **一致**（默认值即冻结值） |
| 7 | 标准服务 `rerank` | `off` | `src/service.py` provenance `"rerank": "off"`；`configs` 的 `rerank.active: local_bge_reranker_v2_m3` 只指定**可选 provider**，与冻结记录脚注说明一致 | **一致** |
| 8 | 证据策略 | A0：`bounded_window` | `src/service.py` `evidence_method: str = "bounded_window"`；`EVIDENCE_METHODS` 含三种取值 | **一致** |
| 9 | 回答策略 | A0：`baseline` | `src/service.py:146` / `src/llm/prompts.py:141` / `src/llm/generation_cache.py:48` 三处默认 `answer_policy = "baseline"`；`ANSWER_POLICIES` 另含未采用的 `strict_v1` | **一致** |
| 10 | 检索优化 | 保留会话级身份绑定快照 | `src/retrieval/session.py` 存在（会话级身份绑定索引快照；CLI 开关 `warm_bm25`/`session_cache`） | **存在**；本批**未重复实测**其性能（不改用历史数字） |
| 11 | 生成模型 | `local_ollama_qwen25_7b` / `qwen2.5:7b` | `generation.active: local_ollama_qwen25_7b`；`providers.local_ollama_qwen25_7b.model: qwen2.5:7b` | **一致** |
| 12 | `num_ctx` | `8192` | 同段 `num_ctx: 8192` | **一致** |
| 13 | `num_predict` | `1024` | 同段 `num_predict: 1024` | **一致** |
| 14 | `temperature` | `0` | 同段 `temperature: 0` | **一致** |
| 15 | `seed` | `0` | 同段 `seed: 0` | **一致** |
| 16 | 证据包预算 | `6000` | 同段 `evidence_pack_max_tokens: 6000` | **一致** |
| 17 | 修复次数上限 | 最多一次 | 同段 `max_repair_attempts: 1`；`src/config.py` `_RANGES["max_repair_attempts"] = (0, 1)` 硬约束"有界：最多一次" | **一致** |
| 18 | generation cache contract | `3` | `generation.cache_contract_version: 3` | **一致** |
| 19 | prompt / schema 版本 | `p7-v1` / `p7-v2` | `prompt_version: 'p7-v1'`、`schema_version: 'p7-v2'`；`SERVICE_CONTRACT_VERSION = "p8a-v1(evidence:<EV>,schema:p7-v2)"` | **一致** |
| 20 | 权重身份（脚注：manifest digest 与权重 blob digest 不混用） | — | `embedding.providers.bge_m3_local` 同时给出 `expected_digest`（blob `sha256:daec91ff…`）与 `expected_manifest_digest`（`sha256:79076464…`），注释明确两者语义不同、双锚点比对 | **一致** |

**对照结果：20 项全部一致，未发现配置漂移。** `configs/**` 中未被冻结记录覆盖、但属于
现役配置的字段（`fusion.rrf_k: 60`、`rerank.cache_contract_version: 2`、
`budget.chars_per_token_lower: 0.8`、模板开销 64、安全余量 128、
`rerank.providers.zhipu_rerank.budget.max_calls_per_run: 0`）**不构成"差异"**：
冻结记录表格未声明它们，且 `max_calls_per_run: 0` 与"零云端"一致。

> 说明：本对照只读 `configs/**` 与代码默认值，**未加载模型、未重建索引、未验证磁盘权重**。
> 冻结记录本身也声明「模型身份取自冻结配置；本次不加载模型、不重新验证磁盘权重」。

---

## 3. 冻结包核对（只读）

### 3.1 目录与可解析性

目录 `data/derived/qa/P8-FREEZE-20260922-190500/` **存在**，4 个文件，mtime 全为
`2026-09-22 19:12`（核对前后**逐字节未变**，含大小）：

| 文件 | 大小 | sha256 |
| --- | --- | --- |
| `candidate.zip` | 762,428 B | `acb7f388b3d7f87e4e85f6c3158efe0fe1b9f9edfb8b6ec211f4fc953fe57e0c` |
| `manifest.json` | 46,021 B | `fdd9dc8d33052091f490f6ead27206a64b56a4e3b4e0b58265a05b44db4aa707` |
| `receipt.json` | 503 B | （未登记自身散列，正常） |
| `freeze_snapshot.py` | 7,382 B | `aa51a0add779ba00a29649778ccdeedda46d811e235a7b29bbd1509eae9cc9f6`（= manifest `snapshot_script`） |

- `manifest.json` **可解析**：顶层键 `archived_files`(144) / `created_at` /
  `creation_note` / `fingerprint_only_files`(93) / `freeze_id` / `git_head` /
  `git_status_porcelain` / `phase` / `scope` / `snapshot_script` / `staged_paths` / `user_decision`。
  `freeze_id = P8-FREEZE-20260922-190500`；`created_at = 2026-09-22T19:12:22.222192+08:00`；
  `staged_paths = ""`（冻结时暂存区为空）。
- `receipt.json` **可解析**：`verified_at = 2026-09-22T19:12:23.132854+08:00`；
  `verification = {archive_members: 144, fingerprinted_artifacts: 93,
  archive_and_sources_match: true, model_calls: 0, product_tests_run: false}`。
- **收据自证**：`receipt.sha256[candidate.zip]` 与 `receipt.sha256[manifest.json]`
  与磁盘实算**逐一匹配**；`archive_bytes` 762,428 与磁盘一致。

### 3.2 抽样核对（禁止重建归档，只做抽样）

| 抽样对象 | 样本 | 结果 |
| --- | --- | --- |
| `archived_files`（144 项） | 7 项：`.gitignore`、`.zcode/agents/bounded-implementer.md`、`src/__init__.py`、`src/parsing/heading_rules.py`、`tests/test_p8b_annotation_contract.py`、`tools/tokenizer_reference.py`、根计划书 md | **6/7 与 manifest 指纹+大小一致**；1 项不一致 → `tests/test_p8b_annotation_contract.py`（属 §3.3 登记的 18 项漂移之一，**预期内**） |
| `fingerprint_only_files`（93 项） | 7 项：`api_usage.jsonl`、`chunks.jsonl`、`structure.jsonl`、`P8A-VERIFY/README.md`、`P8C-GEN-1/gen/cases.jsonl`、`P8C-PERF/_log_replay3.txt`、`tokenizer/qwen2_5_7b_gguf_vocab.json` | **7/7 一致** |
| `snapshot_script` | 1 项 | **一致** |
| `candidate.zip` 归档内容 | 全量 144 项 vs manifest | 成员清单集合相等；逐项 sha256 与 manifest **0 处不符**；`zipfile.testzip()` = `None`（无损坏） |

**关键产物指纹（从 manifest 读出，用于与上游 STATUS 的登记值对照）**：

| 产物 | manifest 登记 sha256 | 与上游 `docs/STATUS.md` 登记值 |
| --- | --- | --- |
| `data/derived/chunks.jsonl`（21,048,841 B） | `049bcaa694d45659a7c19ed2d25388b8b0986ba73547761c6fc8ec7f8114c916` | **一致**（上游 §3 登记 `049bcaa6…`） |
| `data/derived/eval/questions.jsonl`（1,952,005 B） | `24e5c6fdbd0cb61865aa52dd23f519f7dabef7377a7b23e8d462a01600f45135` | **一致**（上游 §3 登记 `24e5c6fd…`，冻结 v2） |
| `data/derived/structure.jsonl`（7,516,129 B） | `4923467298e9689e10976cbe8e8c971ae16647c3155ee09a861fff40fc8f44c4` | 上游 STATUS 未登记该值，本报告补记 |
| `data/derived/index/ollama_bge-m3_latest/vectors_1024_cch.npy`（48,775,296 B） | `518d9c42bf4af442701be1afd6ec02fbc68485f1338c8063523ccf6590ce6c9c` | 与上游 §3.2 登记的 `518d9c42bf4af442…` **一致** |
| `data/derived/api_usage.jsonl`（594,627 B） | `0a071d0abea53420539b676e48e6aa5ad6f4360c9242d24c39343b1815dd175a` | 上游 §3.5 登记 `604e0c07…`（时为 1,503 行）；**已变化**——台账随调用追加，属预期增长，非漂移缺陷 |

> 语料与评测集两个主指纹（`chunks.jsonl` / `questions.jsonl`）与上游登记值**一致**，
> 说明冻结包记录的切分产物与冻结题集**未被改动**。

### 3.3 `freeze_snapshot.py --verify` 是否只读：**是**（先读脚本，后运行）

先逐行读脚本（`data/derived/qa/P8-FREEZE-20260922-190500/freeze_snapshot.py`，148 行），判定：

| 判定点 | 事实 |
| --- | --- |
| 是否写文件 | `--verify` 分支只做 `Path.read_text()` / `path.open("rb")` / `zipfile.ZipFile(...)` 默认 `"r"` 模式 / `json.loads` / `sha256` 流式读取。写路径只出现在**创建分支**（`write_json` 用 `open("x")`、`ZipFile(..., "x")`），该分支在入口处被 `if sys.argv[1:] == ["--verify"]: ... return` 挡掉；且创建分支自带 `Freeze already exists; use --verify, never overwrite` 守卫 |
| 是否调模型 | 否。脚本只 import 标准库（`pathlib/datetime/hashlib/json/os/stat/subprocess/sys/zipfile`），**不 import 项目任何模块**；`verify()` 返回值里显式写 `model_calls: 0`、`product_tests_run: False` |
| 是否有其它副作用 | `--verify` 路径不调用 `git()`（只有创建分支调用）；仅遍历目录 + 计算 sha256。脚本作为 `__main__` 运行**不产生 `__pycache__`**（运行后该目录仍只有原 4 个文件，无新增） |

**结论：只读，可以运行。** 实跑（宿主 `uv run python`，CPython 3.12.14）：

```
$ uv run python "F:/ZQKY_RAG/data/derived/qa/P8-FREEZE-20260922-190500/freeze_snapshot.py" --verify
RuntimeError: current source file inventory differs
source missing/drifted: AGENTS.md
source missing/drifted: docs/CANDIDATE_FREEZE.md
source missing/drifted: docs/EVAL.md
source missing/drifted: docs/qa/P8B-REVIEW-PROTOCOL.md
source missing/drifted: docs/SCHEMA.md
source missing/drifted: docs/START_PROMPT.md
source missing/drifted: docs/STATUS.md
source missing/drifted: src/evaluation/answer_metrics.py
source missing/drifted: src/evaluation/review_material.py
source missing/drifted: src/evaluation/segment_annotation.py
source missing/drifted: src/evaluation/segment_metrics.py
source missing/drifted: tests/test_answer_metrics.py
source missing/drifted: tests/test_p8b_annotation_contract.py
source missing/drifted: tests/test_segment_metrics.py
source missing/drifted: tools/p8b_human_todo.py
source missing/drifted: tools/p8c_completion_stats.py
source missing/drifted: data/derived/qa/P8B-ENTRY/human_todo.json
source missing/drifted: data/derived/qa/P8B-ENTRY/HUMAN_TODO.md
退出码 = 1    （非 PASS）
```

**失败构成（脚本计数）**：`current source file inventory differs` ×1；
`source missing/drifted:` ×18；`archive member inventory differs` ×0；
`archive content:` ×0；`Receipt mismatch` ×0。

**判读（重要，别读成"快照损坏"）**：

1. **快照自身完好**：归档成员清单与逐项散列、以及 receipt 对
   `candidate.zip` / `manifest.json` 的散列**全部通过**——失败只发生在
   **「当前工作树 vs 冻结快照」**这一段。这与上游
   `docs/CANDIDATE_FREEZE.md`「"--verify 现在会报漂移……不是快照损坏"的预期一致。
2. **18 项漂移 = 上游自述的 16 项 + 2 项新增**。上游 `CANDIDATE_FREEZE.md` 登记的
   「16 个已登记源文件内容已变」**全部包含**在这 18 项里；多出的 2 项是
   **`docs/SCHEMA.md`、`docs/START_PROMPT.md`**——即该文档写完之后上游又继续改了这两个文件
   （与 §1.1 的 7 项脏文件清单一致：二者都在其中）。
3. **`git_head` 段不参与 `--verify`**：`verify()` 只比对源文件清单、归档成员与三类指纹，
   **不比对** `manifest["git_head"]` / `manifest["git_status_porcelain"]` 与当前值。
   因此"HEAD 与暂存状态一致"**不是** `--verify` 的结论，只能由人工另行核对
   （本次核对：manifest 记 `3b132df` + 103 行 porcelain，当前是 `a0f9ade` + 7→11→12→13 行，
   **不一致**，见 §1）。
4. 建议后续沿用时的做法：把 `--verify` 的结论表述为
   「归档/receipt 自证一致；当前树与快照不一致（N 项）」，
   不要简写成"核验 PASS/FAIL"。

---

## 4. 依赖与版本：现状与兼容方案

### 4.1 上游实测

| 项 | 实测 |
| --- | --- |
| `requirements.txt` | **存在**，6 个**直接**依赖精确锁定：`numpy==2.5.3`、`jieba==0.42.1`、`rank_bm25==0.2.2`、`PyYAML==6.0.3`、`httpx==0.28.1`、`pytest==9.1.1`。文件头自述是"直接依赖的精确锁定，**不是全量 pip freeze**"；**无 `--require-hashes`** |
| `requirements-local-rerank.txt` | **存在**：独立 venv `.venv-local-rerank/`（CPython **3.13.12**）内锁定 `transformers==4.57.6`、`tokenizers==0.22.2`、`huggingface_hub==0.36.2`、`safetensors==0.8.0`、`PyYAML==6.0.3`、`regex==2026.9.10`，另有 4 个"继承自基础解释器（未重装）"的条目（`numpy==2.4.3`、`tqdm`、`requests`、`packaging/filelock/fsspec/typing_extensions`）。**torch 不在本文件**：由基础解释器 `E:\Python` 的 **torch 2.6.0+cu124** 经 `--system-site-packages` 继承 |
| Python 版本要求 | 仓库内**没有** `pyproject.toml`、**没有** `.python-version`；`requirements.txt` 注释写明运行时实测为 **Windows 原生 CPython 3.14.6（`E:\miniconda3`）**，并明确警告："宿主「智启课源」声明 ≥3.12；合并前须在宿主的锁定版本上重跑测试，不能假定 3.14 的新语法普遍可用" |
| `uv.lock` | **不存在**（上游不用 uv） |

### 4.2 宿主实测（`apps/api`）

| 项 | 实测 |
| --- | --- |
| `pyproject.toml` | `name = zhiqikeyuan-api`、`version = 0.3.0`、`requires-python = ">=3.12"`；运行依赖 `fastapi>=0.116`、`uvicorn>=0.30`；dev 组 `httpx2>=2.12.0`、`pytest>=8.3`、`pytest-asyncio>=1.4.0` |
| `uv.lock` | **存在**（`version = 1`、`requires-python = ">=3.12"`）。关键解析版本：`fastapi 0.141.1`、`starlette 1.6.0`、`uvicorn 0.52.4`、`pydantic 2.13.5`、`pydantic-core 2.46.5`、`pytest 9.1.1`、`pytest-asyncio 1.4.0`、`httpx2 2.12.0` |
| 运行解释器 | `uv run python -V` → **CPython 3.12.14** |
| 上游运行时依赖在宿主锁中的存在性 | **`httpx`、`numpy`、`jieba`、`rank-bm25`、`pyyaml` 全部不在宿主 `uv.lock` 中** |

### 4.3 兼容性判定

| 维度 | 判定 |
| --- | --- |
| 宿主与上游 Python 主版本 | 宿主 3.12.14 vs 上游主环境 3.14.6 → **不同**，且上游自述 3.14 语法不得假定可用于宿主。**兼容性未验证**（本批不跑上游测试） |
| 依赖集合 | 上游检索链需要 `numpy/jieba/rank_bm25/PyYAML/httpx`，宿主**一个都没有**；本地重排链另需 `torch/transformers/tokenizers`，来自未记录的 `--system-site-packages` 个人环境 |
| 冲突项 | 无直接版本冲突（宿主 dev 组用的是 `httpx2`，与上游 `httpx` 不同包名）。`pytest` 两侧都是 **9.1.1**，一致 |
| 本批处置 | **不改宿主 `pyproject.toml` / 锁文件，不改共享环境，不新增依赖**（任务卡禁止项）。本批新增的 adapter 契约只依赖 **pydantic 2.13.5**（宿主已锁定，随 FastAPI 提供），因此**无需任何依赖变更** |

### 4.4 固定版本 + 独立包命名方案（I1 采用，本批只出方案）

1. **本批（I0）**：宿主侧只放 **adapter 契约与纯函数**（`app/contracts/rag_adapter.py`），
   零新增依赖、零锁文件改动。能力声明保持 `planned`（见 §6）。
2. **I1 候选 A（推荐先评估）——独立服务/独立进程**：把上游检索与生成作为**受控的本地进程**
   （沿用上游"纯函数式服务层 + 不绑定 HTTP 框架"的形态，或它已有的常驻 worker /
   stdio JSON 协议），在**它自己的锁定环境**里运行；宿主只经**进程边界**通信，
   不 import 上游代码、不解析其依赖树。宿主侧不新增运行时依赖（只用到标准库 + pydantic）。
   优点：不动宿主锁文件、不共享可变环境、上游 3.14 与其 torch 依赖完全不进入宿主。
3. **I1 候选 B——独立命名的 Python 包**：把上游实现打成**固定版本、独立命名空间**的 wheel
   （例如 `zqky-rag`），宿主以 `uv add` + 锁文件变更显式引入。**前置条件**：必须先在宿主的
   CPython 3.12.14 上跑通上游测试与 `src.verify`，并让 numpy/jieba/rank_bm25 等进入宿主
   锁文件——这会改动依赖与锁文件，**需要单独授权与独立批次**。
4. **两条路都必须遵守的边界**：
   - **不永久修改 `sys.path`** 指向 `F:\ZQKY_RAG\src`（该目录随时会被第三方写入，见 §1.3），
     也不把通用 `src` 命名空间散进宿主；
   - **不复用未记录的 `--system-site-packages` 个人环境**；
   - 索引/权重/向量/缓存/评测题**不进 Git**，教材就地只读；
   - 服务必须实现 §7 的执行边界（有界队列、超时区分、取消、迟到结果、不可用如实报错）。

---

## 5. 缺口清单与结论

| # | 缺口 | 性质 | 证据 / 影响 |
| --- | --- | --- | --- |
| G1 | **无可恢复版本交付物** | 阻塞 R0 出口条件 | 无 tag（0）、无 remote（0）、无 bundle/zip/pack；`in-pack: 0`、`packs: 0`。虽有 2 个新提交（`8ed22b8`、`a0f9ade`），但仍**没有可校验的受控版本包** |
| G2 | **上游工作树存在并发写入者** | 阻塞"候选身份"确认 | 核对期间未跟踪文件由 2 项增至 **8 项**（`src/evaluation/*_v2.py` **5 个** + `tools/p8b_v2_packet.py`，mtime 14:14–14:20，伴随 CPython 3.14 的 `.pyc`）；期间仍在增长（7→11→12→13）。任何指纹/清单结论都只是**时点观测**（见 §1.3）；任务卡要求的"前后完全一致"本次**未满足** |
| G3 | **冻结快照漂移 18 项 + 源文件清单变化** | 影响候选可比性 | `--verify` 退出码 1；归档/receipt 自证一致，失败仅在"当前树 vs 快照"。上游自述 16 项，实际 18 项（多出 `docs/SCHEMA.md`、`docs/START_PROMPT.md`），且仍会扩大 |
| G4 | **`--verify` 不覆盖 `git_head`/porcelain** | 判定口径 | manifest 记 `3b132df` + 103 行 porcelain；当前 `a0f9ade` + 7→11→12→13 行。"HEAD 与暂存一致"不是脚本结论，需人工核对（本报告已核对为**不一致**） |
| G5 | **宿主锁定环境 vs 上游依赖/Python 兼容性未验证** | 阻塞 I1 方案定稿 | 宿主无 numpy/jieba/rank_bm25/PyYAML/httpx；Python 3.12.14 vs 上游 3.14.6；本地重排链依赖未记录的 3.13 + torch 2.6.0+cu124 个人环境。本批**未跑**上游测试 |
| G6 | **并发/队列上限未见实现证据** | 执行边界未闭合 | 宿主 PROJECT_GUIDE §4.2 只读核对已记"未发现并发/队列上限实现（无 Semaphore/max_workers/队列深度限制）"；本批复核**未推翻**该结论（未做实现层搜索以外的新测量，也未实测） |
| G7 | **"实际停止底层推理"能力未测量** | 执行边界未闭合 | 上游有生成侧 `cancel_token`（请求前/返回后/身份核验后各检一次）与 `GenerationCancelled.completed` 计次，但**没有**"取消后底层推理是否真的停下"的测量证据。本契约只声明**取消等待** |
| G8 | **人工质量评审仍 `not_run`** | 质量门槛 | 评审者 0 人、可用人工金标 0 条、claim 判定 0 条；段级质量 / 讲解支持性 / 充分性与拒答 / 阈值选择全部 `not_run`；held-out 90 题未解封 |
| G9 | **`ScopeRef` 列表长度未设上限** | 契约留白 | 任务卡 §2 未规定 `courseScope` 的元素个数上限，本批**不擅自发明**约束；I1 需决定（作为有界队列之外的第二个输入边界） |
| G10 | **`textHash` 的精确口径未定义** | 契约留白 | 本契约只规定其为"64 位小写十六进制、语义为跨区间原文内容的散列"；**散列的输入范围**（整篇文件 / 该区间 / 归一化形态）由 I1 定义并对齐两侧实现，本批不做假设 |
| G11 | 历史云端资产的处理 | 非阻塞 | 上游 STATUS 明确"历史云端资产不删除，本地路线不改变"；本批未评估其处置时点 |
| G12 | `OLLAMA_NO_CLOUD` 未设置 | 非阻塞（历史登记） | 上游 P7-QA 已登记"建议生产环境显式设置"；本批未验证环境变量 |

**本轮不构成缺口的项**（避免被误读成未完成）：

- 现役配置与冻结记录 **20/20 一致**（§2）；
- 冻结包 `candidate.zip` / `manifest.json` / `receipt.json` **未被写入**，归档内容与 receipt **自证一致**；
- 语料与冻结题集主指纹 `chunks.jsonl` / `questions.jsonl` 与上游登记值**一致**；
- 宿主侧 adapter 契约与合成数据契约测试**已完成并通过**（§6）。

**结论：存在具体缺口。** 宿主侧契约/准备已完成，但 G1–G3、G5–G8 为阻塞项：
不得据此进入 I1 真实接入验收；不得写「RAG 已接入」「真实推理通过」「教学质量通过」。
建议的下一步顺序：先由上游解决 G1（受控版本包）并停止写入以冻结候选身份（G2），
再由宿主在**不新增依赖**的前提下选定 I1 接入形态（§4.4 候选 A/B），
并用一次独立验收覆盖 G5–G7。

---

## 6. 宿主侧 adapter 契约摘要（本批交付）

文件（本批新增，均在本批可写范围内）：

| 文件 | 内容 |
| --- | --- |
| `apps/api/app/contracts/__init__.py` | 包说明（仅文档，不做导入聚合） |
| `apps/api/app/contracts/rag_adapter.py` | 5 个 Pydantic 模型 + `RagAdapter` Protocol + `RagAdapterUnavailable` + `get_rag_adapter()` + `validate_answer_payload()` + 2 个坐标换算纯函数 |
| `apps/api/tests/test_rag_adapter_contract.py` | 合成数据契约测试（不联网、不读外部目录、不调模型） |

### 6.1 模型与字段

| 模型 | 字段 |
| --- | --- |
| `ScopeRef` | `kind: Literal["textbook","knowledge_base","notebook"]`、`refId`、`label`（各 1..200） |
| `RagQuery` | `question: str`(1..4000)、`courseScope: list[ScopeRef] \| None = None`、`maxEvidence: int = 5`(1..20) |
| `EvidenceItem` | `evidenceId`、`sourceType`（与 `kind` 同词表）、`sourceId`、`sourceName`、`charStart>=0`、`charEnd>charStart`、`lineStart>=1`、`lineEnd>=lineStart`、`text`(1..2000)、`score: float \| None` |
| `Citation` | `evidenceId`、`fileId`、`fileFingerprint`(64 位小写 hex)、`charStart/charEnd`、`lineStart/lineEnd`、`textHash`(64 位小写 hex) |
| `RagAnswer` | `status: Literal["ok","no_evidence","stale_source","out_of_range","unavailable"]`、`answer: str \| None`、`evidence`、`citations`、`warnings`（四者**必填**，`answer` 允许显式 `null`） |

契约取向（都是"宁可拒绝、不静默"）：`extra="forbid"` + `frozen=True`；
指纹只接受**小写** hexdigest 形态（不做大小写归一）；`score` 拒绝 NaN/Inf；
`answer`/`evidence`/`citations`/`warnings` 无默认值，缺失即拒。

### 6.2 坐标口径（detail）

- 字符区间**半开** `[charStart, charEnd)`；行号**1 基闭区间** `[lineStart, lineEnd]`。
- 后端字符坐标是 **Python `str` 的 Unicode 码点下标**（归一化文本：UTF-8 解码 + 通用换行归一化）；
  前端 JS 是 **UTF-16 码元下标**；**星平面字符（emoji）占 2 个码元**，两侧数值不同，**不可直接混用**。
- `fileFingerprint` 是**源文件原始字节**的 sha256 —— 与字符下标是两套语义，不可互推。
- 提供 `codepoint_to_utf16_offset(text, codepoint_offset)` 与
  `utf16_offset_to_codepoint(text, utf16_offset)`：越界抛 `ValueError`（不夹取）；
  UTF-16 下标落在**代理对内部**时抛 `ValueError`（不取整）；两者在码点边界上互为逆函数。

### 6.3 状态语义与"禁止静默裁剪"

- `ok`：必须同时有非空 `answer`、≥1 条 `evidence`、≥1 条 `citation`。
- `no_evidence`：范围内无可定位内容（**合法结果，不是错误**）。
- `stale_source`：**源文件指纹变化**（被改/被替换/已删除）→ 旧区间不再可解释，禁止展示为已验证引用。
- `out_of_range`：**区间越界**（超出源文件长度，或引用区间不被证据区间包含）。
- `unavailable`：检索能力不可用（模型/索引未就绪）；**不得**降级成 `no_evidence` 冒充"没检索到"。
- **统一规则（可测断言）**：所有非 `ok` 状态 → `answer is None`、`evidence == []`、
  `citations == []`、`warnings` 非空。
- **越界不裁剪**：`validate_answer_payload()` 只校验、不归一化；区间倒置、指纹格式非法、
  引用悬空、`citation ⊄ evidence` 一律抛错。

### 6.4 能力可用性（禁止伪造成功）

- `RagAdapterUnavailable(RuntimeError)`；`get_rag_adapter()` **恒定抛出**它，文案：
  「RAG 未接入：I0 仅定义契约，尚未接入真实检索（未接入、未实测）。」
- **不存在任何返回 `status="ok"` 的假实现**；本批**未注册任何 HTTP 路由**，
  也**未在任何现有端点里调用** adapter（`app/api/**` 一字未改）。
- `RAG_CAPABILITY` 声明 `status = "planned"`，与 `app/api/v1/capabilities.py` 的现状一致
  （该文件由其它负责人维护，本批未修改）；测试同时断言端点仍返回 `planned`。
- `validate_answer_payload(dict) -> RagAnswer` 是**纯校验/纯函数入口，不产生答案、不做 I/O**。
  它**不校验也无法校验**：区间是否超出源文件长度、`textHash` 是否真的等于该区间原文散列、
  `fileFingerprint` 是否与磁盘一致（都需要可信语料根内的真实源文件），
  以及 `Citation.fileId` 与 `EvidenceItem.sourceId` 的绑定关系（I1 责任）。
  也**不**判断答案的语义/教学正确性。

---

## 7. 执行边界（设计描述）

> **本批只描述设计边界，除"契约层可测"的规则外全部为「未实测」**——宿主侧尚无真实检索可跑，
> 因此**没有任何**性能、并发、超时或停止能力的实测数值可报告。不得据此宣称任何已满足。

| 边界 | 契约要求 | 状态 |
| --- | --- | --- |
| 有界队列 | 并发与排队深度必须有上限（GPU 模型访问尤甚）；超限快速失败并给出明确状态，不得无界排队 | **未实测**；具体上限值与溢出行为未定 |
| 超时 | 必须区分**总超时**（一次 `query` 进入→返回）与**子超时**（embedding / 检索 / 生成各自上限）；子超时先到应产生可解释的部分结果或明确状态，总超时到点必须结束等待 | **未实测**；秒数与触发点未定 |
| 取消 | 本契约**只保证"取消等待"**（调用方停止等待并把该轮置为终态）。**"停止底层推理"是本契约不声明的另一件事**：已进入前向计算的本地推理通常无法被协作取消，必须实测（对照上游 `GenerationCancelled.completed` 这类"取消时是否已发生推理"的信号）才能写"已停止" | **未实测**；上游只有 `cancel_token` 三处检查点与计次规则，**无**停止能力测量证据 |
| 迟到结果 | 取消 / 超时 / 轮次已终结后才返回的结果，必须按 `requestId`（结合 `sessionId`/`turnId`）丢弃，不得写入新轮次、不得复活已取消的卡；丢弃必须可观测（计数/日志），不得静默 | **未实测**（端口签名已预留 `requestId`） |
| 模型不可用 | 如实报错（`status="unavailable"` 或抛 `RagAdapterUnavailable`）；不得静默换模型、不得回落云端、不得用空证据冒充"没检索到" | 契约层已可测（§6.3）；**运行时未实测** |
| 不阻塞事件循环 | 同步 CPU/GPU 检索必须放进有界线程/任务，不得直接占用 async 路由的事件循环 | **未实测**（端口为 `async def`，实现约束留给 I1） |

---

## 8. 本批实测命令与只读证据

### 8.1 宿主侧自检（全绿）

```
$ npm run test:api -- tests/test_rag_adapter_contract.py
...................................                                      [100%]
35 passed, 1 warning in 0.41s
```

（1 条 warning 来自 `starlette/testclient.py` 的 `anyio.abc.BlockingPortal` 弃用提示，
与本批代码无关，其它既有测试同样会出现。）

首败与修复（保留记录）：首次运行 **1 failed / 34 passed**，失败项
`test_citation_may_be_a_narrower_subrange_of_evidence`——**原因是测试夹具写错**
（把候选引用区间的 `charEnd` 写成 130，而证据区间实际是 `[100, 129)`，属我构造的
"越界引用"）。修复方式是把该用例改为按 `100 + len(EVIDENCE_TEXT)` 计算区间上界，
**不是**放宽契约的 `citation ⊆ evidence` 校验。修复后 35 passed。

### 8.2 只读证据：上游 HEAD 与 `git status --porcelain` 前后对照

| 时点 | HEAD | porcelain 项数 |
| --- | --- | --- |
| T0（开工第一次读取） | `a0f9adedd3511acd4ec1d5f19a1f263df407f8f0` | **7**（与任务卡 §0 逐项一致） |
| T1（撰写报告前，14:17:53 +08:00） | `a0f9adedd3511acd4ec1d5f19a1f263df407f8f0` | **11** |
| T2（报告初稿后，14:19:29 +08:00） | `a0f9adedd3511acd4ec1d5f19a1f263df407f8f0` | **12** |
| T3（交验前最后一次，14:20:14 +08:00） | `a0f9adedd3511acd4ec1d5f19a1f263df407f8f0` | **13** |

**HEAD 四次读取完全一致**（未变）。**porcelain 并不一致**——但差异**不是本会话造成的**：
新增的 6 个文件是 `src/evaluation/{annotation_v2,segment_metrics_v2,claim_review_v2,fullset_manifest,quality_report_v2}.py`
与 `tools/p8b_v2_packet.py`，mtime `2026-09-23 14:14:38 – 14:20`，并伴随 **CPython 3.14** 的
`__pycache__/annotation_v2.cpython-314.pyc`；本会话所有 Python 调用使用宿主
`apps/api` 的 **CPython 3.12.14**，且**从未 import `F:\ZQKY_RAG` 下的任何模块**。
判定该变化来自**上游并发的第三方写入者**（§1.3 列出 5 条独立依据）。
任务卡要求的"前后完全一致"在本次核对中**未满足**，如实登记为缺口 G2；
**交验时的最终数字可能已高于 13**，接手方须重新读取，不得引用本表的数字作为现状。

**宿主仓库同样存在并发写入者**（与本批无关，供交接参考）：T0 时宿主
`git status --porcelain` 为 3 项（`M apps/web/src/contracts/chat.ts` +
`?? docs/qa/CHAT-CONTEXT-BUDGET/` + `?? docs/qa/RAG-I0-PREP/`），收工复核为 11 项——
新增的 `apps/web/src/features/chat/{ChatWorkspace.tsx,model/store.ts,model/context-budget.ts,
model/context-budget.test.ts,model/request-budget.ts,model/request-budget.test.ts}` 等
mtime 为 `14:16–14:18`，属 CHAT-CONTEXT-BUDGET 批次的另一位写入者。
**本批只新增 3 项**：`?? apps/api/app/contracts/`、
`?? apps/api/tests/test_rag_adapter_contract.py`、`?? docs/qa/RAG-I0-PREP/`（README 在内），
与上述 web 变更**无交集**，也未修改它们。

本会话对 `F:\ZQKY_RAG` 的全部操作只有四类，均无写语义：

1. 读取（`Read`/`cat`/`grep`/`find`/`stat`/`head`/`sed -n`）；
2. 只读 Git 查询：`status`、`log`、`rev-parse`、`branch`、`tag -l`、`remote -v`、
   `count-objects -v`、`stash list`、`diff --cached --name-only`、`diff --stat`、`check-ignore`；
3. 只读 Python 脚本（宿主解释器，仅 `open("rb")` / `read_text` / `json.loads` / `hashlib` /
   `zipfile` 读），用于解析 manifest/receipt 与抽样比对散列；
4. 运行 `freeze_snapshot.py --verify`（事前已逐行读脚本判定为只读，见 §3.3）。

**未执行**：`git add` / `commit` / `checkout` / `stash` / `clean` / `reset` / 任何写操作；
未创建分支或提交；未改写上游任何文件；未 `cat` `.env`（只检查键名与是否空值）。

冻结包未变的正面证据：`data/derived/qa/P8-FREEZE-20260922-190500/` 的 4 个文件在核对后
**mtime 仍为 `2026-09-22 19:12`、大小不变**（762,428 / 46,021 / 503 / 7,382），
且同目录**未出现** `__pycache__` 或新增文件。

本会话写入的 4 个文件（全部落在可写范围内，mtime 与上游并发文件时间窗重叠但路径不相交）：

| 文件 | mtime | 大小 |
| --- | --- | --- |
| `apps/api/app/contracts/__init__.py` | 2026-09-23 14:12:25 | 398 B |
| `apps/api/app/contracts/rag_adapter.py` | 2026-09-23 14:13:18 | 26,482 B |
| `apps/api/tests/test_rag_adapter_contract.py` | 2026-09-23 14:16:50 | 21,353 B |
| `docs/qa/RAG-I0-PREP/README.md` | 2026-09-23 14:19:25 | 本文件 |

`apps/api/app/contracts/__pycache__/` 由测试运行产生，已被根 `.gitignore:21` 的
`__pycache__/` 覆盖（`git check-ignore` 退出码 0），未进入待提交范围。

宿主侧未越界证据：本批只新增/修改 §6 表列的 3 个文件；`docs/STATUS.md`、
`docs/PROJECT_GUIDE.md`、三矩阵、`apps/web/**`、`apps/api/app/api/**`、
`apps/api/app/schemas/chat.py`、依赖与锁文件**均未触碰**；
`package.json` 的 `test:api` 脚本**未改动**（自检命令在旁打印的 `npm notice run ...` 只是
npm 的噪音输出，与脚本变更无关）。

---

## 9. 未执行的检查（如实登记）

- 未运行 RAG 侧 `pytest` / `python -m src.verify` / 任何评测（任务卡禁止）。
- 未启动模型、未加载权重、未调用 Ollama、未重建索引、未联网。
- 未验证磁盘上的模型权重/索引与配置中 digest 的一致性（只读配置，未加载）。
- 未运行真实检索、未做性能/并发/超时/取消测量（§7 全部为**未实测**）。
- 未解封 held-out 90 题、未填任何人工 verdict、未选阈值、未改默认策略。
- 未读取 `.env` 的值；未访问教材目录 `F:\人教版教材\markdown`。
- 未做容器/其它机器上的可重复安装验证（§4 的兼容性结论仅为**静态比对**）。
