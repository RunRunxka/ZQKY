"""确认入库前的结构校验与答案状态判定（纯函数，不碰数据库与外部 I/O）。

判定规则（与任务卡一致）：
- 草稿必须显式标记 ``reviewed`` 才能入库；
- 选择题必须有选项，且答案里的 choiceKey 必须存在于选项中；
- ``true_false`` 的答案必须给出非空 ``accepted``；
- ``fill_blank`` / ``short_answer`` 的答案必须给出 ``textMarkdown``；
- 答案缺失（``answer`` 为空或全部字段为空）时必须显式确认"原文未提供答案"；
- 答案缺失的题目可以入库，``answerState`` 保持 ``not_provided`` 并继续显示。

草稿知识点关联（B2）：
- 输入只带 ``knowledgePointId`` + ``role``；知识点身份/修订/名称/学科由服务层向
  知识点库（只读）解析后补成**完整快照行**，本模块只做形状与去重校验；
- 同一知识点在一次请求里重复出现 → 422 ``KNOWLEDGE_LINK_DUPLICATE``，不静默去重。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.exceptions import AppError
from app.schemas.question_bank import QuestionAnswer, QuestionContent, QuestionMetadata

CHOICE_TYPES = frozenset({"single_choice", "multiple_choice"})
TEXT_ANSWER_TYPES = frozenset({"fill_blank", "short_answer"})
LINK_ROLES = frozenset({"primary", "secondary"})


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


def parse_knowledge_links(raw: object) -> list[tuple[str, str]]:
    """草稿关联输入 → ``[(knowledgePointId, role)]``；形状非法/重复一律 422。"""
    if raw is None:
        return []
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise AppError(
            "knowledgeLinks 必须是数组。",
            code="KNOWLEDGE_LINK_INVALID",
            status_code=422,
        )
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, Mapping):
            point_id = item.get("knowledgePointId")
            role = item.get("role", "primary")
        else:  # pydantic 模型（DraftKnowledgeLinkInput）同样接受
            point_id = getattr(item, "knowledgePointId", None)
            role = getattr(item, "role", "primary")
        if not isinstance(point_id, str) or not point_id.strip():
            raise AppError(
                "knowledgeLinks 的 knowledgePointId 必须是非空字符串。",
                code="KNOWLEDGE_LINK_INVALID",
                status_code=422,
            )
        if not isinstance(role, str) or role not in LINK_ROLES:
            raise AppError(
                f"knowledgeLinks 的 role 必须是 {sorted(LINK_ROLES)} 之一。",
                code="KNOWLEDGE_LINK_INVALID",
                status_code=422,
            )
        point_id = point_id.strip()
        if point_id in seen:
            raise AppError(
                f"knowledgeLinks 里同一知识点不允许重复：{point_id}。",
                code="KNOWLEDGE_LINK_DUPLICATE",
                status_code=422,
            )
        seen.add(point_id)
        links.append((point_id, role))
    return links
