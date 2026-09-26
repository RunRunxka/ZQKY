"""Local test doubles exercise lifecycle boundaries; these are not teaching-quality tests."""

import asyncio
from copy import deepcopy
import threading
import time

import pytest

from app.contracts.rag_adapter import RagContractError, RagQuery, get_rag_adapter
from app.core.exceptions import AppError
from app.schemas.rag import RagReplyRequest, RagStreamRequest
from app.services.rag_presenter import public_result, render_result
from app.services.rag_sessions import RagSessionService


def result(status="ok"):
    source = {
        "citation_id": "c1", "file": "数学/必修一.md", "book": "数学必修一",
        "path": ["第一章", "集合"], "source_sha256": "a" * 64,
        "char_span": [8, 14], "line_span": [2, 2], "text": "集合元素互异",
    }
    return {
        "contract_version": "v1", "status": status, "subject": "数学",
        "evidence": [source], "citations": [deepcopy(source)],
        "explanations": [{"point": "互异性", "citation_ids": ["c1"],
                          "explanation": "集合中的元素互不相同。",
                          "supplement": {"text": "可把重复项目去重理解。", "is_external": True}}],
        "uncertain_reason": "internal F:/private/path", "provenance": {"root": "F:/private/path"},
    }


class Runtime:
    def __init__(self, *, status="ok", gate=None):
        self.status, self.gate = status, gate
        self.calls = []
        self.thread_ids = []
        self.closed = False

    def locate(self, question, *, subject=None, cancel_token=None):
        self.calls.append((question, subject))
        self.thread_ids.append(threading.get_ident())
        if self.gate:
            self.gate.wait(3)
        return result(self.status)

    def close(self):
        self.closed = True


def make_service(tmp_path, runtime=None, **kwargs):
    engine = runtime or Runtime()
    constructions = []

    def factory(**paths):
        constructions.append(paths)
        return engine

    service = RagSessionService(tmp_path / "assets", tmp_path / "state", runtime_factory=factory,
                                probe=lambda _: {"available": True, "detail": "测试替身依赖正常。"}, **kwargs)
    return service, engine, constructions


def request(turn="turn-1", session="session-1", **kwargs):
    return RagStreamRequest(requestId="request-1", sessionId=session, turnId=turn,
                            question="集合元素有什么特点？", **kwargs)


async def wait_for(predicate):
    async with asyncio.timeout(3):
        while not predicate():
            await asyncio.sleep(.005)


def reply(turn, submission="submission-1", *, skip=False, text="细讲互异性", **kwargs):
    return RagReplyRequest(
        sessionId=turn.session_id, turnId=turn.turn_id,
        interactionId=turn.interaction["interactionId"], submissionId=submission,
        answers=[{"questionId": "textbook-follow-up", "labels": [],
                  "freeText": "" if skip else text, "skipped": skip}], **kwargs,
    )


