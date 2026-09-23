"""教材 RAG adapter 的输入输出契约（批次 RAG-I0-PREP v1，宿主侧）。

本模块**只定义契约与纯函数**：没有检索实现、没有模型调用、没有网络、没有路由注册。
真实检索服务位于外部只读项目 `F:\\ZQKY_RAG`，本轮**未接入、未实测**；任何调用
`get_rag_adapter()` 的代码都会得到 `RagAdapterUnavailable`，不会得到"成功"结果。

设计依据：PROJECT_GUIDE §4.1/§4.2 的接入设计，以及冻结记录
`P8-FREEZE-20260922-190500` 保留的现役配置（`local-only` / `bge_m3_local` /
`hybrid_weighted@alpha=0.5` / `bounded_window` / `local_ollama_qwen25_7b`）。

----------------------------------------------------------------------------
一、坐标口径（**最容易被混用，必须逐条遵守**）
----------------------------------------------------------------------------
1. **字符区间一律半开**：`[charStart, charEnd)`——含头不含尾，`charEnd - charStart`
   是该区间覆盖的字符数。本契约要求 `charEnd > charStart`（空区间不构成证据）。
2. **行号区间是 1 基闭区间**：`[lineStart, lineEnd]`——首行 = 1，两端都包含。
   本契约要求 `lineStart >= 1` 且 `lineEnd >= lineStart`。
3. **字符坐标是 Python 字符串的 Unicode 码点下标**：RAG 侧（`EvidenceSpan.char_span`）
   与宿主后端都是 Python `str`，1 个"字符"= 1 个码点（emoji、生僻汉字都算 1）。
4. **前端是 UTF-16 码元下标，两者不可直接混用**：JavaScript `string.length` 与
   `slice` 按 UTF-16 码元计数，**星平面字符（emoji、U+10000 以上）占 2 个码元**。
   同一个位置在两侧的数值不同（例：`"😀a"` 中 `"a"` 的码点下标是 1，UTF-16 下标是 2）。
   换算必须走本模块的 `codepoint_to_utf16_offset` / `utf16_offset_to_codepoint`，
   **不得**用 `len()` 互相顶替、不得在前端直接套用后端返回的 `charStart/charEnd`。
5. 字符下标指向的是**归一化后的文本**（UTF-8 解码 + 通用换行归一化）的 `str`；
   `fileFingerprint` 指向的是**原始文件字节**的 SHA-256。两者是两套语义，
   不可互推：指纹相同不等于区间可复用（需同一份归一化文本），区间可复用也不等于
   文件未变（必须逐次核对指纹）。行号由该归一化文本的行起点计算得出。

----------------------------------------------------------------------------
二、引用契约
----------------------------------------------------------------------------
1. `fileId` 是语料根内的稳定文件标识（相对路径形态，书册唯一标识；
   同名册靠它消歧）。`fileFingerprint` = **该源文件原始字节的 SHA-256**，
   64 位小写十六进制（等价于 Python `hashlib.sha256(...).hexdigest()` 的输出）。
   `textHash` 同样要求 64 位小写十六进制，语义为"跨区间原文内容的散列"，
   用于比对两侧读到的是不是同一段原文。
2. `Citation.charStart/charEnd` 与 `lineStart/lineEnd` 必须是同 `evidenceId`
   所对应 `EvidenceItem` 区间的**子区间**（`citation ⊆ evidence`）。当前 RAG 侧
   `Citation.from_span()` 逐字段复制 `EvidenceSpan`，因此实际取等号；
   允许更窄子区间是为后续"只引用证据中被采纳的那一段"留出口径。
3. `Citation.evidenceId` 必须命中本结果内已存在的 `EvidenceItem`；
   `evidenceId` 在同一份 `RagAnswer` 内唯一。引用 ID 只在**单结果内**唯一，
   宿主必须连同 `requestId`/`sessionId`/`turnId` 一起绑定后才可跨请求使用。
4. **越界不裁剪**：任何越界（字符区间倒置、行号倒置、引用超出证据区间、
   区间超出源文件长度）都必须显式失败或置状态，**禁止静默裁剪/夹取成合法区间**——
   被裁剪的区间指向的原文与引用声明不一致，属于"看起来成功但内容错位"。
   本模块的 `validate_answer_payload()` 不做任何归一化，只做校验并抛错。

----------------------------------------------------------------------------
三、状态语义（`RagAnswer.status`）
----------------------------------------------------------------------------
- `ok`：有可用答案。必须同时给出非空 `answer`、至少 1 条证据、至少 1 条引用。
- `no_evidence`：检索范围内没有可定位内容（合法结果，不是错误）。
- `stale_source`：**源文件指纹与检索/建索引时不一致**（文件被改、被替换或已删除）。
  此时既有区间不再可解释为"当前文件的第 N 个字符"，一律不得展示为已验证引用。
- `out_of_range`：**区间越界**（超出源文件长度，或引用区间不被证据区间包含）。
- `unavailable`：检索能力不可用（模型/索引/运行时不可就绪）。必须如实上报，
  不得降级成 `no_evidence` 冒充"没有内容"，也不得回落云端或回退模拟结果。
- 统一规则：**所有非 `ok` 状态 `answer is None`、`evidence == []`、`citations == []`，
  且 `warnings` 必须非空**（说明为什么没有答案）。这一条把"失败要有明确表达"变成可测断言。

----------------------------------------------------------------------------
四、执行边界（I1 实现的约束；**除标注外均未实测**）
----------------------------------------------------------------------------
以下为设计边界，本批**只描述、未实测**（宿主侧尚无真实检索可跑，故无任何实测数值）：

- **有界队列**：并发与排队深度必须有上限（GPU 模型访问尤其），超出上限的请求应快速
  失败并返回明确状态，而不是无界排队。**具体上限值与溢出行为均未实测**。
- **超时**：必须区分"总超时"（一次 `query` 从进入到返回）与"检索/推理子超时"
  （如 embedding、检索、生成各自的上限）。子超时先到应产生可解释的部分结果或明确状态，
  总超时到点必须结束等待。**具体秒数与触发点均未实测**。
- **取消**：本契约**只保证"取消等待"**——即调用方停止等待并把该轮次置为终态。
  **"停止底层推理"是另一件事，本契约不声明已能中断**：Python/本地推理进程里已进入
  前向计算的调用通常无法被协作取消，必须实测（对照 `GenerationCancelled.completed`
  这类"取消时是否已经发生推理"的信号）才能写"已停止"。**未实测**。
- **迟到结果**：取消、超时或轮次已终结之后才返回的结果必须按 `requestId`
  （并结合 `sessionId`/`turnId`）丢弃，**不得写入新轮次、不得复活已取消的卡**。
  丢弃必须可观测（计数/日志），不能静默。**未实测**。
- **模型不可用**：必须如实报错（`status="unavailable"` 或抛 `RagAdapterUnavailable`），
  不得静默换模型、不得回落云端、不得返回空证据冒充"没检索到"。
- **不阻塞事件循环**：真实检索是同步 CPU/GPU 工作，必须在有界线程/任务中执行，
  不得直接占用 async 路由的事件循环。**未实测**。

----------------------------------------------------------------------------
五、依赖与版本边界（I1 决策约束）
----------------------------------------------------------------------------
- 本模块只依赖 `pydantic`（宿主 `apps/api` 已锁定，见 `uv.lock`），不引入任何新依赖，
  因此不触碰 `pyproject.toml` 与锁文件。
- 真实 RAG 依赖（`numpy`/`jieba`/`rank_bm25`/`PyYAML`/`httpx`，以及本地推理的
  `transformers`/`tokenizers`/`torch`）**不得**通过永久修改 `sys.path` 指向可变的
  外部目录来引入，也不得复用未记录的 `--system-site-packages` 个人环境；
  应以固定版本 + 独立包命名（或受控源码引入）方式接入，且不改宿主共享环境。
"""

