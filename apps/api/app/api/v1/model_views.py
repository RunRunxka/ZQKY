"""视图构建：对外只输出脱敏后的模型设置数据（不含凭证明文与请求头值）。

D15：不下发原始 backend，只下发 mode/authMode/apiFormats 等中性能力信息。
reasoningStyle 是按供应商派生的只读字段，不落库（D6）。
"""

from __future__ import annotations

from app.core.secrets import SecretStore
from app.providers.llm.reasoning_params import reasoning_style_for
from app.providers.llm.registry import (
    AUTH_API_KEY,
    AUTH_NONE,
    ProviderSpec,
    find_provider,
)
from app.schemas.model_config import ModelConnection, ModelProfile
from app.services.model_readiness import callable_state, credential_present


def provider_view(spec: ProviderSpec) -> dict:
    """供应商目录条目：前端只按这些元数据展示，不维护第二份 URL/能力真值。"""
    formats = list(spec.apiFormats)
    base_urls = {fmt: url for fmt, url in spec.apiBaseByFormat}
    return {
        "providerId": spec.providerId,
        "label": spec.label,
        "aliases": list(spec.aliases),
        "mode": spec.mode,
        "authMode": spec.authMode,
        "apiFormats": formats,
        "defaultApiFormat": spec.defaultApiFormat,
        "defaultApiBase": spec.defaultApiBase,
        "baseUrlsByFormat": base_urls,
        "supportsWireApiSelection": spec.supportsWireApiSelection,
        "supportsModelDiscovery": True,
        "requiresKey": spec.requires_key and spec.authMode == AUTH_API_KEY,
        "isLegacy": spec.isLegacy,
        "legacyOf": list(spec.legacyOf),
        "thinkingStyle": spec.thinkingStyle or None,
    }


def connection_view(connection: ModelConnection, secrets: SecretStore) -> dict:
    spec = find_provider(connection.providerId) if connection.providerId else None
    state = callable_state(connection, secrets, spec)
    has_managed = credential_present(connection, secrets)
    return {
        "id": connection.id,
        "displayName": connection.displayName,
        "providerId": connection.providerId,
        "providerLabel": spec.label if spec else None,
        "protocol": connection.protocol.value,
        "apiFormat": connection.apiFormat.value,
        "apiVersion": connection.apiVersion,
        # 保留原值：用户自定义地址不被切换控件静默覆盖
        "baseUrl": connection.baseUrl,
        "resolvedBaseUrl": _resolved_base_url(connection, spec),
        "hasCredential": secrets.has(connection.id),
        # 可调用性同时考虑普通 Key、受管令牌与本机免 Key（MR-02）
        "hasManagedCredential": has_managed,
        "callable": state.ready,
        "callableReason": state.reason,
        "credentialScope": secrets.scope,
        "credentialEnvName": f"ZQKY_API_KEY_{connection.id}",
        "extraHeaderNames": sorted(connection.extraHeaders.keys()),
        "createdAt": connection.createdAt.isoformat(),
        "updatedAt": connection.updatedAt.isoformat(),
    }


def _resolved_base_url(connection: ModelConnection, spec: ProviderSpec | None) -> str:
    """运行期实际地址（不落库）：显式 baseUrl 优先，否则用注册表默认/按格式默认。"""
    if connection.baseUrl:
        return connection.baseUrl
    if spec is None:
        return ""
    return spec.defaultApiBaseFor(connection.apiFormat.value)


def connection_summary(connection: ModelConnection | None, secrets: SecretStore) -> dict | None:
    if connection is None:
        return None
    spec = find_provider(connection.providerId) if connection.providerId else None
    return {
        "displayName": connection.displayName,
        "providerId": connection.providerId,
        "providerLabel": spec.label if spec else None,
        "protocol": connection.protocol.value,
        "apiFormat": connection.apiFormat.value,
        "hasCredential": secrets.has(connection.id),
    }


def profile_view(
    profile: ModelProfile,
    connection: ModelConnection | None,
    secrets: SecretStore,
) -> dict:
    spec = find_provider(connection.providerId) if connection and connection.providerId else None
    return {
        "id": profile.id,
        "connectionId": profile.connectionId,
        "displayName": profile.displayName,
        "modelId": profile.modelId,
        "purpose": profile.purpose,
        "contextTokens": profile.contextTokens,
        "maxOutputTokens": profile.maxOutputTokens,
        "supportedParams": list(profile.supportedParams),
        "params": dict(profile.params),
        "reasoningEnabled": profile.reasoningEnabled,
        "reasoningEffort": profile.reasoningEffort.value if profile.reasoningEffort else None,
        # 只读派生：前端据此提示该供应商的推理表达方式
        "reasoningStyle": reasoning_style_for(spec, connection.providerId if connection else None),
        "capabilities": dict(profile.capabilities),
        "connection": connection_summary(connection, secrets),
        "createdAt": profile.createdAt.isoformat(),
        "updatedAt": profile.updatedAt.isoformat(),
    }


__all__ = [
    "AUTH_API_KEY",
    "AUTH_NONE",
    "connection_summary",
    "connection_view",
    "profile_view",
    "provider_view",
]
