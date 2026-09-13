"""独立审查 1805397 的回归用例（MR-01~MR-14）。

这些用例移植自 _work/review-1805397 的核心/认证探针与前端行为断言，
按"断言期望行为"而不是"适配当前缺陷"编写。
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.core.config import Settings
from app.core.secrets import SecretStore, legacy_scoped_key, scoped_key
from app.main import create_app
from app.providers.llm.base import LLMConfig, LLMMessage, LLMRequest, ProviderError
from app.providers.llm.codex_oauth import (
    OP_COMPLETED,
    CodexLoginOperation,
    CodexOAuthService,
    CodexTokens,
)
from app.providers.llm.factory import create_provider
from app.providers.llm.github_copilot import GitHubCopilotProvider
from app.providers.llm.openai_codex import OpenAICodexProvider
from app.repositories.model_config_repository import ModelConfigRepository
from app.schemas.model_config import ModelConnection, ModelProtocol, now_utc
from app.services.model_auth import ModelAuthService
from app.services.model_config_service import CREDENTIAL_REPLACE, ModelConfigService
from app.services.model_readiness import callable_state
from tests.conftest import ALLOWED_ORIGINS, make_settings


def _connection(connection_id: str = "review", **overrides) -> ModelConnection:
    values = dict(
        id=connection_id,
        displayName="original",
        protocol=ModelProtocol.openai_chat,
        providerId="custom",
        apiFormat="openai_chat",
        baseUrl="https://example.invalid/v1",
        createdAt=now_utc(),
        updatedAt=now_utc(),
    )
    values.update(overrides)
    return ModelConnection(**values)


def _service(tmp_path: Path, store: SecretStore | None = None, api_key: str | None = "dummy-original"):
    repo = ModelConfigRepository(tmp_path / "model-config.json")
    secrets = store or SecretStore()
    service = ModelConfigService(repo, secrets)
    service.create_connection(_connection(), api_key)
    return repo, secrets, service


# --- MR-01 协议分派 --------------------------------------------------------


def _response_handler(paths: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "review"}, "finish_reason": "stop"}],
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "review"}]}],
                "status": "completed",
            },
        )

    return handler


def test_explicit_and_migrated_responses_both_use_responses_endpoint():
    """MR-01：显式 Responses 与迁移后的 Responses 都必须发到 /responses。"""
    paths: list[str] = []
    transport = httpx.MockTransport(_response_handler(paths))
    config = LLMConfig(
        protocol=ModelProtocol.openai_responses,
        baseUrl="https://example.invalid/v1",
        modelId="m",
        apiKey="dummy-key",
        providerId="custom",
        apiFormat="openai_responses",
    )
    request = LLMRequest(messages=[LLMMessage(role="user", content="test")], maxOutputTokens=8)
    asyncio.run(create_provider(ModelProtocol.openai_responses).complete(config, request, transport=transport))
    asyncio.run(
        create_provider(ModelProtocol.openai_responses, config).complete(config, request, transport=transport)
    )
    assert paths == ["/v1/responses", "/v1/responses"]


def test_openai_compat_provider_responses_format_is_not_downgraded_to_chat():
    """MR-01：openai_compat 供应商显式选择 Responses 时不能落到 Chat 适配器。"""
    config = LLMConfig(
        protocol=ModelProtocol.openai_responses,
        baseUrl="https://example.invalid/v1",
        modelId="gpt-5",
        apiKey="dummy-key",
        providerId="openai",
        apiFormat="openai_responses",
    )
    assert type(create_provider(ModelProtocol.openai_responses, config)).__name__ == "OpenAIResponsesProvider"


def test_migrated_responses_connection_keeps_protocol_after_repository_roundtrip(tmp_path: Path):
    """MR-01 兼容：v1 的 openai-responses 连接迁移后仍解析为 Responses。"""
    path = tmp_path / "model-config.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "revision": 1,
                "connections": [
                    {
                        "id": "r1",
                        "displayName": "responses",
                        "protocol": "openai-responses",
                        "baseUrl": "https://x/v1",
                        "extraHeaders": {},
                        "createdAt": "2026-01-01T00:00:00Z",
                        "updatedAt": "2026-01-01T00:00:00Z",
                    }
                ],
                "profiles": [],
                "defaultChatProfileId": None,
            }
        ),
        encoding="utf-8",
    )
    repo = ModelConfigRepository(path)
    connection = repo.get_connection("r1")
    assert connection.apiFormat.value == "openai_responses"
    config = LLMConfig(
        protocol=connection.protocol,
        baseUrl=connection.baseUrl,
        modelId="m",
        apiKey="k",
        providerId=connection.providerId,
        apiFormat=connection.apiFormat.value,
    )
    assert type(create_provider(connection.protocol, config)).__name__ == "OpenAIResponsesProvider"


# --- MR-02 本机免 Key ------------------------------------------------------


def test_local_provider_is_callable_without_key(tmp_path: Path):
    """MR-02：ollama 等本机免 Key 服务不得在联系上游前被拒绝。"""
    paths: list[str] = []
    transport = httpx.MockTransport(_response_handler(paths))
    config = LLMConfig(
        protocol=ModelProtocol.openai_chat,
        baseUrl="http://127.0.0.1:11434/v1",
        modelId="m",
        apiKey=None,
        providerId="ollama",
        apiFormat="openai_chat",
    )
    provider = create_provider(ModelProtocol.openai_chat, config)
    request = LLMRequest(messages=[LLMMessage(role="user", content="test")], maxOutputTokens=8)
    response = asyncio.run(provider.complete(config, request, transport=transport))
    assert response.text == "review"
    assert paths == ["/v1/chat/completions"]


def test_readiness_distinguishes_local_cloud_and_managed():
    """MR-02：可调用性统一判定——本机免 Key 可调用，云服务需凭证，受管需令牌。"""
    secrets = SecretStore()
    local = _connection("local", providerId="ollama", baseUrl="http://127.0.0.1:11434/v1")
    assert callable_state(local, secrets).ready is True

    cloud = _connection("cloud", providerId="deepseek", baseUrl="https://api.deepseek.com")
    assert callable_state(cloud, secrets).ready is False

    secrets.put("cloud", "k")
    assert callable_state(cloud, secrets).ready is True

    codex = _connection("codex", providerId="openai_codex", baseUrl="https://chatgpt.com/backend-api")
    assert callable_state(codex, secrets).ready is False
    secrets.put(scoped_key("codex-tokens", "codex"), CodexTokens("tok").to_json())
    assert callable_state(codex, secrets).ready is True


# --- MR-03 受管键可持久化 --------------------------------------------------


def test_managed_keys_are_writable_in_file_secret_store(tmp_path: Path):
    """MR-03：托管键必须能被文件型 SecretStore 写入并重启后读回。"""
    env_path = tmp_path / ".env"
    store = SecretStore(env_path)
    codex = CodexOAuthService(store)
    codex.store_tokens("testconn", CodexTokens("synthetic-placeholder", expires_at=time.time() + 3600))
    copilot = GitHubCopilotProvider(store)
    store.put(copilot.managed_key("testconn"), "synthetic-gh")

    # 重启：新实例从同一文件恢复
    reopened = SecretStore(env_path)
    assert CodexOAuthService(reopened).load_tokens("testconn").access_token == "synthetic-placeholder"
    assert reopened.resolve(scoped_key("copilot-token", "testconn")) == "synthetic-gh"
    text = env_path.read_text(encoding="utf-8")
    assert "codex-tokens__testconn" in text and ":" not in text.split("=")[0]


def test_legacy_colon_managed_keys_are_still_read(tmp_path: Path):
    """MR-03 兼容：历史冒号键仍可读、可清。"""
    store = SecretStore()
    store.put(legacy_scoped_key("codex-tokens", "c"), CodexTokens("legacy-tok").to_json())
    codex = CodexOAuthService(store)
    assert codex.load_tokens("c").access_token == "legacy-tok"
    codex.clear_tokens("c")
    assert codex.load_tokens("c") is None


# --- MR-04 并发 ------------------------------------------------------------


def test_concurrent_update_cannot_roll_back_other_requests_credential(tmp_path: Path):
    """MR-04：并发更新被串行化，冲突方不得回滚成功方的凭证。

    构造：A 已在写入凭证的临界区内挂起；此时 B 用同一 revision 发起更新。
    正确行为是 B 被阻塞直到 A 完成，然后因 revision 已前进而冲突——
    绝不允许 B 在 A 中途成功、更不允许 A 事后把 B 的凭证回滚。
    """
    inside = threading.Event()
    release = threading.Event()

    class PausingStore(SecretStore):
        def put(self, key_id, value):
            super().put(key_id, value)
            if value == "dummy-A":
                inside.set()
                if not release.wait(5):
                    raise RuntimeError("synchronization failed")

    repo, store, service = _service(tmp_path / "race", PausingStore())
    revision = repo.revision()
    outcome: dict[str, str] = {}

    def update(label: str, api_key: str):
        try:
            service.update_connection(
                "review", lambda c, name=label: setattr(c, "displayName", name),
                api_key=api_key, credential_action=CREDENTIAL_REPLACE, expected_revision=revision,
            )
            outcome[label] = "success"
        except AppError as exc:
            outcome[label] = exc.code

    a = threading.Thread(target=update, args=("A", "dummy-A"))
    a.start()
    assert inside.wait(5)

    b = threading.Thread(target=update, args=("B", "dummy-B"))
    b.start()
    # B 必须被同一临界区挡住，不能抢在 A 之前提交
    b.join(0.5)
    assert b.is_alive(), "B 应在 A 持锁期间被阻塞（写入未被串行化）"

    release.set()
    a.join(5)
    b.join(5)
    assert not a.is_alive() and not b.is_alive()

    assert outcome["A"] == "success"
    assert outcome["B"] == "REVISION_CONFLICT"
    # 最终一致：配置名与凭证都属于同一个成功请求 A
    assert repo.get_connection("review").displayName == "A"
    assert store.resolve("review") == "dummy-A"


# --- MR-05 删除补偿 --------------------------------------------------------


def test_delete_failure_keeps_both_sides_and_is_retryable(tmp_path: Path):
    """MR-05：凭证清理失败时不删配置，两侧一致且重试可成功。"""
    repo, store, service = _service(tmp_path / "delete")
    with patch.object(
        store, "delete", side_effect=AppError("temporary", code="CREDENTIAL_STORAGE_ERROR", status_code=500)
    ):
        with pytest.raises(AppError):
            service.delete_connection("review", repo.revision())
    assert [c.id for c in repo.list_connections()] == ["review"]
    assert store.has("review") is True

    service.delete_connection("review", repo.revision())
    assert repo.list_connections() == []
    assert store.has("review") is False


# --- MR-06 迁移备份 --------------------------------------------------------


def test_migration_backup_failure_blocks_write(tmp_path: Path):
    """MR-06：备份失败必须阻止升级写入，保留原文件与可重试状态。"""
    path = tmp_path / "model-config.json"
    original = json.dumps(
        {"schemaVersion": 1, "revision": 2, "connections": [], "profiles": [], "defaultChatProfileId": None}
    )
    path.write_text(original, encoding="utf-8")
    repo = ModelConfigRepository(path)
    with patch(
        "app.repositories.model_config_repository.shutil.copyfile",
        side_effect=PermissionError("injected backup failure"),
    ):
        with pytest.raises(AppError) as exc_info:
            repo.mutate(lambda _doc: None)
        assert exc_info.value.code == "CONFIG_BACKUP_FAILED"
    assert path.read_text(encoding="utf-8") == original
    assert not (tmp_path / "model-config.v1.backup.json").exists()

    # 恢复后重试可升级，且产生备份
    repo.mutate(lambda _doc: None)
    assert json.loads(path.read_text(encoding="utf-8"))["schemaVersion"] == 2
    assert (tmp_path / "model-config.v1.backup.json").exists()


# --- MR-09/10/11 认证生命周期 ---------------------------------------------


def test_codex_logout_during_exchange_prevents_relogin():
    """MR-09：退出发生在换票期间，迟到的换票结果不得复活登录。"""
    store = SecretStore()
    oauth = CodexOAuthService(store)
    started = asyncio.Event()
    release = asyncio.Event()

    async def exchange(_op, _code):
        started.set()
        await release.wait()
        return CodexTokens("synthetic-placeholder", expires_at=time.time() + 3600)

    oauth._exchange_code = exchange  # type: ignore[assignment]
    operation = CodexLoginOperation(
        operation_id="op", state="state", connection_id="testconn", code_verifier="verifier",
        callback_port=0, redirect_uri="http://127.0.0.1/auth/callback", authorize_url="https://invalid.example",
        started_at=time.time(), expires_at=time.time() + 300, operation_state=OP_COMPLETED,
        code="synthetic-code",
    )
    oauth._operations["testconn"] = operation

    async def scenario():
        task = asyncio.create_task(oauth._await_callback(operation))
        await started.wait()
        logout = await oauth.logout("testconn")
        release.set()
        await task
        return logout

    logout = asyncio.run(scenario())
    assert logout["status"]["connection"] == "disconnected"
    assert oauth.status("testconn")["connection"] == "disconnected"
    assert oauth.has_token("testconn") is False


def test_codex_cancel_during_exchange_prevents_relogin():
    """MR-09：取消授权同样作废在途换票。"""
    store = SecretStore()
    oauth = CodexOAuthService(store)
    started = asyncio.Event()
    release = asyncio.Event()

    async def exchange(_op, _code):
        started.set()
        await release.wait()
        return CodexTokens("synthetic-placeholder", expires_at=time.time() + 3600)

    oauth._exchange_code = exchange  # type: ignore[assignment]
    operation = CodexLoginOperation(
        operation_id="op2", state="state2", connection_id="conn2", code_verifier="verifier",
        callback_port=0, redirect_uri="http://127.0.0.1/auth/callback", authorize_url="https://invalid.example",
        started_at=time.time(), expires_at=time.time() + 300, operation_state=OP_COMPLETED,
        code="synthetic-code",
    )
    oauth._operations["conn2"] = operation

    async def scenario():
        task = asyncio.create_task(oauth._await_callback(operation))
        await started.wait()
        await oauth.cancel_login("conn2")
        release.set()
        await task

    asyncio.run(scenario())
    assert oauth.has_token("conn2") is False


def test_copilot_logout_clears_the_connection_credential():
    """MR-10：Copilot 退出必须清掉 UI 存在 connectionId 上的令牌，而非只清缓存展示。"""
    store = SecretStore()
    store.put("testconn", "synthetic-github-token")
    repo = type("R", (), {"get_connection": lambda self, _id: _connection(_id, providerId="github_copilot")})()
    auth = ModelAuthService(repo, store)
    result = asyncio.run(auth.logout("testconn"))
    assert result["ok"] is True
    assert store.has("testconn") is False
    assert result["status"]["connection"] == "disconnected"


def test_codex_expired_token_is_not_used_and_requires_reauth():
    """MR-11：过期令牌不得继续显示 connected 或用于请求头。"""
    store = SecretStore()
    oauth = CodexOAuthService(store)
    oauth.store_tokens(
        "testconn",
        CodexTokens("synthetic", refresh_token="synthetic-refresh", expires_at=time.time() - 100),
    )
    assert oauth.status("testconn")["connection"] == "error"
    assert oauth.status("testconn")["errorCode"] == "AUTH_EXPIRED"
    # 无法续期（无网络/刷新失败）时，取令牌返回 None，provider 报 AUTH_EXPIRED
    oauth._post_refresh = lambda _rt: None  # type: ignore[assignment]
    provider = OpenAICodexProvider(oauth)
    config = LLMConfig(
        protocol=ModelProtocol.openai_responses,
        baseUrl="https://chatgpt.com/backend-api",
        modelId="m",
        apiKey=None,
        connectionId="testconn",
        providerId="openai_codex",
    )
    with pytest.raises(ProviderError) as exc_info:
        asyncio.run(provider._build_headers(config))
    assert exc_info.value.code == "AUTH_EXPIRED"


def test_codex_expired_token_refreshes_when_refresh_succeeds():
    """MR-11：有 refresh_token 时应续期并继续可用。"""
    store = SecretStore()
    oauth = CodexOAuthService(store)
    oauth.store_tokens(
        "testconn",
        CodexTokens("old", refresh_token="rt", expires_at=time.time() - 100),
    )
    oauth._post_refresh = lambda _rt: {  # type: ignore[assignment]
        "access_token": "fresh",
        "refresh_token": "rt2",
        "expires_in": 3600,
    }
    token = asyncio.run(oauth.get_access_token("testconn"))
    assert token == "fresh"
    assert oauth.status("testconn")["connection"] == "connected"


# --- 认证端点：文件型存储下的可用性 ---------------------------------------


def test_managed_auth_keys_survive_file_store_in_http_flow(tmp_path: Path):
    """MR-03 端到端：文件型凭证存储下，Codex 令牌写入与状态读取都成功。"""
    env_path = tmp_path / ".env"
    secrets = SecretStore(env_path)
    settings = Settings(
        host="127.0.0.1",
        port=8001,
        allowed_origins=ALLOWED_ORIGINS,
        env="test",
        data_dir=tmp_path / "data",
        credentials_file=env_path,
    )
    app = create_app(settings, secret_store=secrets)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        created = client.post(
            "/api/v1/model-connections",
            json={"displayName": "cx", "providerId": "openai_codex"},
        ).json()
        service = client.app.state.model_auth_service  # type: ignore[attr-defined]
        service.codex.store_tokens(created["id"], CodexTokens("synthetic", expires_at=time.time() + 3600))
        status = client.get(f"/api/v1/model-connections/{created['id']}/auth").json()
        assert status["connection"] == "connected"
    # 重启后可读回
    assert CodexOAuthService(SecretStore(env_path)).load_tokens(created["id"]).access_token == "synthetic"


def test_connection_view_exposes_callable_flag(client):
    """MR-02 端到端：连接视图暴露 callable，本机免 Key 为 true。"""
    local = client.post(
        "/api/v1/model-connections",
        json={"displayName": "ollama", "providerId": "ollama"},
    ).json()
    assert local["callable"] is True
    assert local["hasCredential"] is False

    cloud = client.post(
        "/api/v1/model-connections",
        json={"displayName": "ds", "providerId": "deepseek"},
    ).json()
    assert cloud["callable"] is False
    assert cloud["hasCredential"] is False
