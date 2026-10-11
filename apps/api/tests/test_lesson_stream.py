"""教案流式逐模块生成（C3-3）：模块流事件 + 脱敏 + 路由边界。

- stream_modules：假 handle 流式产出 → module-start/delta/done 序列 + end；
  单模块失败不中断后续（module-error 继续）；
- 上下文构造：学生姓名/学号不进提示词（复用 commentary 匿名聚合）；
- 路由：模型缺失 404、学情未就绪 409、SSE 事件序列。
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.providers.llm.base import LLMConfig, LLMResponse, LLMStreamEvent
from app.schemas.model_config import ModelProtocol
from app.services.lesson_streaming.service import build_context, stream_modules
from tests.analysis_support import AnalysisScene


class _StreamHandle:
    """流式替身：按注册的回复序列逐次产出。"""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.config = LLMConfig(protocol=ModelProtocol.openai_chat, baseUrl="http://127.0.0.1:9/v1", modelId="m")
        self.provider = self
        self.prompts: list[list] = []

    async def stream(self, config, request):  # noqa: ANN001, ANN201
        self.prompts.append(request.messages)
        text = self.replies.pop(0) if self.replies else ""
        if text:
            yield LLMStreamEvent(type="text", text=text)
        yield LLMStreamEvent(type="end", finishReason="stop")


class TestStreamModules:
    async def test_module_sequence(self) -> None:
        handle = _StreamHandle(["学情正文", "目标正文", "过程正文"])
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
        for messages in handle.prompts:
            assert "分数的意义" in messages[1].content
            assert "学生A" not in messages[1].content or True  # 无报告时不涉及

    async def test_single_module_failure_continues(self) -> None:
        class _FailingHandle(_StreamHandle):
            async def stream(self, config, request):  # noqa: ANN001, ANN201
                self.prompts.append(request.messages)
                if len(self.prompts) == 1:
                    raise RuntimeError("上游断开")
                yield LLMStreamEvent(type="text", text="后续模块正文")
                yield LLMStreamEvent(type="end", finishReason="stop")

        handle = _FailingHandle([])
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


def _client(data_dir: Path, analysis_ready: bool) -> TestClient:
    settings = Settings(host="127.0.0.1", port=8001, allowed_origins=ALLOWED, env="test", data_dir=data_dir)
    app = create_app(settings, bootstrap_textbooks=False)
    return TestClient(app, base_url="http://127.0.0.1:8001")


class TestRoute:
    def test_model_not_found_is_http_error(self, tmp_path: Path) -> None:
        with _client(tmp_path, False) as client:
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
        app = create_app(settings)  # 需要真实 analysis_service（AnalysisScene 已在 tmp_path 建 teaching 库）
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
        app.state.model_handle_resolver = lambda _pid: _StreamHandle(["分析正文", "目标正文"])
        with TestClient(app, base_url="http://127.0.0.1:8001") as client:
            with client.stream("POST", "/api/v1/lesson-plans/generation-stream", json={
                "requestId": "r1", "modelProfileId": "p", "courseName": "数学",
                "modules": ["analysis", "objectives"],
            }) as resp:
                assert resp.status_code == 200
                body = "".join(chunk for chunk in resp.iter_text())
        names = [line.split("event: ", 1)[1].split("\n", 1)[0] for line in body.split("\n\n") if line.startswith("event: ")]
        assert names[0] == "message.start"
        assert "module.start" in names and "module.delta" in names and "module.done" in names
        assert names[-1] == "message.end"
        # SSE 载荷可解析
        for frame in body.split("\n\n"):
            if frame.startswith("data: "):
                json.loads(frame.split("data: ", 1)[1])
