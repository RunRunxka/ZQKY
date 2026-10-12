"""原文证据重建：**有界**邻块窗口 + 不可变切片 + 预算取舍 + 可读投影。

对应 docs/PLAN.md §3.3（有界证据窗口）与任务卡 B1-RAG-ANSWER：

- 邻块扩展**左右各最多 ``EVIDENCE_NEIGHBOURS_EACH_SIDE`` 块**（默认 1），只有同一文档修订
  （同一分块集）、同一章节路径、同一正文区且几何相邻的块才可并入；绝不跨文档、跨章节、
  跨习题区。旧实现沿同章无上限扩张（823 码点命中扩成整章 45,577 码点），合并结果超预算后
  又被整条丢弃 → 首答误报"没有找到教材依据"；本模块按预算封顶。
- 单条证据：**原文切片 ≤ ``EVIDENCE_SINGLE_RAW_MAX_CHARS``**、**清洗后文本 ≤
  ``EVIDENCE_SINGLE_CLEANED_MAX_CHARS``**。合并窗口装不下时先退回命中块本身（保住整块），
  命中块自身也超预算时按**完整段落/句子**在命中附近取窗口，绝不从公式、代码围栏或表格中间
  截断；连最小可读窗口都装不下时**整条不采用**并记下 locator，继续考察后续候选。
- 首答返回**最多 ``FIRST_ANSWER_EVIDENCE_MAX_ITEMS`` 条**、原文总量
  **≤ ``EVIDENCE_TOTAL_RAW_MAX_CHARS``**；总量放不下的整条跳过，**绝不截断单条**。
- 清洗后为空的候选**跳过**并继续考察后续候选。
- 每条证据都带 ``readable``（B0 ``project_readable`` 的派生展示文本）：``text`` 仍是**逐字节
  一致**的封存原文切片（引用、散列、坐标都绑定它），``readable.text`` 只是清洗后的展示/入模
  文本；来源面板"展开摘录"用的完整清洗文本就是 ``readable.text``，不新造字段。
- 状态语义（不得退化）：有文本命中但全部装不进预算 → ``partial`` +
  ``EVIDENCE_UNIT_TOO_LARGE``（附 locator）；有命中但清洗后没有文本 → ``uncertain`` +
  ``EVIDENCE_TEXT_EMPTY``；范围内没有任何文本命中 → ``no_evidence`` + ``NO_MATCH``。

所有预算数字**只从 ``app.core.rag_budget`` 读**，不在本模块散写（PLAN §3.3 表）。
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.core.exceptions import AppError
from app.core.rag_budget import (
    EVIDENCE_NEIGHBOURS_EACH_SIDE,
    EVIDENCE_SINGLE_CLEANED_MAX_CHARS,
    EVIDENCE_SINGLE_RAW_MAX_CHARS,
    EVIDENCE_TOTAL_RAW_MAX_CHARS,
    FIRST_ANSWER_EVIDENCE_MAX_ITEMS,
)
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import RevisionRecord
from app.schemas.rag_v2 import EvidenceReadable, EvidenceRef, TextbookEvidence
from app.services.rag_v2.retrieval import Candidate
from app.services.rag_v2.scope import (
    BODY_REGION,
    RevisionScope,
    scope_by_chunk_set,
    scope_by_revision,
)
from app.services.rag_v2.source_text import ImmutableSource, ImmutableTextSource, unavailable
from app.services.text_projection import (
    TEXT_PROJECTION_VERSION,
    TextProjection,
    project_readable,
    scan_code_and_math_ranges,
)

#: 旧名保留：首答证据条数上限（= 预算唯一事实来源里的 ``FIRST_ANSWER_EVIDENCE_MAX_ITEMS``）
MAX_EVIDENCE_ITEMS = FIRST_ANSWER_EVIDENCE_MAX_ITEMS
#: 旧名保留：首答原文证据**总量**上限（= ``EVIDENCE_TOTAL_RAW_MAX_CHARS``）
MAX_EVIDENCE_CHARS = EVIDENCE_TOTAL_RAW_MAX_CHARS
#: 相邻判定允许的字符缝：分块在行边界切开时，分隔换行可能落在两块之外，
#: 因此"相邻"包含 ≤2 码点的缝。跨章节由章节路径拦住，跨习题区由块区与区间核验拦住。
MAX_SPAN_GAP = 2
#: 命中锚点搜索：滑动窗口与步长（码点）。只在"命中块自身超预算"路径用来找命中附近窗口。
_ANCHOR_WINDOW = 60
_ANCHOR_STEP = 20
#: 句子切点（切点落在这些字符之后）。
_SENTENCE_ENDS = "。！？；!?;"


def sha256_utf8(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evidence_id(document_revision_id: str, char_start: int, char_end: int) -> str:
    """稳定引用 id：同修订同区间恒等，不随检索顺序或缓存变化。"""
    digest = sha256_utf8(f"{document_revision_id}:{char_start}:{char_end}")
    return f"ev-{digest[:16]}"


@dataclass(frozen=True)
class EvidenceSpan:
    """待重建的一段原文区间（已合并的完整 span）。"""

    chunk_set_id: str
    document_revision_id: str
    char_start: int
    char_end: int
    chapter_path: tuple[str, ...]
    fused_score: float

    @property
    def length(self) -> int:
        return self.char_end - self.char_start


@dataclass(frozen=True)
class EvidenceSelection:
    """一次证据选择的结果：状态、原因码与可解释定位。

    ``status`` / ``reason_code`` 映射固定为（PLAN §3.3，不得退化）：

    ==================  =============================  ====================================
    status              reason_code                    条件
    ==================  =============================  ====================================
    ``ok``              ``None``                       至少一条证据装入预算
    ``partial``         ``EVIDENCE_UNIT_TOO_LARGE``    有文本命中，但全部因受保护单元超预算无法完整装入
    ``uncertain``       ``EVIDENCE_TEXT_EMPTY``        有文本命中，但清洗后没有可检索文本
    ``no_evidence``     ``NO_MATCH``                   范围内没有任何文本命中
    ==================  =============================  ====================================
    """

    status: str
    reason_code: str | None
    reason: str | None
    evidence: tuple[TextbookEvidence, ...]
    oversized_locators: tuple[object, ...] = ()
    skipped_empty_candidates: int = 0
    saw_text_hit: bool = False
    truncated_by_budget: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass(frozen=True)
class _Piece:
    """已装入预算的一段证据（原文区间 + 清洗投影）。"""

    char_start: int
    char_end: int
    projection: TextProjection

    @property
    def raw_chars(self) -> int:
        return self.char_end - self.char_start

    @property
    def cleaned_chars(self) -> int:
        return len(self.projection.text)


# --------------------------------------------------------------------------- 几何

def _mergeable_bounds(
    neighbour,
    *,
    chapter_path: tuple[str, ...],
    span_start: int,
    span_end: int,
    bounds: tuple[int, int],
) -> bool:
    """可以并入当前 span 的邻块：正文区、同章节、且在字符空间上相邻或重叠。

    ``bounds`` 是**裁剪到正文区后**的区间（块可能带跨界重叠尾巴）。
    """
    if neighbour.region != BODY_REGION:
        return False
    if tuple(neighbour.chapter_path) != chapter_path:
        return False
    return bounds[1] + MAX_SPAN_GAP >= span_start and bounds[0] <= span_end + MAX_SPAN_GAP


def _body_ranges(texts, catalog: TextbookCatalog, revision_id: str) -> list[tuple[int, int]] | None:
    """该修订的正文区区间表；没有区能力的替身返回 None（退回"块区间即区间"）。"""
    reader = getattr(texts, "region_spans", None)
    if not callable(reader):
        return None
    revision = catalog.get_revision(revision_id)
    if revision is None:
        raise unavailable("检索候选的修订不存在，已停止重建原文。")
    return [
        (span.char_start, span.char_end)
        for span in reader(revision)
        if span.region == BODY_REGION
    ]


def _clip_to_body(start: int, end: int, body_ranges: list[tuple[int, int]] | None) -> tuple[int, int] | None:
    """把块区间裁到正文区：分块可能在正文/习题边界处带上下文重叠尾巴。

    只取与正文区重叠的那一段；完全不落在正文区的块（含被错误标成 body 的块）返回 None 并跳过——
    证据永不含习题区文本，但一个坏块也不该让整轮失败。
    """
    if body_ranges is None:
        return (start, end)
    for body_start, body_end in body_ranges:
        if body_start < end and body_end > start:
            clipped_start, clipped_end = max(start, body_start), min(end, body_end)
            if clipped_end > clipped_start:
                return (clipped_start, clipped_end)
    return None


@dataclass
class _Environment:
    """一次选择期间的有界缓存（原文、块表、正文区、裁剪区间、保护区）。"""

    catalog: TextbookCatalog
    source: ImmutableTextSource
    texts: dict[str, str] = field(default_factory=dict)
    chunks: dict[str, list] = field(default_factory=dict)
    positions: dict[str, dict[int, int]] = field(default_factory=dict)
    body_ranges: dict[str, list[tuple[int, int]] | None] = field(default_factory=dict)
    clipped: dict[tuple[str, int], tuple[int, int] | None] = field(default_factory=dict)
    protected: dict[str, list[tuple[int, int]]] = field(default_factory=dict)

    def text_for(self, revision: RevisionRecord) -> str:
        cached = self.texts.get(revision.revision_id)
        if cached is None:
            cached = self.source.read_normalized_text(revision)
            if sha256_utf8(cached) != revision.normalized_text_sha256:
                raise unavailable("规范化原文指纹与修订登记不符，已停止使用该教材原句。")
            self.texts[revision.revision_id] = cached
        return cached

    def chunks_for(self, chunk_set_id: str) -> list:
        cached = self.chunks.get(chunk_set_id)
        if cached is None:
            cached = self.catalog.list_chunks(chunk_set_id)
            self.chunks[chunk_set_id] = cached
            self.positions[chunk_set_id] = {
                chunk.ordinal: index for index, chunk in enumerate(cached)
            }
        return cached

    def body_ranges_for(self, revision_id: str) -> list[tuple[int, int]] | None:
        if revision_id not in self.body_ranges:
            self.body_ranges[revision_id] = _body_ranges(self.source, self.catalog, revision_id)
        return self.body_ranges[revision_id]

    def bounds_of(self, chunk_set_id: str, revision_id: str, chunk) -> tuple[int, int] | None:
        """块区间裁剪到正文区（按修订缓存正文区间表）。"""
        key = (chunk_set_id, chunk.ordinal)
        if key not in self.clipped:
            self.clipped[key] = _clip_to_body(
                chunk.char_start, chunk.char_end, self.body_ranges_for(revision_id)
            )
        return self.clipped[key]

    def protected_for(self, revision_id: str, raw: str) -> list[tuple[int, int]]:
        """该修订的公式/代码保护区（整份原文扫描一次，按修订缓存）。"""
        if revision_id not in self.protected:
            self.protected[revision_id] = [
                (item.start, item.end) for item in scan_code_and_math_ranges(raw)
            ]
        return self.protected[revision_id]


def _bounded_window(
    *,
    chunks: Sequence,
    position: int,
    seed: tuple[int, int],
    chapter_path: tuple[str, ...],
    bounds_of: Callable[[object], tuple[int, int] | None],
    neighbours_each_side: int,
) -> tuple[int, int]:
    """命中块 + 左右各最多 ``neighbours_each_side`` 个可并入邻块。

    与旧实现相同的合并条件（正文区 / 同章节 / 几何相邻），只是**步数有界**：
    超长块再也不会沿同章无限扩张成整章。
    """
    start, end = seed
    for step in range(1, max(0, neighbours_each_side) + 1):
        left = position - step
        if left < 0:
            break
        neighbour = chunks[left]
        if neighbour.region != BODY_REGION:
            break
        neighbour_bounds = bounds_of(neighbour)
        if neighbour_bounds is None or not _mergeable_bounds(
            neighbour,
            chapter_path=chapter_path,
            span_start=start,
            span_end=end,
            bounds=neighbour_bounds,
        ):
            break
        start = min(start, neighbour_bounds[0])
    for step in range(1, max(0, neighbours_each_side) + 1):
        right = position + step
        if right >= len(chunks):
            break
        neighbour = chunks[right]
        if neighbour.region != BODY_REGION:
            break
        neighbour_bounds = bounds_of(neighbour)
        if neighbour_bounds is None or not _mergeable_bounds(
            neighbour,
            chapter_path=chapter_path,
            span_start=start,
            span_end=end,
            bounds=neighbour_bounds,
        ):
            break
        end = max(end, neighbour_bounds[1])
    return start, end


# --------------------------------------------------------------------- 完整切点

def _table_ranges(raw: str, lo: int, hi: int) -> list[tuple[int, int]]:
    """连续表格行块（以 ``|`` 开头的行）当作不可拆单元，避免从表格中间截断。"""
    ranges: list[tuple[int, int]] = []
    run_start: int | None = None
    run_end = lo
    position = lo
    while position <= hi:
        line_end = raw.find("\n", position, hi)
        if line_end == -1:
            line_end = hi
        line = raw[position:line_end].strip()
        is_table = line.startswith("|")
        if is_table:
            if run_start is None:
                run_start = position
            run_end = line_end
        elif run_start is not None:
            ranges.append((run_start, run_end))
            run_start = None
        position = line_end + 1
    if run_start is not None:
        ranges.append((run_start, run_end))
    return ranges


def _cut_positions(
    raw: str,
    lo: int,
    hi: int,
    protected: Sequence[tuple[int, int]],
) -> list[int]:
    """允许的切点：段落/句子/行边界，且**不落在保护区或表格行块内部**。

    - ``lo`` 与 ``hi`` 永远允许，因此"整段"本身也是一个合法窗口；
    - 公式（``$…$`` / ``$$…$$``）、行内代码、代码围栏内部一律不可切；
    - 表格行块的内部行边界不可切（表格作为一个整体）。
    """
    blocked = _table_ranges(raw, lo, hi)
    cuts = {lo, hi}
    index = raw.find("\n", lo, hi)
    while index != -1:
        cuts.add(index)
        cuts.add(index + 1)
        index = raw.find("\n", index + 1, hi)
    for offset, char in enumerate(raw[lo:hi], start=lo):
        if char in _SENTENCE_ENDS:
            cuts.add(offset + 1)

    def inside(cut: int) -> bool:
        for start, end in protected:
            if start < cut < end:
                return True
        for start, end in blocked:
            if start < cut < end:
                return True
        return False

    return sorted(cut for cut in cuts if lo <= cut <= hi and not inside(cut))


def _fit(
    raw: str,
    cache: dict[tuple[int, int], _Piece | None],
    start: int,
    end: int,
    *,
    max_raw: int,
    max_cleaned: int,
) -> _Piece | None:
    """窗口是否同时满足原文与清洗后预算；结果按区间缓存（无 I/O、纯内存）。"""
    if end <= start or end - start > max_raw:
        return None
    key = (start, end)
    if key not in cache:
        projection = project_readable(raw[start:end], absolute_start=start)
        cache[key] = (
            None if len(projection.text) > max_cleaned else _Piece(start, end, projection)
        )
    return cache[key]


def _anchor(raw: str, start: int, end: int, question: str | None) -> int:
    """命中附近的锚点：题面二元组在块内匹配最密处；没有题面时退回块起点。"""
    if not question or end - start <= _ANCHOR_WINDOW:
        return start
    grams = {question[index : index + 2] for index in range(len(question) - 1)}
    if not grams:
        return start
    best_score, best_anchor = 0, start
    for offset in range(start, end - _ANCHOR_WINDOW + 1, _ANCHOR_STEP):
        window = raw[offset : offset + _ANCHOR_WINDOW]
        score = sum(1 for index in range(len(window) - 1) if window[index : index + 2] in grams)
        if score > best_score:
            best_score, best_anchor = score, offset + _ANCHOR_WINDOW // 2
    return best_anchor


def _near_hit_window(
    raw: str,
    *,
    lo: int,
    hi: int,
    anchor: int,
    protected: Sequence[tuple[int, int]],
    max_raw: int,
    max_cleaned: int,
) -> _Piece | None:
    """在 [lo, hi) 内按完整段落/句子取命中附近窗口；装不下返回 None。

    - 锚点所在的不可拆单元（公式 / 代码 / 表格）必须**整块**包含，绝不切开；
    - 从最小完整单元向两侧按完整切点扩张（先右后左），直到预算上限；
    - 没有任何合法窗口能装下 → None（调用方记为"受保护单元超预算"，附 locator）。
    """
    if hi <= lo:
        return None
    anchor = min(max(anchor, lo), max(lo, hi - 1))
    units = [*protected, *_table_ranges(raw, lo, hi)]
    cuts = _cut_positions(raw, lo, hi, protected)
    guard_start, guard_end = anchor, anchor + 1
    for start, end in units:
        if start <= anchor < end:
            guard_start, guard_end = max(start, lo), min(end, hi)
            break
    cache: dict[tuple[int, int], _Piece | None] = {}
    if guard_end - guard_start > max_raw:
        return None

    def lower_bound(position: int) -> int:
        allowed = [cut for cut in cuts if cut <= position]
        return max(allowed) if allowed else lo

    def upper_bound(position: int) -> int:
        allowed = [cut for cut in cuts if cut >= position]
        return min(allowed) if allowed else hi

    left, right = lower_bound(guard_start), upper_bound(guard_end)
    piece = _fit(raw, cache, left, right, max_raw=max_raw, max_cleaned=max_cleaned)
    if piece is None:
        left, right = guard_start, guard_end
        piece = _fit(raw, cache, left, right, max_raw=max_raw, max_cleaned=max_cleaned)
        if piece is None:
            return None
    while True:
        grown = None
        if right < hi:
            next_right = upper_bound(right + 1)
            if next_right > right:
                grown = _fit(raw, cache, left, next_right, max_raw=max_raw, max_cleaned=max_cleaned)
                if grown is not None:
                    right = next_right
        if grown is None and left > lo:
            prev_left = lower_bound(left - 1)
            if prev_left < left:
                grown = _fit(raw, cache, prev_left, right, max_raw=max_raw, max_cleaned=max_cleaned)
                if grown is not None:
                    left = prev_left
        if grown is None:
            break
        piece = grown
    return piece


# --------------------------------------------------------------------- 组装

def _assemble(
    *,
    catalog: TextbookCatalog,
    texts: ImmutableTextSource,
    scope_entry: RevisionScope,
    revision: RevisionRecord,
    char_start: int,
    char_end: int,
    chapter_path: Sequence[str],
    require_derived_id: str | None = None,
    readable: TextProjection | None = None,
) -> TextbookEvidence:
    """核验散列、区间与正文区，然后按半开区间切片成证据（``text`` 逐字节来自封存原文）。"""
    text = texts.read_normalized_text(revision)
    if sha256_utf8(text) != revision.normalized_text_sha256:
        raise unavailable("规范化原文指纹与修订登记不符，已停止使用该教材原句。")
    if char_start < 0 or char_end <= char_start or char_end > len(text):
        raise unavailable(
            f"原文区间 [{char_start}, {char_end}) 超出规范化文本长度 {len(text)}，已停止使用该引用。"
        )
    if texts.region_of(revision, char_start, char_end) != BODY_REGION:
        raise unavailable("引用区间落在习题区，不作为知识点依据返回。")
    identifier = evidence_id(revision.revision_id, char_start, char_end)
    if require_derived_id is not None and identifier != require_derived_id:
        raise unavailable("引用标识与教材原文区间不一致，请重新定位后再试。")
    document = catalog.get_document(scope_entry.document_id)
    if document is None or document.deleted_at is not None:
        raise unavailable("引用教材已删除或不存在，请重新定位。")
    if revision.document_id != scope_entry.document_id:
        raise unavailable("引用修订与教材归属不符，已停止使用该引用。")
    slice_text = text[char_start:char_end]
    projection = (
        readable
        if readable is not None
        else project_readable(slice_text, absolute_start=char_start)
    )
    return TextbookEvidence(
        evidenceId=identifier,
        documentRevisionId=revision.revision_id,
        normalizedTextSha256=revision.normalized_text_sha256,
        charStart=char_start,
        charEnd=char_end,
        documentId=scope_entry.document_id,
        title=scope_entry.title,
        editionLabel=scope_entry.edition_label,
        subjectLabel=scope_entry.subject_label,
        chapterPath=[str(part) for part in chapter_path],
        text=slice_text,
        readable=EvidenceReadable(
            version=TEXT_PROJECTION_VERSION,
            text=projection.text,
            removedImageCount=projection.removed_image_count,
        ),
        originalFileSha256=revision.original_file_sha256,
        locator=texts.locate(revision, char_start, char_end),
        isSuperseded=document.current_revision_id != revision.revision_id,
    )


@dataclass(frozen=True)
class _MergeOutcome:
    """合并结果：``appended`` 追加、``merged`` 并入既有条目、``covered`` 重复、``no_fit`` 预算不足。"""

    action: str
    delta: int = 0


def _merge_selected(
    selected: list[TextbookEvidence],
    *,
    catalog: TextbookCatalog,
    source: ImmutableTextSource,
    entry: RevisionScope,
    revision: RevisionRecord,
    chapter_path: tuple[str, ...],
    piece: _Piece,
    raw: str,
    max_single_raw_chars: int,
    max_single_cleaned_chars: int,
    max_total_raw_chars: int,
    current_raw: int,
) -> _MergeOutcome:
    """把新窗口并入已选条目，或作为新条目追加；预算不足时整条不采用。

    合并条件：同修订、同章节、重叠或相邻，且**合并后仍满足单条预算**；
    合并会超过单条预算时保持独立条目（"不得合并成超过预算的大段"）。
    """
    chapter = tuple(str(part) for part in chapter_path)
    for index, existing in enumerate(selected):
        if existing.documentRevisionId != revision.revision_id:
            continue
        if tuple(existing.chapterPath) != chapter:
            continue
        if (
            existing.charEnd + MAX_SPAN_GAP < piece.char_start
            or existing.charStart > piece.char_end + MAX_SPAN_GAP
        ):
            continue
        union = (min(existing.charStart, piece.char_start), max(existing.charEnd, piece.char_end))
        if union == (existing.charStart, existing.charEnd):
            return _MergeOutcome("covered")
        projection = project_readable(raw[union[0] : union[1]], absolute_start=union[0])
        fits_union = (
            union[1] - union[0] <= max_single_raw_chars
            and len(projection.text) <= max_single_cleaned_chars
        )
        overlaps = existing.charStart < piece.char_end and existing.charEnd > piece.char_start
        if not fits_union:
            if overlaps:
                # 与既有条目重叠且合并后超单条预算：整条跳过，绝不重复追加同一段内容。
                return _MergeOutcome("covered")
            continue
        delta = (union[1] - union[0]) - (existing.charEnd - existing.charStart)
        if current_raw + delta > max_total_raw_chars:
            return _MergeOutcome("no_fit")
        selected[index] = _assemble(
            catalog=catalog,
            texts=source,
            scope_entry=entry,
            revision=revision,
            char_start=union[0],
            char_end=union[1],
            chapter_path=chapter_path,
            readable=projection,
        )
        return _MergeOutcome("merged", delta)
    if current_raw + piece.raw_chars > max_total_raw_chars:
        return _MergeOutcome("no_fit")
    selected.append(
        _assemble(
            catalog=catalog,
            texts=source,
            scope_entry=entry,
            revision=revision,
            char_start=piece.char_start,
            char_end=piece.char_end,
            chapter_path=chapter_path,
            readable=piece.projection,
        )
    )
    return _MergeOutcome("appended", piece.raw_chars)


# --------------------------------------------------------------------- 选择

def select_evidence(
    *,
    catalog: TextbookCatalog,
    scope: Sequence[RevisionScope],
    candidates: Sequence[Candidate],
    texts: ImmutableTextSource | None = None,
    question: str | None = None,
    max_items: int = FIRST_ANSWER_EVIDENCE_MAX_ITEMS,
    max_total_raw_chars: int = EVIDENCE_TOTAL_RAW_MAX_CHARS,
    max_single_raw_chars: int = EVIDENCE_SINGLE_RAW_MAX_CHARS,
    max_single_cleaned_chars: int = EVIDENCE_SINGLE_CLEANED_MAX_CHARS,
    neighbours_each_side: int = EVIDENCE_NEIGHBOURS_EACH_SIDE,
) -> EvidenceSelection:
    """从融合候选里有界地选出最多 ``max_items`` 条证据，并给出可解释状态。

    实施顺序严格对应 PLAN §3.3：靠前命中 → 裁到正文区 → 左右各补至多一个可并入邻块 →
    按预算取舍（不截断单条）→ 命中块自身超长时在命中附近按完整段落/句子取窗口 →
    受保护单元自身超长则记 locator 并继续 → 清洗后为空则跳过 → 最多 6 条 / 总量 16000。
    """
    source = texts if texts is not None else ImmutableSource(catalog=catalog)
    env = _Environment(catalog=catalog, source=source)
    scope_chunk_sets = scope_by_chunk_set(scope)
    selected: list[TextbookEvidence] = []
    selected_raw = 0
    oversized: list[object] = []
    saw_text_hit = False
    skipped_empty = 0
    truncated_by_budget = 0

    for candidate in candidates:
        if len(selected) >= max_items:
            break
        entry = scope_chunk_sets.get(candidate.chunk_set_id)
        if entry is None:
            raise unavailable("检索候选超出当前教材范围，已停止重建原文。")
        revision_id = entry.document_revision_id
        revision = catalog.get_revision(revision_id)
        if revision is None:
            raise unavailable("检索候选的修订不存在，已停止重建原文。")
        chunks = env.chunks_for(candidate.chunk_set_id)
        position = env.positions[candidate.chunk_set_id].get(candidate.ordinal)
        if position is None:
            continue
        chunk = chunks[position]
        if chunk.region != BODY_REGION:
            continue
        seed = env.bounds_of(candidate.chunk_set_id, revision_id, chunk)
        if seed is None:
            continue
        # 到这里才算"文本命中"：候选属于范围内、位于正文区且能定位。
        saw_text_hit = True
        chapter_path = tuple(chunk.chapter_path)
        raw = env.text_for(revision)
        protected = env.protected_for(revision_id, raw)
        window = _bounded_window(
            chunks=chunks,
            position=position,
            seed=seed,
            chapter_path=chapter_path,
            bounds_of=lambda neighbour: env.bounds_of(
                candidate.chunk_set_id, revision_id, neighbour
            ),
            neighbours_each_side=neighbours_each_side,
        )
        cache: dict[tuple[int, int], _Piece | None] = {}
        piece = _fit(
            raw,
            cache,
            window[0],
            window[1],
            max_raw=max_single_raw_chars,
            max_cleaned=max_single_cleaned_chars,
        )
        if piece is None and window != seed:
            # 合并窗口超预算：先退回命中块本身，保住整块内容。
            piece = _fit(
                raw,
                cache,
                seed[0],
                seed[1],
                max_raw=max_single_raw_chars,
                max_cleaned=max_single_cleaned_chars,
            )
        if piece is None or piece.raw_chars < seed[1] - seed[0]:
            # 命中块自身超预算：在命中附近按完整段落/句子取窗口（绝不切开受保护单元）。
            shrunk = _near_hit_window(
                raw,
                lo=seed[0],
                hi=seed[1],
                anchor=_anchor(raw, seed[0], seed[1], question),
                protected=protected,
                max_raw=max_single_raw_chars,
                max_cleaned=max_single_cleaned_chars,
            )
            if shrunk is None:
                oversized.append(source.locate(revision, seed[0], seed[1]))
                continue
            piece = shrunk
        if not piece.projection.text.strip():
            # 清洗后为空：跳过该候选，继续考察后续候选（有命中就不再报"没有依据"）。
            skipped_empty += 1
            continue
        outcome = _merge_selected(
            selected,
            catalog=catalog,
            source=source,
            entry=entry,
            revision=revision,
            chapter_path=chapter_path,
            piece=piece,
            raw=raw,
            max_single_raw_chars=max_single_raw_chars,
            max_single_cleaned_chars=max_single_cleaned_chars,
            max_total_raw_chars=max_total_raw_chars,
            current_raw=selected_raw,
        )
        if outcome.action == "no_fit":
            truncated_by_budget += 1
            continue
        selected_raw += outcome.delta

    if selected:
        return EvidenceSelection(
            status="ok",
            reason_code=None,
            reason=None,
            evidence=tuple(selected),
            oversized_locators=tuple(oversized),
            skipped_empty_candidates=skipped_empty,
            saw_text_hit=saw_text_hit,
            truncated_by_budget=truncated_by_budget,
        )
    if oversized:
        return EvidenceSelection(
            status="partial",
            reason_code="EVIDENCE_UNIT_TOO_LARGE",
            reason=_oversized_reason(oversized, truncated=bool(truncated_by_budget)),
            evidence=(),
            oversized_locators=tuple(oversized),
            skipped_empty_candidates=skipped_empty,
            saw_text_hit=saw_text_hit,
            truncated_by_budget=truncated_by_budget,
        )
    if saw_text_hit:
        return EvidenceSelection(
            status="uncertain",
            reason_code="EVIDENCE_TEXT_EMPTY",
            reason=(
                "检索命中只包含图片等非文本内容（清洗后没有可读文本），"
                "请补充题干、章节或确认该教材是否含正文文字。"
            ),
            evidence=(),
            skipped_empty_candidates=skipped_empty,
            saw_text_hit=True,
            truncated_by_budget=truncated_by_budget,
        )
    return EvidenceSelection(
        status="no_evidence",
        reason_code="NO_MATCH",
        reason="当前教材范围没有找到足够依据，请补充题干、章节或确认任教范围。",
        evidence=(),
        skipped_empty_candidates=skipped_empty,
        saw_text_hit=False,
        truncated_by_budget=truncated_by_budget,
    )


def _oversized_reason(locators: Sequence[object], *, truncated: bool) -> str:
    """受保护单元超预算的可读说明：附**可展示**定位，不回显原文内容。"""
    labels: list[str] = []
    for locator in locators:
        label = _locator_text(locator)
        if label and label not in labels:
            labels.append(label)
        if len(labels) >= 3:
            break
    detail = f"（定位：{'、'.join(labels)}）" if labels else ""
    tail = "，其余可用证据未超过预算。" if truncated else ""
    return (
        "检索命中包含超长公式或代码等不可拆分单元，单条证据无法完整装入预算"
        f"，未返回原文摘录{tail}{detail}"
    )


def _locator_text(locator) -> str:
    kind = getattr(locator, "kind", None)
    line_start = getattr(locator, "lineStart", None)
    line_end = getattr(locator, "lineEnd", None)
    if kind == "markdown" and line_start is not None and line_end is not None:
        return f"第 {line_start}–{line_end} 行"
    page_start = getattr(locator, "pageStart", None)
    page_end = getattr(locator, "pageEnd", None)
    if kind == "pdf" and page_start is not None and page_end is not None:
        return f"第 {page_start}–{page_end} 页"
    block_start = getattr(locator, "blockStart", None)
    block_end = getattr(locator, "blockEnd", None)
    if kind == "docx" and block_start is not None and block_end is not None:
        return f"第 {block_start}–{block_end} 段"
    return ""


def build_evidence(
    *,
    catalog: TextbookCatalog,
    scope: Sequence[RevisionScope],
    candidates: Sequence[Candidate],
    texts: ImmutableTextSource | None = None,
    max_items: int = MAX_EVIDENCE_ITEMS,
    max_chars: int = MAX_EVIDENCE_CHARS,
    question: str | None = None,
) -> list[TextbookEvidence]:
    """兼容入口：返回选中的证据列表（状态语义见 :func:`select_evidence`）。

    调用方需要区分 partial / uncertain / no_evidence 时必须直接用 ``select_evidence``。
    """
    selection = select_evidence(
        catalog=catalog,
        scope=scope,
        candidates=candidates,
        texts=texts,
        question=question,
        max_items=max_items,
        max_total_raw_chars=max_chars,
    )
    return list(selection.evidence)


def _chapter_path_for(
    catalog: TextbookCatalog, scope_entry: RevisionScope, char_start: int, char_end: int
) -> list[str]:
    """取与该区间有交叠的首个块的章节路径（块按 ordinal 升序）。"""
    for chunk in catalog.list_chunks(scope_entry.chunk_set_id):
        if chunk.char_start < char_end and chunk.char_end > char_start:
            return [str(part) for part in chunk.chapter_path]
    return []


def rebuild_evidence_refs(
    *,
    catalog: TextbookCatalog,
    scope: Sequence[RevisionScope],
    refs: Sequence[EvidenceRef],
    texts: ImmutableTextSource | None = None,
) -> list[TextbookEvidence]:
    """详解前逐条重建引用：范围成员 → 修订 → 存活 → 散列 → 区间 → 正文区。

    任何一条不满足都抛 409 ``RAG_EVIDENCE_UNAVAILABLE``；不自动替换引用、不静默跳过。
    历史详解的 20 条引用与既有 40,000 字符上限不变（见 ``app.core.rag_budget``），
    因此这里**不套用首答的 6 条 / 6,000 码点窗口**；但每条都补上 ``readable`` 清洗文本，
    详解送模型时用清洗文本（不把图片地址送进模型）。
    """
    source = texts if texts is not None else ImmutableSource(catalog=catalog)
    scope_revisions = scope_by_revision(scope)
    items: list[TextbookEvidence] = []
    for ref in refs:
        entry = scope_revisions.get(ref.documentRevisionId)
        if entry is None:
            raise unavailable("引用不属于当前教材范围，请重新定位后再试。")
        revision = catalog.get_revision(ref.documentRevisionId)
        if revision is None:
            raise unavailable("引用修订不存在，请重新定位后再试。")
        try:
            catalog.require_live_document(revision.document_id)
        except AppError as exc:
            raise unavailable(f"引用教材已失效：{exc}") from exc
        text = source.read_normalized_text(revision)
        if sha256_utf8(text) != ref.normalizedTextSha256:
            raise unavailable("引用指纹与教材原文不符，请重新定位后再试。")
        if ref.charStart < 0 or ref.charEnd > len(text) or ref.charStart >= ref.charEnd:
            raise unavailable("引用区间超出教材原文范围，请重新定位后再试。")
        items.append(
            _assemble(
                catalog=catalog,
                texts=source,
                scope_entry=entry,
                revision=revision,
                char_start=ref.charStart,
                char_end=ref.charEnd,
                chapter_path=_chapter_path_for(catalog, entry, ref.charStart, ref.charEnd),
                require_derived_id=ref.evidenceId,
            )
        )
    return items


__all__ = [
    "EVIDENCE_SINGLE_CLEANED_MAX_CHARS",
    "EVIDENCE_SINGLE_RAW_MAX_CHARS",
    "EvidenceSelection",
    "EvidenceSpan",
    "MAX_EVIDENCE_CHARS",
    "MAX_EVIDENCE_ITEMS",
    "MAX_SPAN_GAP",
    "build_evidence",
    "evidence_id",
    "rebuild_evidence_refs",
    "select_evidence",
    "sha256_utf8",
]
