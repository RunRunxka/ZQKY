"""Wire-level host route tests for the v2 protocol; retrieval, summary and chat models are doubles.

原文件（v1 协议）的三个覆盖点逐项保留：

1. SSE 事件编号与公开载荷 + 断线续传 + 身份不符报错 + 同步定位只执行一次；
2. /rag/status 动态反映依赖状态且不假装成功（缺轮次 → 410，不返回假结果）；
3. 请求校验与来源防护（外站 Origin 403、非法请求 422）。
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.services.text_projection import TEXT_PROJECTION_VERSION
from app.main import create_app
from tests.conftest import make_settings
from tests.test_rag_v2_support import (
    FakeExplainer,
    FakeSummarizer,
    RagEnv,
    RecordingRetrieval,
    sample_text,
)


def make_env(tmp_path) -> tuple[RagEnv, RecordingRetrieval]:
    env = RagEnv(tmp_path / "ragdata", summarizer=FakeSummarizer(), explainer=FakeExplainer())
    env.add_document(title="高中数学必修第一册", text=sample_text())
    retriever = RecordingRetrieval(env.retriever)
    return env, retriever


def body_of(env: RagEnv, *, turn: str = "turn-1", after: int = 0, question: str = "集合的表示方法") -> dict:
    return {
        "requestId": "request-1",
        "sessionId": "session-1",
        "turnId": turn,
        "question": question,
        "scope": {"kind": "frozen", "snapshot": env.snapshot().model_dump(mode="json")},
        "afterEventId": after,
    }


def frames_of(text: str) -> list[list[str]]:
    return [frame.splitlines() for frame in text.strip().split("\n\n") if frame]


def payload_of(frame: list[str]) -> dict:
    return json.loads(next(line for line in frame if line.startswith("data: "))[6:])


def test_sse_ids_and_result_payload_and_idempotent_reconnect(tmp_path):
    env, retriever = make_env(tmp_path)
    service = env.make_service(retrieval=retriever, max_rounds=1)
    app = create_app(make_settings(tmp_path), rag_service=service, bootstrap_textbooks=False)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        body = body_of(env)
        response = client.post("/api/v1/rag/stream", json=body)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        frames = frames_of(response.text)
        assert [frame[0] for frame in frames] == ["id: 1", "id: 2", "id: 3", "id: 4"]
        assert "event: message.start" in frames[0]
        assert "event: rag.result" in frames[1]
        assert "event: text.delta" in frames[2]
        assert "event: message.end" in frames[3]
        for frame in frames:
            data = payload_of(frame)
            assert data["sessionId"] == body["sessionId"] and data["turnId"] == body["turnId"]
        result = payload_of(frames[1])["result"]
        assert result["status"] == "ok" and result["evidence"] and result["points"]
        assert result["reasonCode"] is None
        assert result["presentation"]["version"] == "compact-v1"
        assert result["presentation"]["bodyCharCount"] == sum(
            len(point["title"]) + len(point["summary"]) for point in result["points"]
        )
        # 首答正文只渲染知识点：不含 > 原文块、不含长 ev-id、不追加原文摘录
        content = payload_of(frames[2])["text"]
        assert result["points"][0]["title"] in content and "[1]" in content
        assert "> " not in content and "教材原文摘录" not in content
        assert result["evidence"][0]["evidenceId"] not in content
        assert result["evidence"][0]["readable"]["version"] == TEXT_PROJECTION_VERSION
        assert len(retriever.calls) == 1

        resumed = client.post("/api/v1/rag/stream", json={**body, "afterEventId": 2})
        assert resumed.status_code == 200
        assert resumed.text.startswith("id: 3\n")
        assert len(retriever.calls) == 1, "续传不得重复执行定位"

        mismatch = client.post("/api/v1/rag/stream", json={**body, "sessionId": "different"})
        assert mismatch.status_code == 403
        assert mismatch.json()["code"] == "RAG_SESSION_MISMATCH"


def test_status_is_dynamic_and_missing_or_expired_reply_is_not_fake_success(tmp_path):
    env, retriever = make_env(tmp_path)
    service = env.make_service(retrieval=retriever, max_rounds=1)
    app = create_app(make_settings(tmp_path), rag_service=service, bootstrap_textbooks=False)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        status = client.get("/api/v1/rag/status").json()
        assert status["retrieval"]["available"] is True
        assert status["humanQuality"] == "not_run"
        assert "localOnly" not in status

        env.save_teaching_settings(env.selection())
        capabilities = client.get("/api/v1/capabilities").json()["capabilities"]
        rag = next(item for item in capabilities if item["feature"] == "rag")
        assert rag["status"] == "ready" and "人工教学质量" in rag["detail"]
        assert not retriever.calls and env.vectors.calls == []

        response = client.post(
            "/api/v1/rag/reply",
            json={
                "requestId": "request-1",
                "sessionId": "s",
                "turnId": "expired",
                "interactionId": "old",
                "submissionId": "sub",
                "answers": [{"questionId": "q", "skipped": True}],
            },
        )
        assert response.status_code == 410
        assert response.json()["code"] == "RAG_TURN_EXPIRED"
        assert response.json()["requestId"]


def test_request_validation_and_local_origin_guard_remain_enforced(tmp_path):
    env, retriever = make_env(tmp_path)
    service = env.make_service(retrieval=retriever, max_rounds=1)
    app = create_app(make_settings(tmp_path), rag_service=service, bootstrap_textbooks=False)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        foreign = client.post(
            "/api/v1/rag/stream",
            json=body_of(env),
            headers={"Origin": "https://foreign.invalid"},
        )
        assert foreign.status_code == 403

        invalid = client.post("/api/v1/rag/stream", json={**body_of(env), "question": "   "})
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "INVALID_REQUEST"

        unknown = client.post("/api/v1/rag/stream", json={**body_of(env), "subject": "数学"})
        assert unknown.status_code == 422
        assert unknown.json()["code"] == "INVALID_REQUEST"
        assert not retriever.calls
