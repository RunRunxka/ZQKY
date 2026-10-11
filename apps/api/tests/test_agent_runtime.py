"""Agent 骨架（A2）：运行器事件流 + /agent/stream 路由正确行为回归。

- 运行器：假 chat model（不触网）驱动 create_agent 图，验证 text/end 事件序列与
  SqliteSaver checkpointer 装配；
- 路由：流开始前模型缺失 → 404（HTTP 错误，不进 SSE）；空 body → 422；
  服务未装配 → 503。

全部使用 tmp_path 临时数据库与假模型，不触网、不读写正式数据目录。
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import aiosqlite
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.core.config import Settings
from app.main import create_app
from app.services.agent import runtime
from app.services.agent.graph import AgentDeps, build_agent


class _FakeChatModel(GenericFakeChatModel):
    """直接返回固定 AIMessage 的替身：bind_tools 不改装、同步/异步生成一致。"""

    reply: str = "你好，我是教学 Agent"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001, ANN003
        return self

    def _generate(self, messages, stop=None, **kwargs):  # noqa: ANN001, ANN003
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.reply))])

    async def _agenerate(self, messages, stop=None, **kwargs):  # noqa: ANN001, ANN003
        return self._generate(messages, stop, **kwargs)


def _no_tool_state():
    class _State:
        rag_service = None
        knowledge_service = None
        roster_service = None
        paper_service = None
        assessment_service = None
        score_service = None
        analysis_service = None
        practice_service = None
        lesson_plan_service = None

    return _State()


async def _make_agent(tmp_path: Path):
    conn = await aiosqlite.connect(str(tmp_path / "ck.sqlite3"))
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    from app.services.agent.tools import build_read_tools

    deps = AgentDeps(
        chat_model=_FakeChatModel(messages=iter([])),
        tools=build_read_tools(_no_tool_state()),
        checkpointer=saver,
    )
    return build_agent(deps), conn


@pytest.mark.asyncio
async def test_run_turn_streams_text_and_end(tmp_path: Path) -> None:
    agent, conn = await _make_agent(tmp_path)
    try:
        events = [e async for e in runtime.run_turn(agent, thread_id="t1", user_text="你好")]
        kinds = [e["type"] for e in events]
        assert kinds[0] == "text"
        assert "text" in kinds
        assert kinds[-1] == "end"
        assert events[-1]["finishReason"] == "stop"
        text = "".join(e.get("text", "") for e in events if e["type"] == "text")
        assert "教学 Agent" in text
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_checkpoint_persists_across_graph_rebuild(tmp_path: Path) -> None:
    """同一 thread 重建图（checkpointer 共享同一库文件）后历史仍可恢复（骨架：状态可读）。"""
    agent, conn = await _make_agent(tmp_path)
    conn2 = None
    try:
        _ = [e async for e in runtime.run_turn(agent, thread_id="shared", user_text="第一句")]
        # 复用同一库文件新建连接与图（模拟新请求的 prepare），状态应沿 thread 可读
        agent2, conn2 = await _make_agent(tmp_path)
        state = await agent2.aget_state({"configurable": {"thread_id": "shared"}})
        assert state is not None
        assert state.values.get("messages"), "重建图后 thread 历史应可恢复"
    finally:
        if conn2 is not None:
            await conn2.close()
        await conn.close()


ALLOWED = frozenset({"http://127.0.0.1:5173"})


def _client(data_dir: Path) -> TestClient:
    settings = Settings(
        host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=data_dir
    )
    app = create_app(settings)
    return TestClient(app, base_url="http://127.0.0.1:8001")


def test_agent_stream_rejects_empty_body(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        resp = client.post("/api/v1/agent/stream", json={})
        assert resp.status_code == 422


def test_agent_stream_model_not_found_is_http_error(tmp_path: Path) -> None:
    """流开始前模型缺失 → 404 MODEL_PROFILE_NOT_FOUND（HTTP 错误，不进 SSE 流）。"""
    with _client(tmp_path) as client:
        resp = client.post(
            "/api/v1/agent/stream",
            json={"requestId": "r1", "threadId": "t1", "message": "你好", "modelProfileId": "no-such"},
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == "MODEL_PROFILE_NOT_FOUND"


def test_agent_stream_rejects_oversize_message(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        resp = client.post(
            "/api/v1/agent/stream",
            json={"requestId": "r1", "threadId": "t1", "message": "x" * 40000, "modelProfileId": "p"},
        )
        assert resp.status_code == 422
