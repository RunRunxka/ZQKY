"""Agent 模型工厂：把既有模型配置显式构造为 LangChain 官方 chat model。

与既有 ``app.providers.llm`` 适配层的关系：现有 /chat、/rag、题库 AI、教案生成仍走
``resolve_chat_model``（凭证隔离、OAuth、三协议适配、指纹核对）。本模块**只为 Agent 编排**
提供 LangChain 原生 chat model（bind_tools / astream / interrupt 需要官方接口），两套并存，
不替换既有链路。

凭证红线（D9 / PROJECT_GUIDE）在本模块的落地约束：

- API Key 只从 ``SecretStore.resolve(connection_id)`` 取，**显式传给官方包**；
- 官方包在"未显式传 key 且环境变量存在"时会静默读环境变量（实测确认），因此本模块
  **无条件显式传 key**（本地免 Key 连接传占位符），并在构造前断言相关 ``*_API_KEY``
  环境变量未被设置，从两条路径同时堵死泄漏；
- 受管认证（Codex / Copilot / CodeBuddy）一期不支持 Agent 调用——它们的 OAuth 令牌
  不是普通 API Key，官方包无法承载；这些连接仍可用于 /chat 直连。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.exceptions import AppError
from app.core.secrets import SecretStore
from app.providers.llm.registry import (
    BACKEND_CODEBUDDY,
    BACKEND_GITHUB_COPILOT,
    BACKEND_OPENAI_CODEX,
    effective_backend,
    find_provider,
)
from app.schemas.model_config import ApiFormat, ModelConnection, ModelProfile
from app.services.model_readiness import callable_state

#: Agent 用途（用于 profile.purpose 校验；None 表示不限制）
AGENT_PURPOSE = "chat"

#: 本地免 Key 连接也必须显式传一个非空占位符，避免官方包回退读环境变量。
_LOCAL_PLACEHOLDER_KEY = "zqky-local-no-key"

#: 一期不支持 Agent 调用的受管认证 backend。
_UNSUPPORTED_OAUTH_BACKENDS = frozenset(
    {BACKEND_OPENAI_CODEX, BACKEND_GITHUB_COPILOT, BACKEND_CODEBUDDY}
)

#: 构造前必须确保未被设置的进程环境变量（防"未显式传 key 时静默读环境"泄漏路径）。
_FORBIDDEN_ENV_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")


def assert_no_provider_env_keys() -> None:
    """启动/构造前断言：官方包可能回退读取的进程环境变量一律未设置。

    发现即拒绝（不静默放行），因为本项目凭证只经 SecretStore，进程环境出现
    ``OPENAI_API_KEY``/``ANTHROPIC_API_KEY`` 即意味着配置越界。
    """
    leaked = [name for name in _FORBIDDEN_ENV_VARS if os.environ.get(name)]
    if leaked:
        raise AppError(
            f"检测到进程环境变量 {', '.join(leaked)}。本项目凭证只存后端 .env 并经 "
            "SecretStore 注入，不允许在进程环境中设置供应商 Key；请移除后重启。",
            code="PROVIDER_ENV_FORBIDDEN",
            status_code=500,
        )


@dataclass(frozen=True)
class AgentModelHandle:
    """一次 Agent 运行冻结的 chat model 句柄：模型 + 连接快照 + 生效输出上限。"""

    profile_id: str
    model_id: str
    chat_model: BaseChatModel
    max_output_tokens: int
    context_tokens: int | None = None


def _resolve_api_key(connection: ModelConnection, secrets: SecretStore) -> str:
    """取本连接的调用凭证：云服务等返回真实 Key，本地免 Key 返回占位符。

    无条件返回非空字符串，确保下游构造时永远显式传 key，不给官方包留"读环境变量"的空子。
    """
    key = secrets.resolve(connection.id)
    if key:
        return key
    # 本地免 Key 服务（ollama / llama.cpp / ovms 等）：官方包要求非空 key，用占位符。
    return _LOCAL_PLACEHOLDER_KEY


def _effective_api_format(connection: ModelConnection) -> str:
    """解析连接的生效 API 格式：显式 apiFormat 优先，否则按供应商推导（对齐 protocol_for）。"""
    if connection.apiFormat is not ApiFormat.auto:
        return connection.apiFormat.value
    spec = find_provider(connection.providerId) if connection.providerId else None
    backend = effective_backend(spec, "auto") if connection.providerId else None
    if backend == "anthropic":
        return ApiFormat.anthropic.value
    if backend in {BACKEND_OPENAI_CODEX, "azure_openai"}:
        return ApiFormat.openai_responses.value
    return ApiFormat.openai_chat.value


def _reject_unsupported(connection: ModelConnection) -> None:
    """一期不支持 Agent 调用的连接（受管认证）：明确拒绝并给出可操作指引。"""
    spec = find_provider(connection.providerId) if connection.providerId else None
    backend = effective_backend(spec, connection.apiFormat.value) if connection.providerId else None
    if backend in _UNSUPPORTED_OAUTH_BACKENDS:
        raise AppError(
            "该模型连接受管认证（OAuth），暂不支持 Agent 调用；请在设置中改用 API Key "
            "型云端连接或本机模型后再用于 Agent。",
            code="AGENT_MODEL_UNSUPPORTED",
            status_code=422,
        )


def _build_chat_model(
    connection: ModelConnection,
    profile: ModelProfile,
    api_key: str,
) -> BaseChatModel:
    """按生效格式构造官方 chat model，所有敏感/连接参数显式注入。"""
    api_format = _effective_api_format(connection)
    base_url = connection.baseUrl or None
    if not base_url:
        spec = find_provider(connection.providerId) if connection.providerId else None
        default_base = spec.defaultApiBaseFor(connection.apiFormat.value) if spec else None
        base_url = default_base.rstrip("/") if default_base else None
    if not base_url:
        raise AppError(
            "该连接缺少 Base URL，请在设置中补全。",
            code="MODEL_NOT_CONFIGURED",
            status_code=400,
        )

    common: dict[str, object] = {
        "model": profile.modelId,
        "api_key": api_key,
        "base_url": base_url,
        "default_headers": dict(connection.extraHeaders),
    }
    if profile.maxOutputTokens:
        common["max_tokens"] = profile.maxOutputTokens
    temperature = profile.params.get("temperature")
    if temperature is not None:
        common["temperature"] = temperature

    if api_format == ApiFormat.anthropic.value:
        return ChatAnthropic(**common)  # type: ignore[arg-type]
    if api_format == ApiFormat.openai_responses.value:
        return ChatOpenAI(use_responses_api=True, **common)  # type: ignore[arg-type]
    return ChatOpenAI(**common)  # type: ignore[arg-type]


def resolve_agent_chat_model(
    repo,
    secrets: SecretStore,
    profile_id: str,
) -> AgentModelHandle:
    """按 profileId 解析出可用于 Agent 编排的 LangChain chat model。

    - 复用 ``callable_state`` 做可调用性闸门（本地免 Key / 受管认证不被误判）；
    - 凭证只经 SecretStore 显式注入，构造前断言进程环境无供应商 Key；
    - 不发起任何网络请求（仅构造对象），失败在首次流式调用时按上游错误处理。
    """
    assert_no_provider_env_keys()

    try:
        profile = repo.get_profile(profile_id)
    except AppError as exc:
        if exc.status_code == 404:
            raise AppError(
                "模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404
            ) from exc
        raise
    if profile is None:
        raise AppError("模型配置不存在。", code="MODEL_PROFILE_NOT_FOUND", status_code=404)
    if profile.purpose not in (None, AGENT_PURPOSE):
        raise AppError(
            f"该模型配置用途为 {profile.purpose}，不能用于 Agent。",
            code="MODEL_PURPOSE_MISMATCH",
            status_code=422,
        )

    connection = repo.get_connection(profile.connectionId)
    _reject_unsupported(connection)

    state = callable_state(connection, secrets)
    if not state.ready:
        raise AppError(
            state.reason or "该模型连接当前不可调用。",
            code="MODEL_NOT_CONFIGURED",
            status_code=400,
        )

    api_key = _resolve_api_key(connection, secrets)
    chat_model = _build_chat_model(connection, profile, api_key)
    return AgentModelHandle(
        profile_id=profile.id,
        model_id=profile.modelId,
        chat_model=chat_model,
        max_output_tokens=profile.maxOutputTokens or 4096,
        context_tokens=profile.contextTokens,
    )


__all__ = [
    "AGENT_PURPOSE",
    "AgentModelHandle",
    "assert_no_provider_env_keys",
    "resolve_agent_chat_model",
]
