"""题库视图构造：把仓储记录映射为共享契约的响应模型。

视图只读记录，不做写入；存储内容不符合契约时抛 ``QUESTION_BANK_CORRUPT``（500），
不把损坏内容伪装成空草稿或空题目。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.core.exceptions import AppError
from app.repositories.question_bank.records import (
    DraftRecord,
    ImportRecord,
    JobRecord,
    QuestionRecord,
    SourceBlockRecord,
    SuggestionRecord,
)
from app.schemas.question_bank import (
    DraftView,
    OrganizeBatchFailure,
    OrganizeJobView,
    QuestionContent,
    QuestionDetail,
    QuestionImportDetail,
    QuestionImportSummary,
    QuestionLocatorView,
    QuestionMetadata,
    QuestionSummary,
    SourceBlockView,
    SourceSpan,
    SuggestionView,
)

_STEM_PREVIEW_CHARS = 60

#: 契约里的定位字段；locator_json 额外保存 charStart/charEnd 用于区间运算，这里不外发
_LOCATOR_KEYS = (
    "kind",
    "lineStart",
    "lineEnd",
    "pageStart",
    "pageEnd",
    "blockStart",
    "blockEnd",
)


def _corrupt(detail: str) -> AppError:
    return AppError(
        f"题库数据损坏：{detail}；读取已停止，不会自动覆盖。",
        code="QUESTION_BANK_CORRUPT",
        status_code=500,
    )


def _content(payload: dict[str, Any], *, where: str) -> QuestionContent:
    try:
        return QuestionContent.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        raise _corrupt(f"{where}的内容不符合题库契约") from exc


def _metadata(payload: dict[str, Any], *, where: str) -> QuestionMetadata:
    try:
        return QuestionMetadata.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        raise _corrupt(f"{where}的分类不符合题库契约") from exc


def _spans(record: DraftRecord) -> list[SourceSpan]:
    spans: list[SourceSpan] = []
    for item in record.source_spans:
        try:
            spans.append(SourceSpan.model_validate(item))
        except Exception as exc:  # noqa: BLE001
            raise _corrupt("草稿的 source_spans 结构不符") from exc
    return spans


def locator_view(locator: dict[str, Any]) -> QuestionLocatorView:
    payload = {key: locator[key] for key in _LOCATOR_KEYS if key in locator}
    try:
        return QuestionLocatorView.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        raise _corrupt("原文块 locator 结构不符") from exc


def source_block_view(record: SourceBlockRecord) -> SourceBlockView:
    return SourceBlockView(
        blockId=record.block_id,
        ordinal=record.ordinal,
        text=record.text,
        locator=locator_view(record.locator),
    )


def draft_view(record: DraftRecord) -> DraftView:
    return DraftView(
        draftId=record.draft_id,
        importId=record.import_id,
        revision=record.revision,
        content=_content(record.content, where="草稿"),
        metadata=_metadata(record.metadata, where="草稿"),
        sourceSpans=_spans(record),
        extractionMethod=record.extraction_method,  # type: ignore[arg-type]
        reviewState=record.review_state,  # type: ignore[arg-type]
        missingAnswerAcknowledged=record.missing_answer_acknowledged,
        warnings=list(record.warnings),
        duplicateOfQuestionId=record.duplicate_of_question_id,
    )


def suggestion_view(record: SuggestionRecord) -> SuggestionView:
    return SuggestionView(
        suggestionId=record.suggestion_id,
        organizationJobId=record.organization_job_id,
        targetDraftId=record.target_draft_id,
        baseDraftRevision=record.base_draft_revision,
        proposedContent=_content(record.proposed_content, where="AI 建议"),
        proposedMetadata=_metadata(record.proposed_metadata, where="AI 建议"),
        sourceBlockIds=list(record.source_block_ids),
        state=record.state,  # type: ignore[arg-type]
        note=record.note,
    )


def import_summary(
    record: ImportRecord,
    *,
    draft_count: int,
    reviewed_count: int,
    unassigned_count: int,
) -> QuestionImportSummary:
    return QuestionImportSummary(
        importId=record.import_id,
        ownerId=record.owner_id,
        state=record.state,  # type: ignore[arg-type]
        revision=record.revision,
        uploadedFileName=record.uploaded_file_name,
        uploadedBytes=record.uploaded_bytes,
        draftCount=draft_count,
        reviewedCount=reviewed_count,
        unassignedCount=unassigned_count,
        warnings=list(record.warnings),
        createdAt=record.created_at,
    )


def import_detail(
    record: ImportRecord,
    *,
    drafts: list[DraftRecord],
    unassigned: list[SourceBlockRecord],
) -> QuestionImportDetail:
    summary = import_summary(
        record,
        draft_count=len(drafts),
        reviewed_count=sum(1 for draft in drafts if draft.review_state == "reviewed"),
        unassigned_count=len(unassigned),
    )
    return QuestionImportDetail(
        **summary.model_dump(),
        drafts=[draft_view(draft) for draft in drafts],
        unassignedBlocks=[source_block_view(block) for block in unassigned],
    )


def _stem_preview(stem: str) -> str:
    flattened = " ".join(stem.split())
    if len(flattened) <= _STEM_PREVIEW_CHARS:
        return flattened
    return f"{flattened[:_STEM_PREVIEW_CHARS]}…"


def question_summary(record: QuestionRecord) -> QuestionSummary:
    content = _content(record.content, where="题目")
    metadata = _metadata(record.metadata, where="题目")
    return QuestionSummary(
        questionId=record.question_id,
        ownerId=record.owner_id,
        status=record.status,  # type: ignore[arg-type]
        revision=record.revision,
        type=content.type,
        stemPreview=_stem_preview(content.stemMarkdown),
        subjectId=metadata.subjectId,
        gradeId=metadata.gradeId,
        editionId=metadata.editionId,
        knowledgeTags=list(metadata.knowledgeTags),
        difficulty=metadata.difficulty,
        answerState=record.answer_state,  # type: ignore[arg-type]
        confirmedAt=record.confirmed_at,
    )


def question_detail(record: QuestionRecord) -> QuestionDetail:
    summary = question_summary(record)
    spans: list[SourceSpan] = []
    for item in record.sources:
        try:
            spans.append(SourceSpan.model_validate(item))
        except Exception as exc:  # noqa: BLE001
            raise _corrupt("题目的来源区间结构不符") from exc
    return QuestionDetail(
        **summary.model_dump(),
        content=_content(record.content, where="题目"),
        metadata=_metadata(record.metadata, where="题目"),
        sources=spans,
        sourceImportId=record.source_import_id,
    )


#: 批级失败码的默认中文说明；checkpoint 里 message 为空时用它兜底，不吞掉失败
_BATCH_FAILURE_MESSAGES = {
    "ORGANIZER_INVALID_JSON": "AI 返回内容不是合法 JSON，该批已失败，原文保留。",
    "ORGANIZER_TRUNCATED": "模型输出被截断，该批已失败，原文保留。",
    "ORGANIZER_UNKNOWN_SOURCE_BLOCK": "AI 引用了输入之外的来源块，该批已失败，原文保留。",
    "ORGANIZER_INVALID_CONTENT": "AI 返回内容不符合题库契约，该批已失败，原文保留。",
    "ORGANIZE_TARGET_MISSING": "目标草稿已不存在，该批建议未落库，原文保留。",
    "ORGANIZE_DRAFT_CHANGED": "目标草稿在整理期间被编辑，该批建议已丢弃，请重新整理。",
}


def organize_batch_failure(payload: Any) -> OrganizeBatchFailure:
    """checkpoint 里的失败批记录 → 契约模型；结构不符按数据损坏处理，不静默跳过。"""
    if not isinstance(payload, dict):
        raise _corrupt("整理任务的失败批记录不是对象")
    index = payload.get("index")
    code = payload.get("code")
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        raise _corrupt("整理任务的失败批 batchIndex 非法")
    if not isinstance(code, str) or not code:
        raise _corrupt("整理任务的失败批 code 非法")
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        message = _BATCH_FAILURE_MESSAGES.get(code, f"该批整理失败（{code}），原文保留。")
    return OrganizeBatchFailure(batchIndex=index, code=code, message=message)


def organize_job_view(
    record: JobRecord,
    *,
    suggestions: Sequence[SuggestionRecord],
    suggestion_count: int,
) -> OrganizeJobView:
    """整理任务视图：``suggestions`` 只含仍可处理的 ``pending`` 明细，``suggestionCount`` 仍是任务总数。"""
    raw_failures = record.checkpoint.get("failedBatches")
    if raw_failures is None:
        raw_failures = []
    if not isinstance(raw_failures, list):
        raise _corrupt("整理任务的 failedBatches 不是数组")
    failures = [organize_batch_failure(item) for item in raw_failures]
    return OrganizeJobView(
        jobId=record.job_id,
        state=record.state,  # type: ignore[arg-type]
        suggestionCount=suggestion_count,
        failedBatches=len(failures),
        errorCode=record.error_code,
        suggestions=[suggestion_view(record_item) for record_item in suggestions],
        failures=failures,
    )
