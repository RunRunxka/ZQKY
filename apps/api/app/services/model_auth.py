"""模型连接认证服务：统一四态状态机与各供应商认证方式（D9/D10/D11/D16）。

四态：`disconnected` / `authorizing` / `connected` / `error`，附操作 ID 与
过期/取消语义。**只有 openai_codex 需要时也可用 oauth 流程**；Copilot 用受管
令牌存储做注入与交换；CodeBuddy 用 API Key；其余供应商是普通 API Key。

不读取任何第三方 CLI/IDE 登录文件。
"""

from __future__ import annotations

from typing import Any

from app.core.secrets import SecretStore
from app.providers.llm.codex_oauth import CodexOAuthService
from app.providers.llm.registry import (
    AUTH_API_KEY,
    AUTH_NONE,
    AUTH_OAUTH,
    find_provider,
)
from app.repositories.model_config_repository import ModelConfigRepository

# 认证状态词表
CONNECTION_DISCONNECTED = "disconnected"
CONNECTION_AUTHORIZING = "authorizing"
CONNECTION_CONNECTED = "connected"
CONNECTION_ERROR = "error"

SUPPORTED_AUTH_PROVIDERS = frozenset({"openai_codex", "github_copilot", "codebuddy"})


class ModelAuthService:
    """按 connectionId 管理认证状态；Codex 走 OAuth 状态机，其余为 Key 型。"""

    def __init__(self, repo: ModelConfigRepository, secrets: SecretStore) -> None:
        self._repo = repo
        self._secrets = secrets
        self._codex = CodexOAuthService(secrets)

    @property
    def codex(self) -> CodexOAuthService:
        return self._codex

    @property
    def secrets(self) -> SecretStore:
        return self._secrets

    def provider_id(self, connection_id: str) -> str | None:
        try:
            connection = self._repo.get_connection(connection_id)
        except Exception:  # noqa: BLE001 - 不存在时按未连接处理
            return None
        return connection.providerId

    def status(self, connection_id: str) -> dict[str, Any]:
        provider_id = self.provider_id(connection_id)
        if provider_id is None:
            return {"connection": CONNECTION_ERROR, "authMode": None, "errorCode": "NOT_FOUND"}
        spec = find_provider(provider_id)
        auth_mode = spec.authMode if spec else AUTH_API_KEY

        if provider_id == "openai_codex":
            status = self._codex.status(connection_id)
            status.setdefault("authMode", AUTH_OAUTH)
            return status

        if auth_mode == AUTH_OAUTH:
            # Copilot / CodeBuddy：四种可用方式按实际配置判断
            return self._managed_status(connection_id, provider_id)

        has = self._secrets.has(connection_id)
        return {
            "connection": CONNECTION_CONNECTED if has else CONNECTION_DISCONNECTED,
            "authMode": AUTH_NONE if auth_mode == AUTH_NONE else AUTH_API_KEY,
            "provider": provider_id,
            "available": True,
        }

    def _managed_status(self, connection_id: str, provider_id: str) -> dict[str, Any]:
        if provider_id == "github_copilot":
            from app.core.secrets import legacy_scoped_key, scoped_key

            has_connection_key = self._secrets.has(connection_id)
            managed = self._secrets.resolve(scoped_key("copilot-token", connection_id)) or self._secrets.resolve(
                legacy_scoped_key("copilot-token", connection_id)
            )
            has_access = bool(
                self._secrets.resolve(scoped_key("copilot-access", connection_id))
                or self._secrets.resolve(legacy_scoped_key("copilot-access", connection_id))
            )
            if has_connection_key or managed:
                return {
                    "connection": CONNECTION_CONNECTED,
                    "authMode": AUTH_OAUTH,
                    "provider": provider_id,
                    "available": True,
                    "note": "使用受管的 GitHub 令牌交换 Copilot 访问令牌。",
                }
            return {
                "connection": CONNECTION_DISCONNECTED,
                "authMode": AUTH_OAUTH,
                "provider": provider_id,
                "available": False,
                "unavailableReason": "需要提供 GitHub 访问令牌（personal access token）。请在该连接保存凭证后重试。",
                "hasCachedAccessToken": has_access,
            }
        if provider_id == "codebuddy":
            configured = bool(self._api_key_present(connection_id))
            return {
                "connection": CONNECTION_CONNECTED if configured else CONNECTION_DISCONNECTED,
                "authMode": AUTH_API_KEY,
                "provider": provider_id,
                "available": configured,
                "unavailableReason": None if configured else "需要 CodeBuddy API Key。请在服务端配置后保存到该连接。",
                "supportedModes": ["api_key"],
            }
        return {"connection": CONNECTION_DISCONNECTED, "authMode": AUTH_OAUTH, "provider": provider_id}

    def _api_key_present(self, connection_id: str) -> bool:
        from app.providers.llm.codebuddy import is_codebuddy_configured

        return is_codebuddy_configured(self._secrets.resolve(connection_id))

    async def start(self, connection_id: str) -> dict[str, Any]:
        provider_id = self.provider_id(connection_id)
        spec = find_provider(provider_id) if provider_id else None
        if provider_id == "openai_codex":
            return await self._codex.start_login(connection_id)
        if spec is not None and spec.authMode == AUTH_OAUTH:
            return {
                "ok": False,
                "errorCode": "UNSUPPORTED_OPERATION",
                "message": (
                    "该供应商不使用交互式授权流程；请提供对应令牌/API Key。"
                    "GitHub Copilot 需要 GitHub 访问令牌，CodeBuddy 需要 API Key。"
                ),
                "status": self.status(connection_id),
            }
        return {
            "ok": False,
            "errorCode": "UNSUPPORTED_OPERATION",
            "message": "该连接使用 API Key 认证，无需交互式授权。",
        }

    async def cancel(self, connection_id: str) -> dict[str, Any]:
        provider_id = self.provider_id(connection_id)
        if provider_id == "openai_codex":
            return await self._codex.cancel_login(connection_id)
        return {"ok": False, "errorCode": "UNSUPPORTED_OPERATION", "message": "没有可取消的授权流程。"}

    async def logout(self, connection_id: str) -> dict[str, Any]:
        from app.core.secrets import legacy_scoped_key, scoped_key

        provider_id = self.provider_id(connection_id)
        if provider_id == "openai_codex":
            return await self._codex.logout(connection_id)
        if provider_id == "github_copilot":
            # MR-10：清理本连接**全部**认证来源——托管缓存、历史键，以及 UI 保存在
            # connectionId 上的 GitHub 令牌；只清展示状态会留下仍可调用的凭证。
            self._secrets.delete(scoped_key("copilot-token", connection_id))
            self._secrets.delete(scoped_key("copilot-access", connection_id))
            self._secrets.delete(legacy_scoped_key("copilot-token", connection_id))
            self._secrets.delete(legacy_scoped_key("copilot-access", connection_id))
            self._secrets.delete(connection_id)
            return {"ok": True, "status": self.status(connection_id)}
        if provider_id == "codebuddy":
            self._secrets.delete(connection_id)
            return {"ok": True, "status": self.status(connection_id)}
        return {"ok": False, "errorCode": "UNSUPPORTED_OPERATION", "message": "该连接没有可断开的托管认证。"}

    def augment_providers(self, providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """给目录补充认证可用性与操作能力（D15：不下发原始 backend）。"""
        for entry in providers:
            if entry["providerId"] == "openai_codex":
                entry["authAvailable"] = self._codex.app_configured
                entry["authUnavailableReason"] = self._codex.unavailable_reason()
            else:
                entry["authAvailable"] = True
                entry["authUnavailableReason"] = None
        return providers


__all__ = [
    "CONNECTION_AUTHORIZING",
    "CONNECTION_CONNECTED",
    "CONNECTION_DISCONNECTED",
    "CONNECTION_ERROR",
    "ModelAuthService",
    "SUPPORTED_AUTH_PROVIDERS",
]
