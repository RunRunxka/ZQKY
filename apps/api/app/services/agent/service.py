"""Agent 服务：模型解析 + 图装配 + checkpointer 生命周期。

装配期（main.py）创建一次：持 SqliteSaver（AsyncSqliteSaver）连接，按 thread_id 隔离
各 Agent 会话的 interrupt/checkpoint 状态。``build`` 按请求解析模型并编译图（图轻量、
每次新建即可，checkpointer 共享）。

骨架批的图只挂读类工具；写工具与确认闸门在 A3/A4 通过扩充 ``build_read_tools`` 接入，
图与运行器结构不变。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.core.exceptions import AppError
from app.services.agent import runtime
from app.services.agent.graph import AgentDeps, build_agent
from app.services.agent.model import resolve_agent_chat_model
from app.services.agent.tools import build_read_tools
from app.services.agent.tools_write import build_confirm_tools, build_import_tools


class AgentService:
    """Agent 编排服务：一个进程一个实例，checkpointer 落独立 SQLite 库。"""

    def __init__(self, *, checkpoint_db: Path, repo, secrets, app_state) -> None:
        self._checkpoint_db = checkpoint_db
        self._repo = repo
        self._secrets = secrets
        self._app_state = app_state
        self._conn: aiosqlite.Connection | None = None
        self._saver: AsyncSqliteSaver | None = None

    async def setup(self) -> None:
        """打开 checkpoint 库并建表；幂等（重复调用不重建连接）。"""
        if self._saver is not None:
            return
        self._checkpoint_db.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self._checkpoint_db))
        self._saver = AsyncSqliteSaver(self._conn)
        await self._saver.setup()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self._saver = None

    def prepare(self, model_profile_id: str):
        """流开始前解析模型 + 编译图；任何配置/凭证/可调用性错误在此抛 AppError。

        路由据此把"流开始前失败"转成 HTTP 错误（不进 SSE 流），与 /chat、/rag 一致。
        """
        if self._saver is None:
            raise AppError(
                "Agent 服务未初始化（checkpointer 未装配）。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        handle = resolve_agent_chat_model(self._repo, self._secrets, model_profile_id)
        tools = (
            build_read_tools(self._app_state)
            + build_import_tools(self._app_state)
            + build_confirm_tools(self._app_state)
        )
        deps = AgentDeps(
            chat_model=handle.chat_model,
            tools=tools,
            checkpointer=self._saver,
        )
        return build_agent(deps)

    async def stream_turn(self, agent, *, thread_id: str, message: str) -> AsyncIterator[dict]:
        """驱动已编译的图产出内部事件流（模型已在 prepare 解析，不再抛配置错误）。"""
        async for event in runtime.run_turn(agent, thread_id=thread_id, user_text=message):
            yield event

    async def resume_turn(self, agent, *, thread_id: str, decision: Any) -> AsyncIterator[dict]:
        """恢复被确认闸门挂起的一轮（A4 启用）。"""
        async for event in runtime.resume_turn(agent, thread_id=thread_id, decision=decision):
            yield event


__all__ = ["AgentService"]
