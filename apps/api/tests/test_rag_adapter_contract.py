"""RAG adapter 契约测试（批次 RAG-I0-PREP v1）。

全部为**合成数据**用例：不联网、不读外部目录、不读 `F:\\ZQKY_RAG`、不调用任何模型。
断言口径尽量写成"契约原文可复算"，而不是"实现返回什么就是什么"：

- 坐标换算用 `len(text.encode("utf-16-le")) // 2` 作为**独立参照**（不依赖被测实现）；
- UTF-16 边界用"码点下标 i 与码元下标 u 互相往返"定义，并另断言 `len()` 与
  UTF-16 长度在含 emoji 时**不相等**，把"不可混用"变成可测事实；
- 校验入口只断言"抛错/通过"与"返回值不被改写"，不断言错误文案。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts.rag_adapter import (
    RAG_CAPABILITY,
    RAG_UNAVAILABLE_MESSAGE,
    RagAdapterUnavailable,
    RagContractError,
    RagQuery,
    codepoint_to_utf16_offset,
    get_rag_adapter,
    utf16_offset_to_codepoint,
    validate_answer_payload,
)

# 契约校验的两类拒绝：字段级（pydantic）与跨字段（本模块）。
CONTRACT_ERRORS = (ValidationError, RagContractError)

HEX_A = "a" * 64
HEX_B = "b" * 64

SOURCE_ID = "maths/必修第一册/1.1.md"
SOURCE_NAME = "人教版高中数学必修第一册"
EVIDENCE_TEXT = "列举法是把集合的所有元素一一列举出来，并用花括号表示集合。"
ANSWER_TEXT = "本题考查列举法：先把元素一一列出，再用花括号包起来。"


# ---------------------------------------------------------------------------
# 合成载荷构造
# ---------------------------------------------------------------------------


def make_evidence(**overrides) -> dict:
    payload = {
        "evidenceId": "ev-1",
        "sourceType": "textbook",
        "sourceId": SOURCE_ID,
        "sourceName": SOURCE_NAME,
        "charStart": 100,
        "charEnd": 100 + len(EVIDENCE_TEXT),
        "lineStart": 10,
        "lineEnd": 12,
        "text": EVIDENCE_TEXT,
        "score": 0.42,
    }
    payload.update(overrides)
    return payload


def make_citation(**overrides) -> dict:
    payload = {
        "evidenceId": "ev-1",
        "fileId": SOURCE_ID,
        "fileFingerprint": HEX_A,
        "charStart": 100,
        "charEnd": 100 + len(EVIDENCE_TEXT),
        "lineStart": 10,
        "lineEnd": 12,
        "textHash": HEX_B,
    }
    payload.update(overrides)
    return payload


def make_payload(**overrides) -> dict:
    payload = {
        "status": "ok",
        "answer": ANSWER_TEXT,
        "evidence": [make_evidence()],
        "citations": [make_citation()],
        "warnings": [],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# 1. 合法载荷
# ---------------------------------------------------------------------------


def test_valid_payload_passes_and_ranges_are_not_rewritten():
    """合法载荷通过，且返回值与输入区间逐字段相同（禁止静默裁剪/夹取）。"""
    source = make_payload()
    answer = validate_answer_payload(source)

    assert answer.status == "ok"
    assert answer.answer == ANSWER_TEXT
    assert len(answer.evidence) == 1
    assert len(answer.citations) == 1
    assert answer.warnings == []

    evidence = answer.evidence[0]
    citation = answer.citations[0]
    assert (evidence.charStart, evidence.charEnd) == (100, 100 + len(EVIDENCE_TEXT))
    assert (evidence.lineStart, evidence.lineEnd) == (10, 12)
    assert (citation.charStart, citation.charEnd) == (100, 100 + len(EVIDENCE_TEXT))
    assert (citation.lineStart, citation.lineEnd) == (10, 12)
    assert citation.fileFingerprint == HEX_A
    assert citation.textHash == HEX_B


def test_multiple_evidence_and_citations_are_supported():
    payload = make_payload(
        evidence=[
            make_evidence(evidenceId="ev-1"),
            make_evidence(
                evidenceId="ev-2",
                sourceType="knowledge_base",
                sourceId="kb/teachers-guide.md",
                sourceName="教师用书",
                charStart=0,
                charEnd=20,
                lineStart=1,
                lineEnd=1,
                text="教师用书补充说明。",
                score=None,
            ),
        ],
        citations=[
            make_citation(evidenceId="ev-1"),
            make_citation(evidenceId="ev-2", fileId="kb/teachers-guide.md", charStart=0, charEnd=20,
                          lineStart=1, lineEnd=1),
        ],
    )
    answer = validate_answer_payload(payload)
    assert [item.evidenceId for item in answer.evidence] == ["ev-1", "ev-2"]
    assert answer.evidence[1].score is None


def test_citation_may_be_a_narrower_subrange_of_evidence():
    """citation ⊆ evidence 即可（当前 RAG 侧为逐字段复制，故实际取等号）。"""
    evidence_end = 100 + len(EVIDENCE_TEXT)
    payload = make_payload(
        citations=[
            make_citation(charStart=110, charEnd=evidence_end - 1, lineStart=10, lineEnd=11)
        ]
    )
    answer = validate_answer_payload(payload)
    assert (answer.citations[0].charStart, answer.citations[0].charEnd) == (110, evidence_end - 1)


# ---------------------------------------------------------------------------
# 2. 区间与指纹：结构级拒绝
# ---------------------------------------------------------------------------


def test_empty_or_inverted_char_range_is_rejected():
    """charEnd <= charStart 一律拒绝（半开区间不得为空、不得倒置）。"""
    for char_start, char_end in ((100, 100), (100, 99), (0, 0)):
        payload = make_payload(evidence=[make_evidence(charStart=char_start, charEnd=char_end)])
        with pytest.raises(CONTRACT_ERRORS):
            validate_answer_payload(payload)
        payload = make_payload(
            citations=[make_citation(charStart=char_start, charEnd=char_end)]
        )
        with pytest.raises(CONTRACT_ERRORS):
            validate_answer_payload(payload)


def test_inverted_line_range_is_rejected():
    """行号是 1 基闭区间：lineEnd < lineStart 拒绝，lineStart < 1 也拒绝。"""
    with pytest.raises(CONTRACT_ERRORS):
        validate_answer_payload(make_payload(evidence=[make_evidence(lineStart=12, lineEnd=10)]))
    with pytest.raises(CONTRACT_ERRORS):
        validate_answer_payload(make_payload(citations=[make_citation(lineStart=12, lineEnd=10)]))
    with pytest.raises(CONTRACT_ERRORS):
        validate_answer_payload(make_payload(evidence=[make_evidence(lineStart=0)]))
    with pytest.raises(CONTRACT_ERRORS):
        validate_answer_payload(make_payload(citations=[make_citation(lineEnd=0)]))


def test_negative_char_start_is_rejected():
    with pytest.raises(CONTRACT_ERRORS):
        validate_answer_payload(make_payload(evidence=[make_evidence(charStart=-1, charEnd=5)]))


def test_non_64_hex_fingerprints_are_rejected():
    """指纹/散列必须是 64 位小写十六进制（sha256 hexdigest 形态）。"""
    bad_values = [
        "a" * 63,                      # 少一位
        "a" * 65,                      # 多一位
        "",                            # 空
        "z" * 64,                      # 非十六进制字符
        "A" * 64,                      # 大写（不归一，形态必须规范）
        "a" * 63 + "-",                # 长度对但字符非法
        "sha256:" + "a" * 64,          # 带前缀
    ]
    for bad in bad_values:
        with pytest.raises(CONTRACT_ERRORS):
            validate_answer_payload(make_payload(citations=[make_citation(fileFingerprint=bad)]))
        with pytest.raises(CONTRACT_ERRORS):
            validate_answer_payload(make_payload(citations=[make_citation(textHash=bad)]))


def test_out_of_range_citation_span_is_rejected():
    """越界：引用区间必须落在对应证据区间内（字符与行号各自检查）。"""
    evidence = make_evidence()
    char_end = evidence["charEnd"]

    cases = [
        make_citation(charStart=99),                            # 起点早于证据
        make_citation(charEnd=char_end + 1),                    # 终点超出证据
        make_citation(charStart=0, charEnd=char_end + 100),      # 两端都越界
        make_citation(lineStart=9),                             # 行号起点早于证据
        make_citation(lineEnd=13),                              # 行号终点超出证据
    ]
    for citation in cases:
        with pytest.raises(RagContractError):
            validate_answer_payload(make_payload(citations=[citation]))
        # 结构合法（无倒置、无格式错），必须由跨字段规则拒绝，不能静默裁剪
        assert citation["charEnd"] > citation["charStart"]


def test_dangling_and_duplicate_references_are_rejected():
    with pytest.raises(RagContractError):
        validate_answer_payload(make_payload(citations=[make_citation(evidenceId="ev-missing")]))

    with pytest.raises(RagContractError):
        validate_answer_payload(
            make_payload(
                evidence=[make_evidence(evidenceId="ev-1"), make_evidence(evidenceId="ev-1")],
                citations=[make_citation(evidenceId="ev-1")],
            )
        )

    with pytest.raises(RagContractError):
        validate_answer_payload(
            make_payload(citations=[make_citation(evidenceId="ev-1"), make_citation(evidenceId="ev-1")])
        )


def test_non_finite_score_is_rejected():
    """score 是未校准排序值；NaN/Inf 无法进 JSON，拒绝而不是夹取。"""
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CONTRACT_ERRORS):
            validate_answer_payload(make_payload(evidence=[make_evidence(score=bad)]))


def test_unknown_or_missing_fields_are_rejected():
    """字段名严格匹配：未知字段与缺失字段都拒绝（不静默默认）。"""
    with pytest.raises(CONTRACT_ERRORS):
        validate_answer_payload(make_payload(answerConfidence=0.9))

    for missing in ("status", "answer", "evidence", "citations", "warnings"):
        payload = make_payload()
        payload.pop(missing)
        with pytest.raises(CONTRACT_ERRORS):
            validate_answer_payload(payload)


def test_evidence_text_length_limit_is_enforced():
    with pytest.raises(CONTRACT_ERRORS):
        validate_answer_payload(make_payload(evidence=[make_evidence(text="原" * 2001)]))
    with pytest.raises(CONTRACT_ERRORS):
        validate_answer_payload(make_payload(evidence=[make_evidence(text="")]))


def test_query_bounds_are_enforced():
    assert RagQuery(question="集合是什么？").maxEvidence == 5
    assert RagQuery(question="集合是什么？", maxEvidence=1).maxEvidence == 1
    assert RagQuery(question="集合是什么？", maxEvidence=20).maxEvidence == 20
    for bad in (0, 21, -1):
        with pytest.raises(ValidationError):
            RagQuery(question="集合是什么？", maxEvidence=bad)
    with pytest.raises(ValidationError):
        RagQuery(question="")
    with pytest.raises(ValidationError):
        RagQuery(question="题" * 4001)
    assert len(RagQuery(question="题" * 4000).question) == 4000


# ---------------------------------------------------------------------------
# 3. 非 ok 状态的表达方式（禁止静默裁剪、禁止冒充成功）
# ---------------------------------------------------------------------------


def test_ok_requires_answer_evidence_and_citations():
    with pytest.raises(RagContractError):
        validate_answer_payload(make_payload(answer=None))
    with pytest.raises(RagContractError):
        validate_answer_payload(make_payload(evidence=[]))
    with pytest.raises(RagContractError):
        validate_answer_payload(make_payload(citations=[]))
    with pytest.raises(RagContractError):
        validate_answer_payload(make_payload(answer="   "))


@pytest.mark.parametrize("status", ["no_evidence", "stale_source", "out_of_range", "unavailable"])
def test_failure_statuses_carry_no_payload_and_require_a_reason(status):
    """所有非 ok 状态：answer=None、evidence/citations 为空、warnings 非空。"""
    payload = make_payload(
        status=status,
        answer=None,
        evidence=[],
        citations=[],
        warnings=["教材文件指纹与建索引时不一致，请重新定位。"],
    )
    answer = validate_answer_payload(payload)
    assert answer.status == status
    assert answer.answer is None
    assert answer.evidence == []
    assert answer.citations == []
    assert answer.warnings


@pytest.mark.parametrize("status", ["no_evidence", "stale_source", "out_of_range", "unavailable"])
def test_failure_statuses_reject_smuggled_payload(status):
    """失败状态不得夹带答案、证据或引用（"看起来成功"的失败一律拒绝）。"""
    reason = ["文件已变化。"]

    with pytest.raises(RagContractError):
        validate_answer_payload(
            make_payload(status=status, answer=ANSWER_TEXT, evidence=[], citations=[], warnings=reason)
        )
    with pytest.raises(RagContractError):
        validate_answer_payload(
            make_payload(status=status, answer=None, evidence=[make_evidence()], citations=[], warnings=reason)
        )
    with pytest.raises(RagContractError):
        validate_answer_payload(
            make_payload(
                status=status,
                answer=None,
                evidence=[make_evidence()],
                citations=[make_citation()],
                warnings=reason,
            )
        )
    with pytest.raises(RagContractError):
        validate_answer_payload(
            make_payload(status=status, answer=None, evidence=[], citations=[], warnings=[])
        )


def test_stale_source_is_expressed_as_status_not_as_trimmed_span():
    """指纹变化 → stale_source；禁止把旧区间裁剪成"当前文件里合法"的区间。"""
    answer = validate_answer_payload(
        make_payload(
            status="stale_source",
            answer=None,
            evidence=[],
            citations=[],
            warnings=["源文件 sha256 与索引记录不一致；旧区间不再可解释，已停止展示引用。"],
        )
    )
    assert answer.status == "stale_source"

    # 试图用"裁剪后的合法区间 + status=stale_source"冒充：区间本身不越界，但仍必须被拒
    with pytest.raises(RagContractError):
        validate_answer_payload(
            make_payload(
                status="stale_source",
                answer=None,
                evidence=[make_evidence(charStart=0, charEnd=5, lineStart=1, lineEnd=1)],
                citations=[make_citation(charStart=0, charEnd=5, lineStart=1, lineEnd=1)],
                warnings=["已按新文件裁剪。"],
            )
        )


def test_out_of_range_is_expressed_as_status():
    answer = validate_answer_payload(
        make_payload(
            status="out_of_range",
            answer=None,
            evidence=[],
            citations=[],
            warnings=["引用区间超出源文件长度，已拒绝发布。"],
        )
    )
    assert answer.status == "out_of_range"


def test_unknown_status_is_rejected():
    with pytest.raises(ValidationError):
        validate_answer_payload(
            make_payload(status="partial", answer=None, evidence=[], citations=[], warnings=["x"])
        )


def test_payload_must_be_a_mapping():
    for bad in ([], "{}", None, 42):
        with pytest.raises(RagContractError):
            validate_answer_payload(bad)


# ---------------------------------------------------------------------------
# 4. 坐标口径：Python 码点 vs 前端 UTF-16 码元
# ---------------------------------------------------------------------------

#: 纯 BMP（中文）：码点数 == UTF-16 码元数
CJK_TEXT = "集合与常用逻辑用语"
#: 星平面字符（代理对）：1 个码点 == 2 个 UTF-16 码元
EMOJI_TEXT = "😀"
#: 混合：4 码点 / 5 码元
MIXED_TEXT = "题😀高中"

SAMPLES = [CJK_TEXT, EMOJI_TEXT, MIXED_TEXT, "", "a", "😀😀", "高😀中😀题"]


def utf16_length(text: str) -> int:
    """独立参照口径：UTF-16 码元数（不调用被测实现）。"""
    return len(text.encode("utf-16-le")) // 2


def test_codepoint_to_utf16_matches_independent_oracle():
    """断言口径：码点下标 i 的 UTF-16 偏移 == 前缀 `text[:i]` 的 UTF-16 码元数。"""
    for text in SAMPLES:
        assert utf16_length(text) == len(text) + sum(1 for ch in text if ord(ch) > 0xFFFF)
        for index in range(len(text) + 1):
            expected = utf16_length(text[:index])
            assert codepoint_to_utf16_offset(text, index) == expected
        # 端点：0 -> 0；len(text) -> 总码元数
        assert codepoint_to_utf16_offset(text, 0) == 0
        assert codepoint_to_utf16_offset(text, len(text)) == utf16_length(text)


def test_offsets_are_inverse_on_every_codepoint_boundary():
    """互逆：码点 -> 码元 -> 码点 在同一字符串的每个码点边界上恒等。"""
    for text in SAMPLES:
        for index in range(len(text) + 1):
            units = codepoint_to_utf16_offset(text, index)
            assert utf16_offset_to_codepoint(text, units) == index
        # 反方向：每个合法码元边界 -> 码点 -> 码元 也恒等
        for index in range(len(text) + 1):
            units = codepoint_to_utf16_offset(text, index)
            assert codepoint_to_utf16_offset(text, utf16_offset_to_codepoint(text, units)) == units


def test_cjk_and_emoji_explicit_values():
    """把"不可混用"写成具体数字，避免把 len() 当前端下标用。"""
    assert len(CJK_TEXT) == 9
    assert utf16_length(CJK_TEXT) == 9
    assert codepoint_to_utf16_offset(CJK_TEXT, 2) == 2

    assert len(EMOJI_TEXT) == 1
    assert utf16_length(EMOJI_TEXT) == 2
    assert codepoint_to_utf16_offset(EMOJI_TEXT, 1) == 2

    assert len(MIXED_TEXT) == 4
    assert utf16_length(MIXED_TEXT) == 5
    assert codepoint_to_utf16_offset(MIXED_TEXT, 1) == 1   # "题"
    assert codepoint_to_utf16_offset(MIXED_TEXT, 2) == 3   # "题😀"
    assert codepoint_to_utf16_offset(MIXED_TEXT, 3) == 4   # "题😀高"
    assert codepoint_to_utf16_offset(MIXED_TEXT, 4) == 5   # 末尾

    # 关键反例：把 len() 当 UTF-16 下标会少 1
    assert codepoint_to_utf16_offset(MIXED_TEXT, len(MIXED_TEXT)) != len(MIXED_TEXT)


def test_utf16_offset_inside_surrogate_pair_is_rejected():
    """落在代理对内部的下标不对应任何码点边界：拒绝，不得取整。"""
    with pytest.raises(ValueError):
        utf16_offset_to_codepoint("😀", 1)
    with pytest.raises(ValueError):
        utf16_offset_to_codepoint(MIXED_TEXT, 2)   # "题" 之后、emoji 中间
    # 但代理对边界必须可用
    assert utf16_offset_to_codepoint("😀", 0) == 0
    assert utf16_offset_to_codepoint("😀", 2) == 1
    assert utf16_offset_to_codepoint(MIXED_TEXT, 3) == 2


def test_out_of_range_offsets_are_rejected_not_clamped():
    for text in SAMPLES:
        units = utf16_length(text)
        with pytest.raises(ValueError):
            codepoint_to_utf16_offset(text, len(text) + 1)
        with pytest.raises(ValueError):
            codepoint_to_utf16_offset(text, -1)
        with pytest.raises(ValueError):
            utf16_offset_to_codepoint(text, units + 1)
        with pytest.raises(ValueError):
            utf16_offset_to_codepoint(text, -1)
    # 空串只有唯一合法位置
    assert codepoint_to_utf16_offset("", 0) == 0
    assert utf16_offset_to_codepoint("", 0) == 0
    with pytest.raises(ValueError):
        codepoint_to_utf16_offset("", 1)


def test_non_string_or_non_int_arguments_are_rejected():
    with pytest.raises(TypeError):
        codepoint_to_utf16_offset(b"abc", 1)
    with pytest.raises(TypeError):
        utf16_offset_to_codepoint(b"abc", 1)
    with pytest.raises(TypeError):
        codepoint_to_utf16_offset("abc", "1")
    with pytest.raises(TypeError):
        codepoint_to_utf16_offset("abc", True)      # bool 是 int 子类，仍拒绝
    with pytest.raises(TypeError):
        utf16_offset_to_codepoint("abc", True)


# ---------------------------------------------------------------------------
# 5. 能力可用性：不得返回假实现
# ---------------------------------------------------------------------------


def test_get_rag_adapter_requires_application_owned_service():
    for _ in range(3):
        with pytest.raises(RagAdapterUnavailable) as excinfo:
            get_rag_adapter()
        assert isinstance(excinfo.value, RuntimeError)
        assert str(excinfo.value) == RAG_UNAVAILABLE_MESSAGE
        assert "运行时" in str(excinfo.value)


def test_capability_declaration_is_not_ready():
    assert RAG_CAPABILITY["feature"] == "rag"
    assert RAG_CAPABILITY["status"] == "unavailable"
    assert RAG_CAPABILITY["status"] != "ready"
    assert RAG_CAPABILITY["detail"].strip()


def test_capabilities_endpoint_reports_missing_runtime(client):
    """与既有 capabilities 端点交叉核对：本批没有把 rag 改成 ready。"""
    body = client.get("/api/v1/capabilities").json()
    features = {item["feature"]: item for item in body["capabilities"]}
    assert features["rag"]["status"] == "unavailable"
