"""RAG v2 会话服务：事件编号与续传、断线不取消、澄清幂等、无证据不编造、状态分项。"""

from __future__ import annotations

import asyncio

import pytest

from app.core.exceptions import AppError
from app.schemas.rag_v2 import RagPoint
from app.services.rag_v2.requests import RagReplyRequestV2, RagStreamRequestV2
from app.services.rag_v2.service import RagV2Service
from tests.test_rag_v2_support import FakeSummarizer, RagEnv, sample_text


class EmptyRetrieval:
    """检索替身：永远没有候选，用于验证"无证据不编造"。"""

    dense_limit, lexical_limit, rrf_k = 50, 50, 60
    vectors = None
    embeddings = None

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def retrieve(self, **kwargs):
        self.calls.append(kwargs)
        return []


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


def make_env(tmp_path, *, summarizer=None, **kwargs) -> RagEnv:
    """默认现场：一册教材 + 替身概括/检索，保证范围可解析。"""
    env = RagEnv(
        tmp_path,
        summarizer=summarizer if summarizer is not None else FakeSummarizer(),
        **kwargs,
    )
    env.add_document(title="高中数学必修第一册", text=sample_text())
    return env


def stream_request(env: RagEnv, *, question: str = "集合的表示方法有哪些？", turn: str = "turn-1",
                   session: str = "session-1", after: int = 0, documents=None) -> RagStreamRequestV2:
    snapshot = env.snapshot(*(documents or tuple(env.documents.values())))
    return RagStreamRequestV2(
        requestId="request-1",
        sessionId=session,
        turnId=turn,
        question=question,
        scope={"kind": "frozen", "snapshot": snapshot},
        afterEventId=after,
    )


def selection_request(env: RagEnv, *, turn: str = "turn-1", question: str = "集合的表示方法") -> RagStreamRequestV2:
    return RagStreamRequestV2(
        requestId="request-1",
        sessionId="session-1",
        turnId=turn,
        question=question,
        scope={"kind": "selection", "selection": env.selection()},
        afterEventId=0,
    )


def reply_body(
    turn,
    *,
    submission: str = "submission-1",
    free_text: str = "请细讲并集",
    skipped: bool = False,
    interaction_id: str | None = None,
    question_id: str | None = None,
):
    card = turn.interaction or {}
    return RagReplyRequestV2(
        requestId="request-1",
        sessionId=turn.session_id,
        turnId=turn.turn_id,
        interactionId=interaction_id or card["interactionId"],
        submissionId=submission,
        answers=[
            {
                "questionId": question_id or card["questions"][0]["questionId"],
                "labels": [],
                "freeText": "" if skipped else free_text,
                "skipped": skipped,
            }
        ],
    )


