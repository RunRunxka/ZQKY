"""P1（A1 r1）：`/rag/status` 的可用性必须真实探测上游，且探测慢也不能拖垮状态接口。

- Embedding：身份/可达（复用 provider 的清单能力）；向量库：ping；概括：**配置级检查**
  （只解析「全局默认问答模型」并判定云端，不向云端发起推理调用——概括只用云端档案）。
- 探测短超时（默认 2.5s，可用 ``probe_timeout`` 覆盖）、结果短暂缓存、失败只影响 available/reason。
- `scope.ready` 语义不变（任教范围 ≠ 上游健康）。
"""

from __future__ import annotations

import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppError
from app.main import create_app
from app.services.rag_v2.summary import KnowledgeSummarizer
from tests.conftest import make_settings
from tests.test_rag_v2_api import make_client
from tests.summary_support import SummaryWire
from tests.test_rag_v2_support import FakeEmbeddings, FakeSummarizer, RagEnv, sample_text


class UnreachableEmbeddings(FakeEmbeddings):
    def manifest_digest(self, model: str) -> str:
        raise AppError("本地 Embedding 服务不可达。", code="EMBEDDING_UNAVAILABLE", status_code=503)


class MismatchedEmbeddings(FakeEmbeddings):
    def __init__(self) -> None:
        super().__init__(digest="other-digest")
        self.probe_calls = 0

    def manifest_digest(self, model: str) -> str:
        self.probe_calls += 1
        return self.digest


class CountingEmbeddings(FakeEmbeddings):
    def __init__(self) -> None:
        super().__init__()
        self.probes = 0

    def manifest_digest(self, model: str) -> str:
        self.probes += 1
        return super().manifest_digest(model)


class SlowEmbeddings(FakeEmbeddings):
    def __init__(self, delay: float = 1.5) -> None:
        super().__init__()
        self.delay = delay

    def manifest_digest(self, model: str) -> str:
        time.sleep(self.delay)
        return super().manifest_digest(model)


class DeadVectorStore:
    """向量库不可达替身：ping False + 可读原因。"""

    calls = 0

    def __init__(self, names: list[str] | None = None) -> None:
        self.names = names or []
        self.search_calls = 0

    def ping(self) -> bool:
        return False

    def ping_error(self) -> str:
        return "连接被拒绝（测试替身）"

    def search(self, **kwargs):  # pragma: no cover - 状态用例不应检索
        self.search_calls += 1
        return []

    def count(self, **kwargs) -> int:
        return 0

    def collection_exists(self, name: str) -> bool:
        return name in self.names

    def ensure_collection(self, **kwargs) -> None: ...

    def upsert(self, **kwargs) -> None: ...

    def delete_by_filter(self, **kwargs) -> None: ...

    def delete_collection(self, name: str) -> None: ...


def test_embedding_upstream_down_or_mismatched_marks_retrieval_unavailable(tmp_path):
    dead = RagEnv(tmp_path / "dead", embeddings=UnreachableEmbeddings())
    dead.add_document(title="册", text=sample_text())
    service = dead.make_service()
    status = service._status_sync()
    assert status["retrieval"]["available"] is False
    assert "Embedding" in status["retrieval"]["reason"]
    assert status["scope"]["ready"] is False  # 未保存任教范围，与上游探测无关

    mismatched = RagEnv(tmp_path / "mismatch", embeddings=MismatchedEmbeddings())
    mismatched.add_document(title="册", text=sample_text())
    service2 = mismatched.make_service()
    status2 = service2._status_sync()
    assert status2["retrieval"]["available"] is False
    assert "身份" in status2["retrieval"]["reason"]


def test_vector_store_down_marks_retrieval_unavailable_with_reason(tmp_path):
    env = RagEnv(tmp_path, vectors=DeadVectorStore())
    env.add_document(title="册", text=sample_text())
    service = env.make_service()
    status = service._status_sync()
    assert status["retrieval"]["available"] is False
    assert "向量库不可达" in status["retrieval"]["reason"]
    assert "测试替身" in status["retrieval"]["reason"]


def test_reachable_upstreams_report_available_and_none_reason(tmp_path):
    env = RagEnv(tmp_path, summarizer=FakeSummarizer())
    env.add_document(title="册", text=sample_text())
    service = env.make_service()
    status = service._status_sync()
    assert status["retrieval"]["available"] is True
    assert status["retrieval"]["reason"] is None
    assert status["summarization"]["available"] is True
    assert status["summarization"]["reason"] is None


def test_status_scope_semantics_are_unchanged_when_upstream_is_down(tmp_path):
    env = RagEnv(tmp_path / "scope", embeddings=UnreachableEmbeddings())
    env.add_document(title="册", text=sample_text())
    env.save_teaching_settings(env.selection())
    service = env.make_service()
    status = service._status_sync()
    assert status["retrieval"]["available"] is False
    # 任教范围本身是合法的 → scope.ready 仍 True（范围 ≠ 上游健康）
    assert status["scope"]["ready"] is True
    assert status["available"] is False


