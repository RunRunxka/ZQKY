"""教案流式逐模块生成（C3-3）：POST /lesson-plans/generation-stream（SSE）。

事件：module.start / module.delta / module.error / module.done / message.end / error。
流开始前失败（模型缺失/学情未就绪）用 HTTP 错误，流开始后用 error 事件——与 /chat、/rag 一致。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.exceptions import AppError
from app.schemas.lesson_stream import LessonStreamRequest
from app.services.lesson_streaming.service import DEFAULT_MODULES, stream_modules

router = APIRouter(tags=["lesson-plans"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


def _sse(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _resolver(request: Request):
    resolver = getattr(request.app.state, "model_handle_resolver", None)
    if resolver is None:
        raise AppError("模型解析器未装配，无法生成教案。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)
    return resolver


@router.post("/lesson-plans/generation-stream")
async def lesson_generation_stream(request: Request, body: LessonStreamRequest) -> StreamingResponse:
    # 流开始前的准备工作（模型解析/学情读取/知识点查询）在这里完成，失败即 HTTP 错误。
    resolver = _resolver(request)
    handle = resolver(body.modelProfileId)

    report: dict | None = None
    if body.analysisRunId:
        analysis = getattr(request.app.state, "analysis_service", None)
        if analysis is None:
            raise AppError("学情分析服务未装配。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)
        try:
            report = analysis.read_ready_report(body.analysisRunId)
        except AppError as exc:
            raise AppError(
                f"学情报告读取失败：{exc}", code=exc.code, status_code=exc.status_code, retryable=exc.retryable
            ) from exc

    knowledge_names: list[str] = []
    if body.selectedKnowledgePointIds:
        knowledge = getattr(request.app.state, "knowledge_service", None)
        if knowledge is None:
            raise AppError("知识点服务未装配。", code="SERVICE_UNAVAILABLE", status_code=503, retryable=True)
        for point_id in body.selectedKnowledgePointIds:
            point = knowledge.get_point(point_id)
            knowledge_names.append(point.name)

    modules = body.modules or list(DEFAULT_MODULES)
    request_id = body.requestId

    async def event_stream():
        yield _sse("message.start", {"requestId": request_id, "modules": modules})
        async for event in stream_modules(
            handle,
            report=report,
            knowledge_names=knowledge_names,
            course_name=body.courseName,
            requirements=body.requirements,
            modules=modules,
        ):
            kind = event.get("type")
            if kind == "module-start":
                yield _sse("module.start", {"module": event["module"], "label": event["label"]})
            elif kind == "module-delta":
                yield _sse("module.delta", {"module": event["module"], "text": event["text"]})
            elif kind == "module-error":
                yield _sse("module.error", {"module": event["module"], "message": event["message"]})
            elif kind == "module-done":
                yield _sse("module.done", {"module": event["module"]})
            elif kind == "end":
                yield _sse("message.end", {"finishReason": "stop"})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)
