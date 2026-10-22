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
from types import SimpleNamespace

import aiosqlite
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.errors import GraphInterrupt
from langgraph.types import Interrupt

from app.core.config import Settings
from app.core.exceptions import AppError
from app.main import create_app
from app.services.agent import middleware, runtime
from app.services.agent.graph import AgentDeps, build_agent
from app.services.agent.middleware import AppErrorToolBoundary


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


class _Chunk:
    def __init__(self, content: str = "字") -> None:
        self.content = content


class _EventAgent:
    """直接吐出指定 astream_events 序列的替身（不建图、不触网）。"""

    def __init__(self, events: list[dict]) -> None:
        self._events = events

    async def astream_events(self, invoke_input, config, version):  # noqa: ANN001, ANN201, ARG002
        for event in self._events:
            yield event


@pytest.mark.asyncio
async def test_event_guard_ignores_stream_chunks() -> None:
    """长回答（每个 token 一条 on_chat_model_stream）不得触发 AGENT_EVENT_OVERFLOW。"""
    events = [{"event": "on_chat_model_stream", "data": {"chunk": _Chunk()}} for _ in range(5000)]
    out = [event async for event in runtime._iter_events(_EventAgent(events), {}, {})]
    assert not any(event["type"] == "error" for event in out)
    assert len([event for event in out if event["type"] == "text"]) == 5000
    assert out[-1] == {"type": "end", "finishReason": "unknown"}


@pytest.mark.asyncio
async def test_event_guard_still_stops_control_event_flood() -> None:
    """控制流事件（工具/链/模型生命周期）仍受上限保护，超限报原错误码。"""
    events = [{"event": "on_chain_start", "data": {}} for _ in range(runtime._MAX_EVENTS + 1)]
    out = [event async for event in runtime._iter_events(_EventAgent(events), {}, {})]
    assert out[-1]["type"] == "error"
    assert out[-1]["code"] == "AGENT_EVENT_OVERFLOW"


@pytest.mark.asyncio
async def test_nested_tool_model_stream_is_not_chat_text() -> None:
    """工具内部 LLM 的流式 token（parent_ids 含工具 run）不得写进聊天正文。"""
    events = [
        {
            "event": "on_tool_start",
            "name": "create_lesson_plan_draft",
            "run_id": "tool-1",
            "data": {"input": {}},
        },
        {
            "event": "on_chat_model_stream",
            "run_id": "nested-1",
            "parent_ids": ["tool-1"],
            "data": {"chunk": _Chunk("LEAK")},
        },
        {
            "event": "on_tool_end",
            "name": "create_lesson_plan_draft",
            "run_id": "tool-1",
            "data": {"output": "lessonId=L1"},
        },
        {
            "event": "on_chat_model_stream",
            "run_id": "main-1",
            "parent_ids": ["model-node"],
            "data": {"chunk": _Chunk("VISIBLE")},
        },
        {"event": "on_chain_end", "name": "LangGraph", "data": {"output": {}}},
    ]
    out = [event async for event in runtime._iter_events(_EventAgent(events), {}, {})]
    assert [event["text"] for event in out if event["type"] == "text"] == ["VISIBLE"]
    assert any(event["type"] == "tool_call" for event in out)
    assert any(event["type"] == "tool_result" for event in out)


@pytest.mark.asyncio
async def test_internal_tagged_model_stream_is_not_chat_text() -> None:
    """显式 INTERNAL_TOOL_LLM_TAG 的流式 token 即使没有工具祖先也不外泄。"""
    from app.services.llm.tags import INTERNAL_TOOL_LLM_TAG

    events = [
        {
            "event": "on_chat_model_stream",
            "run_id": "nested-2",
            "tags": [INTERNAL_TOOL_LLM_TAG],
            "data": {"chunk": _Chunk("LEAK")},
        },
        {
            "event": "on_chat_model_stream",
            "run_id": "main-2",
            "data": {"chunk": _Chunk("VISIBLE")},
        },
    ]
    out = [event async for event in runtime._iter_events(_EventAgent(events), {}, {})]
    assert [event["text"] for event in out if event["type"] == "text"] == ["VISIBLE"]


