# RAG-I0-PREP v1 任务卡（冻结契约）

> 批次：RAG-I0-PREP v1（2026-09-22）。起点 `main@b16a825`。队长独占宿主权威文档、集成、构建与 Git；本卡是实现者（I-RAG）的唯一契约来源。

## 0. 现场核对（队长开工复验，2026-09-22）

| 项 | 用户口述 | 队长实测 | 处置 |
| --- | --- | --- | --- |
| RAG 仓库 HEAD | `8ed22b8` | **`a0f9ade`**（`8ed22b8` 是其父提交：`a0f9ade feat(evaluation): 补充人工评审工作包与段级/claim 指标取数入口`） | 以实测为准，写入报告与 STATUS；不得改写 RAG 仓库 |
| RAG 工作区 | 干净 | **7 项不干净**：`M docs/EVAL.md`、`M docs/SCHEMA.md`、`M docs/START_PROMPT.md`、`M docs/STATUS.md`、`M docs/qa/P8B-REVIEW-PROTOCOL.md`、`?? docs/START_PROMPT_P8B_HUMAN_REVIEW_V2.md`、`?? docs/qa/P8B-ROUND12-RULES-v2.md` | 只读登记为漂移，**不自动覆盖、不清理、不提交** |

**只读边界（违反即返工）**：不写、不改、不移动 `F:\ZQKY_RAG` 任何文件（含 `data/derived/**`），不创建分支/提交、不 `git add`、不 `stash`、不 `clean`。不读 `.env` 内容（只允许检查键名是否存在与是否为空值）。不启动模型、不重建索引、不跑评测、不填人工 verdict、不解封 held-out。教材目录 `F:\人教版教材\markdown` 也只读。

## 1. 范围与产出

**范围内**
1. 冻结包 / manifest / receipt / 现役配置的**只读核对**与漂移报告。
2. 宿主侧 **RAG adapter 输入输出契约**（新文件，仅宿主）+ 合成数据契约测试。
3. 引用（citation）契约：文件身份、源文件指纹、字符区间、行号区间、坐标口径。
4. 后续接入的**执行边界**（有界队列/超时/取消/迟到结果/模型不可用）——只描述设计边界，未实测的能力必须写「未实测」。
5. 宿主 Python/uv 与 RAG 依赖的兼容要求：固定版本、独立包命名、**不永久 `sys.path` 指向可变外部目录**、不改宿主共享环境或锁文件。
6. 复用现有 FastAPI，禁止第二套业务后端。

**范围外（不得做）**：启用追问执行、教材上传、真实检索或任何 RAG 内容进宿主；启动模型、改参数、重建索引；在宿主里复制 RAG 实现；改动宿主 `apps/api` 现有路由行为。

## 2. 宿主侧 adapter 契约（新文件，仅宿主）

**文件**
- `apps/api/app/contracts/__init__.py`（新，若目录不存在）
- `apps/api/app/contracts/rag_adapter.py`（新）：Pydantic 模型 + `RagAdapter` Protocol（端口）+ 能力可用性声明。
- `apps/api/tests/test_rag_adapter_contract.py`（新）：合成数据契约测试，**不联网、不读外部目录、不调模型**。

**模型（字段名与语义必须一致）**

```
RagQuery         { question: str(1..4000), courseScope: list[ScopeRef] | None, maxEvidence: int = 5 (1..20) }
ScopeRef         { kind: Literal["textbook","knowledge_base","notebook"], refId: str, label: str }
EvidenceItem     { evidenceId: str, sourceType, sourceId, sourceName,
                   charStart: int >= 0, charEnd: int > charStart, lineStart: int >= 1, lineEnd: int >= lineStart,
                   text: str (1..2000), score: float | None }
Citation         { evidenceId: str, fileId: str, fileFingerprint: str(64 hex),
                   charStart, charEnd, lineStart, lineEnd, textHash: str(64 hex) }
RagAnswer        { status: Literal["ok","no_evidence","stale_source","out_of_range","unavailable"],
                   answer: str | None, evidence: list[EvidenceItem], citations: list[Citation],
                   warnings: list[str] }
```

**能力可用性（禁止伪造成功）**
- 提供 `class RagAdapterUnavailable(RuntimeError)` 与 `get_rag_adapter()`：**必须抛出 `RagAdapterUnavailable`**，文案说明「I0 仅定义契约，尚未接入真实检索（未接入、未实测）」。不得返回任何返回 `status="ok"` 的假实现、不得注册路由、不得在 `apps/api` 的任何现有端点里调用它。
- 允许（且必须）提供一个**纯校验/纯函数**入口（不产生答案）：`validate_answer_payload(dict) -> RagAnswer`，仅做结构校验与引用规则校验（越界/指纹格式/区间倒置必须抛错）。