from __future__ import annotations

import re
from typing import Any, Literal, Mapping, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

__all__ = [
    "DEFAULT_MAX_EVIDENCE",
    "MAX_EVIDENCE_ITEMS",
    "MAX_EVIDENCE_TEXT_CHARS",
    "MAX_QUESTION_CHARS",
    "RAG_CAPABILITY",
    "RAG_UNAVAILABLE_MESSAGE",
    "Citation",
    "EvidenceItem",
    "RagAdapter",
    "RagAdapterUnavailable",
    "RagAnswer",
    "RagContractError",
    "RagQuery",
    "RagStatus",
    "ScopeKind",
    "ScopeRef",
    "codepoint_to_utf16_offset",
    "get_rag_adapter",
    "utf16_offset_to_codepoint",
    "validate_answer_payload",
]

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

MAX_QUESTION_CHARS = 4000
MAX_EVIDENCE_TEXT_CHARS = 2000
MAX_EVIDENCE_ITEMS = 20
DEFAULT_MAX_EVIDENCE = 5
SHA256_HEX_LENGTH = 64

_SHA256_HEX_RE = re.compile(r"[0-9a-f]{64}")

#: 契约要求：`fileFingerprint` / `textHash` 采用 SHA-256 的规范小写十六进制形态
#: （与 Python `hashlib.sha256(...).hexdigest()` 输出一致）。大写形态被拒绝，
#: 因为身份比对必须是字节等价而不是"看起来一样"。
SHA256_HEX_HINT = "64 位小写十六进制（sha256 hexdigest 形态）"

