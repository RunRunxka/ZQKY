"""详解：引用逐条核验、预算不截断、绝不调用检索、断开即关闭上游。"""

from __future__ import annotations

import pytest

from app.core.exceptions import AppError
from app.providers.llm.base import LLMConfig, LLMStreamEvent
from app.schemas.chat import MAX_TOTAL_CHARS
from app.schemas.model_config import ModelProtocol
from app.schemas.rag_v2 import EvidenceRef, RagExplainHistoryMessage, RagExplainRequest
from app.services.rag_v2.evidence import (
    build_evidence,
    evidence_id,
    rebuild_evidence_refs,
    sha256_utf8,
)
from app.services.rag_v2.explain import (
    ChatModelHandle,
    ExplainDelta,
    Explainer,
    build_explanation_request,
)
from app.services.rag_v2.retrieval import Candidate
from app.services.rag_v2.scope import verify_scope
from tests.test_rag_v2_support import FakeExplainer, RagEnv, long_body, sample_text

SINGLE_BODY_TEXT = (
    "# 集合\n\n" + "集合的表示方法。" * 120 + "\n\n## 练习 1.1\n\n1. 求并集。\n"
)


class ExplodingRetrieval:
    """详解绝不允许走到检索：被调用即视为失败。"""

    dense_limit, lexical_limit, rrf_k = 50, 50, 60
    vectors = None
    embeddings = None

    def __init__(self) -> None:
        self.calls = 0

    def retrieve(self, **kwargs):
        self.calls += 1
        raise AssertionError("详解不得再次自动检索")


class StubProvider:
    """真实 Explainer 的上游替身：产出文本增量并记录关闭次数。"""

    def __init__(self, deltas: tuple[str, ...] = ("教材依据说明。",), error: BaseException | None = None):
        self.deltas = deltas
        self.error = error
        self.requests = []
        self.closed = 0

    async def stream(self, config, request):
        self.requests.append(request)
        try:
            for text in self.deltas:
                yield LLMStreamEvent(type="text", text=text)
            if self.error is not None:
                raise self.error
            yield LLMStreamEvent(type="end", finishReason="stop")
        finally:
            self.closed += 1


def handle(provider, profile_id: str = "chat-profile-1") -> ChatModelHandle:
    return ChatModelHandle(
        profile_id=profile_id,
        model_id="chat-model-1",
        provider=provider,
        config=LLMConfig(
            protocol=ModelProtocol.openai_chat,
            baseUrl="http://127.0.0.1:11434",
            modelId="chat-model-1",
        ),
        max_output_tokens=512,
    )


def text_delta(value: str) -> ExplainDelta:
    return ExplainDelta(type="text", text=value)


def evidence_for(env: RagEnv, document):
    scope = verify_scope(env.catalog, env.snapshot(document))
    chunk = document.body_chunks()[0]
    candidate = Candidate(
        chunk_set_id=document.chunk_set_id,
        ordinal=chunk.ordinal,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        region=chunk.region,
        chapter_path=tuple(chunk.chapter_path),
        dense_rank=1,
        lexical_rank=None,
        fused_score=0.5,
        document_revision_id=document.revision_id,
    )
    evidence = build_evidence(catalog=env.catalog, scope=scope, candidates=[candidate])
    assert evidence
    return scope, evidence


def ref_for(item, **overrides) -> EvidenceRef:
    payload = {
        "evidenceId": item.evidenceId,
        "documentRevisionId": item.documentRevisionId,
        "normalizedTextSha256": item.normalizedTextSha256,
        "charStart": item.charStart,
        "charEnd": item.charEnd,
    }
    payload.update(overrides)
    return EvidenceRef(**payload)


def explain_body(env: RagEnv, document, refs, **overrides) -> RagExplainRequest:
    payload = {
        "requestId": "explain-request-1",
        "sessionId": "session-1",
        "turnId": "explain-turn-1",
        "modelProfileId": "chat-profile-1",
        "originalQuestion": "集合的表示方法有哪些？",
        "followUp": "请结合教材原文讲清并集的含义。",
        "scopeSnapshot": env.snapshot(document),
        "evidenceRefs": refs,
        "history": [],
    }
    payload.update(overrides)
    return RagExplainRequest(**payload)


@pytest.mark.asyncio
async def test_explain_streams_without_touching_retrieval_and_rebuilds_refs(tmp_path):
    env = RagEnv(tmp_path, explainer=FakeExplainer())
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    scope, evidence = evidence_for(env, document)
    refs = [ref_for(item) for item in evidence]
    exploding = ExplodingRetrieval()
    service = env.make_service(retrieval=exploding)

    body = explain_body(env, document, refs)
    frames = []
    async for name, data in service.explain(body):
        frames.append((name, data))

    assert [name for name, _data in frames] == ["message.start", "text.delta", "message.end"]
    assert frames[1][1]["text"] == "教材依据说明。"
    assert frames[2][1]["finishReason"] == "stop"
    assert frames[0][1]["modelProfileId"] == "chat-profile-1"
    assert "id" not in frames[0][1], "详解是普通聊天 SSE 语义，没有事件游标"

    assert exploding.calls == 0, "详解不得再次自动检索"
    assert env.vectors.calls == [], "详解不得触碰向量库（Qdrant 离线也应可详解）"
    assert env.explainer.frozen == ["chat-profile-1"], "点击时冻结模型，重试不偷偷换模型"
    sent = env.explainer.calls[0]["evidence"]
    assert [item.evidenceId for item in sent] == [item.evidenceId for item in evidence]
    assert sent[0].text == document.normalized_text[sent[0].charStart : sent[0].charEnd]