@pytest.mark.asyncio
async def test_chat_model_end_emits_provider_usage() -> None:
    """主模型 on_chat_model_end 的 usage_metadata → usage 事件（真实 token）。"""
    events = [
        {
            "event": "on_chat_model_stream",
            "run_id": "main-1",
            "data": {"chunk": SimpleNamespace(content="答")},
        },
        {
            "event": "on_chat_model_end",
            "run_id": "main-1",
            "data": {
                "output": SimpleNamespace(
                    usage_metadata={
                        "input_tokens": 1200,
                        "output_tokens": 80,
                        "total_tokens": 1280,
                        "input_token_details": {"cache_read": 640},
                    }
                )
            },
        },
        {"event": "on_chain_end", "name": "LangGraph", "data": {"output": {}}},
    ]
    out = [event async for event in runtime._iter_events(_EventAgent(events), {}, {})]
    usages = [event for event in out if event["type"] == "usage"]
    assert usages == [
        {
            "type": "usage",
            "inputTokens": 1200,
            "outputTokens": 80,
            "totalTokens": 1280,
            "cachedInputTokens": 640,
        }
    ]
    assert out[-1]["type"] == "end"


@pytest.mark.asyncio
async def test_nested_tool_model_usage_is_filtered() -> None:
    """工具内部 LLM 的 usage 不得计入聊天上下文（只保留主模型一次）。"""
    events = [
        {"event": "on_tool_start", "name": "create_lesson_plan_draft", "run_id": "tool-1", "data": {"input": {}}},
        {
            "event": "on_chat_model_end",
            "run_id": "nested-1",
            "parent_ids": ["tool-1"],
            "data": {"output": SimpleNamespace(usage_metadata={"input_tokens": 9999, "output_tokens": 333})},
        },
        {"event": "on_tool_end", "name": "create_lesson_plan_draft", "run_id": "tool-1", "data": {"output": "ok"}},
        {
            "event": "on_chat_model_end",
            "run_id": "main-1",
            "data": {"output": SimpleNamespace(usage_metadata={"input_tokens": 500, "output_tokens": 20})},
        },
    ]
    out = [event async for event in runtime._iter_events(_EventAgent(events), {}, {})]
    usages = [event for event in out if event["type"] == "usage"]
    assert len(usages) == 1
    assert usages[0]["inputTokens"] == 500
    assert usages[0]["outputTokens"] == 20


@pytest.mark.asyncio
async def test_usage_falls_back_to_last_chunk_metadata() -> None:
    """end output 不带 usage 时，用最后一个流式 chunk 的 usage_metadata 兜底。"""
    events = [
        {
            "event": "on_chat_model_stream",
            "run_id": "main-2",
            "data": {
                "chunk": SimpleNamespace(
                    content="",
                    usage_metadata={"input_tokens": 42, "output_tokens": 7, "total_tokens": 49},
                )
            },
        },
        {
            "event": "on_chat_model_end",
            "run_id": "main-2",
            "data": {"output": SimpleNamespace(usage_metadata=None, response_metadata={})},
        },
    ]
    out = [event async for event in runtime._iter_events(_EventAgent(events), {}, {})]
    usages = [event for event in out if event["type"] == "usage"]
    assert usages == [
        {
            "type": "usage",
            "inputTokens": 42,
            "outputTokens": 7,
            "totalTokens": 49,
            "cachedInputTokens": None,
        }
    ]