#: `ScopeRef.kind` 与 `EvidenceItem.sourceType` 共用同一套取值词表。
ScopeKind = Literal["textbook", "knowledge_base", "notebook"]
SourceType = ScopeKind

RagStatus = Literal["ok", "no_evidence", "stale_source", "out_of_range", "unavailable"]

#: `get_rag_adapter()` 与 `RagAdapterUnavailable` 的统一文案。
#: 明确写"未接入、未实测"，避免任何调用方把契约当成已实现能力。
RAG_UNAVAILABLE_MESSAGE = (
    "RAG 未接入：I0 仅定义契约，尚未接入真实检索（未接入、未实测）。"
)

#: 能力可用性声明。与 `app/api/v1/capabilities.py` 中 `rag` 的 `planned` 状态一致
#: （该文件由其它负责人维护，本模块不修改它，只声明同一事实）。
#: **不得**把它改成 `ready`：能力转 ready 需要端到端真实闭环验收，本轮未做。
RAG_CAPABILITY: dict[str, str] = {
    "feature": "rag",
    "label": "教材检索（RAG）",
    "status": "planned",
    "detail": "I0 仅定义 adapter 契约；没有索引与向量存储，不返回检索结果（未接入、未实测）。",
}


class RagAdapterUnavailable(RuntimeError):
    """RAG adapter 不可用。

    在 I0 阶段这是**唯一**能从 `get_rag_adapter()` 得到的异常：契约已定义，
    能力尚未接入。I1 接入真实检索后，本异常仍用于"已接入但运行时不可就绪"
    （模型/索引加载失败等）的如实上报——不得改写成空证据或模拟结果。
    """


class RagContractError(ValueError):
    """载荷结构合法但违反跨字段契约（状态与载荷不一致、引用悬空、引用区间越界等）。

    与 pydantic 的 `ValidationError`（字段级：类型、长度、区间倒置、指纹格式）
    并列：两者都是 `ValueError` 子类，调用方按 `ValueError` 统一捕获即可。
    本模块不提供任何"自动修正载荷"的入口。
    """


# ---------------------------------------------------------------------------
# 模型
# ---------------------------------------------------------------------------

#: 契约载荷按字段名严格匹配：未知字段直接拒绝，避免上游悄悄加字段后宿主静默丢数据。
_STRICT = ConfigDict(extra="forbid", frozen=True)


def _require_sha256_hex(value: str) -> str:
    """校验 64 位小写十六进制；不做大小写归一（归一=接受两种形态，会掩盖来源差异）。"""
    if not _SHA256_HEX_RE.fullmatch(value):
        preview = value if len(value) <= 16 else f"{value[:16]}…"
        raise ValueError(f"必须是 {SHA256_HEX_HINT}，得到 {preview!r}（长度 {len(value)}）")
    return value


def _require_finite(value: float | None) -> float | None:
    """`score` 是未校准排序值；NaN/Inf 无法进入 JSON、也无法比较，直接拒绝。"""
    if value is None:
        return None
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"score 必须是有限浮点数，得到 {value!r}")
    return value


class ScopeRef(BaseModel):
    """一次查询的限定范围（教材 / 知识库 / 笔记本）。

    范围的作用是**在检索前下推过滤**，而不是检索后再筛掉不合格结果——
    后者会让证据池被范围外的内容挤占（外部项目的 R4 结论）。
    """

    model_config = _STRICT

    kind: ScopeKind
    refId: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)


