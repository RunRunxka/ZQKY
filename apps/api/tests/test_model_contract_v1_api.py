"""contract-v1 HTTP 层：供应商目录、迁移、凭证补偿、认证状态机与发现来源。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.secrets import SecretStore
from app.main import create_app
from app.repositories.model_config_repository import ModelConfigRepository, migrate_document
from app.services.model_config_service import (
    CREDENTIAL_CLEAR,
    CREDENTIAL_REPLACE,
    ModelConfigService,
)
from tests.conftest import ALLOWED_ORIGINS


def _make_client(tmp_path: Path, **kwargs) -> TestClient:
    settings = Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=ALLOWED_ORIGINS,
        env="test",
        data_dir=tmp_path / "data",
    )
    return TestClient(create_app(settings, **kwargs), base_url="http://127.0.0.1:8001")


@pytest.fixture()
def client(tmp_path: Path):
    with _make_client(tmp_path) as test_client:
        yield test_client


# --- 供应商目录 -----------------------------------------------------------


def test_providers_endpoint_lists_38_with_legacy_separated(client):
    payload = client.get("/api/v1/model-providers").json()
    assert len(payload["providers"]) == 36
    assert len(payload["legacy"]) == 2
    ids = {entry["providerId"] for entry in payload["providers"]}
    assert "azure_openai" in ids and "deepseek" in ids and "ollama" in ids
    assert {entry["providerId"] for entry in payload["legacy"]} == {
        "custom_anthropic",
        "minimax_anthropic",
    }
    # D15：不下发原始 backend
    assert all("backend" not in entry for entry in payload["providers"])
    # 前端所需的产物字段齐备
    azure = next(entry for entry in payload["providers"] if entry["providerId"] == "azure_openai")
    assert azure["mode"] == "direct"
    assert azure["apiFormats"] == []
    assert azure["authMode"] == "api_key"


# --- 迁移 -----------------------------------------------------------------


def test_migrate_v1_document_remaps_protocol_without_guessing_vendor():
    raw = {
        "schemaVersion": 1,
        "revision": 5,
        "connections": [
            {"id": "a", "displayName": "chat", "protocol": "openai-chat", "baseUrl": "https://x/v1"},
            {"id": "b", "displayName": "resp", "protocol": "openai-responses", "baseUrl": "https://y/v1"},
            {"id": "c", "displayName": "anth", "protocol": "anthropic-messages", "baseUrl": "https://z/v1"},
        ],
        "profiles": [],
        "defaultChatProfileId": None,
    }
    migrated, changed = migrate_document(raw)
    assert changed is True
    assert migrated["schemaVersion"] == 2
    by_id = {c["id"]: c for c in migrated["connections"]}
    # 不猜供应商：一律映射为 custom，且 URL 原样
    assert by_id["a"]["providerId"] == "custom" and by_id["a"]["apiFormat"] == "openai_chat"
    assert by_id["b"]["apiFormat"] == "openai_responses"
    assert by_id["c"]["apiFormat"] == "anthropic"
    assert by_id["a"]["baseUrl"] == "https://x/v1"


def test_reading_v1_file_does_not_overwrite_until_first_write(tmp_path: Path):
    path = tmp_path / "model-config.json"
    original = {
        "schemaVersion": 1,
        "revision": 3,
        "connections": [
            {"id": "a", "displayName": "legacy", "protocol": "openai-chat", "baseUrl": "https://x/v1",
             "extraHeaders": {}, "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"}
        ],
        "profiles": [],
        "defaultChatProfileId": None,
    }
    path.write_text(json.dumps(original), encoding="utf-8")
    repo = ModelConfigRepository(path)
    # 只读：文件仍是 v1 原文
    assert repo.list_connections()[0].providerId == "custom"
    assert json.loads(path.read_text(encoding="utf-8"))["schemaVersion"] == 1

    # 首次写入后升级为 v2，并保留备份
    repo.create_profile(
        __import__("app.schemas.model_config", fromlist=["ModelProfile"]).ModelProfile(
            id="p1", connectionId="a", displayName="m", modelId="m1",
            capabilities={"chat": "unknown"},
            createdAt=__import__("app.schemas.model_config", fromlist=["now_utc"]).now_utc(),
            updatedAt=__import__("app.schemas.model_config", fromlist=["now_utc"]).now_utc(),
        )
    )
    assert json.loads(path.read_text(encoding="utf-8"))["schemaVersion"] == 2
    assert (tmp_path / "model-config.v1.backup.json").exists()


def test_v1_connections_keep_ids_and_default_reference(tmp_path: Path):
    path = tmp_path / "model-config.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "revision": 7,
                "connections": [
                    {"id": "keep-me", "displayName": "legacy", "protocol": "openai-chat",
                     "baseUrl": "https://x/v1", "extraHeaders": {},
                     "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"}
                ],
                "profiles": [
                    {"id": "prof-keep", "connectionId": "keep-me", "displayName": "m",
                     "modelId": "m1", "capabilities": {"chat": "unknown"},
                     "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z"}
                ],
                "defaultChatProfileId": "prof-keep",
            }
        ),
        encoding="utf-8",
    )
    repo = ModelConfigRepository(path)
    assert repo.get_connection("keep-me").id == "keep-me"
    assert repo.get_profile("prof-keep").id == "prof-keep"
    assert repo.revision() == 7
    assert repo.with_document(lambda d: d.defaultChatProfileId) == "prof-keep"


# --- 凭证补偿（R-01 / R-08）----------------------------------------------


def test_create_rolls_back_credential_when_config_save_fails(tmp_path: Path):
    secrets = SecretStore()
    repo = ModelConfigRepository(tmp_path / "model-config.json")
    service = ModelConfigService(repo, secrets)

    def boom(_connection):
        raise AppError("写配置失败", code="CREDENTIAL_STORAGE_ERROR", status_code=500)

    repo.create_connection = boom  # type: ignore[assignment]
    from app.schemas.model_config import ModelConnection, ModelProtocol, now_utc

    connection = ModelConnection(
        id="c1", displayName="x", providerId="custom", protocol=ModelProtocol.openai_chat,
        baseUrl="https://x/v1", createdAt=now_utc(), updatedAt=now_utc(),
    )
    with pytest.raises(AppError):
        service.create_connection(connection, "new-key")
    assert secrets.has("c1") is False


def test_update_rolls_back_credential_when_config_save_fails(tmp_path: Path):
    """配置落盘失败时，凭证必须回滚到旧值（R-01 / MR-04）。"""
    secrets = SecretStore()
    repo = ModelConfigRepository(tmp_path / "model-config.json")
    service = ModelConfigService(repo, secrets)
    from app.schemas.model_config import ModelConnection, ModelProtocol, now_utc

    connection = ModelConnection(
        id="c1", displayName="x", providerId="custom", protocol=ModelProtocol.openai_chat,
        baseUrl="https://x/v1", createdAt=now_utc(), updatedAt=now_utc(),
    )
    service.create_connection(connection, "old-key")

    with patch.object(repo, "_save", side_effect=AppError("写配置失败", code="CREDENTIAL_STORAGE_ERROR", status_code=500)):
        with pytest.raises(AppError):
            service.update_connection(
                "c1", lambda c: None, api_key="new-key", credential_action=CREDENTIAL_REPLACE,
                expected_revision=None,
            )
    # Key 成功写入但配置失败 → 必须回滚为旧值
    assert secrets.resolve("c1") == "old-key"


def test_update_rolls_back_to_absent_when_no_previous_credential(tmp_path: Path):
    secrets = SecretStore()
    repo = ModelConfigRepository(tmp_path / "model-config.json")
    service = ModelConfigService(repo, secrets)
    from app.schemas.model_config import ModelConnection, ModelProtocol, now_utc

    connection = ModelConnection(
        id="c1", displayName="x", providerId="custom", protocol=ModelProtocol.openai_chat,
        baseUrl="https://x/v1", createdAt=now_utc(), updatedAt=now_utc(),
    )
    service.create_connection(connection, None)

    with patch.object(repo, "_save", side_effect=AppError("写配置失败", code="CREDENTIAL_STORAGE_ERROR", status_code=500)):
        with pytest.raises(AppError):
            service.update_connection(
                "c1", lambda c: None, api_key="new-key", credential_action=CREDENTIAL_REPLACE,
                expected_revision=None,
            )
    assert secrets.has("c1") is False


def test_credential_clear_is_independent_from_empty_key(client):
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "c", "providerId": "deepseek", "apiKey": "secret-key"},
    ).json()
    assert created["hasCredential"] is True

    # 空 apiKey + keep：凭证保持
    kept = client.put(f"/api/v1/model-connections/{created['id']}", json={"apiKey": ""}).json()
    assert kept["hasCredential"] is True

    # 显式 clear：独立清除
    cleared = client.put(
        f"/api/v1/model-connections/{created['id']}", json={"credentialAction": "clear"}
    ).json()
    assert cleared["hasCredential"] is False


def test_delete_connection_reports_credential_cleanup_failure(tmp_path: Path):
    """凭证清理失败时整体不删（MR-05）：连接与凭证都保持原状，可安全重试。

    旧实现先删 JSON 再删凭证，失败会留下孤儿凭证且重试得到 NOT_FOUND；
    现行为是删除前先清凭证，失败即中止，两侧一致。
    """
    secrets = SecretStore()
    repo = ModelConfigRepository(tmp_path / "model-config.json")
    service = ModelConfigService(repo, secrets)
    from app.schemas.model_config import ModelConnection, ModelProtocol, now_utc

    connection = ModelConnection(
        id="c1", displayName="x", providerId="custom", protocol=ModelProtocol.openai_chat,
        baseUrl="https://x/v1", createdAt=now_utc(), updatedAt=now_utc(),
    )
    service.create_connection(connection, "k")

    def boom(_key):
        raise AppError("删除失败", code="CREDENTIAL_STORAGE_ERROR", status_code=500)

    secrets.delete = boom  # type: ignore[assignment]
    with pytest.raises(AppError):
        service.delete_connection("c1", repo.revision())
    # 两侧都还在：连接未删、凭证仍在，没有孤儿
    assert [c.id for c in repo.list_connections()] == ["c1"]
    assert secrets.has("c1") is True

    # 恢复后重试可正常删除，不需要 NOT_FOUND 兜底
    del secrets.delete
    service.delete_connection("c1", repo.revision())
    assert repo.list_connections() == []
    assert secrets.has("c1") is False


# --- 认证状态机 -----------------------------------------------------------


def test_auth_status_for_api_key_connection(client):
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "d", "providerId": "deepseek", "apiKey": "k"},
    ).json()
    status = client.get(f"/api/v1/model-connections/{created['id']}/auth").json()
    assert status["connection"] == "connected"
    assert status["authMode"] == "api_key"


def test_auth_status_for_copilot_without_token_is_disconnected(client):
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "gh", "providerId": "github_copilot", "baseUrl": "https://api.githubcopilot.com"},
    ).json()
    status = client.get(f"/api/v1/model-connections/{created['id']}/auth").json()
    assert status["connection"] == "disconnected"
    assert status["authMode"] == "oauth"
    assert status["available"] is False
    assert "GitHub" in status["unavailableReason"]


def test_auth_status_for_codex_without_app_reports_unavailable(client):
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "cx", "providerId": "openai_codex"},
    ).json()
    status = client.get(f"/api/v1/model-connections/{created['id']}/auth").json()
    assert status["connection"] == "disconnected"
    assert status["available"] is False
    assert "OAuth" in status["unavailableReason"]


def test_auth_start_for_codex_without_app_returns_no_forged_url(client):
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "cx2", "providerId": "openai_codex"},
    ).json()
    started = client.post(f"/api/v1/model-connections/{created['id']}/auth/start").json()
    assert started["ok"] is False
    assert started["errorCode"] == "OAUTH_APP_NOT_CONFIGURED"
    assert "authorizeUrl" not in started


def test_auth_start_rejected_for_api_key_provider(client):
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "api", "providerId": "deepseek", "apiKey": "k"},
    ).json()
    started = client.post(f"/api/v1/model-connections/{created['id']}/auth/start").json()
    assert started["ok"] is False
    assert started["errorCode"] == "UNSUPPORTED_OPERATION"


# --- 发现来源（D12）-------------------------------------------------------


def test_discovery_for_codex_is_manual_source(client):
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "cx3", "providerId": "openai_codex"},
    ).json()
    payload = client.get(f"/api/v1/model-connections/{created['id']}/models").json()
    assert payload["source"] == "manual"
    assert payload["models"] == []


def test_discovery_for_codebuddy_is_catalog_source(client, monkeypatch):
    # CodeBuddy 无 API Key 也能拿到有来源的目录（catalog），并标注非实时
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "cb", "providerId": "codebuddy", "apiKey": "cb-key"},
    ).json()
    payload = client.get(f"/api/v1/model-connections/{created['id']}/models").json()
    assert payload["source"].startswith("catalog:")
    assert payload["models"] == [{"id": "default"}]


def test_discovery_requires_credential_for_cloud(client):
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "ds", "providerId": "deepseek", "baseUrl": "https://api.deepseek.com"},
    ).json()
    response = client.get(f"/api/v1/model-connections/{created['id']}/models")
    assert response.status_code == 400
    assert response.json()["code"] == "MODEL_NOT_CONFIGURED"


# --- 供应商身份校验 -------------------------------------------------------


def test_unknown_provider_is_rejected(client):
    response = client.post(
        "/api/v1/model-connections",
        json={"displayName": "x", "providerId": "not-real", "baseUrl": "https://x/v1"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "UNSUPPORTED_PROVIDER"


def test_unsupported_api_format_is_rejected(client):
    response = client.post(
        "/api/v1/model-connections",
        json={
            "displayName": "azure",
            "providerId": "azure_openai",
            "apiFormat": "openai_chat",
            "baseUrl": "https://x.openai.azure.com",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "UNSUPPORTED_API_FORMAT"


def test_provider_default_base_url_used_when_omitted(client):
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "deepseek", "providerId": "deepseek", "apiKey": "k"},
    ).json()
    assert created["baseUrl"] == ""
    assert created["resolvedBaseUrl"] == "https://api.deepseek.com"


def test_explicit_custom_base_url_preserved(client):
    created = client.post(
        "/api/v1/model-connections",
        json={"displayName": "proxy", "providerId": "openai", "baseUrl": "https://my-proxy.local/v1"},
    ).json()
    assert created["baseUrl"] == "https://my-proxy.local/v1"
    assert created["resolvedBaseUrl"] == "https://my-proxy.local/v1"


# --- 推理字段校验（D6）----------------------------------------------------


def test_profile_reasoning_fields_roundtrip(client):
    connection = client.post(
        "/api/v1/model-connections",
        json={"displayName": "ds", "providerId": "deepseek", "apiKey": "k"},
    ).json()
    profile = client.post(
        "/api/v1/model-profiles",
        json={
            "connectionId": connection["id"],
            "displayName": "reasoner",
            "modelId": "deepseek-reasoner",
            "reasoningEnabled": True,
            "reasoningEffort": "low",
        },
    ).json()
    assert profile["reasoningEnabled"] is True
    assert profile["reasoningEffort"] == "low"
    # reasoningStyle 是只读派生，不落库
    assert profile["reasoningStyle"] == "thinking_type"


def test_reasoning_disabled_with_effort_is_rejected(client):
    connection = client.post(
        "/api/v1/model-connections",
        json={"displayName": "ds2", "providerId": "deepseek", "apiKey": "k"},
    ).json()
    response = client.post(
        "/api/v1/model-profiles",
        json={
            "connectionId": connection["id"],
            "displayName": "conflict",
            "modelId": "m",
            "reasoningEnabled": False,
            "reasoningEffort": "high",
        },
    )
    assert response.status_code == 422


def test_invalid_reasoning_effort_is_rejected(client):
    connection = client.post(
        "/api/v1/model-connections",
        json={"displayName": "ds3", "providerId": "deepseek", "apiKey": "k"},
    ).json()
    response = client.post(
        "/api/v1/model-profiles",
        json={"connectionId": connection["id"], "displayName": "bad", "modelId": "m", "reasoningEffort": "ultra"},
    )
    assert response.status_code == 422


# --- 不串连接 -------------------------------------------------------------


def test_connections_do_not_share_credentials(client):
    a = client.post(
        "/api/v1/model-connections", json={"displayName": "A", "providerId": "deepseek", "apiKey": "key-a"}
    ).json()
    b = client.post(
        "/api/v1/model-connections", json={"displayName": "B", "providerId": "deepseek"}
    ).json()
    assert a["hasCredential"] is True
    assert b["hasCredential"] is False
    listing = {c["id"]: c for c in client.get("/api/v1/model-connections").json()}
    assert listing[a["id"]]["hasCredential"] is True
    assert listing[b["id"]]["hasCredential"] is False
