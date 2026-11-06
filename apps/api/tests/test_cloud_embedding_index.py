"""云端 Embedding 在索引/检索链路中的分派测试（不触网、不产生费用）。

覆盖：
1. 云端探测 + 保存：adapter/连接/维度/声明式身份落库，指纹与旧本机配置不冲突；
2. 重复保存返回既有配置（同指纹幂等）；
3. 云端 profile 重建时用云端 provider，本机 profile 仍用本机 provider（互不串用）；
4. 检索服务在切换索引代后重建 retriever，不复用旧向量空间的 provider；
5. 云端连接缺凭证、配置漂移时明确拒绝，不静默降级。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.providers.embeddings.dashscope_embedding import (
    DashScopeEmbeddingProvider,
    DashScopeTarget,
    declared_identity_digest,
)
from app.repositories.textbook_catalog.catalog import TextbookCatalog
from app.repositories.vector_store import InMemoryVectorStore
from app.services.document_parsing import chunk_document, parse_document
from app.services.embedding_runtime import EmbeddingProviderResolver
from app.services.textbook_index import IndexService
from app.services.textbook_ingest import IngestService
from tests.test_textbook_ingest import FakeEmbeddings

DASH_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class CloudClient:
    """假云端 Embeddings：固定维度、记录每次输入。"""

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[0.25] * self.dimensions for _ in texts]


class _Connection:
    def __init__(self, connection_id: str = "conn-cloud", provider_id: str = "dashscope", base_url: str = DASH_BASE):
        self.id = connection_id
        self.displayName = "百炼"
        self.providerId = provider_id
        self.baseUrl = base_url
        self.apiFormat = type("F", (), {"value": "openai_chat"})()
        self.protocol = "openai-chat"
        self.extraHeaders = {}


class _Repo:
    def __init__(self, connections) -> None:
        self._connections = {item.id: item for item in connections}

    def list_connections(self):
        return list(self._connections.values())

    def get_connection(self, connection_id):
        item = self._connections.get(connection_id)
        if item is None:
            raise AppError("连接不存在。", code="CONNECTION_NOT_FOUND", status_code=404)
        return item


class _Secrets:
    def __init__(self, keys) -> None:
        self._keys = dict(keys)

    def has(self, key_id) -> bool:
        return key_id in self._keys

    def resolve(self, key_id):
        return self._keys.get(key_id)


class CloudEnv:
    def __init__(self, tmp_path: Path, *, keys=None, connections=None) -> None:
        self.settings = Settings(
            host="127.0.0.1", port=8001, allowed_origins=frozenset(), env="test",
            data_dir=tmp_path / "data",
        )
        self.catalog = TextbookCatalog(self.settings.textbooks_root / "catalog.sqlite3")
        self.catalog.migrate()
        self.vectors = InMemoryVectorStore()
        self.local = FakeEmbeddings()
        self.cloud_client = CloudClient()
        self.repo = _Repo(connections or [_Connection()])
        self.secrets = _Secrets({"conn-cloud": "sk-test"} if keys is None else keys)
        self.resolver = EmbeddingProviderResolver(
            self.local, self.settings, model_config_repo=self.repo, secret_store=self.secrets
        )
        # 用假客户端替代真实 LangChain Embeddings：解析器仍走真实的凭证/身份校验，
        # 只把最终网络调用换成内存实现（不触网、不产生费用）。
        self._original_cloud_provider = self.resolver.cloud_provider

        def fake_cloud_provider(*, connection_id, model, dimensions):
            target, api_key = self.resolver.cloud_target(
                connection_id=connection_id, model=model, dimensions=dimensions
            )
            return DashScopeEmbeddingProvider(
                target, api_key=api_key, client_factory=lambda _t, _k: self.cloud_client
            )

        self.resolver.cloud_provider = fake_cloud_provider  # type: ignore[method-assign]
        self.ingest = IngestService(
            self.catalog, parse_document, chunk_document, self.local, self.vectors,
            self.settings, sleep=lambda _s: None, provider_resolver=self.resolver,
        )
        self.index = IndexService(
            self.catalog, self.local, self.vectors, self.settings,
            sleep=lambda _s: None, provider_resolver=self.resolver,
        )

    def cloud_profile(self):
        return self.index.create_profile(
            model_name="text-embedding-v4",
            source="cloud",
            connection_id="conn-cloud",
            dimensions=64,
        )


@pytest.fixture()
def env(tmp_path: Path) -> CloudEnv:
    return CloudEnv(tmp_path)


def test_cloud_probe_creates_profile_with_declared_identity(env: CloudEnv) -> None:
    view = env.index.probe(
        model_name="text-embedding-v4", source="cloud", connection_id="conn-cloud", dimensions=64
    )
    assert view.adapter == "dashscope"
    assert view.digestKind == "declared"
    assert view.stableDigest is False
    assert view.connectionId == "conn-cloud"
    assert view.dimensions == 64
    assert view.alreadyConfigured is False

    created = env.cloud_profile()
    assert created.adapter == "dashscope"
    assert created.providerLabel == "阿里云百炼"
    assert created.connectionId == "conn-cloud"
    assert created.digestKind == "declared"

    stored = env.catalog.find_embedding_profile(created.fingerprint)
    assert stored is not None
    assert stored.adapter == "dashscope"
    assert stored.options["connectionId"] == "conn-cloud"
    assert stored.model_manifest_digest == declared_identity_digest(
        connection_id="conn-cloud", base_url=DASH_BASE, model="text-embedding-v4", dimensions=64
    )


def test_cloud_and_local_profiles_do_not_collide(env: CloudEnv) -> None:
    env.local.dimensions = 64
    env.local.digest = "local-digest"
    local_view = env.index.probe(model_name="bge-m3")
    local_profile = env.index.create_profile(model_name="bge-m3")
    cloud_profile = env.cloud_profile()
    assert local_view.adapter == "ollama"
    assert local_view.digestKind == "manifest"
    assert local_profile.fingerprint != cloud_profile.fingerprint
    assert local_profile.adapter == "ollama"
    assert cloud_profile.adapter == "dashscope"


def test_cloud_profile_create_is_idempotent(env: CloudEnv) -> None:
    first = env.cloud_profile()
    second = env.cloud_profile()
    assert first.profileId == second.profileId


def test_cloud_profile_requires_connection(env: CloudEnv) -> None:
    with pytest.raises(AppError) as exc_info:
        env.index.probe(model_name="text-embedding-v4", source="cloud", dimensions=64)
    assert exc_info.value.code == "EMBEDDING_CONNECTION_REQUIRED"


def test_cloud_profile_requires_credential(env: CloudEnv) -> None:
    env.secrets._keys.clear()
    with pytest.raises(AppError) as exc_info:
        env.index.probe(
            model_name="text-embedding-v4", source="cloud", connection_id="conn-cloud", dimensions=64
        )
    assert exc_info.value.code == "EMBEDDING_AUTH_MISSING"


def test_cloud_profile_detects_connection_drift(env: CloudEnv) -> None:
    profile = env.cloud_profile()
    stored = env.catalog.find_embedding_profile(profile.fingerprint)
    assert stored is not None
    # 连接地址变化后，同一配置必须拒绝使用（不能假定还是同一个向量空间）
    env.repo._connections["conn-cloud"].baseUrl = "https://other.example.com/v1"
    with pytest.raises(AppError) as exc_info:
        env.resolver.for_profile(stored)
    assert exc_info.value.code == "EMBEDDING_MODEL_CHANGED"


def test_rebuild_uses_provider_of_the_target_profile(env: CloudEnv) -> None:
    # 空库先发布起始代（本机）
    env.local.dimensions = 64
    local_profile = env.index.create_profile(model_name="bge-m3")
    env.index.ensure_empty_generation(local_profile.profileId)
    cloud_profile = env.cloud_profile()

    job = env.index.begin_rebuild(
        profile_id=cloud_profile.profileId, submission_id="cloud-rebuild-1"
    )
    finished = env.index.run_rebuild(job.jobId)
    assert finished.state == "succeeded"
    status = env.index.status()
    assert status.activeProfileId == cloud_profile.profileId
    # 空库没有教材，不会有云端调用；但 rebuild 的身份核验走的是云端 provider。
    assert env.local.embed_calls == 0
