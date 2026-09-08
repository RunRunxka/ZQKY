"""学习问答流式接口：规范化 SSE 输出；流开始前用 HTTP 错误，流开始后用 error 事件。

事件协议见 docs/API.md：message.start / text.delta / usage / message.end / error。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import aclosing
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.exceptions import AppError
from app.providers.llm.base import LLMConfig, LLMMessage, LLMRequest, LLMStreamEvent
from app.providers.llm.factory import create_provider
from app.schemas.chat import ChatStreamRequest, validate_chat_request

router = APIRouter(tags=["chat"])

DEFAULT_CHAT_MAX_OUTPUT_TOKENS = 2048


def _sse(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


async def _chain_first(first: LLMStreamEvent, rest: AsyncIterator[LLMStreamEvent]) -> AsyncIterator[LLMStreamEvent]:
    yield first
    async for event in rest:
        yield event


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatStreamRequest) -> StreamingResponse:
    repo = request.app.state.model_config_repo
    secrets = request.app.state.secret_store

    profile = repo.get_profile(body.modelProfileId)
    if profile.purpose not in (None, "chat"):
        raise AppError(f"该模型配置用途为 {profile.purpose}，不能用于学习问答。", status_code=422)
    connection = repo.get_connection(profile.connectionId)
    if not secrets.has(connection.id):
        raise AppError(
            "该模型连接未保存凭证，请先在设置中填写 API Key。",
            code="MODEL_NOT_CONFIGURED",
            status_code=400,
        )
    validate_chat_request(body)
    unsupported = sorted(set(body.params or {}) - set(profile.supportedParams))
    if unsupported:
        raise AppError(
            f"该模型配置未声明支持参数：{', '.join(unsupported)}。",
            code="UNSUPPORTED_PARAMETER",
            status_code=422,
        )

    provider = create_provider(connection.protocol)
    config = LLMConfig(
        protocol=connection.protocol,
        baseUrl=connection.baseUrl,
        modelId=profile.modelId,
        apiKey=secrets.resolve(connection.id),
        extraHeaders=dict(connection.extraHeaders),
    )
    effective_max = body.maxOutputTokens or profile.maxOutputTokens or DEFAULT_CHAT_MAX_OUTPUT_TOKENS
    if profile.maxOutputTokens:
        effective_max = min(effective_max, profile.maxOutputTokens)
    llm_request = LLMRequest(
        messages=[LLMMessage(role=m.role, content=m.content) for m in body.messages],
        maxOutputTokens=effective_max,
        params={**profile.params, **(body.params or {})},
    )

    generator = provider.stream(config, llm_request)
    try:
        # 异步生成器惰性执行：取到首个事件即代表上游已返回 200，
        # 之前的任何 ProviderError 都按“流开始前”转换为 HTTP 错误。
        first = await generator.__anext__()
    except StopAsyncIteration as exc:
        raise AppError("上游流为空。", code="UPSTREAM_ERROR", status_code=502) from exc
    except AppError:
        await generator.aclose()
        raise

    message_id = uuid.uuid4().hex
    request_id = body.requestId

    async def event_stream() -> AsyncIterator[bytes]:
        yield _sse(
            "message.start",
            {"requestId": request_id, "messageId": message_id, "modelProfileId": profile.id},
        )
        try:
            async for event in _chain_first(first, generator):
                if event.type == "text" and event.text is not None:
                    yield _sse("text.delta", {"messageId": message_id, "text": event.text})
                elif event.type == "reasoning" and event.text is not None:
                    yield _sse("reasoning.delta", {"messageId": message_id, "text": event.text})
                elif event.type == "usage" and event.usage is not None:
                    yield _sse(
                        "usage",
                        {
                            "messageId": message_id,
                            "inputTokens": event.usage.inputTokens,
                            "outputTokens": event.usage.outputTokens,
                        },
                    )
                elif event.type == "end":
                    yield _sse(
                        "message.end",
                        {"messageId": message_id, "finishReason": event.finishReason},
                    )
                    break
        except AppError as exc:
            yield _sse(
                "error",
                {"requestId": request_id, "code": exc.code, "message": str(exc), "retryable": exc.retryable},
            )
        except asyncio.CancelledError:
            # 客户端断开：终止响应任务，生成器 finally 会关闭上游连接
            raise
        except Exception:
            yield _sse(
                "error",
                {"requestId": request_id, "code": "UPSTREAM_ERROR", "message": "上游流异常结束。", "retryable": False},
            )

        finally:
            await generator.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