@pytest.mark.asyncio
async def test_usage_falls_back_to_response_metadata() -> None:
    """没有 usage_metadata 时兼容 response_metadata.token_usage（OpenAI 风格）。"""
    events = [
        {
            "event": "on_chat_model_end",
            "run_id": "main-3",
            "data": {
                "output": SimpleNamespace(
                    usage_metadata=None,
                    response_metadata={
                        "token_usage": {
                            "prompt_tokens": 300,
                            "completion_tokens": 30,
                            "total_tokens": 330,
                            "prompt_tokens_details": {"cached_tokens": 100},
                        }
                    },
                )
            },
        },
    ]
    out = [event async for event in runtime._iter_events(_EventAgent(events), {}, {})]
    usages = [event for event in out if event["type"] == "usage"]
    assert usages[0]["inputTokens"] == 300
    assert usages[0]["outputTokens"] == 30
    assert usages[0]["totalTokens"] == 330
    assert usages[0]["cachedInputTokens"] == 100


@pytest.mark.asyncio
async def test_no_usage_metadata_does_not_fabricate_event() -> None:
    events = [
        {
            "event": "on_chat_model_end",
            "run_id": "main-4",
            "data": {"output": SimpleNamespace(usage_metadata=None, response_metadata={})},
        },
    ]
    out = [event async for event in runtime._iter_events(_EventAgent(events), {}, {})]
    assert not any(event["type"] == "usage" for event in out)


# --------------------------------------------------------------- 工具错误边界


def _tool_request(name: str = "list_classes", call_id: str = "call-1"):
    """构造最小 ToolCallRequest（中间件只读 tool/tool_call['name']/tool_call['id']）。"""
    from langgraph.prebuilt.tool_node import ToolCallRequest

    return ToolCallRequest(
        tool_call={"name": name, "args": {}, "id": call_id},
        tool=None,
        state={},
        runtime=None,
    )


class TestAppErrorToolBoundary:
    """工具错误边界：AppError → 可读 error ToolMessage；控制流/未知异常放行。"""

    @pytest.mark.asyncio
    async def test_app_error_becomes_error_tool_message(self) -> None:
        async def handler(request):  # noqa: ANN001, ANN202
            raise AppError("status 只能是 active 或 archived。", code="REQUEST_INVALID")

        result = await AppErrorToolBoundary().awrap_tool_call(_tool_request(), handler)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert result.tool_call_id == "call-1"
        assert result.content == "REQUEST_INVALID: status 只能是 active 或 archived。"

    def test_sync_path_app_error_becomes_error_tool_message(self) -> None:
        def handler(request):  # noqa: ANN001, ARG001
            raise AppError("status 只能是 active 或 archived。", code="REQUEST_INVALID")

        result = AppErrorToolBoundary().wrap_tool_call(_tool_request(), handler)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert result.content.startswith("REQUEST_INVALID:")

    @pytest.mark.asyncio
    async def test_graph_interrupt_propagates(self) -> None:
        """interrupt（GraphBubbleUp 子类）必须原样穿透，写确认卡不能被吞。"""
        marker = GraphInterrupt([Interrupt(value={"kind": "confirm"})])

        async def handler(request):  # noqa: ANN001, ARG001
            raise marker

        with pytest.raises(GraphInterrupt):
            await AppErrorToolBoundary().awrap_tool_call(_tool_request(), handler)
        with pytest.raises(GraphInterrupt):
            AppErrorToolBoundary().wrap_tool_call(_tool_request(), lambda r: (_ for _ in ()).throw(marker))

    @pytest.mark.asyncio
    async def test_unknown_exception_propagates(self) -> None:
        """非 AppError 的未知异常不吞、不转：仍抛给运行器兜底归 UPSTREAM_ERROR。"""
        class _Boom(RuntimeError):
            pass

        async def handler(request):  # noqa: ANN001, ARG001
            raise _Boom("boom")

        with pytest.raises(_Boom):
            await AppErrorToolBoundary().awrap_tool_call(_tool_request(), handler)

    @pytest.mark.asyncio
    async def test_success_passthrough_untouched(self) -> None:
        sentinel = ToolMessage(content="ok", tool_call_id="call-1")

        async def handler(request):  # noqa: ANN001, ARG001
            return sentinel

        assert await AppErrorToolBoundary().awrap_tool_call(_tool_request(), handler) is sentinel

    def test_error_content_format(self) -> None:
        assert middleware._error_content(AppError("教学库已关闭。", code="TEACHING_DB_CLOSED")) == (
            "TEACHING_DB_CLOSED: 教学库已关闭。"
        )

    @pytest.mark.asyncio
    async def test_agent_tool_error_becomes_tool_result_not_crash(self, tmp_path: Path) -> None:
        """端到端：真实图 + 抛 AppError 的工具 → SSE 收到 tool_result(error) 而非 error 帧。"""
        from langchain_core.tools import tool

        @tool
        def boom_tool(x: int = 0) -> str:
            """总是抛业务异常的假工具。"""
            raise AppError("参数不合法。", code="REQUEST_INVALID")

        calls = iter([
            AIMessage(
                content="",
                tool_calls=[{"name": "boom_tool", "args": {"x": 1}, "id": "call-boom"}],
            ),
            AIMessage(content="工具出错了，我已把原因转述给教师。"),
        ])

        class _ToolCallModel(GenericFakeChatModel):
            def bind_tools(self, tools, **kwargs):  # noqa: ANN001, ANN003
                return self

            def _generate(self, messages, stop=None, **kwargs):  # noqa: ANN001, ANN003
                return ChatResult(generations=[ChatGeneration(message=next(calls))])

            async def _agenerate(self, messages, stop=None, **kwargs):  # noqa: ANN001, ANN003
                return self._generate(messages, stop, **kwargs)

        conn = await aiosqlite.connect(str(tmp_path / "ck-boom.sqlite3"))
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        try:
            deps = AgentDeps(
                chat_model=_ToolCallModel(messages=iter([]), disable_streaming=True),
                tools=[boom_tool],
                checkpointer=saver,
            )
            agent = build_agent(deps)
            events = [
                event
                async for event in runtime.run_turn(
                    agent, thread_id="t-boom", user_text="调用 boom_tool"
                )
            ]
            kinds = [event["type"] for event in events]
            assert "tool_result" in kinds, f"应收到工具结果而非整轮报错：{events}"
            assert not any(event["type"] == "error" for event in events)
            results = [event for event in events if event["type"] == "tool_result"]
            assert any("REQUEST_INVALID" in event["output"] for event in results)
            assert events[-1]["type"] == "end"
        finally:
            await conn.close()