@pytest.mark.asyncio
async def test_real_boundary_runs_off_loop_once_and_reconnect_replays(tmp_path):
    service, runtime, builds = make_service(tmp_path)
    try:
        turn = service.start(request())
        await wait_for(lambda: turn.state == "waiting")
        assert len(runtime.calls) == len(builds) == 1
        assert runtime.thread_ids == [runtime.thread_ids[0]]
        assert runtime.thread_ids[0] != threading.get_ident()
        reconnected = service.start(request(afterEventId=2))
        assert reconnected is turn
        stream = service.events(turn, after=2)
        replay = await anext(stream)
        assert replay["id"] == 3
        await stream.aclose()
        service.reply(reply(turn, skip=True))
        assert turn.terminal
        assert len(runtime.calls) == 1
        assert [e["id"] for e in turn.events] == list(range(1, len(turn.events) + 1))
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_reply_is_once_and_continuation_retains_original_question(tmp_path):
    service, runtime, builds = make_service(tmp_path)
    try:
        turn = service.start(request())
        await wait_for(lambda: turn.state == "waiting")
        body = reply(turn)
        assert service.reply(body) == {"accepted": True}
        assert service.reply(body) == {"accepted": True}
        await wait_for(lambda: turn.state == "waiting")
        assert len(runtime.calls) == 2 and len(builds) == 1
        assert runtime.calls[0][0] in runtime.calls[1][0]
        assert "细讲互异性" in runtime.calls[1][0]
        accepted = [e for e in turn.events if e["event"] == "reply.accepted"]
        assert len(accepted) == 1
        assert accepted[0]["data"]["submissionId"] == body.submissionId
        assert turn.events.index(accepted[0]) < next(i for i,e in enumerate(turn.events) if i > 3 and e["event"] == "rag.result")
        with pytest.raises(AppError, match="标识"):
            service.reply(body.model_copy(update={"answers": [body.answers[0].model_copy(update={"freeText": "changed"})]}))
        with pytest.raises(AppError) as expired:
            service.reply(body.model_copy(update={"submissionId": "new-id"}))
        assert expired.value.code == "RAG_INTERACTION_EXPIRED"
        service.reply(reply(turn, "submission-2"))
        await wait_for(lambda: turn.terminal)
        assert len(runtime.calls) == 3
        assert turn.events[-1]["event"] == "message.end"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_uncertain_hides_diagnostic_sources_and_allows_clarification(tmp_path):
    service, runtime, _ = make_service(tmp_path, Runtime(status="uncertain"))
    try:
        turn = service.start(request())
        await wait_for(lambda: turn.state == "waiting")
        published = next(e["data"]["result"] for e in turn.events if e["event"] == "rag.result")
        assert published["status"] == "uncertain"
        assert published["evidence"] == published["citations"] == published["explanations"] == []
        content = next(e["data"]["text"] for e in turn.events if e["event"] == "text.delta")
        assert "证据不足" in content and "集合元素互异" not in content
        assert "F:/" not in str(turn.events)
        runtime.status = "ok"
        service.reply(reply(turn))
        await wait_for(lambda: turn.state == "waiting")
        assert len(runtime.calls) == 2
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_model_failure_is_error_without_answer_or_cloud_fallback(tmp_path):
    service, runtime, _ = make_service(tmp_path, Runtime(status="model_unavailable"))
    try:
        turn = service.start(request())
        await wait_for(lambda: turn.terminal)
        assert [e["event"] for e in turn.events] == ["message.start", "error"]
        assert turn.events[-1]["data"]["code"] == "RAG_MODEL_UNAVAILABLE"
        assert len(runtime.calls) == 1
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_queue_bound_timeout_does_not_release_busy_worker(tmp_path):
    gate = threading.Event()
    service, runtime, _ = make_service(tmp_path, Runtime(gate=gate), queue_size=1, timeout=.06)
    try:
        first = service.start(request())
        await wait_for(lambda: len(runtime.calls) == 1)
        second = service.start(request("turn-2"))
        with pytest.raises(AppError) as full:
            service.start(request("turn-3"))
        assert full.value.code == "RAG_QUEUE_FULL"
        await wait_for(lambda: first.terminal and second.terminal)
        assert first.events[-1]["data"]["code"] == "RAG_TIMEOUT"
        assert len(runtime.calls) == 1
        gate.set()
        await wait_for(lambda: service.discarded_late_results == 1)
        assert len(runtime.calls) == 1
        assert not any(e["event"] == "rag.result" for e in first.events)
    finally:
        gate.set()
        await service.close()


@pytest.mark.asyncio
async def test_cancel_and_cross_session_cannot_revive_turn(tmp_path):
    gate = threading.Event()
    service, runtime, _ = make_service(tmp_path, Runtime(gate=gate))
    try:
        turn = service.start(request())
        await wait_for(lambda: bool(runtime.calls))
        for action in (lambda: service.start(request(session="other")),
                       lambda: service.cancel("other", "turn-1")):
            with pytest.raises(AppError) as mismatch:
                action()
            assert mismatch.value.code == "RAG_SESSION_MISMATCH"
        service.cancel("session-1", "turn-1")
        gate.set()
        await wait_for(lambda: service.discarded_late_results == 1)
        assert len(turn.events) == 2 and turn.events[-1]["data"]["code"] == "RAG_CANCELLED"
        assert service.start(request()) is turn
        with pytest.raises(AppError) as closed:
            service.reply(RagReplyRequest(sessionId="session-1", turnId="turn-1", interactionId="old",
                          submissionId="submission-1", answers=[{"questionId": "textbook-follow-up", "skipped": True}]))
        assert closed.value.code == "RAG_TURN_CLOSED"
    finally:
        gate.set()
        await service.close()


