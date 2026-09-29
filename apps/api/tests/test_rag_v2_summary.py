"""本地知识点概括：结构化输出校验、失败分类与"只允许本机回环"。

真实 Ollama 调用留给总控集成验收；这里注入 HTTP 替身覆盖全部分支。
"""

from __future__ import annotations

import json

import pytest

import httpx

from app.core.exceptions import AppError
from app.services.rag_v2.evidence import build_evidence
from app.services.rag_v2.retrieval import Candidate
from app.services.rag_v2.scope import verify_scope
from app.services.rag_v2.summary import (
    INSTRUCTION,
    KnowledgeSummarizer,
    choose_complete_valid_points,
    filter_points,
    validate_points,
)
from tests.test_rag_v2_support import RagEnv, sample_text


class StubResponse:
    def __init__(self, *, status_code: int = 200, payload: object = None, invalid_json: bool = False):
        self.status_code = status_code
        self.payload = payload
        self.invalid_json = invalid_json
        self.text = "" if payload is None else str(payload)

    def json(self):
        if self.invalid_json:
            raise ValueError("not json")
        return self.payload


class StubClient:
    def __init__(self, outcome) -> None:
        self.outcome = outcome
        self.requests: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def post(self, path: str, json=None, **kwargs):  # noqa: A002 - httpx 关键字
        self.requests.append((path, json))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    def get(self, path: str, **kwargs):
        """状态探测走 GET /api/tags；同一个替身支持两种调用。"""
        self.requests.append((path, None))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def evidence_of(env: RagEnv, document):
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
    return build_evidence(catalog=env.catalog, scope=scope, candidates=[candidate])


def make_summarizer(outcome, **kwargs) -> tuple[KnowledgeSummarizer, StubClient]:
    client = StubClient(outcome)
    summarizer = KnowledgeSummarizer(
        provider_url="http://127.0.0.1:11434",
        client_factory=lambda **_: client,
        **kwargs,
    )
    return summarizer, client


