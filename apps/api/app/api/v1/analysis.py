"""Thin asynchronous T70 HTTP routes; SQL/IO execute in bounded threads."""
import functools
import anyio
from fastapi import APIRouter, Query, Request
from app.contracts.b4 import (AnalysisCreateRequest, AnalysisReceipt, AnalysisRunView, ClassReportRow,
                              EvidenceRow, NoteRequest, NoteView, Page, StudentReportRow)
from app.core.exceptions import AppError

router = APIRouter(tags=["analysis"])


def service(request):
    value = getattr(request.app.state, "analysis_service", None)
    if value is None:
        raise AppError("学情分析服务未装配。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)
    return value


async def run(fn, *args, **kwargs):
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


@router.post("/assessments/{assessment_id}/analysis-runs", response_model=AnalysisReceipt, status_code=202)
async def create_run(request: Request, assessment_id: str, body: AnalysisCreateRequest):
    return await service(request).create_run(assessment_id, body)


@router.get("/analysis-runs", response_model=Page[AnalysisRunView])
async def list_runs(request: Request, assessmentId: str | None = None, scoreRevisionId: str | None = None,
                    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return await run(service(request).list_runs, assessment_id=assessmentId, score_revision_id=scoreRevisionId, offset=offset, limit=limit)


@router.get("/analysis-runs/{run_id}", response_model=AnalysisRunView)
async def get_run(request: Request, run_id: str):
    return await run(service(request).get_run, run_id)


def report_endpoint(kind):
    async def endpoint(request: Request, run_id: str, classId: str | None = None,
                       participantId: str | None = None, knowledgePointId: str | None = None,
                       offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
        return await run(service(request).list_report_rows, run_id, kind, class_id=classId,
                         participant_id=participantId, knowledge_point_id=knowledgePointId, offset=offset, limit=limit)
    endpoint.__name__ = f"list_{kind}"
    return endpoint


for _kind, _model in (("classes", ClassReportRow), ("students", StudentReportRow), ("evidence", EvidenceRow)):
    router.add_api_route(f"/analysis-runs/{{run_id}}/{_kind}", report_endpoint(_kind), methods=["GET"], response_model=Page[_model])


@router.post("/analysis-runs/{run_id}/notes", response_model=NoteView, status_code=201)
async def add_note(request: Request, run_id: str, body: NoteRequest):
    return await run(service(request).add_note, run_id, body)


@router.get("/analysis-runs/{run_id}/notes", response_model=Page[NoteView])
async def list_notes(request: Request, run_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return await run(service(request).list_notes, run_id, offset=offset, limit=limit)
