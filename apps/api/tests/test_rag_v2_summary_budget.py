"""RAG v2.1 知识点概括的上下文预算与打包。

背景（首败）：真实规模证据下提示词被上游按默认窗口截断，模型看不到"必须返回 points 数组并
引用 evidenceId"的指令 → 0 条知识点、首答永远 partial。2026-10-06 起概括模型改为「全局默认
云端模型」，预算改由**档案**的 ``contextTokens`` / 输出上限推导。这里用替身锁定行为：

- 提示词预算由档案窗口与输出上限推导（保守字符估算 + 安全余量），并与首答入模上限
  ``EVIDENCE_PROMPT_MAX_CHARS`` 取较小者；输出上限夹在 ``[OUTPUT_TOKEN_MIN, OUTPUT_TOKEN_MAX]``；
- ``PromptPack`` 返回**真实准入集合**（``admitted_evidence_ids`` / ``admitted_evidence`` /
  ``skipped_evidence_ids``）；证据按顺序整条装入，装不下的整条丢弃（绝不截断单条原文）；
- 连一条都装不下时不发请求，直接 partial 并说明原因；
- 回应结构分级（结构不符 / points 为空 / 引用校验不过）措辞可区分；
- 上游截断（``finish_reason=length``）时拒绝该输出；``usage`` 计数只作诊断字段；
- reason 不回显题目全文或原文内容。
"""

from __future__ import annotations

import json

import httpx2 as httpx
import pytest

from app.core.rag_budget import EVIDENCE_PROMPT_MAX_CHARS
from app.services.rag_v2.summary import (
    CHARS_PER_TOKEN,
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_OUTPUT_TOKENS,
    OUTPUT_TOKEN_MAX,
    OUTPUT_TOKEN_MIN,
    PROMPT_SAFETY_MARGIN,
    RESERVED_TOKENS,
    KnowledgeSummarizer,
    pack_evidence,
    prompt_char_budget,
    prompt_token_budget,
)
from tests.summary_support import SummaryWire, make_summarizer
from tests.test_rag_v2_summary import evidence_of
from tests.test_rag_v2_support import RagEnv, sample_text


def many_evidence(evidence, count: int = 24):
    """把真实证据复制成 count 条（不同 evidenceId）；``text`` 与 ``readable`` 保持同一内容。

    这些复制件没有图片，清洗文本 == 原文切片，便于断言"入模的是完整证据"。
    """
    base = evidence[0]
    items = []
    for index in range(count):
        text = base.text + f"（第{index}段补充原文。）"
        readable = (
            base.readable.model_copy(update={"text": text}) if base.readable is not None else None
        )
        items.append(
            base.model_copy(
                update={"evidenceId": f"ev-{index:016d}", "text": text, "readable": readable}
            )
        )
    return items


def test_prompt_budget_is_derived_from_profile_window_and_output():
    tokens = prompt_token_budget(DEFAULT_CONTEXT_TOKENS, DEFAULT_OUTPUT_TOKENS)
    assert tokens == DEFAULT_CONTEXT_TOKENS - DEFAULT_OUTPUT_TOKENS - RESERVED_TOKENS
    assert prompt_char_budget(DEFAULT_CONTEXT_TOKENS, DEFAULT_OUTPUT_TOKENS) == int(
        tokens * CHARS_PER_TOKEN * PROMPT_SAFETY_MARGIN
    ) == 9318
    # 窗口变小 → 预算单调变小；窗口小于生成预留时预算为 0（不发出必然截断的请求）
    assert prompt_char_budget(4096, 512) < prompt_char_budget(8192, 512)
    assert prompt_char_budget(1024, 1024) == 0

    # 档案声明窗口 + 输出上限：入模预算 = min(档案窗口估算, 首答入模上限)
    profiled = SummaryWire(context_tokens=4096, max_output_tokens=1024).summarizer()
    assert profiled.prompt_budget_chars == min(
        prompt_char_budget(4096, 1024), EVIDENCE_PROMPT_MAX_CHARS
    )
    status = profiled.status()
    assert status["contextTokens"] == 4096 and status["outputTokens"] == 1024
    assert status["promptBudgetChars"] == profiled.prompt_budget_chars
    # 未声明窗口 → 用保守默认；输出上限夹到 [OUTPUT_TOKEN_MIN, OUTPUT_TOKEN_MAX]
    assert SummaryWire(context_tokens=None).summarizer().status()["contextTokens"] == DEFAULT_CONTEXT_TOKENS
    assert SummaryWire(max_output_tokens=99999).summarizer().status()["outputTokens"] == OUTPUT_TOKEN_MAX
    assert SummaryWire(max_output_tokens=1).summarizer().status()["outputTokens"] == OUTPUT_TOKEN_MIN


def test_pack_evidence_takes_whole_items_and_returns_admitted_set(tmp_path):
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

    # 真实准入集合：恰好是提示词里出现过的证据；被排除的 id 不在其中
    assert pack.admitted_evidence_ids == frozenset(
        item.evidenceId for item in pack.admitted_evidence
    )
    assert len(pack.admitted_evidence) == pack.used_evidence
    assert pack.skipped_evidence_ids == tuple(
        item.evidenceId for item in evidence[pack.used_evidence :]
    )
    for excluded in pack.skipped_evidence_ids:
        assert excluded not in pack.prompt and excluded not in pack.admitted_evidence_ids
    for admitted_id in pack.admitted_evidence_ids:
        assert admitted_id in pack.prompt


