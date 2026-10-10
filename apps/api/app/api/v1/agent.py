"""Agent 路由：对话式驱动教学闭环的 SSE 入口（骨架批）。

协议与 /chat、/rag 一致：流开始前失败用 HTTP 错误，流开始后用 error 事件；
首事件产出后才进入 SSE 流。骨架批事件：message.start / text.delta / tool.call /
tool.result / wait-confirm / message.end / error。

写操作确认（A4 全面启用）：Agent 在写节点 interrupt 挂起 → wait-confirm 事件 →
教师确认后 POST /agent/confirm 用 Command(resume=...) 恢复。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.exceptions import AppError
from app.schemas.agent import AgentStreamRequest
from app.services.agent.service import AgentService

router = APIRouter(tags=["agent"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


def _sse(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _service(request: Request) -> AgentService:
    service = getattr(request.app.state, "agent_service", None)
    if service is None:
        raise AppError(
            "Agent 服务未装配：/agent/* 当前不可用，请检查启动日志与依赖。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    return service


def _to_sse(event: dict, *, message_id: str, request_id: str) -> bytes | None:
    """把运行器内部事件翻译成 SSE 帧；未知类型忽略（前向兼容）。"""
    kind = event.get("type")
    if kind == "text":
        return _sse("text.delta", {"messageId": message_id, "text": event["text"]})
    if kind == "tool_call":
        return _sse(
            "tool.call",
            {
                "messageId": message_id,
                "name": event["name"],
                "args": event["args"],
                "callId": event["callId"],
            },
        )
    if kind == "tool_result":
        return _sse(
            "tool.result",
            {
                "messageId": message_id,
                "name": event["name"],
                "callId": event["callId"],
                "output": event["output"],
            },
        )
    if kind == "wait-confirm":
        return _sse(
            "wait-confirm",
            {
                "requestId": request_id,
                "messageId": message_id,
                "confirmId": event["confirmId"],
                "payload": event["payload"],
            },
        )
    if kind == "end":
        return _sse("message.end", {"messageId": message_id, "finishReason": event["finishReason"]})
    if kind == "error":
        return _sse(
            "error",
            {
                "requestId": request_id,
                "code": event["code"],
                "message": event["message"],
                "retryable": event["retryable"],
            },
        )
    return None


@router.post("/agent/stream")
async def agent_stream(request: Request, body: AgentStreamRequest) -> StreamingResponse:
    service = _service(request)
    # 流开始前解析模型 + 编译图：模型缺失/凭证问题/连接不可调用在此抛 AppError，
    # 由统一异常处理器转成 HTTP 错误（不进 SSE 流），与 /chat、/rag 边界一致。
    agent = service.prepare(body.modelProfileId)

    message_id = body.requestId
    request_id = body.requestId

    async def event_stream():
        yield _sse(
            "message.start",
            {
                "requestId": request_id,
                "messageId": message_id,
                "threadId": body.threadId,
                "modelProfileId": body.modelProfileId,
            },
        )
        async for event in service.stream_turn(
            agent,
            thread_id=body.threadId,
            message=body.message,
        ):
            frame = _to_sse(event, message_id=message_id, request_id=request_id)
            if frame is not None:
                yield frame

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)
