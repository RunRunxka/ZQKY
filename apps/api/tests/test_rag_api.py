"""Wire-level host route tests; the local engine is explicitly replaced by a double."""

import json

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings
from tests.test_rag_sessions import make_service, request


def test_sse_ids_and_public_payload_and_idempotent_reconnect(tmp_path):
    service, runtime, builds = make_service(tmp_path, max_rounds=1)
    app = create_app(make_settings(tmp_path), rag_service=service)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        body = request().model_dump()
        response = client.post("/api/v1/rag/stream", json=body)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        frames = [frame for frame in response.text.strip().split("\n\n") if frame]
        assert [frame.splitlines()[0] for frame in frames] == ["id: 1", "id: 2", "id: 3", "id: 4"]
        assert "event: message.start" in frames[0]
        assert "event: message.end" in frames[-1]
        for frame in frames:
            data = json.loads(frame.split("data: ", 1)[1])
            assert data["sessionId"] == body["sessionId"] and data["turnId"] == body["turnId"]
        assert "集合元素互异" in response.text and "教材外补充" in response.text
        resumed = client.post("/api/v1/rag/stream", json={**body, "afterEventId": 2})
        assert resumed.status_code == 200
        assert resumed.text.startswith("id: 3\n")
        assert len(runtime.calls) == len(builds) == 1
        mismatch = client.post("/api/v1/rag/stream", json={**body, "sessionId": "different"})
        assert mismatch.status_code == 403
        assert mismatch.json()["code"] == "RAG_SESSION_MISMATCH"


def test_status_is_dynamic_and_missing_or_expired_reply_is_not_fake_success(tmp_path):
    service, runtime, builds = make_service(tmp_path)
    app = create_app(make_settings(tmp_path), rag_service=service)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        status = client.get("/api/v1/rag/status").json()
        assert status["available"] and status["humanQuality"] == "not_run"
        capabilities = client.get("/api/v1/capabilities").json()["capabilities"]
        rag = next(item for item in capabilities if item["feature"] == "rag")
        assert rag["status"] == "ready" and "人工教学质量" in rag["detail"]
        assert not runtime.calls and not builds
        response = client.post("/api/v1/rag/reply", json={
            "sessionId": "s", "turnId": "expired", "interactionId": "old",
            "submissionId": "sub", "answers": [{"questionId": "q", "skipped": True}],
        })
        assert response.status_code == 410
        assert response.json()["code"] == "RAG_TURN_EXPIRED"
        assert response.json()["requestId"]


def test_rag_request_validation_and_local_origin_guard_remain_enforced(tmp_path):
    service, _, _ = make_service(tmp_path)
    app = create_app(make_settings(tmp_path), rag_service=service)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        response = client.post("/api/v1/rag/stream", json=request().model_dump(),
                               headers={"Origin": "https://foreign.invalid"})
        assert response.status_code == 403
        invalid = client.post("/api/v1/rag/stream", json={**request().model_dump(), "question": "   "})
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "INVALID_REQUEST"
