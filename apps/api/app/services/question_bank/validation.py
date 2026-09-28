"""确认入库前的结构校验与答案状态判定（纯函数，不碰数据库与外部 I/O）。

判定规则（与任务卡一致）：
- 草稿必须显式标记 ``reviewed`` 才能入库；
- 选择题必须有选项，且答案里的 choiceKey 必须存在于选项中；
- ``true_false`` 的答案必须给出非空 ``accepted``；
- ``fill_blank`` / ``short_answer`` 的答案必须给出 ``textMarkdown``；
- 答案缺失（``answer`` 为空或全部字段为空）时必须显式确认"原文未提供答案"；
- 答案缺失的题目可以入库，``answerState`` 保持 ``not_provided`` 并继续显示。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.exceptions import AppError
from app.schemas.question_bank import QuestionAnswer, QuestionContent, QuestionMetadata

CHOICE_TYPES = frozenset({"single_choice", "multiple_choice"})
TEXT_ANSWER_TYPES = frozenset({"fill_blank", "short_answer"})


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


def parse_content(raw: object) -> QuestionContent:
    try:
        return QuestionContent.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 - pydantic 细节不外泄，只给出稳定错误码
        raise AppError(
            f"题目内容不符合题库契约：{exc.__class__.__name__}。",
            code="DRAFT_CONTENT_INVALID",
            status_code=422,
        ) from exc


def parse_metadata(raw: object) -> QuestionMetadata:
    try:
        return QuestionMetadata.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            f"题目分类不符合题库契约：{exc.__class__.__name__}。",
            code="DRAFT_METADATA_INVALID",
            status_code=422,
        ) from exc


def answer_has_content(content: QuestionContent) -> bool:
    answer = content.answer
    if answer is None:
        return False
    if answer.choiceKeys:
        return True
    if answer.accepted is not None:
        return True
    return bool(answer.textMarkdown and answer.textMarkdown.strip())


def answer_state_of(content: QuestionContent) -> str:
    return "provided" if answer_has_content(content) else "not_provided"


def validate_for_confirm(
    *, content: QuestionContent, review_state: str, missing_answer_acknowledged: bool
) -> ValidationIssue | None:
    if review_state != "reviewed":
        return ValidationIssue(
            code="DRAFT_NOT_REVIEWED",
            message="草稿尚未标记为已校对，不能入库。",
        )

    answer: QuestionAnswer | None = content.answer
    option_keys = {option.key for option in content.options}
    provided = answer_has_content(content)

    if not provided and not missing_answer_acknowledged:
        return ValidationIssue(
            code="MISSING_ANSWER_NOT_ACKNOWLEDGED",
            message="原文未提供答案的题目需要显式确认后才能入库。",
        )

    if content.type in CHOICE_TYPES and not content.options:
        return ValidationIssue(
            code="CHOICE_OPTIONS_REQUIRED",
            message="选择题必须至少有一个选项。",
        )

    if answer is not None and answer.choiceKeys:
        unknown = [key for key in answer.choiceKeys if key not in option_keys]
        if unknown:
            return ValidationIssue(
                code="ANSWER_KEY_NOT_IN_OPTIONS",
                message=f"答案 key 不存在于选项中：{', '.join(unknown)}。",
            )
        if content.type == "single_choice" and len(answer.choiceKeys) != 1:
            return ValidationIssue(
                code="CHOICE_KEY_COUNT_INVALID",
                message="单选题的答案只能有一个选项 key。",
            )
        if content.type in TEXT_ANSWER_TYPES:
            return ValidationIssue(
                code="ANSWER_KIND_MISMATCH",
                message="填空题/简答题的答案应为文本，不接受选项 key。",
            )

    if content.type == "true_false" and provided and answer is not None:
        if answer.accepted is None:
            return ValidationIssue(
                code="TRUE_FALSE_ANSWER_REQUIRED",
                message="判断题的答案必须是 accepted 真/假，或改成文本答案。",
            )

    if content.type in TEXT_ANSWER_TYPES and provided and answer is not None:
        if not (answer.textMarkdown and answer.textMarkdown.strip()):
            return ValidationIssue(
                code="ANSWER_TEXT_REQUIRED",
                message="填空题/简答题的答案必须提供 textMarkdown。",
            )

    return None


def content_payload(content: QuestionContent) -> dict[str, Any]:
    return content.model_dump(mode="json")