def test_summarizer_parses_structured_points_and_keeps_prompt_grounded(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    proposal = {
        "points": [
            {
                "title": "并集",
                "summary": "由所有属于 A 或属于 B 的元素组成的集合。",
                "evidenceIds": [evidence[0].evidenceId],
            }
        ]
    }
    summarizer, client = make_summarizer(
        StubResponse(payload={"message": {"content": json.dumps(proposal, ensure_ascii=False)}})
    )

    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert [point.title for point in outcome.points] == ["并集"]
    assert outcome.points[0].evidenceIds == [evidence[0].evidenceId]
    assert outcome.reason is None

    path, payload = client.requests[0]
    assert path == "/api/chat"
    assert payload["model"] == "qwen2.5:7b"
    assert payload["format"] == "json" and payload["stream"] is False
    assert payload["messages"][0]["content"] == INSTRUCTION
    user_prompt = payload["messages"][1]["content"]
    assert "并集是什么？" in user_prompt
    assert evidence[0].evidenceId in user_prompt
    assert evidence[0].text[:40] in user_prompt
    assert "不提供完整解题推导" in payload["messages"][0]["content"]


def test_summarizer_rejects_points_with_not_admitted_evidence_ids(tmp_path):
    """引用不在准入集合内的证据 → **整个点**拒绝；修正一次后仍非法 → 保留完整合法点。"""
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    proposal = {
        "points": [
            {"title": "编造", "summary": "引用不存在证据", "evidenceIds": ["ev-0000000000000000"]},
            {"title": "", "summary": "空标题", "evidenceIds": [evidence[0].evidenceId]},
            {"title": "空摘要", "summary": "   ", "evidenceIds": [evidence[0].evidenceId]},
            {"title": "合法", "summary": "有原文依据的要点。", "evidenceIds": [evidence[0].evidenceId]},
        ]
    }
    summarizer, client = make_summarizer(
        StubResponse(payload={"message": {"content": json.dumps(proposal, ensure_ascii=False)}})
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert [point.title for point in outcome.points] == ["合法"]
    assert outcome.dropped == 3
    assert outcome.reason_code == "SUMMARY_PARTIAL"
    assert outcome.corrected == 1, "非法输出必须触发且只触发一次修正"
    assert len(client.requests) == 2, "模型总调用次数 = 首次 + 一次修正"
    assert "引用了未进入提示词的证据" in outcome.reason
    assert outcome.admitted_evidence_ids == frozenset({evidence[0].evidenceId})


def test_summarizer_never_reuses_a_point_whose_reference_was_rejected(tmp_path):
    """整点拒绝：不得只删非法 ID 后继续使用可能依赖它的标题/说明。"""
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    known = evidence[0].evidenceId
    proposal = {
        "points": [
            # 同一段说明既引用合法证据又引用未入模证据：必须整点丢弃，不能"删掉非法 ID 后留下"
            {"title": "混合引用", "summary": "依赖被排除证据的说明。", "evidenceIds": [known, "ev-nope"]},
            {"title": "纯合法", "summary": "只引用已核验证据。", "evidenceIds": [known]},
        ]
    }
    summarizer, _client = make_summarizer(
        StubResponse(payload={"message": {"content": json.dumps(proposal, ensure_ascii=False)}})
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert [point.title for point in outcome.points] == ["纯合法"]
    assert all("混合引用" not in point.title for point in outcome.points)
    assert outcome.reason_code == "SUMMARY_PARTIAL" and outcome.dropped == 1


def test_summarizer_failure_classes_are_explicit(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)

    # 非法 JSON → partial（保留证据由调用方负责），不抛错、不编造
    summarizer, _client = make_summarizer(
        StubResponse(payload={"message": {"content": "这不是 JSON"}})
    )
    outcome = summarizer.summarize(question="问", evidence=evidence)
    assert outcome.points == [] and "结构不符合要求" in outcome.reason
    assert "不是合法 JSON" in outcome.reason

    # 超时 → partial
    summarizer, _client = make_summarizer(httpx.TimeoutException("timed out"))
    outcome = summarizer.summarize(question="问", evidence=evidence)
    assert outcome.points == [] and "超时" in outcome.reason

    # 服务不可用（非 200）→ 503 RAG_SUMMARY_UNAVAILABLE，由会话层决定 partial/error
    summarizer, _client = make_summarizer(StubResponse(status_code=500, payload={}))
    with pytest.raises(AppError) as unavailable:
        summarizer.summarize(question="问", evidence=evidence)
    assert unavailable.value.code == "RAG_SUMMARY_UNAVAILABLE"
    assert unavailable.value.status_code == 503

    # 连接失败 → 同样显式报不可用
    summarizer, _client = make_summarizer(httpx.ConnectError("refused"))
    with pytest.raises(AppError) as refused:
        summarizer.summarize(question="问", evidence=evidence)
    assert refused.value.code == "RAG_SUMMARY_UNAVAILABLE"


def test_summarizer_only_accepts_loopback_and_reports_status(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)

    for url in (None, "", "https://api.example.com/ollama", "http://192.168.1.10:11434"):
        summarizer = KnowledgeSummarizer(provider_url=url)
        status = summarizer.status()
        assert status["available"] is False and status["reason"]
        with pytest.raises(AppError) as blocked:
            summarizer.summarize(question="问", evidence=evidence)
        assert blocked.value.code == "RAG_SUMMARY_UNAVAILABLE"

    local = KnowledgeSummarizer(provider_url="http://localhost:11434")
    assert local.status()["available"] is True
    assert local.status()["providerUrl"] == "http://localhost:11434"

    # 没有证据：不调用模型，直接返回 partial 语义
    summarizer, client = make_summarizer(StubResponse(payload={}))
    outcome = summarizer.summarize(question="问", evidence=[])
    assert outcome.points == [] and client.requests == []


def test_validate_points_enforces_admitted_refs_and_length_budget():
    """校验只认准入集合：非子集 → 整点拒绝；并强制 3 点 / 90 / 250 / 2 引用上限。"""
    allowed = frozenset({"ev-a", "ev-b"})
    checked = validate_points(
        {
            "points": [
                {"title": "合法", "summary": "两条引用。", "evidenceIds": ["ev-a", "ev-b"]},
                {"title": "非准入", "summary": "引用了证据列表内但未入模的 id。", "evidenceIds": ["ev-c"]},
                {"title": "混合", "summary": "部分非法。", "evidenceIds": ["ev-a", "ev-c"]},
                {"title": "缺引用", "summary": "没有引用。", "evidenceIds": []},
                "不是对象",
            ]
        },
        allowed_ids=allowed,
    )
    assert [point.title for point in checked.points] == ["合法"]
    assert checked.dropped == 4
    assert set(checked.violation_codes) >= {
        "REF_NOT_ADMITTED",
        "REF_EMPTY",
        "POINT_EMPTY",
    }
    assert checked.valid is False

    # 单点超 90 码点 / 单点超 2 引用 / 重复点：逐点拒绝且原因码可区分
    long_point = validate_points(
        {"points": [{"title": "超长", "summary": "长" * 90, "evidenceIds": ["ev-a"]}]},
        allowed_ids=allowed,
    )
    assert long_point.points == () and "POINT_TOO_LONG" in long_point.violation_codes
    too_many_refs = validate_points(
        {"points": [{"title": "引用超限", "summary": "说明", "evidenceIds": ["ev-a", "ev-b", "ev-a"]}]},
        allowed_ids=allowed,
        max_refs_per_point=1,
    )
    assert too_many_refs.points == () and "REF_LIMIT" in too_many_refs.violation_codes
    duplicated = validate_points(
        {
            "points": [
                {"title": "同一点", "summary": "同一说明。", "evidenceIds": ["ev-a"]},
                {"title": "同一点", "summary": "同一说明。", "evidenceIds": ["ev-a"]},
            ]
        },
        allowed_ids=allowed,
    )
    assert len(duplicated.points) == 1 and "DUPLICATE_POINT" in duplicated.violation_codes

    # 数量与总量超限属于"点本身完整但超预算"：点数保留，违规码记录
    over_count = validate_points(
        {
            "points": [
                {"title": f"点{index}", "summary": "说明", "evidenceIds": ["ev-a"]}
                for index in range(5)
            ]
        },
        allowed_ids=allowed,
    )
    assert len(over_count.points) == 5 and "POINT_LIMIT" in over_count.violation_codes
    assert choose_complete_valid_points(over_count.points) == list(over_count.points[:3])

    # 非对象 / 缺 points 数组：结构违规，不抛错
    assert validate_points("not a dict", allowed_ids=allowed).violation_codes == ("STRUCTURE",)
    assert validate_points({"points": "nope"}, allowed_ids=allowed).violation_codes == ("STRUCTURE",)
    assert validate_points({"points": []}, allowed_ids=allowed).violation_codes == ("STRUCTURE",)


def test_filter_points_second_check_uses_admitted_set():
    """服务端二次校验口径：给了准入集合就只认它（替身也不能把非法引用带进结果）。"""
    from app.schemas.rag_v2 import RagPoint

    point = RagPoint(
        pointId="pt-x", title="点", summary="说明", evidenceIds=["ev-not-admitted"]
    )
    kept, dropped = filter_points([point], [], allowed_ids=frozenset({"ev-admitted"}))
    assert kept == [] and dropped == 1
    # 未提供准入集合（替身）时退回"全部已核验证据"：仍然拒绝凭空引用
    kept, dropped = filter_points([point], [])
    assert kept == [] and dropped == 1

