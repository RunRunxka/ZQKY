"""Real owner-scoped confirmed revision selector; no model or write operations."""
import functools
import anyio
from fastapi import APIRouter, Query, Request
from app.contracts.b4 import Page
from app.contracts.lesson_sources import ConfirmedQuestionRevision
from app.core.exceptions import AppError

router = APIRouter(tags=["lesson-sources"])


@router.get("/confirmed-question-revisions", response_model=Page[ConfirmedQuestionRevision])
async def confirmed_question_revisions(request: Request, subjectId: str = Query(min_length=1, max_length=64),
                                       offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    reader = getattr(request.app.state, "fixed_question_reader", None)
    questions = getattr(request.app.state, "question_bank_service", None)
    if reader is None or questions is None:
        raise AppError("固定题库来源未装配。", code="SERVICE_UNAVAILABLE", status_code=503)
    snapshots, total = await anyio.to_thread.run_sync(functools.partial(
        reader.list_confirmed_page, subject_id=subjectId, owner_id=questions.owner_id, offset=offset, limit=limit))
    items = []
    for item in snapshots:
        stem = item.content.get("stemMarkdown")
        if not isinstance(stem, str):
            raise AppError("固定题目内容损坏。", code="QUESTION_ROW_CORRUPT", status_code=500)
        items.append(ConfirmedQuestionRevision(question_id=item.question_id,
            question_revision_id=item.question_revision_id, subject_id=item.subject_id, stem_markdown=stem))
    return Page(items=items, total=total, offset=offset, limit=limit)
