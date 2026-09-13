"""CodeBuddy / WorkBuddy 适配（D16）。

参考有三个通道：本机 IDE/CLI 共享会话（**不采用**，受"不读第三方登录文件"约束）、
SDK 子进程（本实现不引入额外进程依赖）、以及 **X-API-Key**。

本实现只做参考已支持的 API Key 通道（D16 明确要求）：
- 有显式 Key → `X-API-Key` 头；
- 无 Key → 返回可操作错误，说明如何获取 Key；
- 该供应商不支持 `stream_options`（参考 `supports_stream_options=False`）。

发现：云无公开模型列表路由，返回 `manual` 来源，要求手工输入 modelId。
"""

from __future__ import annotations

from app.providers.llm.base import merge_headers, resolve_api_key
from app.providers.llm.openai_chat import OpenAIChatProvider
from app.providers.llm.registry import find_provider, strip_provider_prefix
from app.schemas.model_config import ModelProtocol

CODEBUDDY_DEFAULT_BASE = "https://www.codebuddy.ai/v2"
# 参考 codebuddy_http_provider.py:31 的占位符视为未配置
PLACEHOLDER_KEYS = frozenset({"sk-no-key-required", "no-key", ""})


class CodeBuddyProvider(OpenAIChatProvider):
    protocol = ModelProtocol.openai_chat
    requires_api_key = True

    def _headers(self, config):  # type: ignore[override]
        # 参考用 X-API-Key（非 Bearer）；该供应商虽然注册表标 oauth（本机会话），
        # 但智启课源只实现 API Key 通道，因此强制要求 Key（MR-02/D16）
        key = resolve_api_key(config, required=True, explicit_required=True)
        return merge_headers(config.extraHeaders, {"X-API-Key": key})

    def _base_url(self, config) -> str:  # type: ignore[override]
        spec = find_provider("codebuddy")
        base = config.baseUrl or (spec.defaultApiBase if spec else "") or CODEBUDDY_DEFAULT_BASE
        return base.rstrip("/")

    def _model_id(self, config) -> str:  # type: ignore[override]
        return strip_provider_prefix(config.modelId, find_provider("codebuddy"))


def is_codebuddy_configured(api_key: str | None) -> bool:
    return bool(api_key and api_key.strip() not in PLACEHOLDER_KEYS)

__all__ = ["CODEBUDDY_DEFAULT_BASE", "CodeBuddyProvider", "is_codebuddy_configured"]
