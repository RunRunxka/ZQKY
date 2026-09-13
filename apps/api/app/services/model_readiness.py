"""模型运行时可调用性判定（MR-02）。

统一回答"这条连接现在能不能发起调用"，供后端校验与前端按钮状态共用：

- 无 Key 本机服务（ollama / llama.cpp / ovms 等）：无需凭证即可调用；
- 普通云服务：需要本连接已保存凭证；
- 受管认证（Codex / Copilot）：需要对应的受管令牌，而不是普通 Key。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.secrets import SecretStore, legacy_scoped_key, scoped_key
from app.providers.llm.registry import (
    AUTH_API_KEY,
    AUTH_NONE,
    AUTH_OAUTH,
    ProviderSpec,
    find_provider,
)
from app.schemas.model_config import ModelConnection


@dataclass(frozen=True)
class CallableState:
    """可调用性结论：`ready` 为真才允许发起测试/聊天。"""

    ready: bool
    reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {"callable": self.ready, "callableReason": self.reason}


def credential_present(connection: ModelConnection, secrets: SecretStore) -> bool:
    """本连接是否存在任一可用凭证来源（普通 Key 或受管令牌）。"""
    if secrets.has(connection.id):
        return True
    provider_id = connection.providerId
    if provider_id == "openai_codex":
        return bool(
            secrets.resolve(scoped_key("codex-tokens", connection.id))
            or secrets.resolve(legacy_scoped_key("codex-tokens", connection.id))
        )
    if provider_id == "github_copilot":
        return bool(
            secrets.resolve(scoped_key("copilot-token", connection.id))
            or secrets.resolve(legacy_scoped_key("copilot-token", connection.id))
            or secrets.resolve(scoped_key("copilot-access", connection.id))
        )
    return False


def callable_state(
    connection: ModelConnection,
    secrets: SecretStore,
    spec: ProviderSpec | None = None,
) -> CallableState:
    resolved = spec if spec is not None else (find_provider(connection.providerId) if connection.providerId else None)

    if resolved is None:
        # 无 providerId 的旧连接：退回旧的"有 Key 即可"语义
        if not connection.baseUrl:
            return CallableState(False, "该连接缺少 Base URL。")
        if not secrets.has(connection.id):
            return CallableState(False, "该连接未保存凭证，请先填写 API Key。")
        return CallableState(True)

    if not connection.baseUrl and not resolved.defaultApiBaseFor(connection.apiFormat.value):
        return CallableState(False, "该供应商需要填写 Base URL。")

    if resolved.authMode == AUTH_NONE:
        # 本机免 Key 服务（MR-02）：不因缺少凭证被拒绝
        return CallableState(True)
    if resolved.authMode == AUTH_OAUTH:
        if credential_present(connection, secrets):
            return CallableState(True)
        if resolved.providerId == "openai_codex":
            return CallableState(False, "尚未完成 Codex 登录，请先开始授权流程。")
        return CallableState(False, "尚未提供该供应商所需的令牌。")
    if resolved.authMode == AUTH_API_KEY and not resolved.requires_key:
        return CallableState(True)
    if not credential_present(connection, secrets):
        return CallableState(False, "该连接未保存凭证，请先填写 API Key。")
    return CallableState(True)


__all__ = ["CallableState", "callable_state", "credential_present"]
