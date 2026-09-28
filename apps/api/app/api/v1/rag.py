"""教材 RAG v2 路由：定位（可续传 SSE）、澄清、取消、分别状态与所选模型详解。

协议要点（RAG-REBUILD v1.0，有意替换旧 v1 协议）：

- ``GET /rag/status`` 分别报告检索 / 本地概括 / 原文访问三项状态，另给范围、索引代与
  人工教学质量位；服务未装配时 503，不返回空结果。
- ``POST /rag/stream`` 请求体为 ``{requestId, sessionId, turnId, question, scope, afterEventId}``，
  未知字段 422；事件沿用递增编号与 ``afterEventId`` 续传，断线不取消。
- ``POST /rag/reply`` 澄清提交（``submissionId`` 幂等）；``POST /rag/cancel`` 显式取消。
- ``POST /rag/explain/stream`` 使用普通聊天 SSE 语义（无事件游标），不回到 ``/rag/reply``、
  不再次自动检索；断开或停止即关闭上游。
- ``start`` / ``reply`` / ``cancel`` 是同步方法，必须在事件循环线程调用（它们要创建
  asyncio 任务）；同步重活（向量检索、BM25、原文读取、本地概括）在服务内部的有界线程
  与 executor 中执行。``start`` 只做有界 SQL 读，因此范围错误在流开始前就是 HTTP 错误。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.exceptions import AppError
from app.schemas.rag_v2 import RagExplainRequest
from app.services.rag_v2.service import RagV2Service
from app.services.rag_v2.requests import (
    RagCancelRequestV2,
    RagReplyRequestV2,
    RagStreamRequestV2,
)

router = APIRouter(tags=["rag"])

STATUS_KEYS = ("retrieval", "summarization", "sourceAccess", "scope", "generation", "humanQuality")

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


def _service(request: Request) -> RagV2Service:
    """取 v2 服务；未装配（None 或旧的本地引擎服务）一律 503，绝不返回空结果。"""
    service = getattr(request.app.state, "rag_service", None)
    if service is None or not getattr(service, "is_rag_v2", False):
        raise AppError(
            "教材 RAG v2 服务未装配：/rag/* 当前不可用，请检查启动日志与依赖。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return service


def _sse(name: str, data: dict) -> bytes:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


@router.get("/rag/status")
async def rag_status(request: Request) -> dict:
    status = await _service(request).status()
    return {key: status.get(key) for key in STATUS_KEYS}


@router.post("/rag/stream")
async def rag_stream(request: Request, body: RagStreamRequestV2) -> StreamingResponse:
    service = _service(request)
    turn = service.start(body)

    async def stream():
        async for event in service.events(turn, body.afterEventId):
            if event is None:
                yield b": keep-alive\n\n"
            else:
                data = json.dumps(event["data"], ensure_ascii=False)
                yield f"id: {event['id']}\nevent: {event['event']}\ndata: {data}\n\n".encode("utf-8")
        # 传输层断线刻意保留这一轮：续传与显式 /rag/cancel 才是权威。

    return StreamingResponse(stream(), media_type="text/event-stream", headers=dict(_SSE_HEADERS))


@router.post("/rag/reply")
async def rag_reply(request: Request, body: RagReplyRequestV2) -> dict:
    return _service(request).reply(body)


@router.post("/rag/cancel")
async def rag_cancel(request: Request, body: RagCancelRequestV2) -> dict:
    return _service(request).cancel(body.sessionId, body.turnId)


@router.post("/rag/explain/stream")
async def rag_explain_stream(request: Request, body: RagExplainRequest) -> StreamingResponse:
    service = _service(request)
    generator = service.explain(body)
    try:
        # 异步生成器惰性执行：首个事件之前的所有失败都按"流开始前"转成 HTTP 错误。
        first = await generator.__anext__()
    except StopAsyncIteration as exc:
        await generator.aclose()
        raise AppError("详解上游未返回任何事件。", code="UPSTREAM_ERROR", status_code=502) from exc
    except BaseException:
        await generator.aclose()
        raise

    async def event_stream():
        try:
            yield _sse(first[0], first[1])
            async for name, data in generator:
                yield _sse(name, data)
        finally:
            # 断开或停止：关闭服务层生成器，其 finally 会关闭上游连接。
            await generator.aclose()

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=dict(_SSE_HEADERS))
