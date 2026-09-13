"""Azure OpenAI 专用适配（D4）。

参考 `provider_core/azure_openai_provider.py:34-112`：
- 用户的 Azure 端点（可能含 `/openai/deployments/<name>/chat/completions?api-version=`）
  运行时归一到 `<host>/openai/v1/`；**存储的 baseUrl 原值不改**。
- 认证头用 `api-key`（不是 Bearer，Bearer 留给 Entra）。
- `apiVersion` 只在等于 `preview` 时作为查询参数转发；其他值不假装已生效。
- 参考走 Responses API；本实现遵循同一口径。
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.providers.llm.base import ProviderError
from app.providers.llm.openai_responses import OpenAIResponsesProvider
from app.schemas.model_config import ModelProtocol

# 参考内置默认（provider_core/azure_openai_provider.py:69）
DEFAULT_AZURE_MODEL = "gpt-5.2-chat"


def normalize_azure_base_url(raw: str) -> str:
    """把 Azure 门户经典端点归一到 `<host>/openai/v1`（幂等）。"""
    value = (raw or "").strip().rstrip("/")
    if not value:
        return value
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    path = parsed.path or ""
    # 已归一的端点直接返回
    if path.rstrip("/").endswith("/openai/v1"):
        return f"{parsed.scheme}://{parsed.netloc}/openai/v1"
    # 经典 deployments 端点：只保留 host
    if "/openai/deployments/" in path:
        return f"{parsed.scheme}://{parsed.netloc}/openai/v1"
    if path.rstrip("/").endswith("/openai"):
        return f"{parsed.scheme}://{parsed.netloc}/openai/v1"
    return f"{parsed.scheme}://{parsed.netloc}/openai/v1"


class AzureOpenAIProvider(OpenAIResponsesProvider):
    protocol = ModelProtocol.openai_responses
    requires_api_key = True

    def _url(self, config) -> str:  # type: ignore[override]
        base = normalize_azure_base_url(config.baseUrl)
        url = f"{base}/responses"
        # 参考只在 apiVersion == "preview" 时实际转发
        if (config.apiVersion or "").strip().lower() == "preview":
            url = f"{url}?api-version=preview"
        return url

    def _headers(self, config):  # type: ignore[override]
        from app.providers.llm.base import merge_headers, resolve_api_key

        key = resolve_api_key(config, required=self.requires_api_key)
        auth = {"api-key": key} if key else {}
        return merge_headers(config.extraHeaders, auth)

    async def _complete(self, config, request, transport=None):  # type: ignore[override]
        if not config.baseUrl:
            raise ProviderError("MODEL_NOT_CONFIGURED", "Azure 连接缺少端点地址。", status_code=400)
        return await super()._complete(config, request, transport)


__all__ = ["AzureOpenAIProvider", "DEFAULT_AZURE_MODEL", "normalize_azure_base_url"]
