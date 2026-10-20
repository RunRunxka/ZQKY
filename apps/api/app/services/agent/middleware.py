"""Agent 工具错误边界：只把我们自己的业务异常（``AppError``）转成可读 ToolMessage。

问题背景：工具内部业务异常（如仓储校验失败）默认会穿透 ToolNode（它只把参数校验错误
转成 ToolMessage）一路抛到 ``runtime.run_turn``，整轮对话以 ``UPSTREAM_ERROR`` 崩掉，
模型没有机会看到错误原因并自行纠正。

设计要点：
- **只捕获 ``app.core.exceptions.AppError``**：我们自己的业务错误有稳定 ``code`` 与可读
  中文消息，转成 ``ToolMessage(status="error", content="{code}: {消息}")`` 后模型能看到
  失败原因并改用正确参数重试；
- **绝不捕获控制流异常**：``GraphBubbleUp``（``GraphInterrupt`` 的基类）是写操作确认卡
  （``interrupt`` / ``Command(resume=...)``）的载体，必须原样放行，否则确认闸门失效；
- **也不捕获其他 ``Exception``**：网络/编程错误原样抛出，仍由 ``runtime.run_turn`` 的
  兜底归为 ``UPSTREAM_ERROR``，不把未知异常的内部细节喂给模型。

实现基于 LangChain 1.4 中间件协议（``AgentMiddleware.wrap_tool_call`` /
``awrap_tool_call``，经 ``create_agent(..., middleware=[...])`` 注入）。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphBubbleUp
from langgraph.prebuilt.tool_node import ToolCallRequest

from app.core.exceptions import AppError


def _error_content(exc: AppError) -> str:
    """业务异常 → 给模型看的单行可读错误（code 前缀 + 中文消息）。"""
    return f"{exc.code}: {exc}"


class AppErrorToolBoundary(AgentMiddleware):
    """工具调用错误边界（中间件）：``AppError`` → 可读 error ToolMessage，其余放行。

    挂在 ``create_agent(middleware=[...])`` 上后，LangGraph 的 ToolNode 会用
    ``wrap_tool_call`` / ``awrap_tool_call`` 包住每次工具执行。
    """

    def _to_error_message(
        self, exc: AppError, request: ToolCallRequest
    ) -> ToolMessage:
        tool_name = request.tool.name if request.tool else request.tool_call["name"]
        return ToolMessage(
            content=_error_content(exc),
            tool_call_id=request.tool_call["id"],
            name=tool_name,
            status="error",
        )

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Any],
    ) -> ToolMessage | Any:
        """同步工具执行边界：AppError 转 error ToolMessage；控制流/其他异常放行。"""
        try:
            return handler(request)
        except GraphBubbleUp:
            # interrupt / Command 等控制流信号必须原样传播（写操作确认卡依赖它）。
            raise
        except AppError as exc:
            return self._to_error_message(exc, request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Any]],
    ) -> ToolMessage | Any:
        """异步工具执行边界（运行器主路径）：语义与同步版一致。"""
        try:
            return await handler(request)
        except GraphBubbleUp:
            # interrupt / Command 等控制流信号必须原样传播（写操作确认卡依赖它）。
            raise
        except AppError as exc:
            return self._to_error_message(exc, request)


__all__ = ["AppErrorToolBoundary"]
