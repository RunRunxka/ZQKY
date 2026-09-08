"""学习问答 SSE 端点测试：事件协议、流前 HTTP 错误、流中 error 事件与参数校验。"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings

CONNECTION_PAYLOAD = {
    "displayName": "测试供应商",
    "protocol": "openai-chat",
    "baseUrl": "https://api.example.com/v1",
    "apiKey": "sk-secret-123",
}


@pytest.fixture()
def api_client(tmp_path: Path) -> TestClient:
    with TestClient(
        create_app(make_settings(tmp_path / "data")), base_url="http://127.0.0.1:8001"
    ) as test_client:
        return test_client


def setup_profile(api_client: TestClient) -> str:
    response = api_client.post("/api/v1/model-connections", json=CONNECTION_PAYLOAD)
    assert response.status_code == 201, response.text
    connection_id = response.json()["id"]
    profile = api_client.post(
        "/api/v1/model-profiles",
        json={
            "connectionId": connection_id,
            "displayName": "测试模型",
            "modelId": "sim-model",
            "supportedParams": ["temperature"],
        },
    )
    assert profile.status_code == 201, profile.text
    return profile.json()["id"]


async def fake_open_stream(config, url, headers, body, transport=None):
    """绕过真实 httpx，直接产出已解析的 SSE 数据序列。"""
    from types import SimpleNamespace

    async def sse() -> AsyncIterator[tuple[str | None, str]]:
        yield None, '{"choices":[{"delta":{"content":"你好"}}]}'
        yield None, '{"choices":[{"delta":{"content":"，世界"}}]}'
        yield None, '{"choices":[{"delta":{},"finish_reason":"stop"}]}'
        yield None, '{"usage":{"prompt_tokens":9,"completion_tokens":4}}'
        yield None, "[DONE]"

    yield SimpleNamespace(status_code=200), sse()


def patch_open_stream(monkeypatch: pytest.MonkeyPatch, fake) -> None:
    from app.providers.llm import openai_chat

    monkeypatch.setattr(openai_chat, "open_stream", asynccontextmanager(fake))


class TestChatStreamEndpoint:
    def test_sse_event_protocol(self, api_client, monkeypatch):
        profile_id = setup_profile(api_client)
        patch_open_stream(monkeypatch, fake_open_stream)

        response = api_client.post(
            "/api/v1/chat/stream",
            json={
                "requestId": "req-12345678",
                "modelProfileId": profile_id,
                "messages": [{"role": "user", "content": "你好"}],
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "no-cache" in response.headers["cache-control"]

        events = []
        for block in response.text.split("\n\n"):
            lines = block.splitlines()
            name = next((line[7:] for line in lines if line.startswith("event: ")), None)
            data = next((line[6:] for line in lines if line.startswith("data: ")), None)
            if name and data:
                events.append((name, json.loads(data)))
        assert [name for name, _ in events] == [
            "message.start",
            "text.delta",
            "text.delta",
            "usage",
            "message.end",
        ]
        start_data = events[0][1]
        assert start_data["requestId"] == "req-12345678"
        assert start_data["modelProfileId"] == profile_id
        assert events[1][1]["text"] == "你好"
        assert events[2][1]["text"] == "，世界"
        assert events[3][1]["outputTokens"] == 4
        assert events[4][1]["finishReason"] == "stop"

    def test_without_credential_is_http_error_before_stream(self, api_client):
        connection = api_client.post(
            "/api/v1/model-connections", json={**CONNECTION_PAYLOAD, "apiKey": None}
        ).json()
        profile = api_client.post(
            "/api/v1/model-profiles",
            json={"connectionId": connection["id"], "displayName": "m", "modelId": "sim-model"},
        ).json()
        response = api_client.post(
            "/api/v1/chat/stream",
            json={
                "requestId": "req-12345678",
                "modelProfileId": profile["id"],
                "messages": [{"role": "user", "content": "你好"}],
            },
        )
        assert response.status_code == 400
        assert response.json()["code"] == "MODEL_NOT_CONFIGURED"

    def test_missing_profile_404(self, api_client):
        response = api_client.post(
            "/api/v1/chat/stream",
            json={
                "requestId": "req-12345678",
                "modelProfileId": "missing",
                "messages": [{"role": "user", "content": "你好"}],
            },
        )
        assert response.status_code == 404

    def test_context_too_large(self, api_client):
        profile_id = setup_profile(api_client)
        response = api_client.post(
            "/api/v1/chat/stream",
            json={
                "requestId": "req-12345678",
                "modelProfileId": profile_id,
                "messages": [{"role": "user", "content": "长" * 30_000} for _ in range(5)],
            },
        )
        assert response.status_code == 413
        assert response.json()["code"] == "CONTEXT_TOO_LARGE"

    def test_unsupported_param_422(self, api_client):
        profile_id = setup_profile(api_client)
        response = api_client.post(
            "/api/v1/chat/stream",
            json={
                "requestId": "req-12345678",
                "modelProfileId": profile_id,
                "messages": [{"role": "user", "content": "你好"}],
                "params": {"top_p": 0.9},
            },
        )
        assert response.status_code == 422
        assert response.json()["code"] == "UNSUPPORTED_PARAMETER"

    def test_midstream_upstream_error_becomes_error_event(self, api_client, monkeypatch):
        profile_id = setup_profile(api_client)
        from app.providers.llm.base import ProviderError

        async def failing_open_stream(config, url, headers, body, transport=None):
            async def sse():
                yield None, '{"choices":[{"delta":{"content":"部分"}}]}'
                yield None, '{"error":{"message":"上游中断"}}'

            from types import SimpleNamespace

            yield SimpleNamespace(status_code=200), sse()

        patch_open_stream(monkeypatch, failing_open_stream)
        response = api_client.post(
            "/api/v1/chat/stream",
            json={
                "requestId": "req-12345678",
                "modelProfileId": profile_id,
                "messages": [{"role": "user", "content": "你好"}],
            },
        )
        assert response.status_code == 200
        assert "event: text.delta" in response.text
        assert "部分" in response.text  # 已收到的部分内容不被丢弃
        assert "event: error" in response.text
        assert "UPSTREAM_ERROR" in response.text
        assert "上游中断" not in response.text
        assert "event: message.end" not in response.text

    def test_reasoning_delta_forwarded_as_event(self, api_client, monkeypatch):
        async def fake_open_stream(config, url, headers, body, transport=None):
            async def sse() -> AsyncIterator[tuple[str | None, str]]:
                yield None, '{"choices":[{"delta":{"reasoning_content":"\u63a8\u7406"}}]}'
                yield None, '{"choices":[{"delta":{"content":"\u6b63\u6587"}}]}'
                yield None, '{"choices":[{"delta":{},"finish_reason":"stop"}]}'
                yield None, "[DONE]"

            from types import SimpleNamespace

            yield SimpleNamespace(status_code=200), sse()

        patch_open_stream(monkeypatch, fake_open_stream)
        profile_id = setup_profile(api_client)
        stream_response = api_client.post(
            "/api/v1/chat/stream",
            json={
                "requestId": "req-12345678",
                "modelProfileId": profile_id,
                "messages": [{"role": "user", "content": "你好"}],
            },
        )
        assert stream_response.status_code == 200
        assert "event: reasoning.delta" in stream_response.text
        assert "推理" in stream_response.text
        assert "event: text.delta" in stream_response.text
        assert "正文" in stream_response.text

    def test_pre_stream_upstream_auth_error_is_http_error(self, api_client, monkeypatch):
        profile_id = setup_profile(api_client)
        from app.providers.llm.base import ProviderError

        async def failing_open_stream(config, url, headers, body, transport=None):
            raise ProviderError("UPSTREAM_AUTH_FAILED", "上游返回认证失败。", status_code=502)
            yield  # pragma: no cover - 使其成为异步生成器

        patch_open_stream(monkeypatch, failing_open_stream)
        response = api_client.post(
            "/api/v1/chat/stream",
            json={
                "requestId": "req-12345678",
                "modelProfileId": profile_id,
                "messages": [{"role": "user", "content": "你好"}],
            },
        )
        assert response.status_code == 502
        assert response.json()["code"] == "UPSTREAM_AUTH_FAILED"