def test_summarizer_probe_is_config_level_and_never_calls_upstream(tmp_path):
    """概括探测只做配置级检查：解析默认档案 + 判定云端，不发起推理调用。"""
    cloud_wire = SummaryWire()
    cloud = cloud_wire.summarizer()
    assert cloud.probe()["available"] is True
    assert "配置级检查" in cloud.probe()["detail"]
    assert cloud_wire.requests == [], "探测不得调用模型服务"

    # 未配置默认档案 / 默认是本机部署：探测只回报不可用，不抛错
    assert SummaryWire(profile_id=None).summarizer().probe()["available"] is False
    local = SummaryWire(provider_id="ollama").summarizer()
    assert local.probe()["available"] is False and "本机部署" in local.probe()["reason"]

    # 读取配置本身失败（非 AppError）也不得让状态接口抛错
    broken = SummaryWire(resolve_error=RuntimeError("boom")).summarizer()
    assert broken.probe()["available"] is False and broken.status()["available"] is False


def test_summarization_status_names_the_unavailable_reason(tmp_path):
    """概括不可用时，/rag/status 必须给出可读原因（本机默认档案 / 未配置默认档案）。"""
    env = RagEnv(tmp_path, summarizer=SummaryWire(provider_id="ollama").summarizer())
    env.add_document(title="册", text=sample_text())
    status = env.make_service()._status_sync()
    assert status["summarization"]["available"] is False
    assert "本机部署" in status["summarization"]["reason"]
    assert status["summarization"]["model"] is None

    env2 = RagEnv(tmp_path / "no-default", summarizer=SummaryWire(profile_id=None).summarizer())
    env2.add_document(title="册", text=sample_text())
    status2 = env2.make_service()._status_sync()
    assert status2["summarization"]["available"] is False
    assert "未配置全局默认问答模型" in status2["summarization"]["reason"]


def test_probe_timeout_is_bounded_and_status_still_returns(tmp_path):
    env = RagEnv(tmp_path, embeddings=SlowEmbeddings(delay=1.2), summarizer=FakeSummarizer())
    env.add_document(title="册", text=sample_text())
    service = env.make_service(probe_timeout=0.2, probe_cache_seconds=0.0)
    started = time.monotonic()
    status = service._status_sync()
    elapsed = time.monotonic() - started
    assert elapsed < 1.0, "探测必须短超时返回，不得被慢上游拖死"
    assert status["retrieval"]["available"] is False
    assert "超时" in status["retrieval"]["reason"]


def test_status_is_cached_briefly_and_probe_failures_never_raise(tmp_path):
    embeddings = CountingEmbeddings()
    env = RagEnv(tmp_path, embeddings=embeddings, summarizer=FakeSummarizer())
    env.add_document(title="册", text=sample_text())
    cached = env.make_service()
    cached._status_sync()
    first = embeddings.probes
    cached._status_sync()
    assert embeddings.probes == first, "短缓存窗口内不重复探测"

    uncached = env.make_service(probe_cache_seconds=0.0)
    uncached._status_sync()
    second = embeddings.probes
    uncached._status_sync()
    assert embeddings.probes == second + 1, "缓存关闭时每次状态都重新探测"

    # 上游探测抛非 AppError 异常也不得让状态失败
    class ExplodingEmbeddings(FakeEmbeddings):
        def manifest_digest(self, model: str) -> str:
            raise RuntimeError("boom")

    broken = RagEnv(tmp_path / "boom", embeddings=ExplodingEmbeddings())
    broken.add_document(title="册", text=sample_text())
    status = broken.make_service()._status_sync()
    assert status["retrieval"]["available"] is False and status["retrieval"]["reason"]


def test_rag_status_http_stays_200_when_probe_hangs(tmp_path):
    env = RagEnv(
        tmp_path / "http",
        embeddings=SlowEmbeddings(delay=1.2),
        summarizer=FakeSummarizer(),
    )
    env.add_document(title="册", text=sample_text())
    service = env.make_service(probe_timeout=0.2, probe_cache_seconds=0.0)
    with make_client(tmp_path, env, service=service) as client:
        started = time.monotonic()
        response = client.get("/api/v1/rag/status")
        elapsed = time.monotonic() - started
        assert response.status_code == 200
        assert elapsed < 3.0, "探测慢不得把状态接口拖慢"
        body = response.json()
        assert body["retrieval"]["available"] is False
        assert body["retrieval"]["reason"]
        assert body["humanQuality"] == "not_run"


def test_capabilities_reflects_unavailable_upstream(tmp_path):
    env = RagEnv(tmp_path / "caps", embeddings=UnreachableEmbeddings(), summarizer=FakeSummarizer())
    env.add_document(title="册", text=sample_text())
    service = env.make_service()
    app = create_app(make_settings(tmp_path), rag_service=service, bootstrap_textbooks=False)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        capabilities = client.get("/api/v1/capabilities").json()["capabilities"]
        rag = next(item for item in capabilities if item["feature"] == "rag")
        assert rag["status"] == "unavailable"
        assert "Embedding" in rag["detail"]
