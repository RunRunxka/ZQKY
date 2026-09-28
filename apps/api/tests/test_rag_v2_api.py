"""HTTP 层：v2 路由的 SSE 形状、状态分项、错误信封与"未装配即 503"。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings
from tests.test_rag_v2_support import FakeExplainer, FakeSummarizer, RagEnv, sample_text

STATUS_KEYS = {"retrieval", "summarization", "sourceAccess", "scope", "generation", "humanQuality"}


def make_client(tmp_path, env: RagEnv, service=None) -> TestClient:
    app = create_app(
        make_settings(tmp_path),
        rag_service=service if service is not None else env.make_service(),
        bootstrap_textbooks=False,
    )
    return TestClient(app, base_url="http://127.0.0.1:8001")


def stream_body(env: RagEnv, *, turn: str = "turn-1", after: int = 0, question: str = "集合的表示方法") -> dict:
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


def test_status_reports_three_subsystems_and_never_uses_local_only(tmp_path):
    env = RagEnv(tmp_path / "ragdata", summarizer=FakeSummarizer())
    env.add_document(title="高中数学必修第一册", text=sample_text())
    with make_client(tmp_path, env) as client:
        response = client.get("/api/v1/rag/status")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == STATUS_KEYS
        assert "localOnly" not in body and "available" not in body
        assert body["retrieval"]["available"] is True
        assert body["retrieval"]["denseLimit"] == 50 and body["retrieval"]["rrfK"] == 60
        assert body["summarization"]["available"] is True
        assert body["sourceAccess"]["available"] is True
        assert body["scope"]["ready"] is False and body["scope"]["reason"]
        assert body["generation"]["generationId"] == env.generation.generation_id
        assert body["humanQuality"] == "not_run"

        env.save_teaching_settings(env.selection())
        refreshed = client.get("/api/v1/rag/status").json()
        assert refreshed["scope"]["ready"] is True
        assert refreshed["scope"]["selection"]["subjectId"] == "math"

        capabilities = client.get("/api/v1/capabilities").json()["capabilities"]
        rag = next(item for item in capabilities if item["feature"] == "rag")
        assert rag["status"] == "ready" and "人工教学质量" in rag["detail"]


def test_status_reports_unavailable_when_dependencies_missing(tmp_path):
    env = RagEnv(tmp_path / "ragdata")
    service = env.make_service(summarizer=None, retrieval=None, catalog=None, explainer=None)
    with make_client(tmp_path, env, service=service) as client:
        body = client.get("/api/v1/rag/status").json()
        assert body["retrieval"]["available"] is False
        assert body["summarization"]["available"] is False
        assert body["sourceAccess"]["available"] is False
        assert body["generation"] is None
        assert body["humanQuality"] == "not_run"

        capabilities = client.get("/api/v1/capabilities").json()["capabilities"]
        rag = next(item for item in capabilities if item["feature"] == "rag")
        assert rag["status"] == "unavailable"


def test_stream_ids_resume_and_request_validation_over_http(tmp_path):
    env = RagEnv(tmp_path / "ragdata", summarizer=FakeSummarizer())
    env.add_document(title="高中数学必修第一册", text=sample_text())
    service = env.make_service(max_rounds=1)
    with make_client(tmp_path, env, service=service) as client:
        body = stream_body(env)
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
            data = json.loads(next(line for line in frame if line.startswith("data: "))[6:])
            assert data["sessionId"] == "session-1" and data["turnId"] == "turn-1"
        start_data = json.loads(next(line for line in frames[0] if line.startswith("data: "))[6:])
        assert start_data["scopeSnapshot"]["schemaVersion"] == 2
        result = json.loads(next(line for line in frames[1] if line.startswith("data: "))[6:])["result"]
        assert result["status"] == "ok" and result["evidence"]

        resumed = client.post("/api/v1/rag/stream", json={**body, "afterEventId": 2})
        assert resumed.status_code == 200
        assert resumed.text.startswith("id: 3\n")
        assert "id: 1\n" not in resumed.text and "id: 2\n" not in resumed.text

        mismatch = client.post("/api/v1/rag/stream", json={**body, "sessionId": "other"})
        assert mismatch.status_code == 403
        assert mismatch.json()["code"] == "RAG_SESSION_MISMATCH"

        jumped = client.post("/api/v1/rag/stream", json={**body, "afterEventId": 99})
        assert jumped.status_code == 409
        assert jumped.json()["code"] == "RAG_EVENT_CONFLICT"

        unknown = client.post("/api/v1/rag/stream", json={**body, "subject": "数学"})
        assert unknown.status_code == 422
        assert unknown.json()["code"] == "INVALID_REQUEST"

        blank = client.post("/api/v1/rag/stream", json={**body, "question": "   "})
        assert blank.status_code == 422


def test_stream_scope_change_and_missing_scope_are_pre_stream_errors(tmp_path):
    env = RagEnv(tmp_path / "ragdata", summarizer=FakeSummarizer())
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    with make_client(tmp_path, env) as client:
        empty_scope = {
            "requestId": "request-1",
            "sessionId": "session-1",
            "turnId": "turn-empty",
            "question": "集合的表示方法",
            "scope": {
                "kind": "selection",
                "selection": {
                    "gradeId": "senior-1",
                    "subjectId": "math",
                    "editionId": "renjiao-a",
                    "documentIds": [],
                },
            },
            "afterEventId": 0,
        }
        empty = client.post("/api/v1/rag/stream", json=empty_scope)
        assert empty.status_code == 422
        assert empty.json()["code"] == "RAG_SCOPE_EMPTY"

        wrong_subject = client.post(
            "/api/v1/rag/stream",
            json={
                **empty_scope,
                "turnId": "turn-subject",
                "scope": {
                    "kind": "selection",
                    "selection": {
                        "gradeId": "senior-1",
                        "subjectId": "physics",
                        "editionId": "renjiao-a",
                        "documentIds": [document.document_id],
                    },
                },
            },
        )
        assert wrong_subject.status_code == 409
        assert wrong_subject.json()["code"] == "RAG_SCOPE_CHANGED"

        forged = stream_body(env)
        forged["scope"]["snapshot"]["scopeHash"] = "0" * 64
        response = client.post("/api/v1/rag/stream", json=forged)
        assert response.status_code == 409
        assert response.json()["code"] == "RAG_SCOPE_CHANGED"


def test_reply_cancel_and_explain_error_envelopes_over_http(tmp_path):
    env = RagEnv(tmp_path / "ragdata", summarizer=FakeSummarizer(), explainer=FakeExplainer())
    env.add_document(title="高中数学必修第一册", text=sample_text())
    service = env.make_service(max_rounds=1)
    with make_client(tmp_path, env, service=service) as client:
        expired = client.post(
            "/api/v1/rag/reply",
            json={
                "requestId": "request-1",
                "sessionId": "session-1",
                "turnId": "missing-turn",
                "interactionId": "old",
                "submissionId": "submission-1",
                "answers": [{"questionId": "textbook-follow-up", "skipped": True}],
            },
        )
        assert expired.status_code == 410
        assert expired.json()["code"] == "RAG_TURN_EXPIRED"
        assert expired.json()["requestId"]

        missing_field = client.post(
            "/api/v1/rag/reply",
            json={"sessionId": "session-1", "turnId": "turn-1"},
        )
        assert missing_field.status_code == 422

        cancel_expired = client.post(
            "/api/v1/rag/cancel", json={"sessionId": "session-1", "turnId": "missing-turn"}
        )
        assert cancel_expired.status_code == 410
        extra = client.post(
            "/api/v1/rag/cancel",
            json={"sessionId": "session-1", "turnId": "missing-turn", "requestId": "x"},
        )
        assert extra.status_code == 422

        # 结束后再提交 → 轮次已关闭（不假成功）
        stream_result = client.post("/api/v1/rag/stream", json=stream_body(env, turn="turn-closed"))
        assert stream_result.status_code == 200
        closed = client.post(
            "/api/v1/rag/reply",
            json={
                "requestId": "request-1",
                "sessionId": "session-1",
                "turnId": "turn-closed",
                "interactionId": "old",
                "submissionId": "submission-9",
                "answers": [{"questionId": "textbook-follow-up", "skipped": True}],
            },
        )
        assert closed.status_code == 409
        assert closed.json()["code"] == "RAG_TURN_CLOSED"


def test_explain_stream_uses_plain_chat_sse_without_cursor(tmp_path):
    env = RagEnv(tmp_path / "ragdata", summarizer=FakeSummarizer(), explainer=FakeExplainer())
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    service = env.make_service(max_rounds=1)
    with make_client(tmp_path, env, service=service) as client:
        location = client.post("/api/v1/rag/stream", json=stream_body(env))
        result = json.loads(
            next(line for line in frames_of(location.text)[1] if line.startswith("data: "))[6:]
        )["result"]
        evidence = result["evidence"][0]
        explain = client.post(
            "/api/v1/rag/explain/stream",
            json={
                "requestId": "explain-1",
                "sessionId": "session-1",
                "turnId": "explain-turn-1",
                "modelProfileId": "chat-profile-1",
                "originalQuestion": "集合的表示方法有哪些？",
                "followUp": "请结合教材原文讲清并集。",
                "scopeSnapshot": result["scopeSnapshot"],
                "evidenceRefs": [
                    {
                        "evidenceId": evidence["evidenceId"],
                        "documentRevisionId": evidence["documentRevisionId"],
                        "normalizedTextSha256": evidence["normalizedTextSha256"],
                        "charStart": evidence["charStart"],
                        "charEnd": evidence["charEnd"],
                    }
                ],
                "history": [],
            },
        )
        assert explain.status_code == 200
        text = explain.text
        assert "id: " not in text, "详解是普通聊天 SSE 语义，没有事件编号游标"
        assert "event: message.start" in text
        assert "event: text.delta" in text
        assert "event: message.end" in text
        assert "教材依据说明。" in text

        forged = client.post(
            "/api/v1/rag/explain/stream",
            json={
                "requestId": "explain-2",
                "sessionId": "session-1",
                "turnId": "explain-turn-2",
                "modelProfileId": "chat-profile-1",
                "originalQuestion": "集合的表示方法有哪些？",
                "followUp": "请结合教材原文讲清并集。",
                "scopeSnapshot": result["scopeSnapshot"],
                "evidenceRefs": [
                    {
                        "evidenceId": evidence["evidenceId"],
                        "documentRevisionId": evidence["documentRevisionId"],
                        "normalizedTextSha256": "0" * 64,
                        "charStart": evidence["charStart"],
                        "charEnd": evidence["charEnd"],
                    }
                ],
                "history": [],
            },
        )
        assert forged.status_code == 409
        assert forged.json()["code"] == "RAG_EVIDENCE_UNAVAILABLE"
        assert document.document_id


def test_unassembled_service_returns_503_for_every_rag_route(tmp_path):
    env = RagEnv(tmp_path / "ragdata")
    service = RagV2ServiceStub()
    snapshot = {
        "schemaVersion": 2,
        "selection": {
            "gradeId": "senior-1",
            "subjectId": "math",
            "editionId": "renjiao-a",
            "documentIds": [],
        },
        "documents": [],
        "embeddingGenerationId": "generation-1",
        "scopeHash": "0" * 64,
    }
    ref = {
        "evidenceId": "ev-0000000000000000",
        "documentRevisionId": "revision-1",
        "normalizedTextSha256": "0" * 64,
        "charStart": 0,
        "charEnd": 1,
    }
    with make_client(tmp_path, env, service=service) as client:
        for method, path, payload in (
            ("get", "/api/v1/rag/status", None),
            (
                "post",
                "/api/v1/rag/stream",
                {
                    "requestId": "request-1",
                    "sessionId": "session-1",
                    "turnId": "turn-1",
                    "question": "集合的表示方法",
                    "scope": {"kind": "frozen", "snapshot": snapshot},
                    "afterEventId": 0,
                },
            ),
            (
                "post",
                "/api/v1/rag/reply",
                {
                    "requestId": "request-1",
                    "sessionId": "session-1",
                    "turnId": "turn-1",
                    "interactionId": "interaction-1",
                    "submissionId": "submission-1",
                    "answers": [{"questionId": "textbook-follow-up", "skipped": True}],
                },
            ),
            ("post", "/api/v1/rag/cancel", {"sessionId": "session-1", "turnId": "turn-1"}),
            (
                "post",
                "/api/v1/rag/explain/stream",
                {
                    "requestId": "request-1",
                    "sessionId": "session-1",
                    "turnId": "turn-1",
                    "modelProfileId": "chat-profile-1",
                    "originalQuestion": "集合的表示方法有哪些？",
                    "followUp": "请结合教材原文讲清并集。",
                    "scopeSnapshot": snapshot,
                    "evidenceRefs": [ref],
                    "history": [],
                },
            ),
        ):
            call = getattr(client, method)
            response = call(path, json=payload) if payload is not None else call(path)
            assert response.status_code == 503, path
            assert response.json()["code"] == "SERVICE_UNAVAILABLE"
        assert service.status_calls == 0, "未装配的旧服务不得被调用"


class RagV2ServiceStub:
    """旧本地引擎服务的替身：没有 is_rag_v2 标记，路由必须直接 503。"""

    def __init__(self) -> None:
        self.status_calls = 0

    async def status(self) -> dict:
        self.status_calls += 1
        raise AssertionError("旧服务不应被 v2 路由调用")

    async def close(self) -> None:  # lifespan 会 await 它（main.py 约定）
        return None


@pytest.mark.asyncio
async def test_frozen_assembly_interface_matches_planned_main_wiring(tmp_path):
    """按冻结的装配接口驱动一遍：关键字构造 + start/events/reply/cancel/status/close。

    总控在 main.py 里只写这几行；任何签名漂移都必须在这里先失败。
    """
    from app.services.rag_v2.retrieval import HybridRetriever
    from app.services.rag_v2.requests import RagReplyRequestV2, RagStreamRequestV2
    from app.services.rag_v2.service import RagV2Service

    env = RagEnv(tmp_path / "ragdata", summarizer=FakeSummarizer(), explainer=FakeExplainer())
    env.add_document(title="高中数学必修第一册", text=sample_text())
    service = RagV2Service(
        catalog=env.catalog,
        retrieval=HybridRetriever(env.catalog, env.vectors, env.embeddings),
        summarizer=env.summarizer,
        explainer=env.explainer,
    )
    unsaved = RagV2Service()
    try:
        turn = service.start(
            RagStreamRequestV2(
                requestId="request-1",
                sessionId="session-1",
                turnId="turn-1",
                question="集合的表示方法",
                scope={"kind": "selection", "selection": env.selection()},
                afterEventId=0,
            )
        )
        assert turn.turn_id == "turn-1"
        seen = []
        async for event in service.events(turn, 0):
            if event is None:
                continue
            seen.append(event)
            if event["event"] in ("wait-user", "message.end", "error"):
                break
        assert [event["id"] for event in seen] == [1, 2, 3, 4]
        assert [event["event"] for event in seen] == [
            "message.start",
            "rag.result",
            "text.delta",
            "wait-user",
        ]
        assert set(seen[0]) == {"id", "event", "data"}

        card = turn.interaction
        assert card is not None
        assert service.reply(
            RagReplyRequestV2(
                requestId="request-1",
                sessionId="session-1",
                turnId="turn-1",
                interactionId=card["interactionId"],
                submissionId="submission-1",
                answers=[{"questionId": card["questions"][0]["questionId"], "skipped": True}],
            )
        ) == {"accepted": True}
        assert turn.terminal and turn.events[-1]["event"] == "message.end"
        assert service.cancel("session-1", "turn-1") == {"accepted": True}

        status = await unsaved.status()
        assert status["retrieval"]["available"] is False
        assert status["humanQuality"] == "not_run"

        await unsaved.close()
        await service.close()
        await service.close()  # close 幂等
        assert service.closed is True
    finally:
        if not service.closed:
            await service.close()


def test_origin_guard_still_applies_to_rag_routes(tmp_path):
    env = RagEnv(tmp_path / "ragdata", summarizer=FakeSummarizer())
    env.add_document(title="高中数学必修第一册", text=sample_text())
    with make_client(tmp_path, env) as client:
        response = client.post(
            "/api/v1/rag/stream",
            json=stream_body(env),
            headers={"Origin": "https://foreign.invalid"},
        )
        assert response.status_code == 403
        status = client.get("/api/v1/rag/status", headers={"Origin": "http://127.0.0.1:5173"})
        assert status.status_code == 200
