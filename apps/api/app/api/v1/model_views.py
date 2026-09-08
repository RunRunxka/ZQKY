"""视图构建：对外只输出脱敏后的模型设置数据（不含凭证明文与请求头值）。"""

from __future__ import annotations

from app.core.secrets import SecretStore
from app.schemas.model_config import ModelConnection, ModelProfile


def connection_view(connection: ModelConnection, secrets: SecretStore) -> dict:
    return {
        "id": connection.id,
        "displayName": connection.displayName,
        "protocol": connection.protocol.value,
        "baseUrl": connection.baseUrl,
        "hasCredential": secrets.has(connection.id),
        "credentialScope": "process",
        "extraHeaderNames": sorted(connection.extraHeaders.keys()),
        "createdAt": connection.createdAt.isoformat(),
        "updatedAt": connection.updatedAt.isoformat(),
    }


def connection_summary(
    connection: ModelConnection | None, secrets: SecretStore
) -> dict | None:
    if connection is None:
        return None
    return {
        "displayName": connection.displayName,
        "protocol": connection.protocol.value,
        "hasCredential": secrets.has(connection.id),
    }


def profile_view(
    profile: ModelProfile,
    connection: ModelConnection | None,
    secrets: SecretStore,
) -> dict:
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
        "capabilities": dict(profile.capabilities),
        "connection": connection_summary(connection, secrets),
        "createdAt": profile.createdAt.isoformat(),
        "updatedAt": profile.updatedAt.isoformat(),
    }
