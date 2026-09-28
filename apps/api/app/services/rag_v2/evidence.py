"""原文证据重建：邻块扩展 + 不可变规范化文本切片 + 预算取舍。

规则（对应 docs/PLAN.md §6.4 与任务卡）：

- 邻块扩展只在**同一文档修订（同一分块集）、同一章节路径、同一区（正文）**内进行，
  不跨文档、不跨章节、不跨习题间隙；扩展后按完整区间合并（重叠/相邻并成一个 span）。
- 每个 span 从不可变规范化文本按 ``[char_start, char_end)``（半开区间、Unicode 码点）
  切片，切片前后核验全文散列；不符抛 409 ``RAG_EVIDENCE_UNAVAILABLE``。
- ``evidenceId`` 是稳定派生值（修订 + 区间），同区间同 id，便于前端回传做详解引用。
- 预算：最多 20 条、总字符 ≤40,000，按**完整 span**取舍；放不下就整条不取，不截断。
- ``isSuperseded``：该修订不是文档当前修订时为 True（历史消息仍可读，新检索不用）。
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.exceptions import AppError
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.textbook_catalog.records import RevisionRecord
from app.schemas.rag_v2 import EvidenceRef, TextbookEvidence
from app.services.rag_v2.retrieval import Candidate
from app.services.rag_v2.scope import (
    BODY_REGION,
    RevisionScope,
    scope_by_chunk_set,
    scope_by_revision,
)
from app.services.rag_v2.source_text import ImmutableSource, ImmutableTextSource, unavailable
from app.services.textbook_ingest.blobs import sha256_text

MAX_EVIDENCE_ITEMS = 20
MAX_EVIDENCE_CHARS = 40_000
#: 相邻判定允许的字符缝：分块在行边界切开时，分隔换行可能落在两块之外，
#: 因此"相邻"包含 ≤2 码点的缝。跨章节由章节路径拦住，跨习题区由块区与区间区核验拦住。
MAX_SPAN_GAP = 2


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


def _mergeable(neighbour, *, chapter_path: tuple[str, ...], span_start: int, span_end: int) -> bool:
    """可以并入当前 span 的邻块：正文区、同章节、且在字符空间上相邻或重叠。"""
    if neighbour.region != BODY_REGION:
        return False
    if tuple(neighbour.chapter_path) != chapter_path:
        return False
    return (
        neighbour.char_end + MAX_SPAN_GAP >= span_start
        and neighbour.char_start <= span_end + MAX_SPAN_GAP
    )


def _mergeable_bounds(
    neighbour,
    *,
    chapter_path: tuple[str, ...],
    span_start: int,
    span_end: int,
    bounds: tuple[int, int],
) -> bool:
    """同上，但用**裁剪到正文区后**的区间判断相邻（块可能带跨界重叠尾巴）。"""
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


def expand_spans(
    *,
    catalog: TextbookCatalog,
    scope: Sequence[RevisionScope],
    candidates: Sequence[Candidate],
    texts: ImmutableTextSource | None = None,
) -> list[EvidenceSpan]:
    """按融合顺序把候选块扩展成完整 span，并合并重叠/相邻区间（裁剪到正文区）。"""
    scope_chunk_sets = scope_by_chunk_set(scope)
    source = texts
    chunks_cache: dict[str, list] = {}
    body_ranges_cache: dict[str, list[tuple[int, int]] | None] = {}
    clipped_cache: dict[tuple[str, int], tuple[int, int] | None] = {}
    positions: dict[str, dict[int, int]] = {}
    spans: list[EvidenceSpan] = []
    seen: set[tuple[str, int, int]] = set()

    for candidate in candidates:
        entry = scope_chunk_sets.get(candidate.chunk_set_id)
        if entry is None:
            raise unavailable("检索候选超出当前教材范围，已停止重建原文。")
        revision_id = entry.document_revision_id
        if revision_id not in body_ranges_cache:
            body_ranges_cache[revision_id] = (
                _body_ranges(source, catalog, revision_id) if source is not None else None
            )
        body_ranges = body_ranges_cache[revision_id]
        chunks = chunks_cache.get(candidate.chunk_set_id)
        if chunks is None:
            chunks = catalog.list_chunks(candidate.chunk_set_id)
            chunks_cache[candidate.chunk_set_id] = chunks
            positions[candidate.chunk_set_id] = {chunk.ordinal: index for index, chunk in enumerate(chunks)}
        position = positions[candidate.chunk_set_id].get(candidate.ordinal)
        if position is None:
            continue
        chunk = chunks[position]
        if chunk.region != BODY_REGION:
            continue
        chapter_path = tuple(chunk.chapter_path)
        bounds = _clip_to_body(chunk.char_start, chunk.char_end, body_ranges)
        if bounds is None:
            continue
        start, end = bounds
        left = position - 1
        while left >= 0:
            neighbour = chunks[left]
            if neighbour.region != BODY_REGION:
                break
            neighbour_bounds = clipped_cache.get((candidate.chunk_set_id, neighbour.ordinal))
            if (candidate.chunk_set_id, neighbour.ordinal) not in clipped_cache:
                neighbour_bounds = _clip_to_body(neighbour.char_start, neighbour.char_end, body_ranges)
                clipped_cache[(candidate.chunk_set_id, neighbour.ordinal)] = neighbour_bounds
            if neighbour_bounds is None or not _mergeable_bounds(
                neighbour, chapter_path=chapter_path, span_start=start, span_end=end,
                bounds=neighbour_bounds,
            ):
                break
            start = min(start, neighbour_bounds[0])
            left -= 1
        right = position + 1
        while right < len(chunks):
            neighbour = chunks[right]
            if neighbour.region != BODY_REGION:
                break
            if (candidate.chunk_set_id, neighbour.ordinal) not in clipped_cache:
                clipped_cache[(candidate.chunk_set_id, neighbour.ordinal)] = _clip_to_body(
                    neighbour.char_start, neighbour.char_end, body_ranges
                )
            neighbour_bounds = clipped_cache[(candidate.chunk_set_id, neighbour.ordinal)]
            if neighbour_bounds is None or not _mergeable_bounds(
                neighbour, chapter_path=chapter_path, span_start=start, span_end=end,
                bounds=neighbour_bounds,
            ):
                break
            end = max(end, neighbour_bounds[1])
            right += 1
        key = (candidate.chunk_set_id, start, end)
        if key in seen:
            continue
        seen.add(key)
        spans.append(
            EvidenceSpan(
                chunk_set_id=candidate.chunk_set_id,
                document_revision_id=revision_id,
                char_start=start,
                char_end=end,
                chapter_path=chapter_path,
                fused_score=candidate.fused_score,
            )
        )
    return spans


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
) -> TextbookEvidence:
    """核验散列、区间与正文区，然后按半开区间切片成证据。"""
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
        text=text[char_start:char_end],
        originalFileSha256=revision.original_file_sha256,
        locator=texts.locate(revision, char_start, char_end),
        isSuperseded=document.current_revision_id != revision.revision_id,
    )


def build_evidence(
    *,
    catalog: TextbookCatalog,
    scope: Sequence[RevisionScope],
    candidates: Sequence[Candidate],
    texts: ImmutableTextSource | None = None,
    max_items: int = MAX_EVIDENCE_ITEMS,
    max_chars: int = MAX_EVIDENCE_CHARS,
) -> list[TextbookEvidence]:
    """把融合候选还原为逐字节一致的教材原文证据（按 span 取舍，不截断）。"""
    source = texts if texts is not None else ImmutableSource(catalog=catalog)
    scope_revisions = scope_by_revision(scope)
    spans = expand_spans(catalog=catalog, scope=scope, candidates=candidates, texts=source)
    items: list[TextbookEvidence] = []
    total = 0
    for span in spans:
        if len(items) >= max_items:
            break
        if span.length > max_chars - total:
            continue
        entry = scope_revisions.get(span.document_revision_id)
        if entry is None:
            raise unavailable("检索候选超出当前教材范围，已停止重建原文。")
        revision = catalog.get_revision(span.document_revision_id)
        if revision is None:
            raise unavailable("引用修订不存在，已停止重建原文。")
        item = _assemble(
            catalog=catalog,
            texts=source,
            scope_entry=entry,
            revision=revision,
            char_start=span.char_start,
            char_end=span.char_end,
            chapter_path=span.chapter_path,
        )
        items.append(item)
        total += len(item.text)
    return items


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
    "EvidenceSpan",
    "MAX_EVIDENCE_CHARS",
    "MAX_EVIDENCE_ITEMS",
    "build_evidence",
    "evidence_id",
    "expand_spans",
    "rebuild_evidence_refs",
    "sha256_utf8",
]
