"""本地知识点概括：结构化输出校验、失败分类与"只允许本机回环"。

真实 Ollama 调用留给总控集成验收；这里注入 HTTP 替身覆盖全部分支。
"""

from __future__ import annotations

import json

import pytest

import httpx

from app.core.exceptions import AppError
from app.schemas.rag_v2 import RagPoint
from app.services.rag_v2.evidence import build_evidence
from app.services.rag_v2.retrieval import Candidate
from app.services.rag_v2.scope import verify_scope
from app.services.rag_v2.summary import (
    INSTRUCTION,
    KnowledgeSummarizer,
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


def test_summarizer_drops_points_with_unknown_evidence_ids(tmp_path):
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
    summarizer, _client = make_summarizer(
        StubResponse(payload={"message": {"content": json.dumps(proposal, ensure_ascii=False)}})
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert [point.title for point in outcome.points] == ["合法"]
    assert outcome.dropped == 3


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


def test_validate_points_filters_and_reports_drops(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    known = evidence[0].evidenceId

    points, dropped = validate_points(
        {
            "points": [
                {"title": "要点", "summary": "摘要", "evidenceIds": [known, known, "ev-unknown"]},
                {"title": "超长摘要", "summary": "长" * 5000, "evidenceIds": [known]},
                {"title": "缺引用", "summary": "摘要", "evidenceIds": []},
                "不是对象",
            ]
        },
        evidence,
    )
    assert dropped == 3
    assert len(points) == 1
    assert points[0].evidenceIds == [known], "重复与不存在的引用都必须被去掉"
    assert isinstance(points[0], RagPoint) and points[0].pointId.startswith("pt-")

    # 非对象 / 缺 points 数组：返回空列表，不抛错、不编造
    assert validate_points("not a dict", evidence) == ([], 0)
    assert validate_points({"points": "nope"}, evidence) == ([], 0)