class RagQuery(BaseModel):
    """一次定位+讲解请求。

    `courseScope=None` 表示不限定范围（全库）。是否允许全库、以及如何把范围
    下推到检索层，由 I1 决定；本契约只描述输入形态。
    """

    model_config = _STRICT

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    courseScope: list[ScopeRef] | None = None
    maxEvidence: int = Field(default=DEFAULT_MAX_EVIDENCE, ge=1, le=MAX_EVIDENCE_ITEMS)


class EvidenceItem(BaseModel):
    """一条可核验的原文证据。

    坐标语义见模块 docstring 第一节：`[charStart, charEnd)` 半开、码点下标；
    `[lineStart, lineEnd]` 1 基闭区间。`text` 是**该区间的原文副本**，
    上限 2000 字符——因此 `len(text)` 与 `charEnd - charStart` 在区间较长时
    **不相等**（副本被截断），不得用 `text` 反推坐标。
    """

    model_config = _STRICT

    evidenceId: str = Field(min_length=1, max_length=128)
    sourceType: SourceType
    sourceId: str = Field(min_length=1, max_length=200)
    sourceName: str = Field(min_length=1, max_length=300)
    charStart: int = Field(ge=0)
    charEnd: int = Field(ge=0)
    lineStart: int = Field(ge=1)
    lineEnd: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=MAX_EVIDENCE_TEXT_CHARS)
    score: float | None = None

    @field_validator("score")
    @classmethod
    def _check_score(cls, value: float | None) -> float | None:
        return _require_finite(value)

    @model_validator(mode="after")
    def _check_spans(self) -> "EvidenceItem":
        if self.charEnd <= self.charStart:
            raise ValueError(
                f"charEnd 必须大于 charStart（半开区间 [charStart, charEnd) 不能为空）："
                f"[{self.charStart}, {self.charEnd})"
            )
        if self.lineEnd < self.lineStart:
            raise ValueError(
                f"lineEnd 必须大于等于 lineStart（1 基闭区间）：[{self.lineStart}, {self.lineEnd}]"
            )
        return self


class Citation(BaseModel):
    """展示级引用：指向源文件的一段已核验原文。

    `fileFingerprint` 是**源文件原始字节**的 sha256；它和 `charStart/charEnd`
    必须来自同一次读取，否则区间无法解释。核对顺序固定为"先指纹、后区间"：
    指纹不符直接 `stale_source`，不再尝试解释区间。
    """

    model_config = _STRICT

    evidenceId: str = Field(min_length=1, max_length=128)
    fileId: str = Field(min_length=1, max_length=300)
    fileFingerprint: str
    charStart: int = Field(ge=0)
    charEnd: int = Field(ge=0)
    lineStart: int = Field(ge=1)
    lineEnd: int = Field(ge=1)
    textHash: str

    @field_validator("fileFingerprint", "textHash")
    @classmethod
    def _check_hex(cls, value: str) -> str:
        return _require_sha256_hex(value)

    @model_validator(mode="after")
    def _check_spans(self) -> "Citation":
        if self.charEnd <= self.charStart:
            raise ValueError(
                f"charEnd 必须大于 charStart（半开区间 [charStart, charEnd) 不能为空）："
                f"[{self.charStart}, {self.charEnd})"
            )
        if self.lineEnd < self.lineStart:
            raise ValueError(
                f"lineEnd 必须大于等于 lineStart（1 基闭区间）：[{self.lineStart}, {self.lineEnd}]"
            )
        return self


class RagAnswer(BaseModel):
    """一次定位+讲解的结果。字段语义与状态-载荷规则见模块 docstring 第三节。

    四个载荷字段都是**必填**（`answer` 允许显式 `null`）：缺少 `warnings` 这类字段
    属于载荷不合规，不得按空列表静默默认——静默默认会让"忘了写原因"看起来像正常结果。
    """

    model_config = _STRICT

    status: RagStatus
    answer: str | None
    evidence: list[EvidenceItem]
    citations: list[Citation]
    warnings: list[str]


# ---------------------------------------------------------------------------
# 端口与可用性声明
# ---------------------------------------------------------------------------


@runtime_checkable
class RagAdapter(Protocol):
    """RAG 检索端口（I1 的真实实现必须满足本协议）。

    接口是 `async`，但**实现内部不得阻塞事件循环**：真实检索是同步 CPU/GPU 工作，
    必须放进有界线程/任务执行，并应用模块 docstring 第四节列出的队列、超时、
    取消、迟到结果与不可用语义。未实测的部分不得对外宣称已满足。
    """

    async def query(self, request: RagQuery, *, requestId: str) -> RagAnswer:
        """按 `request` 检索并返回结果。

        `requestId` 是宿主侧请求/轮次标识，用于**丢弃迟到结果**：调用方在取消或
        轮次终结后，必须按 `requestId` 丢弃该次返回，不得写入新轮次。
        """
        ...