@pytest.mark.asyncio
async def test_location_events_are_numbered_and_carry_scope_and_result(tmp_path):
    env = make_env(tmp_path)
    service = env.make_service()
    try:
        turn = service.start(selection_request(env))
        frames = await drain(service, turn, until="wait-user")
        assert [frame["id"] for frame in frames] == [1, 2, 3, 4]
        assert [frame["event"] for frame in frames] == [
            "message.start",
            "rag.result",
            "text.delta",
            "wait-user",
        ]
        start = frames[0]["data"]
        assert start["scopeSnapshot"]["schemaVersion"] == 2
        assert start["scopeSnapshot"]["scopeHash"] == turn.scope_snapshot.scopeHash
        assert start["sessionId"] == "session-1" and start["turnId"] == "turn-1"
        assert start["messageId"]

        result = frames[1]["data"]["result"]
        assert result["contractVersion"] == 2
        assert result["status"] == "ok"
        assert result["scopeSnapshot"] == start["scopeSnapshot"]
        assert result["points"] and result["points"][0]["evidenceIds"]
        assert result["evidence"] and result["evidence"][0]["text"]
        assert result["evidence"][0]["evidenceId"] in result["points"][0]["evidenceIds"]

        content = frames[2]["data"]["text"]
        assert result["points"][0]["title"] in content
        first_line = result["evidence"][0]["text"].splitlines()[0]
        assert f"> {first_line}" in content
        assert "教材外补充" not in content

        interaction = frames[3]["data"]
        assert interaction["interactionId"] and interaction["questions"][0]["questionId"]
        assert turn.state == "waiting"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_resume_after_event_id_replays_without_duplicates_and_conflicts_are_explicit(tmp_path):
    env = make_env(tmp_path)
    service = env.make_service()
    try:
        body = selection_request(env)
        turn = service.start(body)
        await drain(service, turn, until="wait-user")

        replayed = service.start(body.model_copy(update={"afterEventId": 2}))
        assert replayed is turn
        resumed = await drain(service, replayed, after=2, until="wait-user")
        assert [frame["id"] for frame in resumed] == [3, 4]
        assert not any(frame["id"] <= 2 for frame in resumed)

        with pytest.raises(AppError) as overflow:
            service.start(body.model_copy(update={"afterEventId": 99}))
        assert overflow.value.code == "RAG_EVENT_CONFLICT" and overflow.value.status_code == 409

        with pytest.raises(AppError) as mismatch:
            service.start(body.model_copy(update={"sessionId": "other-session"}))
        assert mismatch.value.code == "RAG_SESSION_MISMATCH" and mismatch.value.status_code == 403

        with pytest.raises(AppError) as conflict:
            service.start(body.model_copy(update={"question": "另一个问题"}))
        assert conflict.value.code == "RAG_TURN_CONFLICT"

        other_document = env.add_document(title="新增册", text=sample_text(title="函数"))
        moved = RagStreamRequestV2(
            requestId="request-1",
            sessionId="session-1",
            turnId="turn-1",
            question=body.question,
            scope={"kind": "frozen", "snapshot": env.snapshot(other_document)},
            afterEventId=0,
        )
        with pytest.raises(AppError) as scope_conflict:
            service.start(moved)
        assert scope_conflict.value.code == "RAG_TURN_CONFLICT"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_disconnect_does_not_cancel_but_explicit_cancel_ends_the_turn(tmp_path):
    env = make_env(tmp_path)
    service = env.make_service()
    try:
        turn = service.start(selection_request(env))
        first = await drain(service, turn, until="message.start")
        assert [frame["event"] for frame in first] == ["message.start"]
        await wait_for(lambda: turn.state == "waiting")
        assert not turn.cancel.is_set(), "断线不得取消本轮"

        assert service.cancel("session-1", "turn-1") == {"accepted": True}
        assert turn.cancel.is_set() and turn.terminal
        assert turn.events[-1]["event"] == "error"
        assert turn.events[-1]["data"]["code"] == "RAG_CANCELLED"
        # 取消后不能复活：同轮只能重放既有事件
        replayed = service.start(selection_request(env))
        assert replayed is turn
        assert [frame["id"] for frame in await drain(service, turn, after=len(turn.events) - 1)] == [
            len(turn.events)
        ]
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_reply_is_idempotent_and_relocates_inside_the_frozen_scope(tmp_path):
    env = make_env(tmp_path)
    service = env.make_service()
    try:
        turn = service.start(selection_request(env))
        await drain(service, turn, until="wait-user")
        first_scope = turn.scope_snapshot.scopeHash
        original_document = next(iter(env.documents.values()))

        body = reply_body(turn)
        assert service.reply(body) == {"accepted": True}
        assert service.reply(body) == {"accepted": True}, "同键同载荷必须返回原结果"
        with pytest.raises(AppError) as conflict:
            service.reply(
                body.model_copy(
                    update={"answers": [body.answers[0].model_copy(update={"freeText": "换了内容"})]}
                )
            )
        assert conflict.value.code == "IDEMPOTENCY_CONFLICT" and conflict.value.status_code == 409

        accepted = [event for event in turn.events if event["event"] == "reply.accepted"]
        assert len(accepted) == 1

        # 澄清重定位必须仍用本轮冻结的快照：期间改任教范围也不影响本轮
        moved = env.add_document(title="期间新增的册", text=sample_text(title="统计"))
        env.save_teaching_settings(env.selection(moved))
        await wait_for(lambda: turn.state == "waiting" and turn.round == 2)
        results = [event["data"]["result"] for event in turn.events if event["event"] == "rag.result"]
        assert len(results) == 2
        assert results[1]["scopeSnapshot"]["scopeHash"] == first_scope
        assert all(
            item["documentId"] == original_document.document_id for item in results[1]["evidence"]
        )
        assert "请细讲并集" in turn.clarifications

        # 跳过即结束本轮
        card = turn.interaction
        assert card is not None
        assert service.reply(reply_body(turn, submission="submission-2", skipped=True)) == {
            "accepted": True
        }
        assert turn.terminal and turn.events[-1]["event"] == "message.end"
        with pytest.raises(AppError) as closed:
            service.reply(
                reply_body(
                    turn,
                    submission="submission-3",
                    interaction_id=card["interactionId"],
                    question_id=card["questions"][0]["questionId"],
                )
            )
        assert closed.value.code == "RAG_TURN_CLOSED"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_no_evidence_never_fabricates_points_or_calls_summarizer(tmp_path):
    env = make_env(tmp_path)
    empty = EmptyRetrieval()
    service = env.make_service(retrieval=empty)
    try:
        turn = service.start(selection_request(env))
        frames = await drain(service, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        assert result["status"] == "no_evidence"
        assert result["points"] == [] and result["evidence"] == []
        assert "没有找到足够依据" in result["reason"]
        content = frames[2]["data"]["text"]
        assert "没有找到足够依据" in content
        assert "教材原文摘录" not in content
        assert empty.calls and empty.calls[0]["question"]
        assert env.summarizer.calls == [], "没有证据时不得调用概括模型"
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_summary_failure_keeps_verified_evidence_as_partial(tmp_path):
    unavailable = FakeSummarizer(unavailable=True)
    env = make_env(tmp_path, summarizer=unavailable)
    service = env.make_service()
    try:
        turn = service.start(selection_request(env))
        frames = await drain(service, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        assert result["status"] == "partial", "概括不可用不得降级成 no_evidence"
        assert result["points"] == []
        assert result["evidence"], "部分结果必须保留合法证据"
        assert "不可用" in result["reason"]
        assert "教材原文摘录" in frames[2]["data"]["text"]
        assert unavailable.calls
    finally:
        await service.close()

    # 非法/空输出 → partial 且保留证据
    empty_points = FakeSummarizer(points=[], reason="知识点概括未完成，保留教材原文供核对。")
    env2 = make_env(tmp_path / "empty", summarizer=empty_points)
    service2 = env2.make_service()
    try:
        turn = service2.start(selection_request(env2))
        frames = await drain(service2, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        assert result["status"] == "partial" and result["evidence"]
        assert result["points"] == [] and "概括未完成" in result["reason"]
    finally:
        await service2.close()

    # 概括抛出非"不可用"的错误 → 显式 error 事件，不伪装成无匹配
    broken = FakeSummarizer(error=AppError("解析失败", code="RAG_SUMMARY_BROKEN", status_code=502))
    env3 = make_env(tmp_path / "broken", summarizer=broken)
    service3 = env3.make_service()
    try:
        turn = service3.start(selection_request(env3))
        frames = await drain(service3, turn)
        assert [frame["event"] for frame in frames] == ["message.start", "error"]
        assert frames[-1]["data"]["code"] == "RAG_SUMMARY_BROKEN"
        assert not any(frame["event"] == "rag.result" for frame in frames)
    finally:
        await service3.close()


@pytest.mark.asyncio
async def test_ttl_expiry_and_service_restart_require_a_new_turn(tmp_path):
    env = make_env(tmp_path)
    service = env.make_service(ttl=0.05)
    try:
        turn = service.start(selection_request(env))
        await drain(service, turn, until="wait-user")
        await asyncio.sleep(0.07)
        with pytest.raises(AppError) as expired:
            service.start(selection_request(env))
        assert expired.value.code == "RAG_TURN_EXPIRED" and expired.value.status_code == 410
        assert turn.events[-1]["data"]["code"] == "RAG_TURN_EXPIRED"
        assert len(service.turns) == 0
        # 同 TTL 内旧轮恢复位置也必须显式过期，不偷偷重新推理
        with pytest.raises(AppError) as resume:
            service.start(selection_request(env).model_copy(update={"afterEventId": 2}))
        assert resume.value.code == "RAG_TURN_EXPIRED"
    finally:
        await service.close()

    restarted = env.make_service()
    try:
        with pytest.raises(AppError) as after_restart:
            restarted.start(selection_request(env).model_copy(update={"afterEventId": 1}))
        assert after_restart.value.code == "RAG_TURN_EXPIRED"
        # 重启后新轮可用
        fresh = restarted.start(selection_request(env, turn="turn-2"))
        await drain(restarted, fresh, until="wait-user")
        assert fresh.round == 1
    finally:
        await restarted.close()


@pytest.mark.asyncio
async def test_status_reports_retrieval_summarization_and_source_access_separately(tmp_path):
    env = make_env(tmp_path)
    service = env.make_service()
    try:
        status = await service.status()
        assert set(status) >= {
            "retrieval",
            "summarization",
            "sourceAccess",
            "scope",
            "generation",
            "humanQuality",
        }
        assert status["retrieval"]["available"] is True
        assert status["retrieval"]["denseLimit"] == 50 and status["retrieval"]["rrfK"] == 60
        assert status["summarization"]["available"] is True
        assert status["summarization"]["model"] == "qwen2.5:7b"
        assert status["summarization"]["providerUrl"] == "http://127.0.0.1:11434"
        assert status["sourceAccess"]["available"] is True
        assert status["scope"]["ready"] is False and "尚未保存" in status["scope"]["reason"]
        assert status["available"] is False, "未保存任教范围时整体不可用"
        assert status["generation"]["generationId"] == env.generation.generation_id
        assert status["generation"]["state"] == "ready"
        assert status["humanQuality"] == "not_run"

        env.save_teaching_settings(env.selection())
        refreshed = await service.status()
        assert refreshed["scope"]["ready"] is True
        assert refreshed["scope"]["selection"]["subjectId"] == "math"
        assert refreshed["available"] is True
        assert "localOnly" not in refreshed
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_status_reports_missing_dependencies_truthfully(tmp_path):
    env = RagEnv(tmp_path)
    empty_summarizer = FakeSummarizer(unavailable=True)
    service = RagV2Service(catalog=None, retrieval=None, summarizer=empty_summarizer, explainer=None)
    try:
        status = await service.status()
        assert status["retrieval"]["available"] is False
        assert "未装配" in status["retrieval"]["reason"]
        assert status["sourceAccess"]["available"] is False
        assert status["scope"]["ready"] is False
        assert status["generation"] is None
        assert status["summarization"]["available"] is False
        assert status["available"] is False
        with pytest.raises(AppError) as unassembled:
            service.start(
                RagStreamRequestV2(
                    requestId="request-1",
                    sessionId="session-1",
                    turnId="turn-1",
                    question="集合的表示方法",
                    scope={
                        "kind": "selection",
                        "selection": env.selection(document_ids=["document-without-catalog"]),
                    },
                    afterEventId=0,
                )
            )
        assert unassembled.value.code == "SERVICE_UNAVAILABLE"
        assert unassembled.value.status_code == 503
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_queue_full_and_capacity_are_bounded_and_explicit(tmp_path):
    env = make_env(tmp_path)
    service = env.make_service(queue_size=1, max_turns=1)
    try:
        turn = service.start(selection_request(env))
        await drain(service, turn, until="message.start")
        with pytest.raises(AppError) as capacity:
            service.start(selection_request(env, turn="turn-2"))
        assert capacity.value.code in {"RAG_CAPACITY", "RAG_QUEUE_FULL"}
        await wait_for(lambda: turn.state == "waiting")
        service.cancel("session-1", "turn-1")
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_points_with_unknown_evidence_ids_are_dropped_by_summarizer_contract(tmp_path):
    env = make_env(
        tmp_path,
        summarizer=FakeSummarizer(
            points=[
                RagPoint(
                    pointId="pt-forged",
                    title="编造的知识点",
                    summary="引用不存在的证据",
                    evidenceIds=["ev-0000000000000000"],
                )
            ],
            reason="知识点概括未通过原文引用校验，保留教材原文供核对。",
        ),
    )
    service = env.make_service()
    try:
        turn = service.start(selection_request(env))
        frames = await drain(service, turn, until="wait-user")
        result = frames[1]["data"]["result"]
        assert result["status"] == "partial"
        assert result["points"] == [] or all(
            set(point["evidenceIds"]) <= {item["evidenceId"] for item in result["evidence"]}
            for point in result["points"]
        )
        assert result["evidence"]
    finally:
        await service.close()
