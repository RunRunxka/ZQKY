"""从教材提取知识点（任务③）：预览清单、任务受理与确认后自动建教材依据。

流程边界（教学闭环设计）：

- **预览**（``build_preview``）：某学科全部已入库教材清单，含当前修订、分块数、
  字符数与"是否在当前索引代就绪"（``catalog.allowed_chunks`` 白名单核对）；未就绪
  书册标 ``reason``，不伪造就绪状态。只读，不建任务。
- **受理**（``plan_extraction``）：每个书册一个 AI 候选任务；指定 ``documentIds``
  时只受理这些；**任何**未就绪书册 → 409 逐册列出（不静默跳过、不部分受理）。
- **取材**（``collect_document_evidence``）：该书册正文 chunk（``region="body"``）
  的 ``(documentRevisionId, charStart, charEnd)`` 区间，经 ``TextbookEvidenceReader``
  读取（沿用既有预算：≤20 区间 / ≤6 万字，服务层复用
  ``suggestions.MAX_EVIDENCE_CHARS`` 与每次上限）。
- **年级归类**：不新增迁移——候选行的 ``textbookEvidence`` 保留
  ``documentRevisionId``，前端用预览接口把修订映射到年级。
- **确认后自动建教材依据**（``confirm_textbook_links``）：在确认事务内，对由本批
  AI 候选带入证据的**新建**知识点写 ``textbook_knowledge_links``（source 用既有
  枚举 ``ai_confirmed``，不改迁移）。

本模块只做只读 SQL 与纯计算；跨库读取经注入的教材目录，写库由服务层在事务内做。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.contracts.knowledge import (
    KNOWLEDGE_EXTRACTION_NOT_READY,
    KnowledgeExtractionDocument,
    KnowledgeExtractionPreview,
)
from app.core.exceptions import AppError

#: 正文区（AI 取材只取正文 chunk，练习区/其他区不作为提取证据）
BODY_REGION = "body"
#: 单次候选任务的证据区间上限（与既有 ``KnowledgeSuggestionRequest.textbookEvidence``
#: max_length=20 同一口径）
MAX_EVIDENCE_RANGES = 20


@dataclass(frozen=True)
class EvidenceRange:
    """一个待读取的证据区间（正文 chunk 的冻结坐标）。"""

    document_revision_id: str
    char_start: int
    char_end: int


# --------------------------------------------------------------------------- 预览


def build_preview(catalog: Any, *, subject_id: str) -> KnowledgeExtractionPreview:
    """某学科全部已入库教材的提取预览（只读；未就绪书册带 reason）。

    - 书册来源：``catalog.list_documents(subject_id=...)``（未删除书册）；
    - 就绪判定：书册当前修订是否在**当前索引代**的 ``allowed_chunks`` 白名单里；
    - chunkCount/approxChars 来自当前修订的分块集与 ``char_count``；没有修订的书册
      以 ``reason`` 标注"尚未发布有效修订"。
    """
    subject_id = _text(subject_id, field="subjectId")
    documents = catalog.list_documents(subject_id=subject_id)
    state = catalog.catalog_state()
    generation_id = state.active_generation_id
    entries: list[KnowledgeExtractionDocument] = []
    total_chunks = 0
    approx_chars = 0
    for document in documents:
        entry = _document_entry(catalog, document=document, generation_id=generation_id)
        if entry.index_ready:
            total_chunks += entry.chunk_count
            approx_chars += entry.approx_chars
        entries.append(entry)
    ready = [entry for entry in entries if entry.index_ready]
    return KnowledgeExtractionPreview.model_validate(
        {
            "subjectId": subject_id,
            "documents": [entry.model_dump(by_alias=True) for entry in entries],
            "totalDocuments": len(entries),
            "readyDocuments": len(ready),
            "totalChunks": total_chunks,
            "approxChars": approx_chars,
        }
    )


def _document_entry(
    catalog: Any, *, document: Any, generation_id: str | None
) -> KnowledgeExtractionDocument:
    """一个书册的预览条目（就绪判定 + 原因，不伪造）。"""
    revision_id = document.current_revision_id
    grade_ids = [str(grade) for grade in document.grade_ids]
    base: dict[str, Any] = {
        "documentId": document.document_id,
        "title": str(document.title),
        "gradeIds": grade_ids,
        "revisionId": revision_id,
        "chunkCount": 0,
        "approxChars": 0,
        "indexReady": False,
        "reason": None,
    }
    if not isinstance(revision_id, str) or not revision_id:
        base["reason"] = "该教材尚未发布有效修订。"
        return KnowledgeExtractionDocument.model_validate(base)
    revision = catalog.get_revision(revision_id)
    if revision is None:
        base["reason"] = "当前修订在教材目录中不可读。"
        return KnowledgeExtractionDocument.model_validate(base)
    base["approxChars"] = int(getattr(revision, "char_count", 0) or 0)
    if not generation_id:
        base["reason"] = "当前没有已发布的教材索引代。"
        return KnowledgeExtractionDocument.model_validate(base)
    try:
        allowed = catalog.allowed_chunks(generation_id, [revision_id])
    except AppError as exc:
        base["reason"] = f"教材索引代尚未包含该修订：{exc}"
        return KnowledgeExtractionDocument.model_validate(base)
    chunk_set_ids = list(allowed.chunk_set_ids)
    if not chunk_set_ids:
        base["reason"] = "教材索引代尚未包含该修订。"
        return KnowledgeExtractionDocument.model_validate(base)
    chunk_set = catalog.get_chunk_set(chunk_set_ids[0])
    chunk_count = int(chunk_set.chunk_count) if chunk_set is not None else 0
    base["chunkCount"] = chunk_count
    base["indexReady"] = True
    return KnowledgeExtractionDocument.model_validate(base)


# --------------------------------------------------------------------------- 受理


def not_ready_error(entries: Sequence[KnowledgeExtractionDocument]) -> AppError:
    """构造 409 ``KNOWLEDGE_EXTRACTION_NOT_READY``：逐册列出未就绪原因。"""
    reasons = [
        {
            "documentId": entry.document_id,
            "title": entry.title,
            "reason": entry.reason or "该教材未就绪。",
        }
        for entry in entries
    ]
    names = "、".join(entry.title for entry in entries)
    return AppError(
        f"以下教材尚未就绪，无法发起提取：{names}。",
        code=KNOWLEDGE_EXTRACTION_NOT_READY,
        status_code=409,
        details={"documents": reasons},
    )


def resolve_target_documents(
    catalog: Any, *, subject_id: str, document_ids: Sequence[str] | None
) -> list[KnowledgeExtractionDocument]:
    """确定本次提取的目标书册：缺省 = 该学科全部就绪书册；指定时逐册核验。

    指定的 documentIds 里有任何未就绪书册（不存在 / 已删除 / 非本学科 / 无修订 /
    不在当前索引代）→ 409 ``KNOWLEDGE_EXTRACTION_NOT_READY``，不部分受理。
    """
    preview = build_preview(catalog, subject_id=subject_id)
    by_id = {entry.document_id: entry for entry in preview.documents}
    if document_ids is None:
        return [entry for entry in preview.documents if entry.index_ready]
    targets: list[KnowledgeExtractionDocument] = []
    missing: list[KnowledgeExtractionDocument] = []
    for document_id in document_ids:
        text = _text(document_id, field="documentIds")
        entry = by_id.get(text)
        if entry is None:
            missing.append(
                KnowledgeExtractionDocument.model_validate(
                    {
                        "documentId": text,
                        "title": text,
                        "gradeIds": [],
                        "revisionId": None,
                        "chunkCount": 0,
                        "approxChars": 0,
                        "indexReady": False,
                        "reason": "该教材不存在、已删除或不属于该学科。",
                    }
                )
            )
            continue
        targets.append(entry)
    not_ready = [entry for entry in targets if not entry.index_ready] + missing
    if not_ready:
        raise not_ready_error(not_ready)
    return targets


def collect_document_evidence(
    catalog: Any, *, entry: KnowledgeExtractionDocument, revision: Any
) -> tuple[EvidenceRange, ...]:
    """一个书册的正文证据区间：region="body" 的 chunk 坐标（≤20 区间）。

    区间数超过上限时**均匀保留前部 chunk**（按顺序取前 20 个）：预算与既有 AI 候选
    输入契约一致（``textbookEvidence`` ≤20 条），由调用方把超预算提示冻结进任务。
    """
    revision_id = entry.revision_id
    if not isinstance(revision_id, str) or not revision_id:
        return ()
    state = catalog.catalog_state()
    if not state.active_generation_id:
        return ()
    try:
        allowed = catalog.allowed_chunks(state.active_generation_id, [revision_id])
    except AppError:
        return ()
    chunk_set_ids = list(allowed.chunk_set_ids)
    if not chunk_set_ids:
        return ()
    ranges: list[EvidenceRange] = []
    for chunk in catalog.list_chunks(chunk_set_ids[0]):
        if chunk.region != BODY_REGION:
            continue
        if len(ranges) >= MAX_EVIDENCE_RANGES:
            break
        ranges.append(
            EvidenceRange(
                document_revision_id=revision_id,
                char_start=int(chunk.char_start),
                char_end=int(chunk.char_end),
            )
        )
    return tuple(ranges)


# --------------------------------------------------------------------------- 确认后自动建依据


def extract_evidence_from_raw_cells(raw_cells: Mapping[str, Any]) -> list[dict[str, Any]]:
    """从候选行 ``raw_cells`` 里读回 AI 任务的教材证据（冻结输入的证据条目）。

    AI 候选批次把每行证据提示（含 ``textbook:…`` 证据 id 与冻结的
    ``documentRevisionId/charStart/charEnd``）写进行级 ``raw_cells_json`` 的保留键
    ``knowledgeExtractionEvidence``；确认时从这里恢复证据坐标，为**新建**知识点自动
    建教材依据。形状不符 / 非对象条目一律跳过（确认不被证据恢复失败阻断）。
    """
    payload = raw_cells.get(EXTRACTION_EVIDENCE_KEY)
    if not isinstance(payload, list):
        return []
    result: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        revision_id = item.get("documentRevisionId")
        char_start = item.get("charStart")
        char_end = item.get("charEnd")
        if not isinstance(revision_id, str) or not revision_id.strip():
            continue
        if (
            not isinstance(char_start, int)
            or isinstance(char_start, bool)
            or not isinstance(char_end, int)
            or isinstance(char_end, bool)
            or char_end <= char_start
        ):
            continue
        result.append(
            {
                "documentRevisionId": revision_id.strip(),
                "charStart": char_start,
                "charEnd": char_end,
                "title": str(item.get("title") or "") or None,
            }
        )
    return result


#: AI 候选行 raw_cells 里冻结提取证据的保留键（形状见 extract_evidence_from_raw_cells）
EXTRACTION_EVIDENCE_KEY = "knowledgeExtractionEvidence"


def build_extraction_evidence(
    evidence_entries: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    """把 AI 任务的教材证据条目冻结进候选行 ``raw_cells``（与确认恢复同一形状）。

    返回 ``(证据条目, 提示文本)``：条目进入行的 ``raw_cells``；提示文本并入
    ``hint_issues`` 的说明（教师可见证据区间）。
    """
    entries: list[dict[str, Any]] = []
    labels: list[str] = []
    for item in evidence_entries:
        revision_id = str(item.get("documentRevisionId") or "").strip()
        char_start = item.get("charStart")
        char_end = item.get("charEnd")
        if not revision_id or not isinstance(char_start, int) or not isinstance(char_end, int):
            continue
        entries.append(
            {
                "documentRevisionId": revision_id,
                "charStart": char_start,
                "charEnd": char_end,
                "title": str(item.get("title") or "") or None,
            }
        )
        labels.append(f"{revision_id}:{char_start}-{char_end}")
    hint = ""
    if labels:
        hint = "提取证据区间：" + "、".join(labels) + "。"
    return entries, hint


def freeze_evidence_into_raw_cells(
    raw_cells: Mapping[str, Any], evidence_entries: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """把提取证据并入候选行 ``raw_cells``（保留键；不覆盖其他原始单元格）。"""
    payload = dict(raw_cells)
    payload[EXTRACTION_EVIDENCE_KEY] = list(evidence_entries)
    return payload


def confirm_textbook_links(
    conn: sqlite3.Connection,
    *,
    created_by_code: Mapping[str, str],
    row_evidence: Mapping[int, Sequence[Mapping[str, Any]]],
    row_codes: Mapping[int, str],
    links: Any,
    points: Any,
) -> int:
    """确认事务内为新建知识点写教材依据（source="ai_confirmed"，既有枚举值）。

    - 只对 ``created_by_code`` 里**新建**的知识点写（update 行的历史不动）；
    - 证据坐标已在候选受理时经 ``TextbookEvidenceReader`` 核验；这里直接冻结登记
      （``locator_json`` 区间权威 + title 快照）；
    - 同一知识点多行 / 同一修订同区间重复登记由 ``UNIQUE`` 兜底，重复行跳过；
    - 返回写入的依据行数。
    """
    written = 0
    seen: set[tuple[str, str, str, int, int]] = set()
    for row_no, entries in row_evidence.items():
        code = row_codes.get(row_no, "")
        point_id = created_by_code.get(code)
        if point_id is None:
            continue
        point = points.get_point(conn, point_id)
        if point is None:
            continue
        for entry in entries:
            revision_id = str(entry.get("documentRevisionId") or "")
            char_start = int(entry.get("charStart") or 0)
            char_end = int(entry.get("charEnd") or 0)
            title = str(entry.get("title") or "") or "教材依据"
            key = (point_id, point.revision_id, revision_id, char_start, char_end)
            if key in seen:
                continue
            seen.add(key)
            try:
                links.create_link(
                    conn,
                    point_id=point_id,
                    knowledge_revision_id=point.revision_id,
                    document_revision_id=revision_id,
                    char_start=char_start,
                    char_end=char_end,
                    title_snapshot=title,
                    source="ai_confirmed",
                    locator=None,
                )
                written += 1
            except AppError as exc:
                # 重复区间（UNIQUE）与已损坏坐标跳过；其他约束错误继续抛出
                if getattr(exc, "code", "") == "KNOWLEDGE_LINK_DUPLICATE":
                    continue
                raise
    return written


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError(
            f"{field} 必须是非空字符串。", code="INVALID_REQUEST", status_code=422
        )
    return value.strip()


__all__ = [
    "BODY_REGION",
    "EvidenceRange",
    "EXTRACTION_EVIDENCE_KEY",
    "MAX_EVIDENCE_RANGES",
    "build_extraction_evidence",
    "build_preview",
    "collect_document_evidence",
    "confirm_textbook_links",
    "extract_evidence_from_raw_cells",
    "freeze_evidence_into_raw_cells",
    "not_ready_error",
    "resolve_target_documents",
]