def get_rag_adapter() -> RagAdapter:
    """返回 RAG adapter。**本阶段恒定抛出 `RagAdapterUnavailable`。**

    这里没有、也不得有"空实现"或"返回 `status="ok"` 的假实现"：
    契约的存在不等于能力已接入，任何让调用方以为检索成功的替身都会把
    "未接入"伪装成"检索到了"。I1 接入真实检索时改为从依赖注入/受控工厂取得实例，
    并保持"不可用即抛错"的语义。
    """
    raise RagAdapterUnavailable(RAG_UNAVAILABLE_MESSAGE)


# ---------------------------------------------------------------------------
# 纯校验入口（不产生答案）
# ---------------------------------------------------------------------------


def _check_status_payload(answer: RagAnswer) -> None:
    """状态与载荷一致性（禁止静默降级/静默裁剪）。"""
    if answer.status == "ok":
        if not answer.answer or not answer.answer.strip():
            raise RagContractError("status=ok 必须给出非空 answer")
        if not answer.evidence:
            raise RagContractError("status=ok 必须至少给出 1 条 evidence")
        if not answer.citations:
            raise RagContractError("status=ok 必须至少给出 1 条 citation")
        return

    # 非 ok：不得携带任何"看起来可用"的内容，且必须说明原因。
    if answer.answer is not None:
        raise RagContractError(
            f"status={answer.status} 时 answer 必须为 None（不得用说明文本冒充答案）"
        )
    if answer.evidence:
        raise RagContractError(
            f"status={answer.status} 时 evidence 必须为空（禁止展示未经核验/已越界的区间）"
        )
    if answer.citations:
        raise RagContractError(
            f"status={answer.status} 时 citations 必须为空（禁止展示失效或越界的引用）"
        )
    if not answer.warnings:
        raise RagContractError(f"status={answer.status} 必须至少给出 1 条 warning 说明原因")


def _check_citation_links(answer: RagAnswer) -> None:
    """引用与证据的对应关系：不悬空、不重复、不越界。"""
    by_id: dict[str, EvidenceItem] = {}
    for item in answer.evidence:
        if item.evidenceId in by_id:
            raise RagContractError(f"evidenceId 在同一结果内必须唯一，重复：{item.evidenceId!r}")
        by_id[item.evidenceId] = item

    seen_citations: set[str] = set()
    for citation in answer.citations:
        if citation.evidenceId in seen_citations:
            raise RagContractError(
                f"同一证据不得对应多条 citation（citation.evidenceId 必须唯一）："
                f"{citation.evidenceId!r}"
            )
        seen_citations.add(citation.evidenceId)

        evidence = by_id.get(citation.evidenceId)
        if evidence is None:
            raise RagContractError(
                f"citation 引用了不存在的 evidenceId：{citation.evidenceId!r}"
                "（悬空引用不得发布）"
            )
        if not (
            evidence.charStart <= citation.charStart
            and citation.charEnd <= evidence.charEnd
            and evidence.lineStart <= citation.lineStart
            and citation.lineEnd <= evidence.lineEnd
        ):
            raise RagContractError(
                "citation 区间必须落在对应 evidence 区间内（citation ⊆ evidence），"
                f"得到 citation=[{citation.charStart}, {citation.charEnd}) 行"
                f"[{citation.lineStart}, {citation.lineEnd}] vs evidence=[{evidence.charStart}, "
                f"{evidence.charEnd}) 行[{evidence.lineStart}, {evidence.lineEnd}]"
            )