@pytest.mark.asyncio
async def test_explain_rejects_forged_refs_before_streaming(tmp_path):
    env = RagEnv(tmp_path, explainer=FakeExplainer())
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    _scope, evidence = evidence_for(env, document)
    item = evidence[0]
    service = env.make_service()

    forged = {
        "散列不符": ref_for(item, normalizedTextSha256="0" * 64),
        "区间越界": ref_for(item, charEnd=len(document.normalized_text) + 5),
        "引用标识不符": ref_for(item, evidenceId="ev-0000000000000000"),
    }
    for label, ref in forged.items():
        with pytest.raises(AppError) as rejected:
            async for _frame in service.explain(explain_body(env, document, [ref])):
                pass
        assert rejected.value.code == "RAG_EVIDENCE_UNAVAILABLE", label
        assert rejected.value.status_code == 409

    with pytest.raises(ValueError):
        # 契约层就拒绝倒置区间
        ref_for(item, charStart=item.charEnd, charEnd=item.charStart)

    assert env.explainer.calls == [], "核验失败不得调用任何模型"


@pytest.mark.asyncio
async def test_explain_rejects_deleted_document_and_out_of_scope_ref(tmp_path):
    env = RagEnv(tmp_path, explainer=FakeExplainer())
    inside = env.add_document(title="在范围内的册", text=sample_text())
    outside = env.add_document(title="不在范围内的一册", text=SINGLE_BODY_TEXT)
    _scope, inside_evidence = evidence_for(env, inside)
    _other_scope, outside_evidence = evidence_for(env, outside)
    service = env.make_service()

    # ① 范围仍然有效，但引用不属于该范围 → RAG_EVIDENCE_UNAVAILABLE（不自动替换引用）
    with pytest.raises(AppError) as foreign:
        async for _frame in service.explain(
            explain_body(env, inside, [ref_for(outside_evidence[0])])
        ):
            pass
    assert foreign.value.code == "RAG_EVIDENCE_UNAVAILABLE"
    assert foreign.value.status_code == 409

    # ② 文档已删 → 范围核验先失败（不静默替换引用，也不偷偷重新定位）
    dead_snapshot = env.snapshot(inside)
    record = env.catalog.get_document(inside.document_id)
    env.catalog.delete_document(inside.document_id, expected_revision=record.revision)
    with pytest.raises(AppError) as deleted:
        async for _frame in service.explain(
            explain_body(env, inside, [ref_for(inside_evidence[0])], scopeSnapshot=dead_snapshot)
        ):
            pass
    assert deleted.value.code == "RAG_SCOPE_CHANGED"
    assert deleted.value.status_code == 409


def test_rebuild_refs_maps_deleted_document_to_evidence_unavailable(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="册", text=SINGLE_BODY_TEXT)
    scope, evidence = evidence_for(env, document)
    refs = [ref_for(evidence[0])]

    class DeadDocumentCatalog:
        """替身：范围核验通过但文档在读取阶段已失效。"""

        def __init__(self, inner) -> None:
            self.inner = inner

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def require_live_document(self, document_id):
            raise AppError("文档已删除。", code="DOCUMENT_NOT_FOUND", status_code=404)

    with pytest.raises(AppError) as gone:
        rebuild_evidence_refs(catalog=DeadDocumentCatalog(env.catalog), scope=scope, refs=refs)
    assert gone.value.code == "RAG_EVIDENCE_UNAVAILABLE"
    assert gone.value.status_code == 409