# ------------------------------------------------------------- 运行器兜底语义


class _RaisingAgent:
    """astream_events 直接抛指定异常的替身。"""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def astream_events(self, invoke_input, config, version):  # noqa: ANN001, ANN002, ANN201, ARG002
        raise self._exc
        yield  # pragma: no cover - 使本函数成为异步生成器


class TestRunTurnErrorSemantics:
    @pytest.mark.asyncio
    async def test_app_error_uses_original_code(self) -> None:
        agent = _RaisingAgent(
            AppError("教学库已关闭。", code="TEACHING_DB_CLOSED", retryable=True)
        )
        out = [event async for event in runtime.run_turn(agent, thread_id="t1", user_text="hi")]
        assert len(out) == 1 and out[0]["type"] == "error"
        assert out[0]["code"] == "TEACHING_DB_CLOSED"
        assert out[0]["retryable"] is True
        assert "教学库已关闭" in out[0]["message"]

    @pytest.mark.asyncio
    async def test_app_error_on_resume_uses_original_code(self) -> None:
        agent = _RaisingAgent(AppError("教案版本已变化。", code="REVISION_CONFLICT"))
        out = [event async for event in runtime.resume_turn(agent, thread_id="t1", decision={})]
        assert out[0]["code"] == "REVISION_CONFLICT"
        assert out[0]["retryable"] is False

    @pytest.mark.asyncio
    async def test_other_exception_still_upstream_error(self) -> None:
        agent = _RaisingAgent(RuntimeError("boom"))
        out = [event async for event in runtime.run_turn(agent, thread_id="t1", user_text="hi")]
        assert out[0]["code"] == "UPSTREAM_ERROR"
        assert out[0]["retryable"] is False
        assert "boom" in out[0]["message"]


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
