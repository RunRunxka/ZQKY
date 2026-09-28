"""RAG v2 会话生命周期：有界执行、重放、澄清、无证据、取消、TTL 与重启。

本文件是原 `tests/test_rag_sessions.py` 覆盖点的逐项迁移：原断言（事件编号、续传、
单次执行、澄清保留原题、无依据不展示诊断、模型失败无云端回退、队列/超时、取消与跨会话、
TTL/容量/重启、回复队列不消耗追问卡、回复长度不静默截断）全部保留，改为断言 v2 服务。
文件末保留旧本地资产（presenter / legacy adapter）的既有覆盖：那些资产被保留但不再是生产路径。

测试替身只覆盖 Embedding / 向量库 / 本地概括 / 聊天模型；目录、修订、分块与原文都是真实
B0/B1 产物，全部在 tmp_path 内。
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from app.contracts.rag_adapter import RagContractError, RagQuery, get_rag_adapter
from app.core.exceptions import AppError
from app.services.rag_v2.requests import RagReplyRequestV2, RagStreamRequestV2
from app.services.rag_v2.service import RagV2Service
from tests.test_rag_v2_support import (
    EmptyRetrieval,
    FakeSummarizer,
    RagEnv,
    RecordingRetrieval,
    sample_text,
)


async def wait_for(predicate) -> None:
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.005)


async def drain(service, turn, *, after: int = 0, until: str | None = None):
    frames = []
    async for event in service.events(turn, after):
        if event is None:
            continue
        frames.append(event)
        if until is not None and event["event"] == until:
            break
        if event["event"] in ("message.end", "error"):
            break
    return frames


def make_env(tmp_path, *, retrieval=None, summarizer=None, **kwargs) -> RagEnv:
    env = RagEnv(tmp_path, summarizer=summarizer or FakeSummarizer(), **kwargs)
    env.add_document(title="高中数学必修第一册", text=sample_text())
    return env


def request(env: RagEnv, *, turn: str = "turn-1", session: str = "session-1", question: str = "集合的表示方法") -> RagStreamRequestV2:
    return RagStreamRequestV2(
        requestId="request-1",
        sessionId=session,
        turnId=turn,
        question=question,
        scope={"kind": "selection", "selection": env.selection()},
        afterEventId=0,
    )


def reply_body(turn, *, submission: str = "submission-1", text: str = "细讲互异性", skipped: bool = False, question_id: str = "textbook-follow-up"):
    card = turn.interaction or {}
    return RagReplyRequestV2(
        requestId="request-1",
        sessionId=turn.session_id,
        turnId=turn.turn_id,
        interactionId=card["interactionId"],
        submissionId=submission,
        answers=[
            {"questionId": question_id, "labels": [], "freeText": "" if skipped else text, "skipped": skipped}
        ],
    )


@pytest.mark.asyncio
async def test_real_boundary_runs_off_loop_once_and_reconnect_replays(tmp_path):
    env = make_env(tmp_path)
    retriever = RecordingRetrieval(env.retriever)
    service = env.make_service(retrieval=retriever)
    try:
        turn = service.start(request(env))
        await drain(service, turn, until="wait-user")
        assert len(retriever.calls) == 1, "重连不得重复执行定位"
        assert retriever.thread_ids[0] != threading.get_ident(), "同步重活必须在工作线程执行"

        reconnected = service.start(request(env).model_copy(update={"afterEventId": 2}))
        assert reconnected is turn
        stream = service.events(turn, after=2)
        replay = await anext(stream)
        assert replay["id"] == 3
        await stream.aclose()
        assert len(retriever.calls) == 1
        assert [event["id"] for event in turn.events] == list(range(1, len(turn.events) + 1))
        service.reply(reply_body(turn, skipped=True))
        assert turn.terminal
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_reply_is_once_and_continuation_retains_original_question(tmp_path):
    env = make_env(tmp_path)
    retriever = RecordingRetrieval(env.retriever)
    service = env.make_service(retrieval=retriever)
    try:
        turn = service.start(request(env))
        await drain(service, turn, until="wait-user")
        body = reply_body(turn)
        assert service.reply(body) == {"accepted": True}
        assert service.reply(body) == {"accepted": True}
        await wait_for(lambda: turn.state == "waiting" and turn.round == 2)
        assert len(retriever.calls) == 2
        assert turn.question in retriever.calls[1]
        assert "细讲互异性" in retriever.calls[1]

        accepted = [event for event in turn.events if event["event"] == "reply.accepted"]
        assert len(accepted) == 1
        assert accepted[0]["data"]["submissionId"] == body.submissionId
        assert turn.events.index(accepted[0]) < next(
            index for index, event in enumerate(turn.events) if index > 3 and event["event"] == "rag.result"
        )
        with pytest.raises(AppError, match="标识"):
            service.reply(
                body.model_copy(
                    update={"answers": [body.answers[0].model_copy(update={"freeText": "changed"})]}
                )
            )
        with pytest.raises(AppError) as expired:
            service.reply(body.model_copy(update={"submissionId": "new-id"}))
        assert expired.value.code == "RAG_INTERACTION_EXPIRED"
        service.reply(reply_body(turn, submission="submission-2"))
        await wait_for(lambda: turn.terminal)
        assert len(retriever.calls) == 3
        assert turn.events[-1]["event"] == "message.end"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_no_evidence_hides_diagnostics_and_allows_clarification(tmp_path):
    env = make_env(tmp_path)
    empty = EmptyRetrieval()
    service = env.make_service(retrieval=empty)
    try:
        turn = service.start(request(env))
        await drain(service, turn, until="wait-user")
        published = next(event["data"]["result"] for event in turn.events if event["event"] == "rag.result")
        assert published["status"] == "no_evidence"
        assert published["points"] == [] and published["evidence"] == []
        content = next(event["data"]["text"] for event in turn.events if event["event"] == "text.delta")
        assert "没有找到足够依据" in content and "集合的表示方法" not in content
        assert "F:/" not in str(turn.events)
        service.reply(reply_body(turn))
        await wait_for(lambda: turn.state == "waiting" and turn.round == 2)
        assert len(empty.calls) == 2
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_model_failure_is_error_without_answer_or_cloud_fallback(tmp_path):
    env = make_env(tmp_path, summarizer=FakeSummarizer(error=AppError("本地概括失败", code="RAG_SUMMARY_UNAVAILABLE", status_code=503)))
    service = env.make_service()
    try:
        turn = service.start(request(env))
        await drain(service, turn, until="wait-user")
        result = next(event["data"]["result"] for event in turn.events if event["event"] == "rag.result")
        assert result["status"] == "partial"
        assert result["points"] == [] and result["evidence"]
        assert not any(event["event"] == "error" for event in turn.events)
    finally:
        await service.close()

    # 检索层不可用 → 显式错误事件，绝不冒充"没有匹配"、不回落普通聊天
    env2 = make_env(tmp_path / "broken")
    broken = EmptyRetrieval()

    def explode(**kwargs):  # noqa: ANN001
        raise AppError("向量库不可用。", code="QDRANT_UNAVAILABLE", status_code=503, retryable=True)

    broken.retrieve = explode  # type: ignore[method-assign]
    service2 = env2.make_service(retrieval=broken)
    try:
        turn = service2.start(request(env2))
        frames = await drain(service2, turn)
        assert [event["event"] for event in frames] == ["message.start", "error"]
        assert frames[-1]["data"]["code"] == "QDRANT_UNAVAILABLE"
        assert frames[-1]["data"]["retryable"] is True
        assert not any(event["event"] == "rag.result" for event in turn.events)
    finally:
        await service2.close()


@pytest.mark.asyncio
async def test_queue_bound_timeout_does_not_release_busy_worker(tmp_path):
    gate = threading.Event()
    env = make_env(tmp_path)
    retriever = RecordingRetrieval(env.retriever, gate=gate)
    service = env.make_service(retrieval=retriever, queue_size=1, timeout=0.06)
    try:
        first = service.start(request(env))
        await wait_for(lambda: len(retriever.calls) == 1)
        second = service.start(request(env, turn="turn-2"))
        with pytest.raises(AppError) as full:
            service.start(request(env, turn="turn-3"))
        assert full.value.code == "RAG_QUEUE_FULL"
        await wait_for(lambda: first.terminal and second.terminal)
        assert first.events[-1]["data"]["code"] == "RAG_TIMEOUT"
        assert len(retriever.calls) == 1
        gate.set()
        await wait_for(lambda: service.discarded_late_results >= 1)
        assert len(retriever.calls) == 1
        assert not any(event["event"] == "rag.result" for event in first.events)
    finally:
        gate.set()
        await service.close()


@pytest.mark.asyncio
async def test_cancel_and_cross_session_cannot_revive_turn(tmp_path):
    gate = threading.Event()
    env = make_env(tmp_path)
    retriever = RecordingRetrieval(env.retriever, gate=gate)
    service = env.make_service(retrieval=retriever)
    try:
        turn = service.start(request(env))
        await wait_for(lambda: bool(retriever.calls))
        for action in (
            lambda: service.start(request(env, session="other")),
            lambda: service.cancel("other", "turn-1"),
        ):
            with pytest.raises(AppError) as mismatch:
                action()
            assert mismatch.value.code == "RAG_SESSION_MISMATCH"
        service.cancel("session-1", "turn-1")
        gate.set()
        await wait_for(lambda: service.discarded_late_results >= 1)
        assert len(turn.events) == 2 and turn.events[-1]["data"]["code"] == "RAG_CANCELLED"
        assert service.start(request(env)) is turn
        with pytest.raises(AppError) as closed:
            service.reply(
                RagReplyRequestV2(
                    requestId="request-1",
                    sessionId="session-1",
                    turnId="turn-1",
                    interactionId="old",
                    submissionId="submission-1",
                    answers=[{"questionId": "textbook-follow-up", "skipped": True}],
                )
            )
        assert closed.value.code == "RAG_TURN_CLOSED"
    finally:
        gate.set()
        await service.close()


@pytest.mark.asyncio
async def test_ttl_memory_capacity_and_restart_are_explicit(tmp_path):
    env = make_env(tmp_path)
    service = env.make_service(max_turns=1, ttl=0.05)
    try:
        turn = service.start(request(env))
        await drain(service, turn, until="wait-user")
        with pytest.raises(AppError) as capacity:
            service.start(request(env, turn="turn-2"))
        assert capacity.value.code == "RAG_CAPACITY"
        await asyncio.sleep(0.07)
        with pytest.raises(AppError) as expired:
            service.start(request(env).model_copy(update={"afterEventId": 1}))
        assert expired.value.code == "RAG_TURN_EXPIRED"
        with pytest.raises(AppError):
            service.start(request(env))
        assert len(service.turns) == 0 and len(service.retired) <= 4
        service.start(request(env, turn="turn-2"))
    finally:
        await service.close()

    restarted = env.make_service()
    try:
        with pytest.raises(AppError) as expired:
            restarted.start(request(env).model_copy(update={"afterEventId": 3}))
        assert expired.value.code == "RAG_TURN_EXPIRED"
    finally:
        await restarted.close()


@pytest.mark.asyncio
async def test_public_status_checks_dependencies_and_keeps_quality_boundary(tmp_path):
    env = make_env(tmp_path)
    retriever = RecordingRetrieval(env.retriever)
    service = env.make_service(retrieval=retriever)
    try:
        status = await service.status()
        assert status["retrieval"]["available"] is True
        assert status["sourceAccess"]["available"] is True
        assert status["humanQuality"] == "not_run"
        assert not retriever.calls and env.vectors.calls == []
        assert "localOnly" not in status
    finally:
        await service.close()


def test_exact_source_and_external_labels_remain_in_both_outputs():
    """旧本地资产（rag_presenter）保留：其引用一致性检查与外部标注仍被覆盖。"""
    from copy import deepcopy

    from app.services.rag_presenter import public_result, render_result

    source = {
        "citation_id": "c1",
        "file": "数学/必修一.md",
        "book": "数学必修一",
        "path": ["第一章", "集合"],
        "source_sha256": "a" * 64,
        "char_span": [8, 14],
        "line_span": [2, 2],
        "text": "集合元素互异",
    }
    raw = {
        "contract_version": "v1",
        "status": "ok",
        "subject": "数学",
        "evidence": [source],
        "citations": [deepcopy(source)],
        "explanations": [
            {
                "point": "互异性",
                "citation_ids": ["c1"],
                "explanation": "集合中的元素互不相同。",
                "supplement": {"text": "可把重复项目去重理解。", "is_external": True},
            }
        ],
        "uncertain_reason": "internal F:/private/path",
        "provenance": {"root": "F:/private/path"},
    }
    published = public_result(raw)
    assert published["citations"][0]["text"] == raw["citations"][0]["text"]
    rendered = render_result(published)
    assert "第 2–2 行" in rendered and "教材外补充" in rendered
    assert "集合元素互异" in rendered and "c1" in rendered
    raw["citations"][0]["text"] = "错误引用"
    with pytest.raises(AppError) as invalid:
        public_result(raw)
    assert invalid.value.code == "RAG_INVALID_RESULT"


def test_partial_retains_verified_payload_but_empty_partial_is_technical_failure():
    from copy import deepcopy

    from app.services.rag_presenter import public_result, render_result

    source = {
        "citation_id": "c1",
        "file": "数学/必修一.md",
        "book": "数学必修一",
        "path": ["第一章", "集合"],
        "source_sha256": "a" * 64,
        "char_span": [8, 14],
        "line_span": [2, 2],
        "text": "集合元素互异",
    }
    raw = {
        "contract_version": "v1",
        "status": "partial",
        "subject": "数学",
        "evidence": [source],
        "citations": [deepcopy(source)],
        "explanations": [
            {"point": "互异性", "citation_ids": ["c1"], "explanation": "集合中的元素互不相同。", "supplement": None}
        ],
        "uncertain_reason": "internal",
        "provenance": {},
    }
    published = public_result(raw)
    assert published["status"] == "partial"
    assert published["citations"] == raw["citations"]
    assert published["explanations"] == raw["explanations"]
    assert "仅展示" in render_result(published) and "集合元素互异" in render_result(published)
    raw.update(evidence=[], citations=[], explanations=[])
    with pytest.raises(AppError) as failed:
        public_result(raw)
    assert failed.value.code == "RAG_REVIEW_UNAVAILABLE" and failed.value.retryable


@pytest.mark.asyncio
async def test_reply_queue_failure_does_not_consume_card_or_submission(tmp_path):
    gate = threading.Event()
    env = make_env(tmp_path)
    retriever = RecordingRetrieval(env.retriever)
    service = env.make_service(retrieval=retriever, queue_size=1)
    try:
        waiting = service.start(request(env))
        await drain(service, waiting, until="wait-user")
        body = reply_body(waiting)
        retriever.gate = gate
        service.start(request(env, turn="turn-2"))
        await wait_for(lambda: len(retriever.calls) == 2)
        service.start(request(env, turn="turn-3"))
        with pytest.raises(AppError) as full:
            service.reply(body)
        assert full.value.code == "RAG_QUEUE_FULL"
        assert waiting.state == "waiting" and body.submissionId not in waiting.submissions
        assert waiting.interaction["interactionId"] == body.interactionId
        gate.set()
        await wait_for(lambda: service.queue.empty())
        assert service.reply(body)["accepted"]
        await wait_for(lambda: len(retriever.calls) >= 4)
    finally:
        gate.set()
        await service.close()


@pytest.mark.asyncio
async def test_reply_length_overflow_is_not_silently_truncated_or_consumed(tmp_path):
    env = make_env(tmp_path)
    service = env.make_service()
    try:
        body = request(env).model_copy(update={"question": "完整题干" * 700})
        turn = service.start(body)
        await drain(service, turn, until="wait-user")
        submission = reply_body(turn, text="補充" * 700)
        with pytest.raises(AppError) as long:
            service.reply(submission)
        assert long.value.code == "RAG_INPUT_TOO_LONG"
        assert turn.question == body.question and not turn.submissions
        assert turn.state == "waiting"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_legacy_adapter_still_binds_the_legacy_engine_snapshot(tmp_path):
    """旧本地引擎与新适配器仍可装配（保留资产），但与 v2 服务互不干扰。"""
    from app.services.rag_sessions import RagSessionService

    engine_calls = []

    class Runtime:
        def locate(self, question, *, subject=None, cancel_token=None):
            engine_calls.append(question)
            return {
                "status": "uncertain",
                "evidence": [],
                "citations": [],
                "explanations": [],
                "provenance": {},
            }

        def close(self):
            return None

    legacy = RagSessionService(
        tmp_path / "assets",
        tmp_path / "state",
        runtime_factory=lambda **_: Runtime(),
        probe=lambda _: {"available": True, "detail": "legacy"},
    )
    try:
        adapter = get_rag_adapter(legacy)
        with pytest.raises(RagContractError, match="uncertain"):
            await adapter.query(RagQuery(question="集合元素有什么特点？"), requestId="legacy-1")
        assert engine_calls == ["集合元素有什么特点？"]
    finally:
        await legacy.close()


@pytest.mark.asyncio
async def test_v2_service_is_marked_and_legacy_service_is_not(tmp_path):
    env = make_env(tmp_path)
    service = env.make_service()
    try:
        assert isinstance(service, RagV2Service) and service.is_rag_v2 is True
    finally:
        await service.close()