def test_budget_drops_oldest_history_and_never_truncates_question_or_evidence(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="册", text=SINGLE_BODY_TEXT)
    _scope, evidence = evidence_for(env, document)
    refs = [ref_for(item) for item in evidence]
    model = handle(StubProvider())

    long_question = "原题：" + "集合的表示方法有哪些？" * 40
    history = [
        RagExplainHistoryMessage(role="user", content=f"历史{index}：" + "。" * 30000)
        for index in range(5)
    ]
    body = explain_body(
        env,
        document,
        refs,
        originalQuestion=long_question,
        followUp="请结合原文讲清并集。",
        history=history,
    )
    messages, budget = build_explanation_request(body=body, evidence=evidence, model=model)
    assert budget.dropped_history == 2, "超限时从最旧开始整条丢弃历史"
    assert budget.total_chars <= MAX_TOTAL_CHARS and budget.message_count <= budget.max_messages
    joined = "\n".join(message.content for message in messages)
    assert long_question in joined, "原题不得截断"
    assert body.followUp in joined
    assert refs[0].evidenceId in joined and evidence[0].text[:40] in joined
    assert "历史4：" in joined and "历史0：" not in joined and "历史1：" not in joined

    # 未超限时一条历史也不丢，且最新历史保留
    small_history = [
        RagExplainHistoryMessage(role="user", content="较早的历史" + "。" * 400),
        RagExplainHistoryMessage(role="assistant", content="最新的历史" + "。" * 40),
    ]
    messages, budget = build_explanation_request(
        body=body.model_copy(update={"history": small_history}),
        evidence=evidence,
        model=model,
    )
    assert budget.dropped_history == 0
    assert "最新的历史" in "\n".join(message.content for message in messages)

    # 原题 + 追问 + 证据本身超硬上限 → 413，且不返回被截断的请求
    oversized = [item for item in evidence for _ in range(200)]
    with pytest.raises(AppError) as too_large:
        build_explanation_request(body=body, evidence=oversized, model=model)
    assert too_large.value.code == "CONTEXT_TOO_LARGE"
    assert too_large.value.status_code == 413


@pytest.mark.asyncio
async def test_explain_service_surfaces_budget_error_before_streaming(tmp_path):
    """长正文：单条引用本身合法（历史详解不套首答窗口），20 条合计超过 120,000 字符硬上限。"""
    env = RagEnv(tmp_path, explainer=FakeExplainer())
    document = env.add_document(
        title="长正文册",
        text="# 第一章 集合\n\n" + long_body("集合", paragraphs=60, sentences=8) + "\n\n## 练习 1.1\n\n1. 求并集。\n",
    )
    scope = verify_scope(env.catalog, env.snapshot(document))
    body = document.body_chunks()
    big_ref = EvidenceRef(
        evidenceId=evidence_id(document.revision_id, body[0].char_start, body[-1].char_end),
        documentRevisionId=document.revision_id,
        normalizedTextSha256=sha256_utf8(document.normalized_text),
        charStart=body[0].char_start,
        charEnd=body[-1].char_end,
    )
    rebuilt = rebuild_evidence_refs(catalog=env.catalog, scope=scope, refs=[big_ref])
    assert len(rebuilt[0].text) > 5_000, "本用例依赖足够长的单条证据"
    service = env.make_service()
    body_request = explain_body(env, document, [big_ref] * 20)

    with pytest.raises(AppError) as too_large:
        async for _frame in service.explain(body_request):
            pass
    assert too_large.value.code == "CONTEXT_TOO_LARGE"
    assert too_large.value.status_code == 413
    assert env.explainer.calls == [], "流开始前的预算失败不得调用模型"


@pytest.mark.asyncio
async def test_service_closing_explain_generator_closes_upstream(tmp_path):
    env = RagEnv(
        tmp_path,
        explainer=FakeExplainer(deltas=(text_delta("第一段"), text_delta("第二段"))),
    )
    document = env.add_document(title="册", text=SINGLE_BODY_TEXT)
    _scope, evidence = evidence_for(env, document)
    service = env.make_service()
    body = explain_body(env, document, [ref_for(item) for item in evidence])

    generator = service.explain(body)
    first = await generator.__anext__()
    assert first[0] == "message.start"
    second = await generator.__anext__()
    assert second[0] == "text.delta"
    await generator.aclose()
    assert env.explainer.closed == 1, "断开/停止必须关闭上游"

    # 上游流中错误 → error 事件，不伪装成正常结束
    env.explainer.error = AppError("上游中断", code="UPSTREAM_ERROR", status_code=502)
    frames = []
    async for name, data in service.explain(body):
        frames.append((name, data))
    assert [name for name, _data in frames] == ["message.start", "error"]
    assert frames[-1][1]["code"] == "UPSTREAM_ERROR"


@pytest.mark.asyncio
async def test_real_explainer_streams_provider_deltas_and_closes_on_stop(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="册", text=SINGLE_BODY_TEXT)
    _scope, evidence = evidence_for(env, document)
    provider = StubProvider(deltas=("甲。", "乙。"))
    explainer = Explainer(lambda profile_id: handle(provider, profile_id))
    body = explain_body(env, document, [ref_for(item) for item in evidence])

    stream = explainer.explain(body, evidence=evidence, model=explainer.freeze_model("chat-profile-1"))
    assert await stream.__anext__() == text_delta("甲。")
    await stream.aclose()
    assert provider.closed == 1, "提前停止必须关闭上游请求"
    assert provider.requests and provider.requests[0].maxOutputTokens == 512

    full = [
        delta
        async for delta in explainer.explain(
            body, evidence=evidence, model=explainer.freeze_model("chat-profile-1")
        )
    ]
    assert [delta.type for delta in full] == ["text", "text", "end"]
    assert full[-1].finishReason == "stop"

    with pytest.raises(AppError) as unassembled:
        Explainer(None).freeze_model("chat-profile-1")
    assert unassembled.value.code == "SERVICE_UNAVAILABLE"
    assert unassembled.value.status_code == 503