@pytest.mark.asyncio
async def test_ttl_memory_capacity_and_restart_are_explicit(tmp_path):
    service, _, _ = make_service(tmp_path, max_turns=1, ttl=.05)
    try:
        turn = service.start(request())
        await wait_for(lambda: turn.state == "waiting")
        with pytest.raises(AppError) as capacity:
            service.start(request("turn-2"))
        assert capacity.value.code == "RAG_CAPACITY"
        await asyncio.sleep(.07)
        with pytest.raises(AppError) as expired:
            service.start(request(afterEventId=1))
        assert expired.value.code == "RAG_TURN_EXPIRED"
        with pytest.raises(AppError):
            service.start(request())
        assert len(service.turns) == 0 and len(service.retired) <= 4
        service.start(request("turn-2"))
    finally:
        await service.close()
    restarted, _, _ = make_service(tmp_path)
    try:
        with pytest.raises(AppError) as expired:
            restarted.start(request(afterEventId=3))
        assert expired.value.code == "RAG_TURN_EXPIRED"
    finally:
        await restarted.close()


@pytest.mark.asyncio
async def test_public_status_checks_dependencies_and_keeps_quality_boundary(tmp_path):
    service, runtime, builds = make_service(tmp_path)
    try:
        status = await service.status()
        assert status["available"] and status["localOnly"]
        assert status["humanQuality"] == "not_run"
        assert not runtime.calls and not builds
    finally:
        await service.close()


def test_exact_source_and_external_labels_remain_in_both_outputs():
    raw = result()
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
    raw = result("partial")
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
    service, runtime, _ = make_service(tmp_path, queue_size=1)
    gate = threading.Event()
    try:
        waiting = service.start(request())
        await wait_for(lambda: waiting.state == "waiting")
        body = reply(waiting)
        runtime.gate = gate
        service.start(request("turn-2"))
        await wait_for(lambda: len(runtime.calls) == 2)
        service.start(request("turn-3"))
        with pytest.raises(AppError) as full:
            service.reply(body)
        assert full.value.code == "RAG_QUEUE_FULL"
        assert waiting.state == "waiting" and body.submissionId not in waiting.submissions
        assert waiting.interaction["interactionId"] == body.interactionId
        gate.set()
        await wait_for(lambda: service.queue.empty())
        assert service.reply(body)["accepted"]
        await wait_for(lambda: len(runtime.calls) == 4)
    finally:
        gate.set()
        await service.close()


@pytest.mark.asyncio
async def test_reply_length_overflow_is_not_silently_truncated_or_consumed(tmp_path):
    service, _, _ = make_service(tmp_path)
    try:
        body = request().model_copy(update={"question": "完整题干" * 700})
        turn = service.start(body)
        await wait_for(lambda: turn.state == "waiting")
        submission = reply(turn, text="補充" * 700)
        with pytest.raises(AppError) as long:
            service.reply(submission)
        assert long.value.code == "RAG_INPUT_TOO_LONG"
        assert turn.question == body.question and not turn.submissions
        assert turn.state == "waiting"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_legacy_adapter_binds_app_and_refuses_lossy_uncertain_mapping(tmp_path):
    service, runtime, _ = make_service(tmp_path)
    try:
        adapter = get_rag_adapter(service)
        answer = await adapter.query(RagQuery(question="集合元素有什么特点？"), requestId="legacy-1")
        assert answer.status == "ok" and answer.citations[0].charStart == 8
        runtime.status = "uncertain"
        with pytest.raises(RagContractError, match="uncertain"):
            await adapter.query(RagQuery(question="集合元素有什么特点？"), requestId="legacy-2")
    finally:
        await service.close()
