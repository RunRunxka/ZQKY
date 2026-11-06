"""百炼（DashScope）云端 Embedding 适配器测试。

全部使用注入的假客户端：不连接真实百炼、不读取真实凭证、不产生费用。
覆盖：显式 Key 与请求参数、维度校验、输出校验、上游错误映射、声明式身份、
按配置分派（本机/云端互不串用）以及配置漂移拒绝。
"""

from __future__ import annotations

import pytest

from app.core.exceptions import AppError
from app.providers.embeddings.dashscope_embedding import (
    MAX_BATCH_SIZE,
    DashScopeEmbeddingProvider,
    DashScopeTarget,
    declared_identity_digest,
    dimension_choices,
    validate_target,
)
from app.services.embedding_runtime import EmbeddingProviderResolver


class FakeClient:
    """假 LangChain Embeddings：记录入参，按预设返回向量或抛错。"""

    def __init__(self, *, dimensions: int = 1024, error: Exception | None = None) -> None:
        self.dimensions = dimensions
        self.error = error
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.error is not None:
            raise self.error
        return [[0.01 * (index + 1)] * self.dimensions for index in range(len(texts))]


class UpstreamError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"upstream {status_code}")
        self.status_code = status_code


def make_provider(
    *, client: FakeClient | None = None, connection_id: str = "conn-1"
) -> tuple[DashScopeEmbeddingProvider, FakeClient]:
    client = client or FakeClient()
    target = validate_target(
        connection_id=connection_id,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="text-embedding-v4",
        dimensions=1024,
    )
    provider = DashScopeEmbeddingProvider(
        target, api_key="sk-test-not-real", client_factory=lambda _t, _k: client
    )
    return provider, client


# ------------------------------------------------------------------ 目标校验


def test_dimension_choices_follow_official_table() -> None:
    assert 1024 in dimension_choices("text-embedding-v4")
    assert 2048 in dimension_choices("text-embedding-v4")
    assert dimension_choices("unknown-model") == ()


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"connection_id": "", "model": "text-embedding-v4", "dimensions": 1024}, "EMBEDDING_CONNECTION_REQUIRED"),
        ({"connection_id": "c", "model": "text-embedding-v9", "dimensions": 1024}, "EMBEDDING_MODEL_UNSUPPORTED"),
        ({"connection_id": "c", "model": "text-embedding-v4", "dimensions": 999}, "EMBEDDING_DIMENSIONS_UNSUPPORTED"),
        ({"connection_id": "c", "model": "", "dimensions": 1024}, "INVALID_REQUEST"),
    ],
)
def test_validate_target_rejects_invalid_config(kwargs, code) -> None:
    with pytest.raises(AppError) as exc_info:
        validate_target(base_url="https://example.com/v1", **kwargs)
    assert exc_info.value.code == code


def test_validate_target_requires_http_base_url() -> None:
    with pytest.raises(AppError) as exc_info:
        validate_target(
            connection_id="c", base_url="", model="text-embedding-v4", dimensions=1024
        )
    assert exc_info.value.code == "EMBEDDING_BASE_URL_INVALID"


# ------------------------------------------------------------------ 调用


def test_embed_uses_explicit_client_and_validates_count() -> None:
    provider, client = make_provider()
    vectors = provider.embed(model="text-embedding-v4", texts=["甲", "乙"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 1024
    assert client.calls == [["甲", "乙"]]
    assert MAX_BATCH_SIZE == 10


def test_embed_rejects_other_model_without_calling_upstream() -> None:
    provider, client = make_provider()
    with pytest.raises(AppError) as exc_info:
        provider.embed(model="text-embedding-v3", texts=["甲"])
    assert exc_info.value.code == "EMBEDDING_MODEL_CHANGED"
    assert client.calls == []


@pytest.mark.parametrize(
    "texts,code",
    [([], "INVALID_REQUEST"), (["  "], "INVALID_REQUEST"), ("甲", "INVALID_REQUEST")],
)
def test_embed_rejects_bad_input(texts, code) -> None:
    provider, _client = make_provider()
    with pytest.raises(AppError) as exc_info:
        provider.embed(model="text-embedding-v4", texts=texts)
    assert exc_info.value.code == code


def test_embed_rejects_bad_output_shape() -> None:
    class ShortClient(FakeClient):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.1] * 8 for _ in texts[:-1]] or [[0.1] * 8]

    provider, _client = make_provider(client=ShortClient())
    with pytest.raises(AppError) as exc_info:
        provider.embed(model="text-embedding-v4", texts=["甲", "乙"])
    assert exc_info.value.code == "EMBEDDING_INVALID_OUTPUT"


