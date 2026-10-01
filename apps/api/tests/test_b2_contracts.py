"""B2 契约测试（TEACHING-LOOP B2 / 验收 A2）。

覆盖：分值十进制字符串边界（×100 整数单位口径）、草稿 PATCH/确认请求形状与别名往返、
参测输入的"显式确认必须带依据"对称约束、题库六态视图与生成请求、错误码常量存在性。
TS 镜像的一致性由 `npm run typecheck` 与本文件字段名对照保证（字段名在测试中逐项断言）。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import pytest
from pydantic import ValidationError

from app.contracts.assessments import (
    ASSESSMENT_PAPER_INVALID,
    PARTICIPANT_CLASS_UNCONFIRMED,
    AssessmentCreateRequest,
    ParticipantAddRequest,
)
from app.contracts.papers import (
    ITEM_CYCLE,
    PAPER_BLOCK_UNASSIGNED,
    PAPER_CONFIRM_INVALID,
    PAPER_REVISION_STALE,
    PaperConfirmRequest,
    PaperDraftPatchRequest,
    PaperProposalDecisionRequest,
)
from app.schemas.question_bank import (
    DraftPatchRequest,
    GenerationJobView,
    OrganizeJobView,
    QuestionGenerationRequest,
)


def test_paper_patch_accepts_camel_case_and_rejects_unknown() -> None:
    payload = {
        "expectedRevision": 3,
        "items": [
            {
                "questionNo": "16(1)",
                "ordinal": 1,
                "isScored": True,
                "maxScore": "2.5",
                "parentItemId": None,
                "content": {"version": 2},
                "sourceLocator": {"blockStart": 4},
                "knowledge": [{"knowledgePointId": "kp1", "role": "primary"}],
            }
        ],
        "blocks": [
            {"blockId": "b1", "disposition": "item", "itemId": "it1"},
            {"blockId": "b2", "disposition": "excluded", "excludeReason": "页眉"},
        ],
    }
    parsed = PaperDraftPatchRequest.model_validate(payload)
    assert parsed.items[0].max_score == "2.5"
    assert parsed.items[0].knowledge[0].knowledge_point_id == "kp1"
    assert parsed.blocks[1].exclude_reason == "页眉"
    with pytest.raises(ValidationError):
        PaperDraftPatchRequest.model_validate({**payload, "unexpected": 1})


def test_score_text_pattern_boundaries() -> None:
    ok = ["0.01", "2", "2.5", "100", "9999.99"]
    bad = ["2.555", "-1", "abc", "1e3", "", "2,5", " 2"]
    for text in ok:
        PaperDraftPatchRequest(
            expectedRevision=0,
            items=[{"questionNo": "1", "ordinal": 1, "isScored": True, "maxScore": text}],
        )
    for text in bad:
        with pytest.raises(ValidationError):
            PaperDraftPatchRequest(
                expectedRevision=0,
                items=[{"questionNo": "1", "ordinal": 1, "isScored": True, "maxScore": text}],
            )
    # ×100 整数单位口径（服务端实现使用的换算方式，这里固定算法意图）
    units = int((Decimal("2.5") * 100).to_integral_value())
    assert units == 250
    with pytest.raises(InvalidOperation):
        Decimal("abc")


def test_confirm_and_proposal_requests_require_guards() -> None:
    confirm = PaperConfirmRequest.model_validate(
        {"expectedRevision": 1, "submissionId": "sub-1"}
    )
    assert confirm.submission_id == "sub-1"
    with pytest.raises(ValidationError):
        PaperConfirmRequest.model_validate({"expectedRevision": 1})
    decision = PaperProposalDecisionRequest.model_validate(
        {"expectedRevision": 2, "selections": []}
    )
    assert decision.selections == []


def test_assessment_participant_confirmation_must_carry_note() -> None:
    base = {
        "submissionId": "sub-1",
        "paperRevisionId": "pr-1",
        "title": "第一次月考",
        "heldOn": "2026-10-08",
        "classIds": ["c1"],
        "participants": [{"studentId": "s1", "classId": "c1"}],
    }
    request = AssessmentCreateRequest.model_validate(base)
    assert request.participants[0].class_confirmed is False
    confirmed = AssessmentCreateRequest.model_validate(
        {
            **base,
            "participants": [
                {
                    "studentId": "s1",
                    "classId": "c1",
                    "classConfirmed": True,
                    "classConfirmationNote": "名单今日导入，历史归属不覆盖施测日",
                }
            ],
        }
    )
    assert confirmed.participants[0].class_confirmation_note
    # 确认却没依据 → 拒绝（与 DB CHECK 对称）
    with pytest.raises(ValidationError):
        AssessmentCreateRequest.model_validate(
            {**base, "participants": [{"studentId": "s1", "classId": "c1", "classConfirmed": True}]}
        )
    # 有依据却没确认 → 拒绝
    with pytest.raises(ValidationError):
        AssessmentCreateRequest.model_validate(
            {
                **base,
                "participants": [
                    {"studentId": "s1", "classId": "c1", "classConfirmationNote": "备注"}
                ],
            }
        )
    # 空名单与重复班级 → 拒绝
    with pytest.raises(ValidationError):
        AssessmentCreateRequest.model_validate({**base, "participants": []})
    with pytest.raises(ValidationError):
        AssessmentCreateRequest.model_validate({**base, "classIds": ["c1", "c1"]})
    add = ParticipantAddRequest.model_validate(
        {
            "submissionId": "sub-2",
            "expectedRevision": 0,
            "participants": [{"studentId": "s1", "classId": "c1", "attemptNo": 2}],
        }
    )
    assert add.participants[0].attempt_no == 2


def test_organize_view_six_states_and_generation_request() -> None:
    for state in ("queued", "running", "succeeded", "failed", "cancelled", "interrupted"):
        view = OrganizeJobView(jobId="j1", state=state, suggestionCount=0, failedBatches=0, errorCode=None)
        assert view.attempt == 0
    job = GenerationJobView(jobId="j2", state="interrupted", importId=None, candidateCount=0, errorCode=None)
    assert job.state == "interrupted"
    request = QuestionGenerationRequest.model_validate(
        {
            "modelProfileId": "p1",
            "subjectId": "math",
            "knowledgePointIds": ["kp1"],
            "questionTypes": ["single_choice"],
            "difficulty": "medium",
            "count": 2,
        }
    )
    assert request.count == 2
    draft_patch = DraftPatchRequest.model_validate(
        {
            "expectedRevision": 0,
            "content": {
                "type": "single_choice",
                "stemMarkdown": "题干",
                "options": [{"key": "A", "textMarkdown": "a"}],
            },
            "metadata": {},
            "knowledgeLinks": [{"knowledgePointId": "kp1"}],
        }
    )
    # app/schemas/question_bank.py 用 camelCase 字段名（无别名），访问属性即 camelCase
    assert draft_patch.knowledgeLinks is not None
    assert draft_patch.knowledgeLinks[0].role == "primary"


def test_error_codes_exported() -> None:
    assert PAPER_CONFIRM_INVALID and PAPER_REVISION_STALE and ITEM_CYCLE
    assert PAPER_BLOCK_UNASSIGNED and ASSESSMENT_PAPER_INVALID and PARTICIPANT_CLASS_UNCONFIRMED