def validate_answer_payload(payload: Mapping[str, Any]) -> RagAnswer:
    """纯校验入口：把 dict 校验成 `RagAnswer`。**不产生答案、不访问源文件、不做 I/O。**

    分为两层，任一失败都抛 `ValueError`（`ValidationError` 或 `RagContractError`）：

    1. **字段级**（pydantic）：类型、长度、`charEnd > charStart`、`lineEnd >= lineStart`、
       指纹/散列的 64 位小写十六进制、未知字段、缺失字段。
    2. **跨字段**：状态与载荷一致（非 `ok` 不得带 answer/evidence/citations 且必须有
       warning）、`evidenceId` 唯一、引用不悬空、`citation ⊆ evidence`。

    **本函数不校验、也无法校验的内容（如实说明）**：
    - `charEnd` 是否超出源文件长度；`textHash` 是否真的等于该区间原文的散列；
      `fileFingerprint` 是否与磁盘上的文件一致。这些都需要**可信语料根内的真实源文件**，
      必须由服务端在读取时重新核对（先指纹、后区间），本纯函数没有该输入。
    - `Citation.fileId` 与对应 `EvidenceItem.sourceId` 的绑定关系（同一证据是否指向
      同一源文件）。本契约不规定这两个字段必须字面相等（它们的命名空间由 I1 决定），
      绑定与核对是 I1 服务端的责任。
    - 答案的语义正确性、教学正确性、检索质量。

    区间倒置、指纹格式非法、越界引用一律**抛错**，绝不静默裁剪成合法区间。
    """
    if not isinstance(payload, Mapping):
        raise RagContractError(f"payload 必须是映射（dict），得到 {type(payload).__name__}")

    answer = RagAnswer.model_validate(payload)
    _check_status_payload(answer)
    _check_citation_links(answer)
    return answer


# ---------------------------------------------------------------------------
# 坐标换算纯函数（码点 <-> UTF-16 码元）
# ---------------------------------------------------------------------------


def _is_astral(character: str) -> bool:
    """是否占用 2 个 UTF-16 码元（U+10000 及以上的星平面字符，含 emoji）。"""
    return ord(character) > 0xFFFF


def codepoint_to_utf16_offset(text: str, codepoint_offset: int) -> int:
    """把 Python 码点下标换算成前端 UTF-16 码元下标。

    `text` 是被索引的字符串；`codepoint_offset` 是同一字符串上的码点下标，
    允许等于 `len(text)`（表示"末尾之后"）。返回 `text[:codepoint_offset]`
    占用的 UTF-16 码元数，范围 `[0, utf16_length]`。

    越界（负数或大于 `len(text)`）抛 `ValueError`；不夹取、不取模。
    """
    if not isinstance(text, str):
        raise TypeError(f"text 必须是 str，得到 {type(text).__name__}")
    if not isinstance(codepoint_offset, int) or isinstance(codepoint_offset, bool):
        raise TypeError(f"codepoint_offset 必须是 int，得到 {type(codepoint_offset).__name__}")
    if codepoint_offset < 0 or codepoint_offset > len(text):
        raise ValueError(
            f"codepoint_offset 越界：{codepoint_offset} 不在 [0, {len(text)}] 内"
        )
    return sum(2 if _is_astral(character) else 1 for character in text[:codepoint_offset])


def utf16_offset_to_codepoint(text: str, utf16_offset: int) -> int:
    """把前端 UTF-16 码元下标换算回 Python 码点下标。

    `utf16_offset` 允许等于该字符串的 UTF-16 总长度（表示"末尾之后"），
    此时返回 `len(text)`。

    两种越界都抛 `ValueError`：① 超出 `[0, utf16_length]`；
    ② 落在代理对**内部**（即该 UTF-16 下标把 2 码元的星平面字符切成两半），
    这种位置不对应任何码点边界，必须拒绝而不是取整——
    取整会让前端定位悄悄偏移一个字符。

    对合法码点边界，本函数与 `codepoint_to_utf16_offset` 互为逆函数。
    """
    if not isinstance(text, str):
        raise TypeError(f"text 必须是 str，得到 {type(text).__name__}")
    if not isinstance(utf16_offset, int) or isinstance(utf16_offset, bool):
        raise TypeError(f"utf16_offset 必须是 int，得到 {type(utf16_offset).__name__}")
    if utf16_offset < 0:
        raise ValueError(f"utf16_offset 越界：{utf16_offset} 不能为负")

    consumed = 0
    for index, character in enumerate(text):
        if consumed == utf16_offset:
            return index
        consumed += 2 if _is_astral(character) else 1
        if consumed > utf16_offset:
            raise ValueError(
                f"utf16_offset={utf16_offset} 落在代理对内部（第 {index} 个码点是星平面字符，"
                "占 2 个 UTF-16 码元），该位置不对应任何码点边界"
            )
    if consumed == utf16_offset:
        return len(text)
    raise ValueError(
        f"utf16_offset 越界：{utf16_offset} 超出字符串的 UTF-16 长度 {consumed}"
    )
