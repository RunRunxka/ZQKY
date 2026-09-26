"""跨模块数据契约 —— 单一定义点，配套 docs/SCHEMA.md。

任何模块不得重复定义 Chunk / 评测题结构；字段变更须同步 docs/SCHEMA.md 并升版本。
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass

EVAL_VERSION = "v2"  # v2 = v1 + source_file 字段（题面/gold/题数/顺序零变化，见 EVAL.md 变更记录）

REGION_BODY = "body"
REGION_EXERCISE = "exercise"
REGIONS = (REGION_BODY, REGION_EXERCISE)

SUBHEAD_KIND_SECTION = "section"
SUBHEAD_KIND_SUB = "sub"
SUBHEAD_KIND_PRACTICE = "practice"
SUBHEAD_KIND_COLUMN = "column"
SUBHEAD_KINDS = (SUBHEAD_KIND_SECTION, SUBHEAD_KIND_SUB,
                 SUBHEAD_KIND_PRACTICE, SUBHEAD_KIND_COLUMN)

# 评测题 JSON 的字段集（docs/SCHEMA.md §二）。source_chunk_id + source_file
# 联合定位来源 chunk（A/B 同名册 chunk_id 跨册重复，单键有歧义），
# 供评测时屏蔽来源 chunk 与数据泄漏检查。
EVAL_QUESTION_FIELDS = ("question", "book", "gold_path", "source_file",
                        "source_chunk_id", "subject", "eval_version")

CHUNK_JSON_FIELDS = ("book", "file", "path", "subhead", "subhead_kind", "start",
                     "end", "start_line", "end_line", "text", "region", "chunk_id")


@dataclass
class Chunk:
    """检索/定位的基本单元。不变量由 src/verify.py 与 tests 保证（docs/SCHEMA.md §一）。

    file 是来源文件相对语料根的路径（溯源用）。A/B 版存在同名册，book/chunk_id
    在书内唯一但跨同名册会重复——分组与过滤一律以 file 为准，命中判定用 book
    （与原型一致的语义）。
    """

    book: str
    file: str
    path: list[str]
    subhead: str
    subhead_kind: str
    start: int
    end: int
    start_line: int
    end_line: int
    text: str
    region: str
    chunk_id: str = ""

    def __post_init__(self) -> None:
        if self.region not in REGIONS:
            raise ValueError(f"region 必须是 {REGIONS}，得到 {self.region!r}")
        if self.subhead_kind not in SUBHEAD_KINDS:
            raise ValueError(f"subhead_kind 必须是 {SUBHEAD_KINDS}，得到 {self.subhead_kind!r}")

    def header(self) -> str:
        """章节路径 + 有信息量的栏目名。

        「思考」「观察」等高频栏目（subhead_kind == column）在全书出现几十次，
        写进索引只引入噪声，不进 header；「列举法」这类无编号子标题是真正的
        知识点名，习题区标题（习题1.1）用于标注归属，都要保留。
        """
        parts = list(self.path)
        if self.subhead and self.subhead not in parts and self.subhead_kind != SUBHEAD_KIND_COLUMN:
            parts.append(self.subhead)
        return " > ".join(parts)

    def index_text(self) -> str:
        """送入索引的文本 = 章节路径前置 + 正文（contextual chunk headers）。"""
        return f"{self.header()}\n{self.text}"

    def locate(self) -> str:
        return f"{self.header()}  [第 {self.start_line}-{self.end_line} 行]"

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: d[k] for k in CHUNK_JSON_FIELDS}

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        missing = [k for k in CHUNK_JSON_FIELDS if k not in d]
        if missing:
            raise ValueError(f"chunk 缺少字段: {missing}")
        return cls(**{k: d[k] for k in CHUNK_JSON_FIELDS})


def sha256_file(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_jsonl(path: str | os.PathLike, rows: list[dict]) -> None:
    """原子写出 jsonl（先写临时文件再替换，冻结产物不被半途状态污染）。"""
    path = os.fspath(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def read_jsonl(path: str | os.PathLike) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# P6 证据契约（v1）—— 原文区间重建与引用。单一定义点，配套 docs/SCHEMA.md §九。
# ---------------------------------------------------------------------------

EVIDENCE_CONTRACT_VERSION = "v1"

#: LocateResult.status（显式区分，不允许都返回"成功"）
STATUS_OK = "ok"                                 # 定位与（可选）解释均成功
STATUS_PARTIAL = "partial"                       # 定位/原文可用，但解释缺失或生成失败
STATUS_UNCERTAIN = "uncertain"                   # 证据不足：不硬答
STATUS_GENERATION_FAILED = "generation_failed"   # 有证据但生成失败（保留定位）
STATUS_MODEL_UNAVAILABLE = "model_unavailable"   # 本地生成模型不可用（不回落云端）
STATUS_INVALID_CITATION = "invalid_citation"     # 引用校验失败（错误引用禁止展示）
LOCATE_STATUSES = (STATUS_OK, STATUS_PARTIAL, STATUS_UNCERTAIN,
                   STATUS_GENERATION_FAILED, STATUS_MODEL_UNAVAILABLE,
                   STATUS_INVALID_CITATION)

EVIDENCE_METHODS = ("single_chunk", "bounded_window", "rse")
#: 分数种类。不同来源的分数**不可比**，不得共享同一绝对阈值。
SCORE_KINDS = ("fusion_score", "bm25", "cosine", "rerank_raw_logit")


@dataclass
class EvidenceSpan:
    """一段可核验的教材原文证据（坐标语义见 docs/SCHEMA.md §九）。

    - `char_span` 为半开区间 `[start, end)`，下标是 `read_book()` 返回的 **str** 的
      Unicode 码点下标（UTF-8 解码 + 通用换行归一化之后），**不是文件字节偏移**；
    - `source_sha256` 是**原始文件字节**的 sha256（与字符下标是两套语义）；
    - `line_span` 为 1-based **闭区间** `[start_line, end_line]`，由
      `src.parsing.structure.to_line(line_starts_of(source_text), pos)` 计算，与 chunk 一致；
    - `text` 必须逐字符等于 `source_text[start:end]`（由 `validate_evidence` 校验），
      **不得**由 chunk.text 拼接（会丢标题/空白）。
    """

    citation_id: str                 # 服务内唯一（如 "c1"）；同一结果内不重复
    file: str                        # 相对语料根路径（书册唯一标识；A/B 同名册据此消歧）
    book: str                        # 展示用书名
    path: list[str]                  # 章节路径
    source_sha256: str               # 原始文件字节 sha256
    char_span: list[int]             # [start, end)
    line_span: list[int]             # [start_line, end_line]，1-based 闭区间
    text: str                        # = source_text[start:end]，程序切出
    chunk_ids: list[str]             # 来源 chunk 的联合 ID（配合 file 全局唯一）
    method: str                      # ∈ EVIDENCE_METHODS
    selection_score: float | None = None   # 未校准的选择分（不同来源不可比）
    score_kind: str | None = None          # ∈ SCORE_KINDS
    expansions: dict | None = None         # 扩展依据（补入的相邻块/跳过区域等）

    def __post_init__(self) -> None:
        if self.method not in EVIDENCE_METHODS:
            raise ValueError(f"method 必须是 {EVIDENCE_METHODS}，得到 {self.method!r}")
        if not self.citation_id:
            raise ValueError("citation_id 不能为空")
        if len(self.char_span) != 2 or self.char_span[0] < 0 or self.char_span[1] < self.char_span[0]:
            raise ValueError(f"char_span 必须是 [start, end) 且 start>=0：{self.char_span}")
        if len(self.line_span) != 2 or self.line_span[0] < 1 or self.line_span[1] < self.line_span[0]:
            raise ValueError(f"line_span 必须是 1-based 闭区间：{self.line_span}")
        if self.score_kind is not None and self.score_kind not in SCORE_KINDS:
            raise ValueError(f"score_kind 必须是 {SCORE_KINDS} 之一，得到 {self.score_kind!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EvidenceSpan":
        return cls(**d)


@dataclass
class Citation:
    """面向最终用户/合并的展示级引用（EvidenceSpan 的精简子集：去掉分数与内部分法）。"""

    citation_id: str
    file: str
    book: str
    path: list[str]
    source_sha256: str
    char_span: list[int]
    line_span: list[int]
    text: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_span(cls, span: EvidenceSpan) -> "Citation":
        return cls(citation_id=span.citation_id, file=span.file, book=span.book,
                   path=list(span.path), source_sha256=span.source_sha256,
                   char_span=list(span.char_span), line_span=list(span.line_span),
                   text=span.text)


@dataclass
class Supplement:
    """教材外补充：`is_external` 恒为 True，默认可为空（不强行补充）。"""

    text: str
    is_external: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExplanationItem:
    """一条可审核的解释：`citation_ids` 必须是本结果内已校验证据的 ID。"""

    point: str
    citation_ids: list[str]
    explanation: str
    supplement: Supplement | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ExplanationItem":
        sup = d.get("supplement")
        return cls(point=d["point"], citation_ids=list(d.get("citation_ids") or []),
                   explanation=d.get("explanation", ""),
                   supplement=Supplement(**sup) if isinstance(sup, dict) else None)


@dataclass
class LocateResult:
    """服务层结果（版本化）。字段语义见 docs/SCHEMA.md §九。"""

    contract_version: str
    question: str
    status: str
    subject: str | None
    constraints: dict                    # 检索约束（scope/subject/book/file、pool/k 等）
    evidence: list[EvidenceSpan]
    citations: list[Citation]
    explanations: list[ExplanationItem]
    uncertain_reason: str | None
    provenance: dict                     # 检索配置、模型身份、来源、计数等

    def __post_init__(self) -> None:
        if self.status not in LOCATE_STATUSES:
            raise ValueError(f"status 必须是 {LOCATE_STATUSES} 之一，得到 {self.status!r}")

    def to_dict(self) -> dict:
        return {
            "contract_version": self.contract_version,
            "question": self.question,
            "status": self.status,
            "subject": self.subject,
            "constraints": self.constraints,
            "evidence": [e.to_dict() for e in self.evidence],
            "citations": [c.to_dict() for c in self.citations],
            "explanations": [e.to_dict() for e in self.explanations],
            "uncertain_reason": self.uncertain_reason,
            "provenance": self.provenance,
        }


def line_starts_of(text: str) -> list[int]:
    """每行起始字符偏移（1-based 行号由 `to_line` 二分得到）。与 chunk 同实现。"""
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def normalize_file(path: str) -> str:
    """路径分隔符归一化为 ``/``。

    冻结产物里 `chunks.jsonl` 的 `file` 与 `questions.jsonl` 的 `source_file` 在 Windows 上
    含反斜杠（不修改冻结数据），而 P6 证据契约的 `EvidenceSpan.file` 使用正斜杠。
    **任何跨这两个来源的字面比较都必须先过本函数**，否则同一本书会被判成两个来源。
    """
    return str(path).replace("\\", "/")


def to_line(line_starts: list[int], off: int) -> int:
    """字符偏移 → 1-based 行号（最后一个起点 ≤ off 的行）。与 `src.parsing.structure` 同义。"""
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= off:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


def validate_evidence(span: EvidenceSpan, source_text: str,
                      source_sha256: str | None = None,
                      line_starts: list[int] | None = None) -> list[str]:
    """校验证据与原文一致性；返回问题列表（空 = 通过）。**程序化校验是引用放行的唯一依据。**

    检查：① 区间合法且在范围内；② `text == source_text[start:end]` 逐字符一致；
    ③ `line_span` 与 `to_line` 重算一致（给了 line_starts 时）；④ 文件字节 sha256 一致（给了时）。
    """
    problems: list[str] = []
    start, end = span.char_span
    if start < 0 or end > len(source_text) or start >= end:
        problems.append(f"char_span {span.char_span} 越界或为空（源文本长 {len(source_text)}）")
        return problems
    piece = source_text[start:end]
    if piece != span.text:
        problems.append("text 与 source_text[start:end] 不一致（禁止拼接/改写原文）")
    if line_starts is not None:
        want = [to_line(line_starts, start), to_line(line_starts, end)]
        if list(span.line_span) != want:
            problems.append(f"line_span {span.line_span} 与重算 {want} 不一致")
    if source_sha256 is not None and span.source_sha256 != source_sha256:
        problems.append("源文件字节 sha256 与当前文件不一致（陈旧引用，拒绝展示）")
    return problems
