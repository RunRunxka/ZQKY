"""Agent 路由：对话式驱动教学闭环的 SSE 入口。

协议与 /chat、/rag 一致：流开始前失败用 HTTP 错误，流开始后用 error 事件；
首事件产出后才进入 SSE 流。事件：message.start / text.delta / tool.call /
tool.result / wait-confirm / message.end / error。

写操作确认：写类工具（confirm/apply）内部 interrupt 挂起 → wait-confirm 事件 →
教师确认后 POST /agent/confirm 用 Command(resume=decision) 恢复同一 thread。
上传：POST /agent/upload 先落 blob 拿 assetRef，随 /agent/stream 的 attachments 传入；
import_* 工具按 assetRef 读字节建导入草稿（产候选），教师在工作台预览确认。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.core.exceptions import AppError
from app.schemas.agent import AgentConfirmRequest, AgentStreamRequest, AgentUploadResponse
from app.schemas.textbook import MAX_UPLOAD_BYTES
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

    # 附件以结构化文本附在用户消息后（字节不进上下文，只给 assetRef 供 import 工具读取）。
    message_text = body.message
    if body.attachments:
        lines = ["", "【随附文件（用 import 工具按 assetId 读取字节建导入草稿）】"]
        for att in body.attachments:
            lines.append(
                f"- assetId={att.assetId} fileName={att.fileName} "
                f"mediaType={att.mediaType or '未知'} 建议类型={att.kind}"
            )
        message_text = body.message + "\n" + "\n".join(lines)

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
            message=message_text,
        ):
            frame = _to_sse(event, message_id=message_id, request_id=request_id)
            if frame is not None:
                yield frame

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/agent/upload", response_model=AgentUploadResponse)
async def agent_upload(request: Request, file: UploadFile) -> AgentUploadResponse:
    """接收上传文件并落受管 blob，返回 assetRef 供 /agent/stream 的 attachments 引用。

    只存字节并返回 sha256/assetId；解析与建草稿由 import_* 工具在对话中完成。
    """
    _service(request)  # 服务未装配 → 503（与对话入口同一闸门）
    assets = getattr(request.app.state, "asset_store", None)
    if assets is None:
        raise AppError(
            "资产存储未装配，暂无法接收上传文件。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    data = await file.read()
    if not data:
        raise AppError("上传文件为空。", code="INVALID_REQUEST", status_code=422)
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError(
            f"上传文件超过 {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB 上限。",
            code="UPLOAD_TOO_LARGE",
            status_code=413,
        )
    media_type = file.content_type or ""
    original_name = file.filename or "upload"
    stored = assets.store_original(data, media_type=media_type, original_name=original_name)
    return AgentUploadResponse(
        assetId=stored.sha256,
        fileName=original_name,
        mediaType=media_type,
        byteSize=stored.byte_size,
        sha256=stored.sha256,
    )


@router.post("/agent/confirm")
async def agent_confirm(request: Request, body: AgentConfirmRequest) -> StreamingResponse:
    """教师对写操作确认卡的决定：approve → Command(resume) 恢复执行，reject → 恢复但不写库。

    恢复后的事件同样以 SSE 流回（继续的文本/工具调用/结束）。
    """
    service = _service(request)
    agent = service.prepare(body.modelProfileId)

    message_id = body.requestId
    request_id = body.requestId
    decision = {"decision": body.decision, "submissionId": body.submissionId, "confirmId": body.confirmId}

    async def event_stream():
        yield _sse(
            "message.start",
            {
                "requestId": request_id,
                "messageId": message_id,
                "threadId": body.threadId,
                "modelProfileId": body.modelProfileId,
                "resumed": True,
            },
        )
        async for event in service.resume_turn(
            agent,
            thread_id=body.threadId,
            decision=decision,
        ):
            frame = _to_sse(event, message_id=message_id, request_id=request_id)
            if frame is not None:
                yield frame

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)
