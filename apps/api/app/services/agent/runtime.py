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

from app.core.exceptions import AppError
from app.services.llm.tags import INTERNAL_TOOL_LLM_TAG

#: 单轮控制流事件上限（防模型失控反复调工具/建链把流撑爆）；超出按 error 收尾。
#: **只统计非流式事件**：``on_chat_model_stream`` 每个 token 一条，计进来等于给输出长度
#: 设硬上限（教案级长文约 2000 token 就会误判「模型失控」）。输出长度由模型档案的
#: ``max_output_tokens`` 约束；图死循环另由 ``_RECURSION_LIMIT`` 兜底。
_MAX_EVENTS = 2000

#: 图的递归步数上限（防模型失控反复调工具死循环）；LangGraph 超限抛 GraphRecursionError，
#: 由运行器归为可读 error 事件。
_RECURSION_LIMIT = 50


def _error_event(exc: Exception, *, fallback_message: str) -> dict:
    """异常 → error 事件：业务 AppError 用原 code/retryable，其余归 UPSTREAM_ERROR。"""
    if isinstance(exc, AppError):
        return {
            "type": "error",
            "code": exc.code,
            "message": str(exc)[:300] or fallback_message,
            "retryable": bool(exc.retryable),
        }
    return {
        "type": "error",
        "code": "UPSTREAM_ERROR",
        "message": str(exc)[:300] or fallback_message,
        "retryable": False,
    }


def _norm_tool_args(raw: Any) -> dict:
    return raw if isinstance(raw, dict) else {"value": raw}


def _is_internal_stream_event(ev: dict, active_tool_runs: set[str]) -> bool:
    """工具内部 LLM 的流式事件：不进入聊天正文。

    两层判断：显式标签（``INTERNAL_TOOL_LLM_TAG``）优先；没有标签时看事件祖先里
    是否有正在执行的工具 run（LangChain 会把工具内部的模型调用挂在工具 run 之下）。
    """
    if INTERNAL_TOOL_LLM_TAG in set(ev.get("tags") or ()):
        return True
    parent_ids = ev.get("parent_ids") or ()
    return bool(active_tool_runs.intersection(parent_ids))


async def _pending_interrupts(agent, config) -> tuple:
    """读取图检查点里的待办中断。

    LangGraph 1.2 的 ``astream_events`` 顶层 ``on_chain_end`` 不再把 ``__interrupt__``
    放进 output（中间版本曾如此）；中断只落在 ``aget_state(config).interrupts``。
    这里兼容两种来源，查不到就按无中断处理（不伪造确认卡）。
    """
    getter = getattr(agent, "aget_state", None)
    if getter is None:
        return ()
    try:
        snapshot = await getter(config)
    except Exception:  # pragma: no cover - 无 checkpointer/状态不可读时不阻断收尾
        return ()
    return tuple(getattr(snapshot, "interrupts", ()) or ())


async def _iter_events(agent, invoke_input, config) -> AsyncIterator[dict]:
    """把 astream_events 原始事件翻译成内部事件；文本只取主模型的 chat_model_stream。"""
    emitted_end = False
    count = 0
    active_tool_runs: set[str] = set()
    async for ev in agent.astream_events(invoke_input, config, version="v2"):
        kind = ev.get("event")
        run_id = str(ev.get("run_id") or "")
        if kind == "on_tool_start":
            if run_id:
                active_tool_runs.add(run_id)
        elif kind in ("on_tool_end", "on_tool_error"):
            active_tool_runs.discard(run_id)
        # 流式 token/chunk 是输出长度，不是失控信号；只统计控制流事件。
        if kind != "on_chat_model_stream":
            count += 1
            if count > _MAX_EVENTS:
                yield {
                    "type": "error",
                    "code": "AGENT_EVENT_OVERFLOW",
                    "message": "本轮事件过多，已中止（可能模型失控）。",
                    "retryable": True,
                }
                return
        elif _is_internal_stream_event(ev, active_tool_runs):
            # 工具内部 LLM（如教案七模块结构化生成）的中间 token：不写进聊天正文。
            continue
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
        elif kind == "on_tool_error":
            # 工具执行抛错：错误边界中间件会把业务 AppError 转成 error ToolMessage 让
            # 模型继续（图不崩），但 LangGraph 对这次工具运行只发 on_tool_error、不发
            # on_tool_end。这里把它翻译成 tool_result，前端才能收尾这次工具调用；
            # 非 AppError 的异常随后会让图崩掉并走 error 事件，此帧只作前端补显。
            error = data.get("error")
            code = getattr(error, "code", "")
            text = f"{code}: {error}" if code else str(error)
            yield {
                "type": "tool_result",
                "name": ev.get("name") or "tool",
                "callId": ev.get("run_id") or "",
                "output": f"工具执行出错：{text}",
            }
        elif kind == "on_chain_end" and ev.get("name") == "LangGraph":
            # 图收尾：若是 interrupt 挂起，output 可能带 __interrupt__（旧版）或只在
            # 检查点状态里（LangGraph 1.2）。两者都查，先发 wait-confirm 再发 end，
            # 否则前端 token 已 terminal 会把确认卡事件丢掉。
            output = data.get("output") or {}
            interrupts = output.get("__interrupt__") if isinstance(output, dict) else None
            if not interrupts:
                interrupts = await _pending_interrupts(agent, config)
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
        # 没有顶层收尾事件时补一次检查点检查，避免确认卡漏发。
        interrupts = await _pending_interrupts(agent, config)
        if interrupts:
            first = interrupts[0]
            yield {
                "type": "wait-confirm",
                "confirmId": getattr(first, "id", "") or "",
                "payload": getattr(first, "value", None),
            }
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
        yield _error_event(exc, fallback_message="Agent 运行异常结束。")


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
        yield _error_event(exc, fallback_message="Agent 恢复运行异常结束。")


__all__ = ["resume_turn", "run_turn"]
