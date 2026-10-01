"""AI 整理的批次打包、回复校验与错误分类（不自动下载、不调用云端、不自己选模型）。

模型语义（RAG-QUALITY v1.1 起，唯一定义，见 `docs/PLAN.md` §5.1）：

- 题库「AI 整理」使用**点击时的当前聊天模型，本地或云端一视同仁**；
- ``OrganizeRequest.modelProfileId`` 是聊天模型 profile id，解析走共享的
  ``app.services.model_runtime.resolve_chat_model``（服务层注入 ``model_resolver`` 调用）；
  本模块不解释 profile id、不列本机模型清单、不做任何默认模型回退——不得留下第二套模型选择；
- 模型调用经 ``provider.complete(config, request)``（非流式），网络调用一律在 SQL 写事务之外；
- 建任务时把 ``modelProfileId`` 与非敏感 ``modelFingerprint`` 冻结进 checkpoint；
  任务进行中用户切换聊天模型不影响已冻结任务。

预算：每批 ``MAX_BATCH_INPUT_CHARS`` 个 **Unicode 码点**，**包含来源标签与分隔符**
（``Batch.char_count`` 恒等于 ``len(Batch.input_text)``，且恒 ≤ 上限）；输出预算
``MAX_OUTPUT_TOKENS``，并受所选模型 ``max_output_tokens`` 约束（取较小值，见服务层）。

错误分类（本批唯一事实来源；服务层按 ``BATCH_LEVEL_ORGANIZER_ERRORS`` 分流，
**绝不把上游失败说成题目有问题**）：

- **批级**（内容问题：该批失败，原文保留、草稿不变，其余批次继续）：
  ``ORGANIZER_INVALID_JSON``（非法 JSON）、``ORGANIZER_OUTPUT_TRUNCATED``
  （``finish_reason == length`` 截断，**不生成可应用建议**）、
  ``ORGANIZER_UNKNOWN_SOURCE_BLOCK``（未知 sourceBlockId）、``ORGANIZER_INVALID_CONTENT``
  （不符合题库契约）；草稿在整理期间被人工编辑另记 ``ORGANIZE_DRAFT_CHANGED``；
- **任务级**（模型服务问题：整条任务失败，错误文案指向模型服务）：
  认证 ``AUTH_REQUIRED``、限流 ``RATE_LIMITED``、网络/超时/协议/未知上游故障统一
  ``UPSTREAM_UNAVAILABLE``；模型配置类 ``MODEL_NOT_CONFIGURED`` / ``MODEL_PROFILE_NOT_FOUND`` /
  ``MODEL_PURPOSE_MISMATCH`` 原样保留（可读、可操作）；整理器未装配 ``SERVICE_UNAVAILABLE``；
- **旧语义 checkpoint**（不是本契约形状）：不自动恢复，标记 ``ORGANIZER_MODEL_RESELECT_REQUIRED``，
  已产生的建议（``question_suggestions``）一条不动。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol, Sequence
from urllib.parse import urlsplit

from app.core.exceptions import AppError
from app.services.model_runtime import ChatModelHandle
from app.services.question_bank import validation
from app.services.question_bank.fingerprint import canonical_json
from app.services.question_bank.rules import infer_type

#: 单批输入上限（Unicode 码点；含 ``[块 id]`` 标签与 ``\n\n`` 分隔符）
MAX_BATCH_INPUT_CHARS = 6000
#: 组织者侧输出上限；实际请求值 = min(它, 所选模型的 max_output_tokens)
MAX_OUTPUT_TOKENS = 2048
#: 标签与分隔符之外至少要留出的正文预算；小到无法容纳来源标签属于装配错误
MIN_BLOCK_BODY_CHARS = 64
#: 冻结 checkpoint 的契约版本；低于它的未完成任务一律不自动恢复
ORGANIZE_CONTRACT_VERSION = 2

_BLOCK_SEPARATOR = "\n\n"

ORGANIZE_INSTRUCTION = (
    "整理提供的试题原文。返回题干、选项、原文已有答案与解析，以及 sourceBlockIds。"
    "不推断原文缺失的答案，不引用输入之外的来源。"
    "只输出一个 JSON 对象，字段固定为："
    '{"type":"single_choice|multiple_choice|true_false|fill_blank|short_answer|other",'
    '"stem":"题干 Markdown","options":[{"key":"A","text":"选项文本"}],'
    '"answer":{"choiceKeys":["A"],"accepted":null,"text":null} 或 null,'
    '"explanation":"解析文本或 null","sourceBlockIds":["<输入中出现的块 id>"]}。'
    "没有把握的字段留空或 null，不要编造，不要输出 JSON 以外的任何文字。"
)

#: 批级失败码：该批不产生建议，原文保留、草稿不变，其余批次继续
BATCH_LEVEL_ORGANIZER_ERRORS = frozenset(
    {
        "ORGANIZER_INVALID_JSON",
        "ORGANIZER_OUTPUT_TRUNCATED",
        "ORGANIZER_UNKNOWN_SOURCE_BLOCK",
        "ORGANIZER_INVALID_CONTENT",
    }
)
#: 服务层补记的批级失败码（在事务内核对草稿时产生）
BATCH_LEVEL_CONFLICT_ERRORS = frozenset(
    {"ORGANIZE_DRAFT_CHANGED", "ORGANIZE_TARGET_MISSING"}
)

#: 上游/装配错误码 → 任务级错误码。未列出的 code 一律按 ``UPSTREAM_UNAVAILABLE`` 处理：
#: 分不清是不是内容问题时，按「模型服务问题」落库，不冤枉试题内容。
JOB_LEVEL_ERROR_CODES: dict[str, str] = {
    "AUTH_REQUIRED": "AUTH_REQUIRED",
    "UPSTREAM_AUTH_FAILED": "AUTH_REQUIRED",
    "RATE_LIMITED": "RATE_LIMITED",
    "UPSTREAM_TIMEOUT": "UPSTREAM_UNAVAILABLE",
    "UPSTREAM_UNREACHABLE": "UPSTREAM_UNAVAILABLE",
    "UPSTREAM_ERROR": "UPSTREAM_UNAVAILABLE",
    "UPSTREAM_PROTOCOL_ERROR": "UPSTREAM_UNAVAILABLE",
    "EMPTY_RESPONSE": "UPSTREAM_UNAVAILABLE",
    "MODEL_NOT_CONFIGURED": "MODEL_NOT_CONFIGURED",
    "MODEL_PROFILE_NOT_FOUND": "MODEL_PROFILE_NOT_FOUND",
    "MODEL_PURPOSE_MISMATCH": "MODEL_PURPOSE_MISMATCH",
    "SERVICE_UNAVAILABLE": "SERVICE_UNAVAILABLE",
}
#: 任务级错误码全集（落进 ``question_jobs.error_code``）
JOB_LEVEL_ORGANIZER_ERRORS = frozenset(JOB_LEVEL_ERROR_CODES.values())

#: 面向固定文案：所有任务级文案都指向「模型服务」，绝不出现「试题内容无效」一类表述
JOB_LEVEL_MESSAGES: dict[str, str] = {
    "AUTH_REQUIRED": "模型服务认证失败：请在模型设置里检查该模型的凭证后重试。",
    "RATE_LIMITED": "模型服务限流：请稍后重试，或改选其他聊天模型。",
    "MODEL_NOT_CONFIGURED": "所选模型配置当前不可调用：请在模型设置里补全后重试。",
    "MODEL_PROFILE_NOT_FOUND": "所选模型配置已不存在：请重新选择聊天模型后再整理。",
    "MODEL_PURPOSE_MISMATCH": "所选模型配置用途不是聊天：请改选聊天模型后再整理。",
    "SERVICE_UNAVAILABLE": "题库 AI 整理未装配模型解析器（model_resolver）：请检查后端启动配置。",
    "UPSTREAM_UNAVAILABLE": "模型服务当前不可用（网络或上游故障）：请稍后重试，或改选其他聊天模型。",
}
DEFAULT_JOB_LEVEL_MESSAGE = JOB_LEVEL_MESSAGES["UPSTREAM_UNAVAILABLE"]

#: 旧语义 checkpoint（不是 profile id 形状）不自动恢复，要求重新选择模型
RESELECT_MODEL_CODE = "ORGANIZER_MODEL_RESELECT_REQUIRED"
RESELECT_MODEL_MESSAGE = (
    "该整理任务由旧版模型语义创建，未自动恢复：请在界面上重新选择聊天模型后再整理；"
    "已产生的建议一条未动。"
)


def job_level_error_code(code: str) -> str:
    """任意 AppError.code → 任务级错误码（未知 code 归入 ``UPSTREAM_UNAVAILABLE``）。"""
    if code in BATCH_LEVEL_ORGANIZER_ERRORS or code in BATCH_LEVEL_CONFLICT_ERRORS:
        # 批级码不得被任务级路径吞掉：调用方应先按批级分流，这里保持其原值只作兜底
        return "UPSTREAM_UNAVAILABLE"
    return JOB_LEVEL_ERROR_CODES.get(code, "UPSTREAM_UNAVAILABLE")


def job_level_message(code: str) -> str:
    return JOB_LEVEL_MESSAGES.get(code, DEFAULT_JOB_LEVEL_MESSAGE)


def output_truncated_error() -> AppError:
    """``finish_reason == length``：该批失败且不生成可应用建议（不是题目内容有问题）。"""
    return AppError(
        "模型输出被截断（结束原因 length）：该批未生成可应用建议，原文保留、草稿不变；"
        "请提高该模型的输出上限或缩小该批原文后重试。",
        code="ORGANIZER_OUTPUT_TRUNCATED",
        status_code=422,
    )


def batch_budget_error(hint: str) -> AppError:
    return AppError(
        f"原文块超出单批预算且无法安全切片（{hint}）。",
        code="ORGANIZER_BATCH_BUDGET_INVALID",
        status_code=422,
    )


@dataclass(frozen=True)
class Batch:
    """一个打包好的模型输入批次；``char_count`` 恒等于 ``len(input_text)``。"""

    index: int
    draft_id: str
    block_ids: tuple[str, ...]
    input_text: str
    char_count: int


class ChatModelResolver(Protocol):
    """依赖注入缝：``(modelProfileId) -> ChatModelHandle``。

    唯一实现由总控在 ``main.py`` 装配（内部走共享的
    ``services.model_runtime.resolve_chat_model``）；题库不自己解析 profile id。
    """

    def __call__(self, model_profile_id: str) -> ChatModelHandle:  # pragma: no cover - 协议声明
        ...


def block_prefix(block_id: str) -> str:
    return f"[块 {block_id}]\n"


def render_block(block_id: str, text: str) -> str:
    return f"{block_prefix(block_id)}{text.strip()}"


def pack_batches(
    draft_id: str,
    blocks: Sequence[tuple[str, str]],
    *,
    start_index: int = 0,
    max_chars: int = MAX_BATCH_INPUT_CHARS,
) -> list[Batch]:
    """按完整原文块打包；**标签与分隔符都计入预算**，每批 ``input_text`` 长度 ≤ ``max_chars``。

    - 单块渲染后仍超限时按行切批（同一 ``block id`` 出现在多批，来源可回溯）；
    - 不丢弃原文：同一块的多个切片按序拼接后等于原块正文（首尾空白除外）；
    - 只打包给定的块，不做任何跨草稿合并。
    """
    if max_chars <= 0:
        raise batch_budget_error(f"max_chars={max_chars}")
    batches: list[Batch] = []
    pending: list[str] = []
    pending_ids: list[str] = []
    pending_chars = 0

    def flush() -> None:
        nonlocal pending, pending_ids, pending_chars
        if not pending:
            return
        input_text = _BLOCK_SEPARATOR.join(pending)
        batches.append(
            Batch(
                index=start_index + len(batches),
                draft_id=draft_id,
                block_ids=tuple(pending_ids),
                input_text=input_text,
                char_count=len(input_text),
            )
        )
        pending = []
        pending_ids = []
        pending_chars = 0

    for block_id, text in blocks:
        rendered = render_block(block_id, text)
        if len(rendered) <= max_chars:
            if pending and pending_chars + len(rendered) + len(_BLOCK_SEPARATOR) > max_chars:
                flush()
            pending.append(rendered)
            pending_ids.append(block_id)
            pending_chars += len(rendered) + (
                len(_BLOCK_SEPARATOR) if len(pending) > 1 else 0
            )
            continue
        flush()
        for slice_text in slice_block(block_id, text, max_chars):
            input_text = render_block(block_id, slice_text)
            batches.append(
                Batch(
                    index=start_index + len(batches),
                    draft_id=draft_id,
                    block_ids=(block_id,),
                    input_text=input_text,
                    char_count=len(input_text),
                )
            )
    flush()
    return batches


def slice_block(block_id: str, text: str, max_chars: int) -> list[str]:
    """把超长块切成能装进 ``max_chars``（已扣除标签与换行）的正文片段。

    按行聚合；单行本身超预算时按字符硬切，保证每个片段渲染后都不超上限。
    """
    body_budget = max_chars - len(block_prefix(block_id))
    if body_budget < MIN_BLOCK_BODY_CHARS:
        raise batch_budget_error(f"block={block_id} 的正文预算只剩 {body_budget} 码点")
    lines = text.split("\n")
    slices: list[str] = []
    current: list[str] = []
    current_chars = 0
    for line in lines:
        if current and current_chars + len(line) + 1 > body_budget:
            slices.append("\n".join(current))
            current = []
            current_chars = 0
        if len(line) > body_budget:
            for start in range(0, len(line), body_budget):
                slices.append(line[start : start + body_budget])
            continue
        current.append(line)
        current_chars += len(line) + 1
    if current:
        slices.append("\n".join(current))
    return slices or [text]


#: 允许的题目类型（与共享契约 ``QuestionType`` 一致；模型给别的值就按规则回退）
_QUESTION_TYPES = frozenset(
    {
        "single_choice",
        "multiple_choice",
        "true_false",
        "fill_blank",
        "short_answer",
        "other",
    }
)


def normalize_reply(raw: str, allowed_block_ids: Sequence[str]) -> dict[str, Any]:
    """把模型回复规范化为题库内容与来源；任一处不合法抛对应**批级**错误码。

    - 非法 JSON / 非对象 → ``ORGANIZER_INVALID_JSON``；
    - 缺 ``sourceBlockIds`` 或引用了输入之外的块 → ``ORGANIZER_UNKNOWN_SOURCE_BLOCK``；
    - 缺题干或不符合题库契约 → ``ORGANIZER_INVALID_CONTENT``；
    - 以上都失败该批，**原文保留、草稿不变**（由调用方落库失败批记录）。
    """
    allowed = {block_id for block_id in allowed_block_ids}
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            head, _, tail = text.partition("\n")
            if head.strip().lower() in {"json", ""}:
                text = tail
        text = text.strip()
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise AppError(
            "模型返回内容不是合法 JSON，该批已失败，原文保留、草稿不变。",
            code="ORGANIZER_INVALID_JSON",
            status_code=422,
        ) from exc
    if not isinstance(payload, dict):
        raise AppError(
            "模型返回的 JSON 不是对象，该批已失败，原文保留、草稿不变。",
            code="ORGANIZER_INVALID_JSON",
            status_code=422,
        )

    block_ids = _string_list(payload.get("sourceBlockIds"))
    if not block_ids:
        raise AppError(
            "模型未返回 sourceBlockIds，无法核验来源，该批已失败，原文保留、草稿不变。",
            code="ORGANIZER_UNKNOWN_SOURCE_BLOCK",
            status_code=422,
        )
    unknown = [block_id for block_id in block_ids if block_id not in allowed]
    if unknown:
        raise AppError(
            f"模型引用了输入之外的来源块：{', '.join(unknown[:5])}，"
            "该批已失败，原文保留、草稿不变。",
            code="ORGANIZER_UNKNOWN_SOURCE_BLOCK",
            status_code=422,
        )

    stem = _first_text(payload, ("stem", "stemMarkdown"))
    options = _options(payload.get("options"))
    answer = _answer(payload.get("answer"))
    explanation = _first_text(payload, ("explanation", "explanationMarkdown")) or None
    question_type = payload.get("type")
    if not isinstance(question_type, str) or question_type not in _QUESTION_TYPES:
        question_type = None
    if not stem:
        raise AppError(
            "模型返回内容缺少题干，该批已失败，原文保留、草稿不变。",
            code="ORGANIZER_INVALID_CONTENT",
            status_code=422,
        )

    content: dict[str, Any] = {
        "type": question_type or infer_type(stem, options, answer),
        "stemMarkdown": stem,
        "options": options,
        "answer": answer,
        "explanationMarkdown": explanation,
        "assetIds": [],
    }
    try:
        validation.parse_content(content)
    except AppError as exc:
        raise AppError(
            "模型返回内容不符合题库契约，该批已失败，原文保留、草稿不变。",
            code="ORGANIZER_INVALID_CONTENT",
            status_code=422,
        ) from exc
    return {"content": content, "source_block_ids": block_ids}


def _first_text(payload: dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _options(value: Any) -> list[dict[str, str]]:
    if value is None:
        return []
    options: list[dict[str, str]] = []
    if not isinstance(value, list):
        return options
    for item in value:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        text = _first_text(item, ("text", "textMarkdown"))
        if isinstance(key, str) and key.strip() and text:
            options.append({"key": key.strip(), "textMarkdown": text})
    return options


def _answer(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return (
            {"choiceKeys": [], "accepted": None, "textMarkdown": stripped}
            if stripped
            else None
        )
    if not isinstance(value, dict):
        return None
    keys = _string_list(value.get("choiceKeys"))
    accepted = value.get("accepted")
    if not isinstance(accepted, bool):
        accepted = None
    text = _first_text(value, ("textMarkdown", "text"))
    if not keys and accepted is None and not text:
        return None
    return {
        "choiceKeys": [key.upper() for key in keys],
        "accepted": accepted,
        "textMarkdown": text or None,
    }


def model_fingerprint(
    *, model_id: str, protocol: str, base_url: str, api_format: str
) -> str:
    """非敏感模型指纹；B3/G0 起实现统一在 ``app.services.model_runtime``（此处保留名字兼容）。"""
    from app.services.model_runtime import model_fingerprint as shared

    return shared(
        model_id=model_id, protocol=protocol, base_url=base_url, api_format=api_format
    )


def is_current_checkpoint(checkpoint: Any) -> bool:
    """checkpoint 是否为本契约形状（可自动恢复）。

    旧语义 checkpoint（把 profile id 当模型名、或缺 profile/指纹）返回 ``False``：
    恢复入口据此**拒绝自动恢复**并要求重新选择模型，绝不猜模型。
    """
    if not isinstance(checkpoint, dict):
        return False
    if checkpoint.get("contractVersion") != ORGANIZE_CONTRACT_VERSION:
        return False
    profile_id = checkpoint.get("modelProfileId")
    fingerprint = checkpoint.get("modelFingerprint")
    batches = checkpoint.get("batches")
    return (
        isinstance(profile_id, str)
        and bool(profile_id.strip())
        and isinstance(fingerprint, str)
        and bool(fingerprint)
        and isinstance(batches, list)
    )


def batch_snapshot(batches: Sequence[Batch]) -> list[dict[str, Any]]:
    """写入任务 checkpoint 的批次快照（可跨进程重启恢复）。"""
    return [
        {
            "index": batch.index,
            "draftId": batch.draft_id,
            "blockIds": list(batch.block_ids),
            "inputText": batch.input_text,
            "charCount": batch.char_count,
        }
        for batch in batches
    ]


def batch_from_snapshot(payload: dict[str, Any]) -> Batch:
    return Batch(
        index=int(payload["index"]),
        draft_id=str(payload["draftId"]),
        block_ids=tuple(str(item) for item in payload["blockIds"]),
        input_text=str(payload["inputText"]),
        char_count=int(payload["charCount"]),
    )


def deterministic_batch_key(batch: Batch) -> str:
    """批次的稳定标识：同快照重放得到同一 key（便于恢复时核对）。"""
    return canonical_json({"draftId": batch.draft_id, "blockIds": list(batch.block_ids)})


__all__ = [
    "BATCH_LEVEL_CONFLICT_ERRORS",
    "BATCH_LEVEL_ORGANIZER_ERRORS",
    "Batch",
    "ChatModelResolver",
    "JOB_LEVEL_ERROR_CODES",
    "JOB_LEVEL_MESSAGES",
    "JOB_LEVEL_ORGANIZER_ERRORS",
    "MAX_BATCH_INPUT_CHARS",
    "MAX_OUTPUT_TOKENS",
    "MIN_BLOCK_BODY_CHARS",
    "ORGANIZE_CONTRACT_VERSION",
    "ORGANIZE_INSTRUCTION",
    "RESELECT_MODEL_CODE",
    "RESELECT_MODEL_MESSAGE",
    "batch_from_snapshot",
    "batch_snapshot",
    "block_prefix",
    "deterministic_batch_key",
    "is_current_checkpoint",
    "job_level_error_code",
    "job_level_message",
    "model_fingerprint",
    "normalize_reply",
    "output_truncated_error",
    "pack_batches",
    "render_block",
    "slice_block",
]