**引用契约（必须写进模块 docstring 与测试）**
1. `fileId` 稳定标识；`fileFingerprint` = 源文件 SHA-256（64 hex）。
2. 区间一律**半开** `[charStart, charEnd)`，且 `lineStart/lineEnd` 为 **1 基、闭区间**。
3. **坐标口径**：RAG 侧为 Python 字符串（Unicode 码点）坐标；宿主前端为 **UTF-16 码元**索引，**不得直接混用**；模块需提供 `codepoint_to_utf16_offset(text, codepoint_offset)` / `utf16_offset_to_codepoint(text, utf16_offset)` 两个纯函数，并在测试中用中文与 emoji（代理对）验证。
4. 失效/漂移：文件指纹变化 → `status="stale_source"`；区间越界 → `out_of_range`；两者都必须有明确错误或状态，禁止静默裁剪成合法区间。

**执行边界（写入模块 docstring + `docs/qa/RAG-I0-PREP/README.md`）**：有界队列（并发与排队上限）、超时（总超时 vs 检索超时的区分）、取消（**取消等待**与**停止底层推理**必须分开描述：本契约只保证取消等待，不声明已能中断底层推理）、迟到结果（按 `requestId`/`turnId` 丢弃）、模型不可用时的如实错误。**未实测的能力写「未实测」**。

## 3. 只读核对报告（`docs/qa/RAG-I0-PREP/README.md`）

必须包含：
1. 仓库状态实测（HEAD/full sha/父提交/工作区 7 项漂移/`git log -1 --format=%cI`）。
2. 冻结记录 `docs/CANDIDATE_FREEZE.md`：冻结编号 `P8-FREEZE-20260922-190500`、保留的现役配置表（执行策略/embedding/检索/证据策略/生成模型与参数/缓存与 schema 版本）与**实际配置文件的逐项对照**（读到 `configs/**` 的实际值并列出差异或一致）。
3. 冻结包核对：`data/derived/qa/P8-FREEZE-20260922-190500/` 是否存在、`manifest.json`/`receipt.json` 是否可解析、关键指纹是否与文件一致（**抽样**即可，禁止重建归档）；`freeze_snapshot.py --verify` **先读脚本**：若它只读（不写任何文件、不调模型）则运行并记录输出；若会写文件则记 `not_run` 并说明原因。
4. 依赖与版本：RAG 的 `requirements.txt`/`requirements-local-rerank.txt`、Python 版本要求、`uv.lock` 是否存在；宿主 `apps/api/pyproject.toml` + `uv.lock` 的实际版本要求；给出**固定版本 + 独立包命名**方案（例如宿主侧仅放 adapter 契约、真实依赖后续以独立包/独立服务方式引入），并明确：不永久 `sys.path`、不改宿主锁文件、不改共享环境。
5. 缺口清单（缺失/漂移/未实测）+ 结论：**只能是「契约/准备已完成」或「存在具体缺口」**；不得写「RAG 已接入」「真实推理通过」「教学质量通过」。

## 4. 禁止项（逐条会被 A1 核）

- 不改 RAG 仓库任何文件、不改宿主 `apps/api` 现有路由与 schemas、不新增 HTTP 路由。
- 不启动模型/不重建索引/不跑评测/不联网调用外部 API；不读 `.env` 值。
- 不把 RAG 源码复制进宿主；不在宿主新增依赖到 `pyproject.toml`/锁文件（只出方案）。
- 不声称任何未实测能力（性能、质量、并发、超时实测值）。

## 5. 文件归属（单一写入者：I-RAG）

| 文件 | 动作 |
| --- | --- |
| `apps/api/app/contracts/rag_adapter.py`（+ `__init__.py`） | 新建 |
| `apps/api/tests/test_rag_adapter_contract.py` | 新建 |
| `docs/qa/RAG-I0-PREP/README.md` | 新建（§3 报告） |

**不得触碰**：`docs/STATUS.md`、`docs/PROJECT_GUIDE.md`、矩阵、`apps/web/**`、`apps/api/app/api/**`、`apps/api/app/schemas/chat.py`、任何锁文件。

## 6. 交付格式

- 代码 + 测试 + 报告；运行 `npm run test:api -- tests/test_rag_adapter_contract.py` 并给出实测输出。
- 结果卡：核对结论（含漂移事实）、契约摘要、测试数字、缺口与未实测项、剩余边界。
- 队长负责：宿主文档（STATUS/PROJECT_GUIDE/矩阵）、集成、构建、独立验收组织、本地提交（RAG-I0 单独提交）。