def test_embed_rejects_zero_vector() -> None:
    class ZeroClient(FakeClient):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.0] * 8 for _ in texts]

    provider, _client = make_provider(client=ZeroClient())
    with pytest.raises(AppError) as exc_info:
        provider.embed(model="text-embedding-v4", texts=["甲"])
    assert exc_info.value.code == "EMBEDDING_INVALID_OUTPUT"


def test_missing_api_key_is_rejected_before_any_call() -> None:
    target = DashScopeTarget(
        connection_id="c",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="text-embedding-v4",
        dimensions=1024,
    )
    with pytest.raises(AppError) as exc_info:
        DashScopeEmbeddingProvider(target, api_key="  ")
    assert exc_info.value.code == "EMBEDDING_AUTH_MISSING"


# ------------------------------------------------------------------ 错误映射


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "EMBEDDING_AUTH_FAILED", False),
        (403, "EMBEDDING_AUTH_FAILED", False),
        (404, "EMBEDDING_MODEL_MISSING", False),
        (429, "EMBEDDING_RATE_LIMITED", True),
        (500, "EMBEDDING_UNAVAILABLE", True),
        (400, "EMBEDDING_REQUEST_REJECTED", False),
    ],
)
def test_upstream_status_maps_to_stable_codes(status, code, retryable) -> None:
    provider, _client = make_provider(client=FakeClient(error=UpstreamError(status)))
    with pytest.raises(AppError) as exc_info:
        provider.embed(model="text-embedding-v4", texts=["甲"])
    assert exc_info.value.code == code
    assert exc_info.value.retryable is retryable
    # 错误消息不得夹带 Key
    assert "sk-test-not-real" not in str(exc_info.value)


def test_timeout_maps_to_retryable_error() -> None:
    class TimeoutError_(Exception):
        pass

    TimeoutError_.__name__ = "APITimeoutError"
    provider, _client = make_provider(client=FakeClient(error=TimeoutError_("slow")))
    with pytest.raises(AppError) as exc_info:
        provider.embed(model="text-embedding-v4", texts=["甲"])
    assert exc_info.value.code == "EMBEDDING_TIMEOUT"
    assert exc_info.value.retryable is True


# ------------------------------------------------------------------ 身份


def test_probe_marks_declared_identity_not_manifest() -> None:
    provider, client = make_provider()
    result = provider.verify_embedding_candidate(model_name="text-embedding-v4")
    assert result.stable_digest is False
    assert result.dimensions == 1024
    assert result.sample_count == len(client.calls[0])
    assert result.model_manifest_digest.startswith("dashscope-declared:")
    assert provider.supports_digest_verification is False


def test_declared_identity_changes_with_configuration() -> None:
    base = dict(connection_id="c1", base_url="https://a/v1", model="text-embedding-v4", dimensions=1024)
    first = declared_identity_digest(**base)
    assert first == declared_identity_digest(**base)
    assert first != declared_identity_digest(**{**base, "dimensions": 2048})
    assert first != declared_identity_digest(**{**base, "connection_id": "c2"})
    assert first != declared_identity_digest(**{**base, "model": "text-embedding-v3"})


# ------------------------------------------------------- 按配置分派（解析器）


class _Connection:
    def __init__(self, connection_id: str, provider_id: str, base_url: str, api_format="openai_chat"):
        self.id = connection_id
        self.displayName = "百炼"
        self.providerId = provider_id
        self.baseUrl = base_url
        self.apiFormat = type("F", (), {"value": api_format})()
        self.protocol = "openai-chat"
        self.extraHeaders = {}


class _Repo:
    def __init__(self, connections):
        self._connections = {item.id: item for item in connections}

    def list_connections(self):
        return list(self._connections.values())

    def get_connection(self, connection_id):
        item = self._connections.get(connection_id)
        if item is None:
            raise AppError("连接不存在。", code="CONNECTION_NOT_FOUND", status_code=404)
        return item


class _Secrets:
    def __init__(self, keys):
        self._keys = dict(keys)

    def has(self, key_id):
        return key_id in self._keys

    def resolve(self, key_id):
        return self._keys.get(key_id)


