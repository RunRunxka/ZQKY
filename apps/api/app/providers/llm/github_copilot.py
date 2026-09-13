"""GitHub Copilot 适配（D16）。

参考 `provider_core/github_copilot_provider.py` 的关键差异：
- 参考**不自动读取第三方 CLI/IDE 登录文件**（按 D16 硬约束），而是消费智启课源
  **自身受管令牌存储**中的 GitHub 令牌。
- 用 GitHub 令牌向 `https://api.github.com/copilot_internal/v2/token` 交换 Copilot
  access token（与普通模型 API Key 不同），再以 OpenAI 兼容协议调用。
- 未配置/已过期时返回可操作错误，说明用户需要做什么，不自称已支持。

令牌存储键：`copilot-token:<connectionId>`。
"""

from __future__ import annotations

import time

import httpx2 as httpx

from app.providers.llm.base import ProviderError
from app.providers.llm.openai_chat import OpenAIChatProvider
from app.providers.llm.registry import find_provider
from app.schemas.model_config import ModelProtocol

COPILOT_EXCHANGE_URL = "https://api.github.com/copilot_internal/v2/token"
COPILOT_DEFAULT_BASE = "https://api.githubcopilot.com"
COPILOT_EDITOR_VERSION = "vscode/1.99.0"
COPILOT_PLUGIN_VERSION = "copilot-chat/0.26.0"
EXPIRY_SKEW_SECONDS = 60
DEFAULT_ACCESS_TTL_SECONDS = 1500


class GitHubCopilotProvider(OpenAIChatProvider):
    protocol = ModelProtocol.openai_chat
    requires_api_key = False

    def __init__(self, secret_store=None) -> None:  # noqa: ANN001
        self._secrets = secret_store
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def bind_secrets(self, secret_store) -> None:  # noqa: ANN001
        self._secrets = secret_store

    def _github_token(self, config) -> str | None:  # noqa: ANN001
        # 优先使用显式传入的凭证（来自 SecretStore 的连接 Key），否则查受管令牌键
        if config.apiKey:
            return config.apiKey
        if self._secrets is None or not config.connectionId:
            return None
        return self._secrets.resolve(f"copilot-token:{config.connectionId}")

    def _ensure_access_token(self, config) -> str:  # noqa: ANN001
        if self._access_token and time.time() < self._expires_at - EXPIRY_SKEW_SECONDS:
            return self._access_token
        github_token = self._github_token(config)
        if not github_token:
            raise ProviderError(
                "AUTH_REQUIRED",
                "GitHub Copilot 需要先提供 GitHub 访问令牌。请在设置中填写该连接的凭证（personal access token 或已授权的 GitHub 令牌）。",
                status_code=400,
            )
        access_token, expires_at = self._exchange(github_token)
        self._access_token = access_token
        self._expires_at = expires_at
        if self._secrets is not None and config.connectionId:
            self._secrets.put(f"copilot-access:{config.connectionId}", access_token)
        return access_token

    def _exchange(self, github_token: str) -> tuple[str, float]:
        headers = {
            "Authorization": f"token {github_token}",
            "Editor-Version": COPILOT_EDITOR_VERSION,
            "Editor-Plugin-Version": COPILOT_PLUGIN_VERSION,
            "User-Agent": "zhiqikeyuan/1",
            "Accept": "application/json",
        }
        try:
            with httpx.Client(timeout=20) as client:
                response = client.get(COPILOT_EXCHANGE_URL, headers=headers)
        except httpx.HTTPError as exc:
            raise ProviderError("UPSTREAM_UNREACHABLE", "无法连接 GitHub Copilot 令牌服务。", retryable=True) from exc
        if response.status_code in (401, 403):
            raise ProviderError(
                "UPSTREAM_AUTH_FAILED",
                "GitHub 令牌无效或未授权 Copilot，请检查凭证。",
            )
        if response.status_code >= 400:
            raise ProviderError("UPSTREAM_ERROR", f"GitHub Copilot 令牌交换失败（HTTP {response.status_code}）。")
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError("UPSTREAM_ERROR", "GitHub Copilot 令牌响应无法解析。") from exc
        token = data.get("token")
        if not token:
            raise ProviderError("UPSTREAM_ERROR", "GitHub Copilot 未返回访问令牌。")
        expires_at = data.get("expires_at")
        if isinstance(expires_at, (int, float)) and expires_at > 0:
            ttl = float(expires_at) - time.time()
        else:
            ttl = float(data.get("refresh_in") or DEFAULT_ACCESS_TTL_SECONDS)
        return str(token), time.time() + max(ttl, 60.0)

    def _headers(self, config) -> dict[str, str]:  # type: ignore[override]
        from app.providers.llm.base import merge_headers

        token = self._ensure_access_token(config)
        spec = find_provider("github_copilot")
        auth: dict[str, str] = {"Authorization": f"Bearer {token}"}
        if spec is not None:
            auth["Editor-Version"] = COPILOT_EDITOR_VERSION
            auth["Editor-Plugin-Version"] = COPILOT_PLUGIN_VERSION
        return merge_headers(config.extraHeaders, auth)

    def _base_url(self, config) -> str:  # noqa: ANN001
        return (config.baseUrl or COPILOT_DEFAULT_BASE).rstrip("/")


__all__ = ["COPILOT_DEFAULT_BASE", "COPILOT_EXCHANGE_URL", "GitHubCopilotProvider"]
