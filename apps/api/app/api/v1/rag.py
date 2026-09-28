"""Same-process local textbook RAG with resumable, session-scoped SSE turns."""

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.schemas.rag import RagIdentity, RagReplyRequest, RagStreamRequest

router = APIRouter(tags=["rag"])


@router.get("/rag/status")
async def rag_status(request: Request) -> dict:
    return await request.app.state.rag_service.status()


@router.post("/rag/stream")
async def rag_stream(request: Request, body: RagStreamRequest) -> StreamingResponse:
    service = request.app.state.rag_service
    turn = service.start(body)

    async def stream():
        async for event in service.events(turn, body.afterEventId):
            if event is None:
                yield b": keep-alive\n\n"
            else:
                data = json.dumps(event["data"], ensure_ascii=False)
                yield f"id: {event['id']}\nevent: {event['event']}\ndata: {data}\n\n".encode("utf-8")
        # A transport disconnect deliberately keeps the bounded turn for resumption.
        # Explicit /cancel is the authority for cancellation, including card expiry.

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
    })


@router.post("/rag/reply")
async def rag_reply(request: Request, body: RagReplyRequest) -> dict:
    return request.app.state.rag_service.reply(body)


@router.post("/rag/cancel")
async def rag_cancel(request: Request, body: RagIdentity) -> dict:
    return request.app.state.rag_service.cancel(body.sessionId, body.turnId)