def test_pack_evidence_uses_cleaned_readable_text_not_image_markdown(tmp_path):
    """入模文本是清洗后的 readable.text：图片地址不进入提示词，文本仍是完整证据。"""
    env = RagEnv(tmp_path)
    document = env.add_document(
        title="图册",
        text="# 第一章 集合\n\n集合的表示方法。![加速度与力关系图](images/a1b2c3d4e5f6.png)\n"
        "并集由所有属于 A 或属于 B 的元素组成。\n\n## 练习 1.1\n\n1. 求并集。\n",
    )
    document_evidence = evidence_of(env, document)
    assert document_evidence and document_evidence[0].readable is not None
    item = document_evidence[0]
    assert "![加速度与力关系图](images/a1b2c3d4e5f6.png)" in item.text, "封存原文切片不变"
    assert "![" not in item.readable.text and "images/a1b2c3d4e5f6.png" not in item.readable.text
    assert item.readable.removedImageCount == 1

    pack = pack_evidence(question="并集是什么？", evidence=[item], budget_chars=6000)
    assert pack.fits is True
    assert "![" not in pack.prompt and "images/a1b2c3d4e5f6.png" not in pack.prompt
    assert "加速度与力关系图" in pack.prompt, "有意义的图片说明文字保留"


def test_over_budget_evidence_skips_request_and_reports_coverage(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = many_evidence(evidence_of(env, document), count=8)
    summarizer, wire = make_summarizer(text="{}", context_tokens=1024, max_output_tokens=256)
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)

    assert wire.requests == [], "发送前自检失败时不得调用模型"
    assert outcome.points == []
    assert "超出知识点概括输入预算" in outcome.reason
    assert outcome.total_evidence == 8 and outcome.skipped_evidence == 8
    assert outcome.used_evidence == 0
    assert outcome.prompt_eval_count is None and outcome.elapsed_seconds is None
    assert summarizer.prompt_budget_chars < len(evidence[0].text)


def test_summarize_sends_profile_output_budget(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    summarizer, wire = make_summarizer(text='{"points": []}')
    summarizer.summarize(question="并集是什么？", evidence=evidence)
    _path, payload = wire.requests[0]
    assert payload["max_tokens"] == DEFAULT_OUTPUT_TOKENS
    assert "temperature" not in payload, "不向未声明支持的档案下发生成参数"

    custom, custom_wire = make_summarizer(text='{"points": []}', max_output_tokens=2048,
                                          context_tokens=32768)
    custom.summarize(question="并集是什么？", evidence=evidence)
    _path, custom_payload = custom_wire.requests[0]
    assert custom_payload["max_tokens"] == 2048, "输出上限来自档案（未超封顶）"


def test_response_structure_tiers_and_coverage_are_distinguishable(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    known = evidence[0].evidenceId

    # 结构不符：不是 points 数组（模型自造结构）
    summarizer, _wire = make_summarizer({"title": "自造", "content": []})
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert "结构不符合要求" in outcome.reason and "缺少 points 数组" in outcome.reason

    # points 为空数组
    summarizer, _wire = make_summarizer({"points": []})
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert "points 为空" in outcome.reason

    # 引用校验不过：结构对但引用不存在证据
    summarizer, _wire = make_summarizer(
        {"points": [{"title": "编造", "summary": "无依据", "evidenceIds": ["ev-nope"]}]}
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert "未通过原文引用校验" in outcome.reason and outcome.dropped == 1
    assert "结构不符合要求" not in outcome.reason

    # 成功：reason 保持 None，覆盖与上游计数只在诊断字段
    summarizer, _wire = make_summarizer(
        {"points": [{"title": "并集", "summary": "由所有元素组成。", "evidenceIds": [known]}]}
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert outcome.points and outcome.reason is None
    assert outcome.prompt_eval_count == 321 and outcome.eval_count == 123, "usage 只作诊断字段"
    assert outcome.used_evidence == 1 and outcome.total_evidence == 1
    assert outcome.elapsed_seconds is not None and outcome.elapsed_seconds >= 0


def test_truncated_output_is_rejected(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = evidence_of(env, document)
    known = evidence[0].evidenceId
    summarizer, _wire = make_summarizer(
        {"points": [{"title": "并集", "summary": "摘要", "evidenceIds": [known]}]},
        finish="length",  # 上游按输出上限截断
    )
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert outcome.points == [] and outcome.truncated is True
    assert "超出模型上下文" in outcome.reason and "截断" in outcome.reason
    assert outcome.prompt_eval_count == 321


def test_partial_reason_mentions_coverage_but_never_echoes_question_or_source(tmp_path):
    env = RagEnv(tmp_path)
    document = env.add_document(title="高中数学必修第一册", text=sample_text())
    evidence = many_evidence(evidence_of(env, document), count=6)
    summarizer, wire = make_summarizer(text="{}", context_tokens=4096, max_output_tokens=256)
    outcome = summarizer.summarize(question="并集是什么？", evidence=evidence)
    assert wire.requests, "预算够时仍应调用模型"
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
        {"title": "x"},
        {"points": []},
        {"points": [{"title": "t", "summary": "s", "evidenceIds": ["ev-nope"]}]},
        "不是 JSON",
        {},
    ):
        summarizer, _wire = make_summarizer(payload)
        outcomes.append(summarizer.summarize(question=secret_question, evidence=evidence))
    summarizer, _wire = make_summarizer(fail=httpx.ReadTimeout("timed out"))
    outcomes.append(summarizer.summarize(question=secret_question, evidence=evidence))

    for outcome in outcomes:
        assert outcome.points == []
        assert outcome.reason, "partial 必须给出可读原因"
        assert secret_question not in outcome.reason
        assert secret_text not in outcome.reason
        assert "\n\n" not in outcome.reason
