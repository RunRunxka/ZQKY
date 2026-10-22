"""Agent 模型工厂（services/agent/model.py）正确行为回归。

覆盖红线与协议映射，全部不触网、不读写正式数据目录：

- 凭证红线：Key 只经 SecretStore 显式注入；本地免 Key 连接用占位符；进程环境出现
  ``OPENAI_API_KEY``/``ANTHROPIC_API_KEY`` 即 ``PROVIDER_ENV_FORBIDDEN``（不静默放行）；
- 协议映射：anthropic → ChatAnthropic；openai_responses → ChatOpenAI(use_responses_api)；
  其余 OpenAI 兼容 → ChatOpenAI；网关/自定义走显式 base_url；
- 闸门：受管认证（Codex/Copilot/CodeBuddy）→ ``AGENT_MODEL_UNSUPPORTED``；profile 用途不符
  → ``MODEL_PURPOSE_MISMATCH``；连接不可调用 → ``MODEL_NOT_CONFIGURED``；profile 缺失 → 404。
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from app.core.exceptions import AppError
from app.core.secrets import SecretStore
from app.schemas.model_config import (
    ApiFormat,
    ModelConnection,
    ModelProfile,
    ModelProtocol,
)
from app.services.agent.model import (
    _LOCAL_PLACEHOLDER_KEY,
    assert_no_provider_env_keys,
    resolve_agent_chat_model,
)


def _conn(
    connection_id: str = "conn-1",
    *,
    protocol: ModelProtocol = ModelProtocol.openai_chat,
    base_url: str = "https://api.example.com/v1",
    provider_id: str | None = None,
    api_format: ApiFormat = ApiFormat.auto,
    extra_headers: dict[str, str] | None = None,
) -> ModelConnection:
    now = datetime.now(UTC)
    return ModelConnection(
        id=connection_id,
        displayName="测试连接",
        protocol=protocol,
        baseUrl=base_url,
        extraHeaders=extra_headers or {},
        providerId=provider_id,
        apiFormat=api_format,
        createdAt=now,
        updatedAt=now,
    )


def _profile(
    profile_id: str = "prof-1",
    *,
    connection_id: str = "conn-1",
    model_id: str = "test-model",
    purpose: str | None = "chat",
    max_output_tokens: int | None = 2048,
    params: dict[str, float] | None = None,
) -> ModelProfile:
    now = datetime.now(UTC)
    return ModelProfile(
        id=profile_id,
        connectionId=connection_id,
        displayName="测试模型",
        modelId=model_id,
        purpose=purpose,
        maxOutputTokens=max_output_tokens,
        params=params or {},
        createdAt=now,
        updatedAt=now,
    )


class _FakeRepo:
    """最小内存仓储：只实现 get_profile/get_connection。"""

    def __init__(self, connection: ModelConnection, profile: ModelProfile) -> None:
        self._connection = connection
        self._profile = profile

    def get_profile(self, profile_id: str) -> ModelProfile:
        if profile_id != self._profile.id:
            raise AppError("模型配置不存在。", code="NOT_FOUND", status_code=404)
        return self._profile

    def get_connection(self, connection_id: str) -> ModelConnection:
        if connection_id != self._connection.id:
            raise AppError("模型连接不存在。", code="NOT_FOUND", status_code=404)
        return self._connection


def _secrets(pairs: dict[str, str] | None = None) -> SecretStore:
    store = SecretStore()
    for key, value in (pairs or {}).items():
        store.put(key, value)
    return store


@pytest.fixture(autouse=True)
def _clean_provider_env(monkeypatch: pytest.MonkeyPatch):
    """每个用例前清掉官方包可能回退读取的环境变量，用例间互不污染。"""
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    yield


class TestEnvGuard:
    def test_openai_env_leak_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-leak")
        with pytest.raises(AppError) as excinfo:
            assert_no_provider_env_keys()
        assert excinfo.value.code == "PROVIDER_ENV_FORBIDDEN"
        assert "OPENAI_API_KEY" in str(excinfo.value)

    def test_anthropic_env_leak_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-leak")
        with pytest.raises(AppError) as excinfo:
            assert_no_provider_env_keys()
        assert excinfo.value.code == "PROVIDER_ENV_FORBIDDEN"

    def test_clean_env_passes(self) -> None:
        assert_no_provider_env_keys()  # 不抛错

    def test_resolve_rejects_when_env_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-leak")
        repo = _FakeRepo(_conn(), _profile())
        with pytest.raises(AppError) as excinfo:
            resolve_agent_chat_model(repo, _secrets({"conn-1": "sk-real"}), "prof-1")
        assert excinfo.value.code == "PROVIDER_ENV_FORBIDDEN"


class TestProtocolMapping:
    def test_openai_chat_default(self) -> None:
        repo = _FakeRepo(_conn(api_format=ApiFormat.auto), _profile())
        handle = resolve_agent_chat_model(repo, _secrets({"conn-1": "sk-real"}), "prof-1")
        assert isinstance(handle.chat_model, ChatOpenAI)
        assert handle.chat_model.openai_api_key.get_secret_value() == "sk-real"  # type: ignore[union-attr]
        assert handle.profile_id == "prof-1"
        assert handle.model_id == "test-model"

    def test_openai_compatible_stream_usage_enabled(self) -> None:
        """自定义/兼容端点默认 base_url 下 LangChain 不自动开 stream_usage，必须显式打开。"""
        repo = _FakeRepo(_conn(provider_id="custom"), _profile())
        handle = resolve_agent_chat_model(repo, _secrets({"conn-1": "sk-real"}), "prof-1")
        assert isinstance(handle.chat_model, ChatOpenAI)
        assert handle.chat_model.stream_usage is True

    def test_openai_responses(self) -> None:
        repo = _FakeRepo(
            _conn(protocol=ModelProtocol.openai_responses, api_format=ApiFormat.openai_responses),
            _profile(),
        )
        handle = resolve_agent_chat_model(repo, _secrets({"conn-1": "sk-real"}), "prof-1")
        assert isinstance(handle.chat_model, ChatOpenAI)

    def test_anthropic(self) -> None:
        repo = _FakeRepo(
            _conn(
                protocol=ModelProtocol.anthropic_messages,
                api_format=ApiFormat.anthropic,
                base_url="https://api.anthropic.com",
            ),
            _profile(model_id="claude-test"),
        )
        handle = resolve_agent_chat_model(repo, _secrets({"conn-1": "sk-ant"}), "prof-1")
        assert isinstance(handle.chat_model, ChatAnthropic)
        assert handle.chat_model.anthropic_api_key.get_secret_value() == "sk-ant"  # type: ignore[union-attr]

    def test_gateway_openai_compat_uses_explicit_base_url(self) -> None:
        """网关类（OpenRouter/SiliconFlow 等 OpenAI 兼容）走显式 base_url，不读默认地址。"""
        repo = _FakeRepo(
            _conn(base_url="https://openrouter.example/api/v1"),
            _profile(),
        )
        handle = resolve_agent_chat_model(repo, _secrets({"conn-1": "sk-gw"}), "prof-1")
        assert isinstance(handle.chat_model, ChatOpenAI)
        assert "openrouter.example" in str(handle.chat_model.openai_api_base)

    def test_extra_headers_forwarded(self) -> None:
        repo = _FakeRepo(
            _conn(extra_headers={"X-Custom": "v1"}),
            _profile(),
        )
        handle = resolve_agent_chat_model(repo, _secrets({"conn-1": "sk-real"}), "prof-1")
        headers = getattr(handle.chat_model, "default_headers", None) or {}
        assert headers.get("X-Custom") == "v1"


class TestLocalNoKey:
    def test_local_connection_uses_placeholder_key(self) -> None:
        """本地免 Key 连接（ollama）：无凭证也能构造，且用占位符而非读环境变量。"""
        repo = _FakeRepo(
            _conn(base_url="http://127.0.0.1:11434/v1", provider_id="ollama"),
            _profile(),
        )
        handle = resolve_agent_chat_model(repo, _secrets(), "prof-1")
        assert isinstance(handle.chat_model, ChatOpenAI)
        assert handle.chat_model.openai_api_key.get_secret_value() == _LOCAL_PLACEHOLDER_KEY  # type: ignore[union-attr]


class TestGates:
    def test_oauth_codex_rejected(self) -> None:
        repo = _FakeRepo(
            _conn(provider_id="openai_codex", base_url="https://chatgpt.com/backend-api"),
            _profile(),
        )
        with pytest.raises(AppError) as excinfo:
            resolve_agent_chat_model(repo, _secrets(), "prof-1")
        assert excinfo.value.code == "AGENT_MODEL_UNSUPPORTED"

    def test_oauth_copilot_rejected(self) -> None:
        repo = _FakeRepo(
            _conn(provider_id="github_copilot", base_url="https://api.githubcopilot.com"),
            _profile(),
        )
        with pytest.raises(AppError) as excinfo:
            resolve_agent_chat_model(repo, _secrets(), "prof-1")
        assert excinfo.value.code == "AGENT_MODEL_UNSUPPORTED"

    def test_purpose_mismatch(self) -> None:
        repo = _FakeRepo(_conn(), _profile(purpose="embedding"))
        with pytest.raises(AppError) as excinfo:
            resolve_agent_chat_model(repo, _secrets({"conn-1": "sk-real"}), "prof-1")
        assert excinfo.value.code == "MODEL_PURPOSE_MISMATCH"

    def test_missing_credential_not_callable(self) -> None:
        """云端连接缺凭证 → callable_state 不通过 → MODEL_NOT_CONFIGURED。"""
        repo = _FakeRepo(_conn(provider_id=None), _profile())
        with pytest.raises(AppError) as excinfo:
            resolve_agent_chat_model(repo, _secrets(), "prof-1")
        assert excinfo.value.code == "MODEL_NOT_CONFIGURED"

    def test_profile_not_found(self) -> None:
        repo = _FakeRepo(_conn(), _profile())
        with pytest.raises(AppError) as excinfo:
            resolve_agent_chat_model(repo, _secrets({"conn-1": "sk-real"}), "no-such-profile")
        assert excinfo.value.code == "MODEL_PROFILE_NOT_FOUND"
        assert excinfo.value.status_code == 404

    def test_no_network_on_resolve(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """构造只建对象、不发请求：拦截 httpx 以证明零网络。"""
        def _forbid(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("resolve_agent_chat_model 不应发起网络请求")

        import httpx  # noqa: PLC0415

        monkeypatch.setattr(httpx, "request", _forbid, raising=False)
        repo = _FakeRepo(_conn(), _profile())
        handle = resolve_agent_chat_model(repo, _secrets({"conn-1": "sk-real"}), "prof-1")
        assert handle.chat_model is not None
