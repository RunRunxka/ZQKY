# RAG-I0-PREP v1 独立验收报告 r1（A1，只读复验）

> 归档说明（队长）：A1（`Independent-Acceptor`，只读）本轮对**两条工作流**出了一份合并报告；本文件保存其中与候选 2（RAG-I0-PREP v1）有关的部分，预算批（CHAT-CONTEXT-BUDGET v1）部分见 [CHAT-CONTEXT-BUDGET/A1-REPORT-01.md](../CHAT-CONTEXT-BUDGET/A1-REPORT-01.md)。文末「总控处置」为队长记录，不改写 A1 的原始结论与数字。A1 探针在仓库外（`%TEMP%\a1-verif-20260923\rag_probe.py`），不随仓库提交。

## 0. 候选与写入停止

- 候选 2：`13a93ae`（`feat(rag-i0)`，父 `a9968cd`），tree `a067b4870d01edab24588cd17b011942c9c41eef`。
- 外部只读仓 `F:\ZQKY_RAG`：HEAD `a0f9adedd3511acd4ec1d5f19a1f263df407f8f0`，父 `8ed22b86…`，分支 `master` —— 与 FROZEN-2 一致。
- 候选自到验起未被写入（宿主 `git status --porcelain -uall` = 0）。

## 1. 逐条结论（A1 自测）

| 项 | 结论 | 证据 |
| --- | --- | --- |
| **契约真实性** | **pass** | `get_rag_adapter()` 连调 3 次全部抛 `RagAdapterUnavailable`（文案含「未接入、未实测」）；模块内无 `APIRouter`/`@router`/`include_router`；全 `apps/api` 仅 `tests/test_rag_adapter_contract.py` 引用；TestClient 实测 `GET /api/v1/capabilities` → 200 且 `rag=planned`（`chat=ready`），路由清单无 rag；模块内**无任何构造 `RagAnswer` 的成功返回路径** |
| **校验强度** | **pass** | 自建 Python 探针（exit 0）覆盖 20 类非法载荷：区间倒置、行号倒置、负数/非 1 基、指纹大写/63 位/非 hex、`textHash` 非法、引用悬空、`citation ⊄ evidence`（char 与 line 两路）、非 ok 夹带 `answer/evidence/citations`、非 ok 缺 warnings、ok 空 answer/缺 evidence/缺 citation、`evidenceId` 重复、同证据多 citation、未知字段、缺键、`score=NaN/inf`、非法 status、非 Mapping、frozen 写、子模型未知字段 —— **全部抛错，无静默归一化**。`charEnd` 超出源文件长度不被纯函数校验，属模块 docstring 明示局限（I1 责任），报告未把它写成已校验 |
| **坐标口径** | **pass** | `"😀a"`：码点 1 → UTF-16 **2**（与文档示例一致）；UTF-16=1（代理对内部）抛 `ValueError` 不取整；中文/emoji 混排 9 个码点全部互逆；越界/负数/float/bool/非 str 全部抛错 |
| **只读证据** | **pass（A1 独立复算）** | receipt 的 sha256 与磁盘 `candidate.zip`/`manifest.json` 逐一匹配；`archived_files=144`、`fingerprint_only_files=93`；zip 成员集合与 manifest 相等、逐项 sha256 **0 处不符**、`testzip()=None`；manifest `git_head=3b132df…` + 103 行 porcelain；A1 **实跑** `freeze_snapshot.py --verify`（先读脚本确认 `--verify` 分支只读）→ exit **1**，仅 18 项 `source missing/drifted`，archive member/archive content/Receipt mismatch 各 **0**；冻结目录 4 文件 mtime 仍 `2026-09-22 19:12`、无新增文件；上游 HEAD 两次读取一致；**核对结束后上游仍在写入**（`src/evaluation/*_v2.py`、`data/derived/qa/P8B-V2-ACCEPT-DENOM/**`、`.pytest_cache`，mtime 至 15:06）——与 FROZEN「未确认停止写入」一致，非本会话所为 |
| **诚实性** | **pass** | 结论为「宿主侧契约/准备已完成 + 上游存在具体缺口 G1–G12」；抽查 G5（宿主 `uv.lock` 中 numpy/jieba/rank-bm25/pyyaml/httpx 各 0 条、`uv run python -V = 3.12.14`）、G12（`OLLAMA_NO_CLOUD` 未设置）、G3/G4（读脚本确认 `verify()` 不比对 `git_head`/porcelain）、G6/G7（上游仅 `cancel_token` 检查点，无停止能力测量证据；报告写「未推翻」而非实测）；队列/超时/取消/迟到结果/性能/质量**全部标未实测/not_run**；P8A「fixed 14/14」与上游 `docs/STATUS.md:125/524/859` 一致，**未见 P8A 状态错记** |

## 2. 独立复跑

| 项 | 声称 | A1 实测 |
| --- | --- | --- |
| RAG 契约测试 | 35 例 | `uv run python -m pytest tests/test_rag_adapter_contract.py -q` 收集 **35** 例，全通过 |
| 宿主 API 全量 | 217 passed | **217 passed**（1 warning 为 starlette anyio 弃用提示） |

## 3. A1 结论（原文摘要）

> **候选 2（RAG-I0-PREP v1，`13a93ae`）：可交付（限定为"契约/准备"范围）。** 覆盖范围：契约真实性（恒定不可用、无路由、无假成功、capability 仍 `planned`）、校验强度、坐标口径、冻结包与上游只读证据（独立复算 receipt/zip/`--verify`）、诚实性（结论为「存在具体缺口」，G1–G12 抽查属实，未宣称接入/质量）。**不覆盖**：任何真实检索、性能、并发、超时、取消与质量结论（均 not_run，与文档一致）；上游缺口 G1/G2 仍未清，I1 需用户明确解除冻结。

## 4. 总控处置（队长，2026-09-23）

| 项 | 处置 |
| --- | --- |
| 结论采纳 | **采纳**：RAG-I0-PREP v1 在本批内**不再改动**（`git diff 13a93ae HEAD -- apps/api` 保持为空），其结论按「宿主侧契约/准备已完成、上游存在具体缺口（G1–G12）」记录在 STATUS §5.A/§6.1、PROJECT_GUIDE §4.2/§4.5 |
| G1/G2（无可恢复版本包、上游未停止写入） | **保持未清，不做代做**：冻结包在 `data/derived/`（gitignore），无 tag/remote/bundle；上游写入者仍在活动（A1 亦观测到）。**I1 需用户明确解除冻结并确认停止写入后才启动** |
| G5（宿主依赖/Python 兼容未验证） | **登记为 I1 前置**：本批只出方案（独立进程边界优先 / 独立命名 wheel 需单独授权改依赖与锁文件），未改宿主 `pyproject.toml`/`uv.lock` |
| G9/G10（`courseScope` 元素上限、`textHash` 散列范围未定义） | **留给 I1 定义**，本批不擅自发明契约值 |
| 版本与指纹 | RAG 候选提交 `13a93ae`（tree `a067b487…`）与上游 `a0f9ade` 的核对结论写入 [FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)；性能边界补注来源（上游 `docs/EVAL.md`/`docs/STATUS.md` 历史记录，本批未实测） |

**处置后状态**：候选 2 无返工项；其在同批中的引用（STATUS §5.A 第 4 条、§6.1、§6 路线行、PROJECT_GUIDE §4.5、矩阵 A-rag-adapter-contract 行）与 A1 结论一致。
