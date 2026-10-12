"""教案流式逐模块生成（C3-3）：模块流事件 + 脱敏 + 路由边界（R7 LangChain 适配）。

- stream_modules：假 LangChain handle（``chat_model.astream``）逐 delta 产出 →
  module-start/delta/done 序列 + end；单模块失败不中断后续（module-error 继续）；
- 上下文构造：学生姓名/学号不进提示词（复用 commentary 匿名聚合）；
- 路由：模型缺失 404、学情未就绪 409、SSE 事件序列。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.core.config import Settings
from app.main import create_app
from app.services.lesson_streaming.service import build_context, stream_modules
from tests.analysis_support import AnalysisScene


class _StreamChatModel:
    """流式替身：``astream`` 按注册的回复序列逐次产出增量（AIMessage chunk）。"""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.prompts: list[list] = []

    async def astream(self, messages):  # noqa: ANN001, ANN201
        self.prompts.append(list(messages))
        text = self.replies.pop(0) if self.replies else ""
        if text:
            yield AIMessage(content=text)


class _StreamHandle:
    """``resolve_agent_chat_model`` 句柄替身（只带 chat_model）。"""

    def __init__(self, model: _StreamChatModel) -> None:
        self.chat_model = model


class TestStreamModules:
    async def test_module_sequence(self) -> None:
        model = _StreamChatModel(["学情正文", "目标正文", "过程正文"])
        handle = _StreamHandle(model)
        events = []
        async for event in stream_modules(handle, report=None, knowledge_names=["分数的意义"],
                                          course_name="数学", requirements="", modules=["analysis", "objectives", "process"]):
            events.append(event)
        kinds = [e["type"] for e in events]
        assert kinds.count("module-start") == 3 and kinds.count("module-done") == 3
        assert kinds[-1] == "end"
        deltas = [e for e in events if e["type"] == "module-delta"]
        assert [d["module"] for d in deltas] == ["analysis", "objectives", "process"]
        # 脱敏上下文进每条 prompt
        for messages in model.prompts:
            assert "分数的意义" in messages[1].content

    async def test_single_module_failure_continues(self) -> None:
        class _FailingModel(_StreamChatModel):
            async def astream(self, messages):  # noqa: ANN001, ANN201
                self.prompts.append(list(messages))
                if len(self.prompts) == 1:
                    raise RuntimeError("上游断开")
                yield AIMessage(content="后续模块正文")

        handle = _StreamHandle(_FailingModel([]))
        events = []
        async for event in stream_modules(handle, report=None, knowledge_names=[], course_name="",
                                          requirements="", modules=["analysis", "objectives"]):
            events.append(event)
        kinds = [e["type"] for e in events]
        assert "module-error" in kinds
        assert kinds.count("module-done") == 1  # 第二个模块成功
        assert kinds[-1] == "end"

    def test_context_anonymizes_students(self) -> None:
        report = {
            "paperTitle": "期中卷",
            "participants": [{"participantId": "p1", "name": "张三", "studentNo": "20240101"}],
            "students": [
                {"participant": {"participantId": "p1", "name": "张三", "studentNo": "20240101"},
                 "knowledgePoint": {"knowledgePointId": "kp1", "name": "分数的意义"},
                 "observation": "needs_consolidation", "informationIncomplete": False,
                 "expectedCount": 2, "validCount": 2, "totalScoreUnits": 30, "totalMaxScoreUnits": 100},
            ],
            "classes": [],
        }
        context = build_context(report, ["分数的意义"], "数学", "侧重基础")
        assert "张三" not in context and "20240101" not in context
        assert "学生A" in context and "侧重基础" in context


ALLOWED = frozenset({"http://127.0.0.1:5173"})


def _client(data_dir: Path) -> TestClient:
    settings = Settings(host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=data_dir)
    app = create_app(settings, bootstrap_textbooks=False)
    return TestClient(app, base_url="http://127.0.0.1:8001")


class TestRoute:
    def test_model_not_found_is_http_error(self, tmp_path: Path) -> None:
        with _client(tmp_path) as client:
            resp = client.post("/api/v1/lesson-plans/generation-stream", json={
                "requestId": "r1", "modelProfileId": "no-such", "courseName": "数学",
            })
            assert resp.status_code == 404
            assert resp.json()["code"] == "MODEL_PROFILE_NOT_FOUND"

    def test_unready_analysis_is_http_error(self, tmp_path: Path) -> None:
        import anyio  # noqa: PLC0415

        scene = AnalysisScene(tmp_path / "teaching")  # 对齐 app 的 teaching_root
        receipt = anyio.run(scene.accept)
        settings = Settings(host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=tmp_path)
        app = create_app(settings, bootstrap_textbooks=False)
        # 注入真实 analysis_service（AnalysisScene 已在 tmp_path 建 teaching 库）+ 流路由
        app.state.analysis_service = scene.service
        from app.api.v1.lesson_stream import router as lesson_stream_router

        app.include_router(lesson_stream_router, prefix="/api/v1")
        with TestClient(app, base_url="http://127.0.0.1:8001") as client:
            connection = client.post("/api/v1/model-connections", json={
                "displayName": "测试供应商", "protocol": "openai-chat",
                "baseUrl": "https://api.example.com/v1", "apiKey": "sk-secret-123",
            }).json()
            profile = client.post("/api/v1/model-profiles", json={
                "connectionId": connection["id"], "displayName": "测试模型", "modelId": "test-model",
            }).json()
            resp = client.post("/api/v1/lesson-plans/generation-stream", json={
                "requestId": "r1", "modelProfileId": profile["id"], "courseName": "数学",
                "analysisRunId": receipt.run_id,
            })
            assert resp.status_code == 409, resp.text

    def test_stream_event_sequence(self, tmp_path: Path) -> None:
        """真机装配 + 注入假 handle 不易；此处用「resolver 替身」直接在 app.state 上覆盖。"""
        settings = Settings(host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=tmp_path)
        app = create_app(settings, bootstrap_textbooks=False)

        class _ResolverHandle:
            def __init__(self, model: _StreamChatModel) -> None:
                self.chat_model = model

        app.state.model_handle_resolver = None  # 归档注入点已由 resolve_agent_chat_model 取代
        from app.services.lesson_streaming.service import stream_modules as _sm  # noqa: F401

        # 直接替换路由使用的解析依赖：注入假句柄到 resolver 函数内部不可行，
        # 这里用 monkeypatch resolve_agent_chat_model 的模块级名字。
        import app.api.v1.lesson_stream as lesson_stream_module

        original = lesson_stream_module.stream_modules

        class _FakeResolverRepo:
            pass

        def _fake_resolve(repo, secrets, profile_id):
            return _ResolverHandle(_StreamChatModel(["分析正文", "目标正文"]))

        import app.services.agent.model as agent_model_module

        agent_model_module.resolve_agent_chat_model = _fake_resolve
        try:
            with TestClient(app, base_url="http://127.0.0.1:8001") as client:
                with client.stream("POST", "/api/v1/lesson-plans/generation-stream", json={
                    "requestId": "r1", "modelProfileId": "p", "courseName": "数学",
                    "modules": ["analysis", "objectives"],
                }) as resp:
                    assert resp.status_code == 200
                    body = "".join(chunk for chunk in resp.iter_text())
        finally:
            agent_model_module.resolve_agent_chat_model = __import__("app.services.agent.model", fromlist=["resolve_agent_chat_model"]).resolve_agent_chat_model
        names = [line.split("event: ", 1)[1].split("\n", 1)[0] for line in body.split("\n\n") if line.startswith("event: ")]
        assert names[0] == "message.start"
        assert "module.start" in names and "module.delta" in names and "module.done" in names
        assert names[-1] == "message.end"
        # SSE 载荷可解析
        for frame in body.split("\n\n"):
            if frame.startswith("data: "):
                json.loads(frame.split("data: ", 1)[1])
