"""Agent 运行器：驱动编译后的图，把 LangGraph 事件规范化为内部事件流。

职责单一：``run_turn`` 接收用户消息（或 resume 决定），产出统一形状的内部事件 dict，
由路由层翻译成 SSE 帧。中断（写操作确认）在此挂起为 ``wait-confirm`` 事件；
``resume_turn`` 用 ``Command(resume=...)`` 恢复同一 thread 的图。

事件形状（路由层据此映射 SSE）：
- ``{"type": "text", "text": str}``            正文增量
- ``{"type": "tool_call", "name", "args", "callId"}``
- ``{"type": "tool_result", "name", "callId", "output"}``
- ``{"type": "wait-confirm", "confirmId", "payload"}``  写操作确认卡（A4 全面启用）
- ``{"type": "end", "finishReason"}``
- ``{"type": "error", "code", "message", "retryable"}``
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import Command

#: 单轮事件流上限保护（防模型失控死循环把流撑爆）；超出按 error 收尾。
_MAX_EVENTS = 2000

#: 图的递归步数上限（防模型失控反复调工具死循环）；LangGraph 超限抛 GraphRecursionError，
#: 由运行器归为可读 error 事件。
_RECURSION_LIMIT = 50


def _norm_tool_args(raw: Any) -> dict:
    return raw if isinstance(raw, dict) else {"value": raw}


async def _iter_events(agent, invoke_input, config) -> AsyncIterator[dict]:
    """把 astream_events 原始事件翻译成内部事件；文本只取主模型的 chat_model_stream。"""
    emitted_end = False
    count = 0
    async for ev in agent.astream_events(invoke_input, config, version="v2"):
        count += 1
        if count > _MAX_EVENTS:
            yield {
                "type": "error",
                "code": "AGENT_EVENT_OVERFLOW",
                "message": "本轮事件过多，已中止（可能模型失控）。",
                "retryable": True,
            }
            return
        kind = ev.get("event")
        data = ev.get("data") or {}

        if kind == "on_chat_model_stream":
            chunk = data.get("chunk")
            text = getattr(chunk, "content", None) if chunk is not None else None
            if isinstance(text, str) and text:
                yield {"type": "text", "text": text}
        elif kind == "on_tool_start":
            yield {
                "type": "tool_call",
                "name": ev.get("name") or "tool",
                "args": _norm_tool_args(data.get("input")),
                "callId": ev.get("run_id") or "",
            }
        elif kind == "on_tool_end":
            output = data.get("output")
            content = getattr(output, "content", output)
            yield {
                "type": "tool_result",
                "name": ev.get("name") or "tool",
                "callId": ev.get("run_id") or "",
                "output": content if isinstance(content, str) else str(content),
            }
        elif kind == "on_chain_end" and ev.get("name") == "LangGraph":
            # 图收尾：若是 interrupt 挂起，output 带 __interrupt__；否则正常结束。
            output = data.get("output") or {}
            interrupts = output.get("__interrupt__") if isinstance(output, dict) else None
            if interrupts:
                first = interrupts[0]
                yield {
                    "type": "wait-confirm",
                    "confirmId": getattr(first, "id", "") or "",
                    "payload": getattr(first, "value", None),
                }
            emitted_end = True
            yield {"type": "end", "finishReason": "stop"}

    if not emitted_end:
        yield {"type": "end", "finishReason": "unknown"}


async def run_turn(agent, *, thread_id: str, user_text: str) -> AsyncIterator[dict]:
    """发起一轮：把用户消息喂给图，产出内部事件流。"""
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": _RECURSION_LIMIT,
    }
    invoke_input = {"messages": [HumanMessage(content=user_text)]}
    try:
        async for event in _iter_events(agent, invoke_input, config):
            yield event
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # 上游/图异常：归为可读错误事件，不让裸异常进 SSE
        yield {
            "type": "error",
            "code": "UPSTREAM_ERROR",
            "message": str(exc)[:300] or "Agent 运行异常结束。",
            "retryable": False,
        }


async def resume_turn(agent, *, thread_id: str, decision: Any) -> AsyncIterator[dict]:
    """恢复被 interrupt 挂起的一轮（教师确认/拒绝后）。"""
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": _RECURSION_LIMIT,
    }
    try:
        async for event in _iter_events(agent, Command(resume=decision), config):
            yield event
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        yield {
            "type": "error",
            "code": "UPSTREAM_ERROR",
            "message": str(exc)[:300] or "Agent 恢复运行异常结束。",
            "retryable": False,
        }


__all__ = ["resume_turn", "run_turn"]
