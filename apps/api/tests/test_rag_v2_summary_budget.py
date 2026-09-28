"""RAG v2.1 知识点概括的上下文预算与打包（v1.1 修复的专属用例）。

背景（首败）：真实规模证据下提示词被上游按默认窗口截断，模型看不到"必须返回 points 数组并
引用 evidenceId"的指令 → 0 条知识点、首答永远 partial。这里用替身锁定修复后的行为：

- 提示词预算由显式 ``num_ctx``/``num_predict`` 推导（保守字符估算 + 安全余量）；
- 证据按顺序整条装入，装不下的整条丢弃（绝不截断单条原文）；
- 连一条都装不下时不发请求，直接 partial 并说明原因；
- 回应结构分级（结构不符 / points 为空 / 引用校验不过）措辞可区分；
- 上游截断自检（prompt_eval_count 顶到窗口）时拒绝该输出；
- reason 不回显题目全文或原文内容。
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.rag_v2.summary import (
    CHARS_PER_TOKEN,
    DEFAULT_NUM_CTX,
    DEFAULT_NUM_PREDICT,
    OUTPUT_TOKEN_MAX,
    OUTPUT_TOKEN_MIN,
    PROMPT_SAFETY_MARGIN,
    RESERVED_TOKENS,
    KnowledgeSummarizer,
    pack_evidence,
    prompt_char_budget,
    prompt_token_budget,
)
from tests.test_rag_v2_summary import evidence_of, make_summarizer, StubResponse
from tests.test_rag_v2_support import RagEnv, sample_text


def many_evidence(evidence, count: int = 24):
    """把真实证据复制成 count 条（不同 evidenceId），用于打包/预算用例。"""
    base = evidence[0]
    return [
        base.model_copy(
            update={
                "evidenceId": f"ev-{index:016d}",
                "text": base.text + f"（第{index}段补充原文。）",
            }
        )
        for index in range(count)
    ]


def test_prompt_budget_is_derived_from_explicit_context_window():
    tokens = prompt_token_budget(DEFAULT_NUM_CTX, DEFAULT_NUM_PREDICT)
    assert tokens == DEFAULT_NUM_CTX - DEFAULT_NUM_PREDICT - RESERVED_TOKENS
    assert prompt_char_budget(DEFAULT_NUM_CTX, DEFAULT_NUM_PREDICT) == int(
        tokens * CHARS_PER_TOKEN * PROMPT_SAFETY_MARGIN
    ) == 8601
    # 窗口变小 → 预算单调变小；窗口小于生成预留时预算为 0（不发出必然截断的请求）
    assert prompt_char_budget(4096, 512) < prompt_char_budget(8192, 512)
    assert prompt_char_budget(1024, 1024) == 0

    summarizer = KnowledgeSummarizer("http://127.0.0.1:11434", num_ctx=4096, num_predict=1024)
    assert summarizer.prompt_budget_chars == prompt_char_budget(4096, 1024)
    status = summarizer.status()
    assert status["numCtx"] == 4096 and status["numPredict"] == 1024
    assert status["promptBudgetChars"] == summarizer.prompt_budget_chars
    # 输出侧有界：夹到 [OUTPUT_TOKEN_MIN, OUTPUT_TOKEN_MAX]
    assert KnowledgeSummarizer("http://127.0.0.1:11434", num_predict=99999).num_predict == OUTPUT_TOKEN_MAX
    assert KnowledgeSummarizer("http://127.0.0.1:11434", num_predict=1).num_predict == OUTPUT_TOKEN_MIN
    assert KnowledgeSummarizer("http://127.0.0.1:11434", num_ctx=8).num_ctx == 1024


def test_pack_evidence_takes_whole_items_and_never_truncates(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = many_evidence(evidence_of(env, document), count=6)

    first_two = len(evidence[0].text) * 2 + len(evidence[0].evidenceId) * 2 + 80
    pack = pack_evidence(question="并集是什么？", evidence=evidence, budget_chars=first_two)
    assert pack.fits is True
    assert pack.used_evidence >= 1 and pack.skipped_evidence == 6 - pack.used_evidence
    assert pack.chars <= first_two
    # 装入的是完整原文，逐字节相同；未装入的整条不出现
    for item in evidence[: pack.used_evidence]:
        assert item.text in pack.prompt
        assert item.evidenceId in pack.prompt
    if pack.used_evidence < 6:
        assert evidence[-1].text not in pack.prompt
    assert "并集是什么？" in pack.prompt
    assert pack.prompt.rstrip().endswith("]}]}")

    # 预算连一条都放不下 → fits=False 且不产生提示词（调用方必须跳过请求）
    tiny = pack_evidence(question="并集是什么？", evidence=evidence, budget_chars=50)
    assert tiny.fits is False and tiny.prompt == ""
    assert tiny.used_evidence == 0 and tiny.skipped_evidence == 6

    # 超长题目吃掉预算：同样不产生提示词
    long_question = "并集" * 300
    assert pack_evidence(question=long_question, evidence=evidence, budget_chars=200).fits is False


def test_over_budget_evidence_skips_request_and_reports_coverage(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = many_evidence(evidence_of(env, document), count=8)
    summarizer, client = make_summarizer(
        StubResponse(payload={"message": {"content": "{}"}}), num_ctx=1024, num_predict=256
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)

    assert client.requests == [], "发送前自检失败时不得调用模型"
    assert outcome.points == []
    assert "超出本地概括输入预算" in outcome.reason
    assert outcome.total_evidence == 8 and outcome.skipped_evidence == 8
    assert outcome.used_evidence == 0
    assert outcome.prompt_eval_count is None and outcome.elapsed_seconds is None
    assert summarizer.prompt_budget_chars < len(evidence[0].text)


def test_summarize_sends_explicit_context_and_output_options(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    summarizer, client = make_summarizer(
        StubResponse(payload={"message": {"content": '{"points": []}'}})
    )
    summarizer.summarize(question="并集是什么？", evidence=evidence)
    _path, payload = client.requests[0]
    assert payload["options"]["num_ctx"] == 8192
    assert payload["options"]["num_predict"] == 1536
    assert payload["options"]["temperature"] == 0

    custom, custom_client = make_summarizer(
        StubResponse(payload={"message": {"content": '{"points": []}'}}),
        num_ctx=4096,
        num_predict=1024,
    )
    custom.summarize(question="并集是什么？", evidence=evidence)
    _path, payload = custom_client.requests[0]
    assert payload["options"]["num_ctx"] == 4096 and payload["options"]["num_predict"] == 1024


def test_response_structure_tiers_and_coverage_are_distinguishable(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    known = evidence[0].evidenceId

    # 结构不符：不是 points 数组（模型自造结构）
    summarizer, _client = make_summarizer(
        StubResponse(payload={"message": {"content": json.dumps({"title": "自造", "content": []})}})
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert "结构不符合要求" in outcome.reason and "缺少 points 数组" in outcome.reason

    # points 为空数组
    summarizer, _client = make_summarizer(
        StubResponse(payload={"message": {"content": '{"points": []}'}})
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert "points 为空" in outcome.reason

    # 引用校验不过：结构对但引用不存在证据
    summarizer, _client = make_summarizer(
        StubResponse(
            payload={
                "message": {
                    "content": json.dumps(
                        {"points": [{"title": "编造", "summary": "无依据", "evidenceIds": ["ev-nope"]}]},
                        ensure_ascii=False,
                    )
                }
            }
        )
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert "未通过原文引用校验" in outcome.reason and outcome.dropped == 1
    assert "结构不符合要求" not in outcome.reason

    # 成功：reason 保持 None，覆盖与上游计数只在诊断字段
    summarizer, _client = make_summarizer(
        StubResponse(
            payload={
                "message": {
                    "content": json.dumps(
                        {"points": [{"title": "并集", "summary": "由所有元素组成。", "evidenceIds": [known]}]},
                        ensure_ascii=False,
                    )
                },
                "prompt_eval_count": 5000,
                "eval_count": 120,
            }
        )
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert outcome.points and outcome.reason is None
    assert outcome.prompt_eval_count == 5000 and outcome.eval_count == 120
    assert outcome.used_evidence == 1 and outcome.total_evidence == 1
    assert outcome.elapsed_seconds is not None and outcome.elapsed_seconds >= 0


def test_truncated_prompt_detection_rejects_output(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    known = evidence[0].evidenceId
    summarizer, _client = make_summarizer(
        StubResponse(
            payload={
                "message": {
                    "content": json.dumps(
                        {"points": [{"title": "并集", "summary": "摘要", "evidenceIds": [known]}]},
                        ensure_ascii=False,
                    )
                },
                "prompt_eval_count": 8192,  # 顶到窗口 → 上游已截断
                "eval_count": 40,
            }
        )
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert outcome.points == [] and outcome.truncated is True
    assert "超出模型上下文" in outcome.reason and "截断" in outcome.reason
    assert outcome.prompt_eval_count == 8192


def test_partial_reason_mentions_coverage_but_never_echoes_question_or_source(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = many_evidence(evidence_of(env, document), count=6)
    summarizer, client = make_summarizer(
        StubResponse(payload={"message": {"content": "{}"}}), num_ctx=4096, num_predict=256
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert client.requests, "预算够时仍应调用模型"
    # 覆盖不足（装不下全部证据）时 reason 必须说明 N/M
    if outcome.skipped_evidence:
        assert f"{outcome.used_evidence}/{outcome.total_evidence}" in outcome.reason


def test_reason_never_echoes_question_or_source_text(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    secret_question = "独一无二的题目措辞QZX123"
    secret_text = evidence[0].text[:60]

    outcomes = []
    for payload in (
        {"message": {"content": json.dumps({"title": "x"})}},
        {"message": {"content": '{"points": []}'}},
        {
            "message": {
                "content": json.dumps(
                    {"points": [{"title": "t", "summary": "s", "evidenceIds": ["ev-nope"]}]},
                    ensure_ascii=False,
                )
            }
        },
        {"message": {"content": "不是 JSON"}},
        {"message": {"content": "{}"}, "prompt_eval_count": 8192},
    ):
        summarizer, _client = make_summarizer(StubResponse(payload=payload))
        outcomes.append(summarizer.summarize(question=secret_question, evidence=evidence))
    summarizer, _client = make_summarizer(httpx.TimeoutException("timed out"))
    outcomes.append(summarizer.summarize(question=secret_question, evidence=evidence))

    for outcome in outcomes:
        assert outcome.points == []
        assert outcome.reason, "partial 必须给出可读原因"
        assert secret_question not in outcome.reason
        assert secret_text not in outcome.reason
        assert "\n\n" not in outcome.reason
