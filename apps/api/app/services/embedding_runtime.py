"""Embedding provider 解析：按索引配置选择本机 Ollama 或云端百炼。

教材域的所有向量入口（模型探测、配置保存、入库、重建、检索）都经这里取 provider，
保证"当前索引配置属于哪个向量空间，就用哪个适配器"，不会拿本机适配器去调用云端模型，
也不会在切换回旧本机索引时继续使用云端调用器。

云端身份约束：

- 百炼没有权重 manifest digest，配置里保存的是**声明式身份**（供应商 + 连接 + 模型 +
  维度 的派生值）。``supports_digest_verification=False``，界面不得描述成权重哈希。
- 每次解析都核对"登记时的 Base URL / 连接 / 模型 / 维度"与当前配置是否一致：
  连接被删除、地址漂移或供应商变化一律抛 ``EMBEDDING_MODEL_CHANGED``，
  绝不静默使用另一个向量空间。
- 凭证只从 ``SecretStore`` 取；解析阶段不发起网络请求。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.exceptions import AppError
from app.providers.embeddings.dashscope_embedding import (
    DEFAULT_MODEL,
    PROVIDER_ID,
    SUPPORTED_MODELS,
    DashScopeEmbeddingProvider,
    DashScopeTarget,
    declared_identity_digest,
    default_dimensions,
    dimension_choices,
    validate_target,
)
from app.providers.embeddings.ollama_embedding import OllamaEmbeddingProvider
from app.repositories.textbook_catalog.records import ProfileRecord
from app.services.model_readiness import callable_state

#: 云端连接选项里的模型清单（受控：只列官方支持 dimensions 的文本 Embedding 模型）。
CLOUD_MODELS: tuple[str, ...] = SUPPORTED_MODELS


@dataclass(frozen=True)
class CloudConnectionOption:
    connection_id: str
    display_name: str
    base_url: str
    ready: bool
    reason: str | None


def _changed(message: str) -> AppError:
    return AppError(message, code="EMBEDDING_MODEL_CHANGED", status_code=409)


class EmbeddingProviderResolver:
    """按配置解析 provider；本机适配器复用进程内单例，云端按连接即时构造。"""

    def __init__(
        self,
        local_provider: Any,
        settings: Any,
        *,
        model_config_repo: Any = None,
        secret_store: Any = None,
    ) -> None:
        self._local = local_provider
        self.settings = settings
        self._repo = model_config_repo
        self._secrets = secret_store

    # ------------------------------------------------------------------ 本机

    @property
    def local(self) -> Any:
        return self._local

    def local_options(self) -> list[CloudConnectionOption]:  # pragma: no cover - 语义占位
        return []

    # ------------------------------------------------------------------ 云端

    @property
    def cloud_enabled(self) -> bool:
        return self._repo is not None and self._secrets is not None

    def _require_cloud_deps(self) -> None:
        if not self.cloud_enabled:
            raise AppError(
                "云端 Embedding 未装配模型配置服务，暂不可用。",
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                retryable=False,
            )

    def _resolve_base_url(self, connection) -> str:
        base = (connection.baseUrl or "").strip().rstrip("/")
        if base:
            return base
        from app.providers.llm.registry import find_provider

        spec = find_provider(connection.providerId) if connection.providerId else None
        default = spec.defaultApiBaseFor(connection.apiFormat.value) if spec else ""
        return (default or "").rstrip("/")

    def cloud_connections(self) -> list[CloudConnectionOption]:
        """列出可用于云端 Embedding 的百炼连接（不发起网络请求、不回传凭证）。"""
        if not self.cloud_enabled:
            return []
        options: list[CloudConnectionOption] = []
        for connection in self._repo.list_connections():
            if (connection.providerId or "") != PROVIDER_ID:
                continue
            state = callable_state(connection, self._secrets)
            options.append(
                CloudConnectionOption(
                    connection_id=connection.id,
                    display_name=connection.displayName,
                    base_url=self._resolve_base_url(connection),
                    ready=state.ready,
                    reason=state.reason,
                )
            )
        return options

    def cloud_target(
        self, *, connection_id: str, model: str, dimensions: int | None
    ) -> tuple[DashScopeTarget, str]:
        """按连接构造云端目标与 Key；缺连接、缺凭证或配置不合法即拒绝。"""
        self._require_cloud_deps()
        connection = self._repo.get_connection(connection_id)
        if (connection.providerId or "") != PROVIDER_ID:
            raise AppError(
                "所选连接不是阿里云百炼（DashScope）连接，不能用于云端 Embedding。",
                code="EMBEDDING_CONNECTION_UNSUPPORTED",
                status_code=422,
            )
        state = callable_state(connection, self._secrets)
        if not state.ready:
            raise AppError(
                state.reason or "该百炼连接当前不可调用。",
                code="EMBEDDING_AUTH_MISSING",
                status_code=400,
            )
        target = validate_target(
            connection_id=connection.id,
            base_url=self._resolve_base_url(connection),
            model=model or DEFAULT_MODEL,
            dimensions=dimensions,
        )
        api_key = self._secrets.resolve(connection.id)
        if not api_key:
            raise AppError(
                "该百炼连接未保存 API Key；请先在设置 → 模型与连接中填写。",
                code="EMBEDDING_AUTH_MISSING",
                status_code=400,
            )
        return target, api_key

    def cloud_provider(
        self, *, connection_id: str, model: str, dimensions: int | None
    ) -> DashScopeEmbeddingProvider:
        target, api_key = self.cloud_target(
            connection_id=connection_id, model=model, dimensions=dimensions
        )
        return DashScopeEmbeddingProvider(target, api_key=api_key)

    # ------------------------------------------------------------------ 分派

    def for_profile(self, profile: ProfileRecord) -> Any:
        adapter = (profile.adapter or "").strip()
        if adapter == "ollama":
            return self._local
        if adapter != PROVIDER_ID:
            raise AppError(
                f"未知的 Embedding 适配器 {adapter or '（空）'}，拒绝使用该配置。",
                code="EMBEDDING_ADAPTER_UNSUPPORTED",
                status_code=409,
            )
        connection_id = str(profile.options.get("connectionId") or "").strip()
        if not connection_id:
            raise _changed("云端 Embedding 配置缺少连接标识，拒绝使用；请重新检测并保存配置。")
        self._require_cloud_deps()
        try:
            connection = self._repo.get_connection(connection_id)
        except AppError as exc:
            raise _changed(
                "云端 Embedding 配置引用的百炼连接已不存在，拒绝使用；请重新配置。"
            ) from exc
        if (connection.providerId or "") != PROVIDER_ID:
            raise _changed("云端 Embedding 配置引用的连接已不是百炼连接，拒绝使用。")
        current_base = self._resolve_base_url(connection)
        if current_base.rstrip("/") != (profile.native_base_url or "").strip().rstrip("/"):
            raise _changed(
                "百炼连接地址自该配置保存后已变化；请重新检测并保存配置后再使用。"
            )
        if (profile.model_name or "") not in SUPPORTED_MODELS:
            raise _changed(
                f"云端 Embedding 模型 {profile.model_name} 不在当前支持清单内，拒绝使用。"
            )
        if profile.dimensions not in dimension_choices(profile.model_name):
            raise _changed(
                f"云端 Embedding 维度 {profile.dimensions} 与模型 {profile.model_name} 不匹配，拒绝使用。"
            )
        expected = declared_identity_digest(
            connection_id=connection_id,
            base_url=current_base,
            model=profile.model_name,
            dimensions=profile.dimensions,
        )
        if expected != profile.model_manifest_digest:
            raise _changed(
                "云端 Embedding 配置的身份摘要与登记不一致，拒绝使用；请重新检测并保存配置。"
            )
        api_key = self._secrets.resolve(connection.id)
        if not api_key:
            raise AppError(
                "该百炼连接未保存 API Key，云端 Embedding 暂不可用；请先在设置中补全。",
                code="EMBEDDING_AUTH_MISSING",
                status_code=400,
            )
        target = DashScopeTarget(
            connection_id=connection_id,
            base_url=current_base,
            model=profile.model_name,
            dimensions=profile.dimensions,
        )
        return DashScopeEmbeddingProvider(target, api_key=api_key)

    # ------------------------------------------------------------- 探测/保存

    def probe_provider(
        self,
        *,
        source: str,
        model_name: str,
        connection_id: str | None = None,
        dimensions: int | None = None,
        base_url: str | None = None,
    ) -> Any:
        """探测阶段取 provider：local 允许临时 Base URL，cloud 绑定具体连接。"""
        if source == "cloud":
            if not connection_id:
                raise AppError(
                    "云端 Embedding 需要选择一个已保存凭证的百炼连接。",
                    code="EMBEDDING_CONNECTION_REQUIRED",
                    status_code=422,
                )
            return self.cloud_provider(
                connection_id=connection_id,
                model=model_name or DEFAULT_MODEL,
                dimensions=dimensions,
            )
        target = (base_url or "").strip()
        settings_url = str(getattr(self.settings, "embedding_base_url", ""))
        if not target or target.rstrip("/") == settings_url.rstrip("/"):
            return self._local
        return OllamaEmbeddingProvider(target)

    def default_cloud_dimensions(self, model: str) -> int:
        return default_dimensions(model)


__all__ = [
    "CLOUD_MODELS",
    "CloudConnectionOption",
    "EmbeddingProviderResolver",
]
