"""D1（A1 r1）：查询路径必须校验 Embedding 清单身份，同名换权重不得继续检索。

写入路径一直有 digest 校验（B1）；这里锁定查询半边：

- `HybridRetriever._embed_query` 在**发起查询向量化之前**核一次、**算完向量之后**再核一次；
- 不一致 / 模型不在本机 / 适配器无核对能力 → 409 ``EMBEDDING_MODEL_CHANGED``，不返回向量、不检索；
- 服务本身不可达（``EMBEDDING_UNAVAILABLE``）原样抛出，两类失败可区分；
- 身份不符时**一次向量检索都没发生**（嵌入与向量库替身计数断言）。
"""

from __future__ import annotations

import pytest

from app.core.exceptions import AppError
from app.services.rag_v2.requests import RagStreamRequestV2
from app.services.rag_v2.retrieval import HybridRetriever
from app.services.rag_v2.scope import verify_scope
from tests.test_rag_v2_support import FakeEmbeddings, RagEnv, RecordingVectorStore

SAMPLE = "# 集合\n\n" + "集合的表示方法。" * 120 + "\n\n## 练习 1.1\n\n1. 求并集。\n"


class UnreachableEmbeddings(FakeEmbeddings):
    """Embedding 服务不可达：不是身份问题，错误码必须保持 EMBEDDING_UNAVAILABLE。"""

    def manifest_digest(self, model: str) -> str:
        raise AppError(
            "本地 Embedding 服务不可达。", code="EMBEDDING_UNAVAILABLE", status_code=503, retryable=True
        )


class NoIdentityEmbeddings(FakeEmbeddings):
    """适配器没有清单核对能力：不能证明身份 → 保守拒绝（不得静默继续）。"""

    manifest_digest = None  # type: ignore[assignment]


class MissingModelEmbeddings(FakeEmbeddings):
    """登记模型不在本机（同名 tag 被删/改名）。"""

    def manifest_digest(self, model: str) -> str:
        raise AppError("本地未安装模型。", code="EMBEDDING_MODEL_MISSING", status_code=404)


class SwitchingEmbeddings(FakeEmbeddings):
    """第一次核验通过；embed 之后同名 tag 被换权重 → 第二次核验失败。"""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.identity_checks = 0
        self.embed_calls = 0

    def manifest_digest(self, model: str) -> str:
        self.identity_checks += 1
        if self.embed_calls:
            return f"{self.digest}-changed"
        return self.digest

    def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        self.embed_calls += 1
        return super().embed(model=model, texts=texts)


def build_env(tmp_path, embeddings):
    """现场：目录里登记的 digest 是 ``DIGEST``，嵌入替身可以如实/不如实上报。"""
    env = RagEnv(tmp_path, embeddings=embeddings, vectors=RecordingVectorStore())
    env.add_document(title="高中数学必修第一册", text=SAMPLE)
    scope = verify_scope(env.catalog, env.snapshot())
    return env, scope


def retrieve(env: RagEnv, scope):
    return env.retriever.retrieve(
        question="集合的表示方法", scope=scope, profile=env.profile, generation=env.generation
    )


def test_digest_mismatch_is_rejected_before_any_embedding_or_vector_search(tmp_path):
    embeddings = FakeEmbeddings(digest="tampered-digest")
    env, scope = build_env(tmp_path, embeddings)
    assert embeddings.manifest_digest(env.profile.model_name) != env.profile.model_manifest_digest

    # A1 最小复现的形状：直接调 _embed_query 也必须被拒绝
    with pytest.raises(AppError) as blocked:
        env.retriever._embed_query(env.profile, "等差数列的通项公式")
    assert blocked.value.code == "EMBEDDING_MODEL_CHANGED"
    assert blocked.value.status_code == 409

    with pytest.raises(AppError) as retrieval_blocked:
        retrieve(env, scope)
    assert retrieval_blocked.value.code == "EMBEDDING_MODEL_CHANGED"
    assert embeddings.calls == [], "身份不符时不得调用嵌入接口"
    assert env.vectors.calls == [], "身份不符时不得发起向量检索"


def test_identity_swapped_during_embedding_is_rejected_after_the_call(tmp_path):
    embeddings = SwitchingEmbeddings()
    env, scope = build_env(tmp_path, embeddings)

    with pytest.raises(AppError) as switched:
        retrieve(env, scope)
    assert switched.value.code == "EMBEDDING_MODEL_CHANGED"
    assert switched.value.status_code == 409
    assert embeddings.identity_checks == 2, "embed 前后必须各核一次身份"
    assert embeddings.embed_calls == 1, "第二次核验失败发生在嵌入调用之后"
    assert env.vectors.calls == [], "第二次核验失败时不得使用该向量检索"


def test_identity_verification_does_not_break_the_normal_path(tmp_path):
    env = RagEnv(tmp_path, vectors=RecordingVectorStore())
    document = env.add_document(title="高中数学必修第一册", text=SAMPLE)
    scope = verify_scope(env.catalog, env.snapshot(document))
    candidates = retrieve(env, scope)
    assert candidates, "身份一致时检索必须正常工作"
    assert env.vectors.calls and env.vectors.calls[-1]["allowed"] is not None
    assert env.embeddings.calls and env.embeddings.calls[-1][0] == env.profile.model_name


def test_unreachable_embedding_service_keeps_its_own_error_code(tmp_path):
    env, scope = build_env(tmp_path, UnreachableEmbeddings())
    with pytest.raises(AppError) as unreachable:
        retrieve(env, scope)
    assert unreachable.value.code == "EMBEDDING_UNAVAILABLE", "服务不可达与身份不符必须可区分"
    assert env.vectors.calls == []


def test_model_missing_and_adapter_without_identity_capability_are_refused(tmp_path):
    env, scope = build_env(tmp_path, MissingModelEmbeddings())
    with pytest.raises(AppError) as missing:
        retrieve(env, scope)
    assert missing.value.code == "EMBEDDING_MODEL_CHANGED"

    env2, scope2 = build_env(tmp_path / "no-identity", NoIdentityEmbeddings())
    with pytest.raises(AppError) as unverifiable:
        retrieve(env2, scope2)
    assert unverifiable.value.code == "EMBEDDING_MODEL_CHANGED"
    assert env2.vectors.calls == []


@pytest.mark.asyncio
async def test_service_turn_reports_identity_error_without_result(tmp_path):
    from app.services.rag_v2.service import RagV2Service

    embeddings = FakeEmbeddings(digest="tampered-digest")
    env = RagEnv(tmp_path, embeddings=embeddings, vectors=RecordingVectorStore())
    env.add_document(title="高中数学必修第一册", text=SAMPLE)
    service = RagV2Service(
        catalog=env.catalog,
        retrieval=HybridRetriever(env.catalog, env.vectors, embeddings),
        summarizer=None,
        explainer=None,
    )
    try:
        turn = service.start(
            RagStreamRequestV2(
                requestId="request-1",
                sessionId="session-1",
                turnId="turn-1",
                question="集合的表示方法",
                scope={"kind": "selection", "selection": env.selection()},
                afterEventId=0,
            )
        )
        events = []
        async for event in service.events(turn):
            if event is None:
                continue
            events.append(event)
            if event["event"] in ("error", "message.end", "wait-user"):
                break
        assert [event["event"] for event in events] == ["message.start", "error"]
        assert events[-1]["data"]["code"] == "EMBEDDING_MODEL_CHANGED"
        assert not any(event["event"] == "rag.result" for event in events)
        assert env.vectors.calls == []
    finally:
        await service.close()
