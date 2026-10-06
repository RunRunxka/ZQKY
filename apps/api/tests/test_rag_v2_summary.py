"""知识点概括：结构化输出校验、失败分类与"只用云端默认档案"。

概括在 2026-10-06 改为走「全局默认云端模型」：测试用**真实 provider + MockTransport 替身**
（``tests/summary_support.py``）覆盖全部分支，不发起真实网络请求；本机部署档案一律按不可用拒绝。
"""

from __future__ import annotations

import json

import pytest

import httpx2 as httpx

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
from tests.summary_support import SummaryWire, make_summarizer
from tests.test_rag_v2_support import RagEnv, sample_text


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
    summarizer, wire = make_summarizer(proposal)

    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert [point.title for point in outcome.points] == ["并集"]
    assert outcome.points[0].evidenceIds == [evidence[0].evidenceId]
    assert outcome.reason is None

    path, payload = wire.requests[0]
    assert path.endswith("/chat/completions"), "概括必须走档案协议的聊天接口"
    assert payload["model"] == "cloud-model"
    assert "stream" not in payload, "概括是单次非流式调用"
    assert payload["max_tokens"] == 1024, "输出预算来自档案并夹在 [256, 2048]"
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
    summarizer, wire = make_summarizer(proposal)
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert [point.title for point in outcome.points] == ["合法"]
    assert outcome.dropped == 3
    assert outcome.reason_code == "SUMMARY_PARTIAL"
    assert outcome.corrected == 1, "非法输出必须触发且只触发一次修正"
    assert len(wire.requests) == 2, "模型总调用次数 = 首次 + 一次修正"
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
    summarizer, _wire = make_summarizer(proposal)
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert [point.title for point in outcome.points] == ["纯合法"]
    assert all("混合引用" not in point.title for point in outcome.points)
    assert outcome.reason_code == "SUMMARY_PARTIAL" and outcome.dropped == 1


def test_summarizer_failure_classes_are_explicit(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)

    # 非法 JSON → partial（保留证据由调用方负责），不抛错、不编造
    summarizer, _wire = make_summarizer(text="这不是 JSON")
    outcome = summarizer.summarize(question="问", evidence=evidence)
    assert outcome.points == [] and "结构不符合要求" in outcome.reason
    assert "不是合法 JSON" in outcome.reason

    # 上游超时（provider 归一为 UPSTREAM_TIMEOUT）→ partial 语义
    summarizer, _wire = make_summarizer(fail=httpx.ReadTimeout("timed out"))
    outcome = summarizer.summarize(question="问", evidence=evidence)
    assert outcome.points == [] and "超时" in outcome.reason

    # 上游截断（finish_reason=length）→ 不采用该输出，partial
    summarizer, _wire = make_summarizer(text=json.dumps({"points": []}, ensure_ascii=False), finish="length")
    outcome = summarizer.summarize(question="问", evidence=evidence)
    assert outcome.points == [] and outcome.truncated is True

    # 服务不可用（非 200）→ 503 RAG_SUMMARY_UNAVAILABLE，由会话层决定 partial/error
    summarizer, _wire = make_summarizer(status_code=500)
    with pytest.raises(AppError) as unavailable:
        summarizer.summarize(question="问", evidence=evidence)
    assert unavailable.value.code == "RAG_SUMMARY_UNAVAILABLE"
    assert unavailable.value.status_code == 503

    # 连接失败 → 同样显式报不可用
    summarizer, _wire = make_summarizer(fail=httpx.ConnectError("refused"))
    with pytest.raises(AppError) as refused:
        summarizer.summarize(question="问", evidence=evidence)
    assert refused.value.code == "RAG_SUMMARY_UNAVAILABLE"


def test_summarizer_only_uses_cloud_default_profile(tmp_path):
    """模型口径：只取全局默认档案；未配置或默认是本机部署 → 明确不可用，绝不回退本地。"""
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)

    # 未配置默认档案
    summarizer = SummaryWire(profile_id=None).summarizer()
    status = summarizer.status()
    assert status["available"] is False and "未配置全局默认问答模型" in status["reason"]
    assert summarizer.probe()["available"] is False
    with pytest.raises(AppError) as blocked:
        summarizer.summarize(question="问", evidence=evidence)
    assert blocked.value.code == "RAG_SUMMARY_UNAVAILABLE"

    # 默认档案落在本机部署（Ollama 等 is_local 供应商）
    local = SummaryWire(provider_id="ollama").summarizer()
    local_status = local.status()
    assert local_status["available"] is False and "本机部署" in local_status["reason"]
    assert local.probe()["available"] is False
    with pytest.raises(AppError) as refused:
        local.summarize(question="问", evidence=evidence)
    assert refused.value.code == "RAG_SUMMARY_UNAVAILABLE"

    # 云端默认档案：状态可用、身份来自档案，且状态/探测都不发起推理调用
    cloud_wire = SummaryWire()
    cloud = cloud_wire.summarizer()
    cloud_status = cloud.status()
    assert cloud_status["available"] is True and cloud_status["reason"] is None
    assert cloud_status["model"] == "cloud-model" and cloud_status["modelProfileId"] == "cloud-profile"
    assert cloud_status["providerUrl"] is None and cloud_status["contextTokens"] == 8192
    assert cloud.probe() == {"available": True, "reason": None,
                             "detail": "配置级检查：默认云端档案已就绪（未发起真实推理调用）。"}
    assert cloud.status()["promptBudgetChars"] == 6000, "6000 字符证据上限是主约束"
    assert cloud_wire.requests == [], "状态与探测是配置级检查，不得发起推理调用"

    # 没有证据：不调用模型，直接返回 partial 语义
    summarizer, wire = make_summarizer({"points": []})
    outcome = summarizer.summarize(question="问", evidence=[])
    assert outcome.points == [] and wire.requests == []

    # 默认档案解析失败（档案被删/连接不可用）→ 仍是 503 概括不可用，不能把问答拖成 500
    broken = SummaryWire(
        handle_error=AppError("模型档案不存在。", code="MODEL_NOT_CONFIGURED", status_code=404)
    ).summarizer()
    with pytest.raises(AppError) as stopped:
        broken.summarize(question="问", evidence=evidence)
    assert stopped.value.code == "RAG_SUMMARY_UNAVAILABLE"


def test_summarizer_follows_the_profile_protocol(tmp_path):
    """概括按**档案协议**调用：openai-chat / openai-responses / anthropic-messages 都能跑通。"""
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    known = evidence[0].evidenceId
    proposal = {"points": [{"title": "并集", "summary": "由所有元素组成。", "evidenceIds": [known]}]}

    for protocol, path, budget_key in (("openai_chat", "/chat/completions", "max_tokens"),
                                       ("openai_responses", "/responses", "max_output_tokens"),
                                       ("anthropic_messages", "/v1/messages", "max_tokens")):
        summarizer, wire = make_summarizer(proposal, protocol=protocol)
        outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
        assert [point.title for point in outcome.points] == ["并集"], protocol
        assert outcome.prompt_eval_count == 321 and outcome.eval_count == 123, protocol
        assert wire.requests[0][0].endswith(path), protocol
        assert wire.requests[0][1][budget_key] == 1024, protocol

    # 截断判定同样跨协议（anthropic 的 max_tokens / responses 的 incomplete）
    for protocol in ("openai_responses", "anthropic_messages"):
        summarizer, _wire = make_summarizer(proposal, protocol=protocol, finish="length")
        outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
        assert outcome.points == [] and outcome.truncated is True, protocol


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
