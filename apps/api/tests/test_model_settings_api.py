"""模型设置接口测试：CRUD、凭证脱敏、revision 冲突、连接测试结果。"""

from __future__ import annotations

import json
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

UPSTREAM_OK = {
    "choices": [{"message": {"content": "连接正常。"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 5, "completion_tokens": 3},
}


@pytest.fixture()
def api_client(tmp_path: Path) -> TestClient:
    with TestClient(
        create_app(make_settings(tmp_path / "data")), base_url="http://127.0.0.1:8001"
    ) as test_client:
        return test_client


def create_connection(client: TestClient, **overrides) -> dict:
    response = client.post("/api/v1/model-connections", json={**CONNECTION_PAYLOAD, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def create_profile(client: TestClient, connection_id: str, **overrides) -> dict:
    response = client.post(
        "/api/v1/model-profiles",
        json={
            "connectionId": connection_id,
            "displayName": "测试模型",
            "modelId": "test-model",
            "supportedParams": ["temperature"],
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def current_revision(client: TestClient) -> int:
    return client.app.state.model_config_repo.revision()


class TestConnections:
    def test_create_masks_credential_and_never_persists_it(self, api_client, tmp_path):
        connection = create_connection(api_client)
        assert connection["hasCredential"] is True
        assert connection["credentialScope"] == "process"
        serialized = json.dumps(connection)
        assert "apiKey" not in serialized
        assert "sk-secret-123" not in serialized
        config_file = (tmp_path / "data" / "model-config.json").read_text(encoding="utf-8")
        assert "sk-secret-123" not in config_file

    def test_list_and_update(self, api_client):
        connection = create_connection(api_client)
        items = api_client.get("/api/v1/model-connections").json()
        assert [c["id"] for c in items] == [connection["id"]]

        updated = api_client.put(
            f"/api/v1/model-connections/{connection['id']}",
            json={"displayName": "改名", "expectedRevision": current_revision(api_client)},
        )
        assert updated.status_code == 200
        assert updated.json()["displayName"] == "改名"

    def test_update_with_stale_revision_conflicts(self, api_client):
        connection = create_connection(api_client)
        response = api_client.put(
            f"/api/v1/model-connections/{connection['id']}",
            json={"displayName": "过期更新", "expectedRevision": current_revision(api_client) - 1},
        )
        assert response.status_code == 409
        assert response.json()["code"] == "REVISION_CONFLICT"

    def test_delete_referenced_connection_conflicts(self, api_client):
        connection = create_connection(api_client)
        create_profile(api_client, connection["id"])
        response = api_client.delete(f"/api/v1/model-connections/{connection['id']}")
        assert response.status_code == 409

    def test_local_http_base_url_allowed_but_public_http_rejected(self, api_client):
        ok = create_connection(
            api_client, displayName="本机模型", baseUrl="http://127.0.0.1:11434/v1"
        )
        assert ok["baseUrl"] == "http://127.0.0.1:11434/v1"
        bad = api_client.post(
            "/api/v1/model-connections",
            json={**CONNECTION_PAYLOAD, "displayName": "明文", "baseUrl": "http://api.example.com/v1"},
        )
        assert bad.status_code == 422


class TestProfiles:
    def test_create_and_masked_connection_summary(self, api_client):
        connection = create_connection(api_client)
        profile = create_profile(api_client, connection["id"])
        assert profile["connection"]["displayName"] == "测试供应商"
        assert profile["connection"]["hasCredential"] is True
        assert profile["capabilities"]["chat"] == "unknown"

    def test_delete_profile_then_connection(self, api_client):
        connection = create_connection(api_client)
        profile = create_profile(api_client, connection["id"])
        assert api_client.delete(f"/api/v1/model-profiles/{profile['id']}").status_code == 204
        assert api_client.delete(f"/api/v1/model-connections/{connection['id']}").status_code == 204
        assert api_client.get("/api/v1/model-connections").json() == []


class TestProfileTestEndpoint:
    def test_without_credential_reports_not_configured(self, api_client):
        connection = create_connection(api_client, apiKey=None)
        profile = create_profile(api_client, connection["id"])
        response = api_client.post(f"/api/v1/model-profiles/{profile['id']}/test", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "MODEL_NOT_CONFIGURED"

    def test_param_not_declared_by_profile_rejected(self, api_client):
        connection = create_connection(api_client, apiKey=None)
        profile = create_profile(api_client, connection["id"], supportedParams=[])
        response = api_client.post(
            f"/api/v1/model-profiles/{profile['id']}/test",
            json={"params": {"temperature": 0.5}},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "UNSUPPORTED_PARAMETER"

    def test_successful_test_verifies_capability(self, api_client, monkeypatch):
        async def fake_post_json(config, url, headers, body, transport=None):
            assert config.apiKey == "sk-secret-123"
            assert "sk-secret-123" not in json.dumps(headers).replace(config.apiKey, "")
            return UPSTREAM_OK

        monkeypatch.setattr("app.providers.llm.openai_chat.post_json", fake_post_json)
        connection = create_connection(api_client)
        profile = create_profile(api_client, connection["id"])
        response = api_client.post(f"/api/v1/model-profiles/{profile['id']}/test", json={})

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["text"] == "连接正常。"
        assert body["finishReason"] == "stop"
        assert body["usage"]["outputTokens"] == 3
        assert body["latencyMs"] >= 0
        profiles = api_client.get("/api/v1/model-profiles").json()
        assert profiles[0]["capabilities"]["chat"] == "verified"

    def test_upstream_auth_failure_reported_as_test_result(self, api_client, monkeypatch):
        from app.providers.llm.base import ProviderError

        async def fake_post_json(config, url, headers, body, transport=None):
            raise ProviderError("UPSTREAM_AUTH_FAILED", "上游返回认证失败，请检查 API Key。")

        monkeypatch.setattr("app.providers.llm.openai_chat.post_json", fake_post_json)
        connection = create_connection(api_client)
        profile = create_profile(api_client, connection["id"])
        response = api_client.post(f"/api/v1/model-profiles/{profile['id']}/test", json={})

        body = response.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "UPSTREAM_AUTH_FAILED"
        profiles = api_client.get("/api/v1/model-profiles").json()
        assert profiles[0]["capabilities"]["chat"] == "unknown"