class _Profile:
    def __init__(self, **kwargs):
        self.profile_id = kwargs.get("profile_id", "p1")
        self.fingerprint = kwargs.get("fingerprint", "fp1")
        self.adapter = kwargs["adapter"]
        self.native_base_url = kwargs["native_base_url"]
        self.model_name = kwargs["model_name"]
        self.model_manifest_digest = kwargs["model_manifest_digest"]
        self.dimensions = kwargs.get("dimensions", 1024)
        self.options_json = "{}"
        self._options = kwargs.get("options", {})

    @property
    def options(self):
        return dict(self._options)


class _Local:
    adapter = "ollama"
    base_url = "http://127.0.0.1:11434"

    def __init__(self):
        self.embed_calls: list[list[str]] = []

    def embed(self, *, model, texts):
        self.embed_calls.append(list(texts))
        return [[0.5] * 8 for _ in texts]


def _resolver(*, keys=None, connections=None):
    local = _Local()
    repo = _Repo(
        connections
        or [
            _Connection(
                "conn-1",
                "dashscope",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        ]
    )
    settings = type("S", (), {"embedding_base_url": "http://127.0.0.1:11434"})()
    return (
        EmbeddingProviderResolver(
            local, settings, model_config_repo=repo, secret_store=_Secrets(keys or {})
        ),
        local,
    )


def test_local_profile_uses_local_provider() -> None:
    resolver, local = _resolver()
    profile = _Profile(
        adapter="ollama",
        native_base_url="http://127.0.0.1:11434",
        model_name="bge-m3",
        model_manifest_digest="digest-1",
    )
    assert resolver.for_profile(profile) is local


def test_cloud_profile_binds_cloud_provider() -> None:
    resolver, local = _resolver(keys={"conn-1": "sk-real"})
    profile = _Profile(
        adapter="dashscope",
        native_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="text-embedding-v4",
        model_manifest_digest=declared_identity_digest(
            connection_id="conn-1",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="text-embedding-v4",
            dimensions=1024,
        ),
        options={"connectionId": "conn-1"},
    )
    provider = resolver.for_profile(profile)
    assert provider is not local
    assert provider.adapter == "dashscope"
    assert provider.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_cloud_profile_without_credential_is_rejected() -> None:
    resolver, _local = _resolver(keys={})
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    profile = _Profile(
        adapter="dashscope",
        native_base_url=base_url,
        model_name="text-embedding-v4",
        model_manifest_digest=declared_identity_digest(
            connection_id="conn-1",
            base_url=base_url,
            model="text-embedding-v4",
            dimensions=1024,
        ),
        options={"connectionId": "conn-1"},
    )
    with pytest.raises(AppError) as exc_info:
        resolver.for_profile(profile)
    assert exc_info.value.code == "EMBEDDING_AUTH_MISSING"


def test_cloud_profile_with_changed_base_url_is_rejected() -> None:
    resolver, _local = _resolver(keys={"conn-1": "sk-real"})
    profile = _Profile(
        adapter="dashscope",
        native_base_url="https://old.example.com/v1",
        model_name="text-embedding-v4",
        model_manifest_digest="dashscope-declared:x",
        options={"connectionId": "conn-1"},
    )
    with pytest.raises(AppError) as exc_info:
        resolver.for_profile(profile)
    assert exc_info.value.code == "EMBEDDING_MODEL_CHANGED"


def test_cloud_profile_with_missing_connection_is_rejected() -> None:
    resolver, _local = _resolver(keys={"gone": "sk-real"})
    profile = _Profile(
        adapter="dashscope",
        native_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="text-embedding-v4",
        model_manifest_digest="dashscope-declared:x",
        options={"connectionId": "gone"},
    )
    with pytest.raises(AppError) as exc_info:
        resolver.for_profile(profile)
    assert exc_info.value.code == "EMBEDDING_MODEL_CHANGED"


def test_cloud_connections_only_lists_dashscope() -> None:
    connections = [
        _Connection("conn-1", "dashscope", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        _Connection("conn-2", "openai", "https://api.openai.com/v1"),
    ]
    resolver, _local = _resolver(keys={"conn-1": "sk-real"}, connections=connections)
    options = resolver.cloud_connections()
    assert [item.connection_id for item in options] == ["conn-1"]
    assert options[0].ready is True


def test_cloud_probe_rejects_non_dashscope_connection() -> None:
    connections = [_Connection("conn-2", "openai", "https://api.openai.com/v1")]
    resolver, _local = _resolver(keys={"conn-2": "sk-real"}, connections=connections)
    with pytest.raises(AppError) as exc_info:
        resolver.cloud_provider(
            connection_id="conn-2", model="text-embedding-v4", dimensions=1024
        )
    assert exc_info.value.code == "EMBEDDING_CONNECTION_UNSUPPORTED"
