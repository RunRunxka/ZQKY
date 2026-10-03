"""AI 补题（``question:generate``）：冻结输入、独立回复解析与同事务发布。

与 AI 整理的分工（**不复用** ``organizer.normalize_reply``）：

- 整理要求模型引用**真实上传原文块**（``sourceBlockIds`` 必须命中输入集合）；
  AI 补题没有原文块，模型面对的是知识点、可选证据（受管资料文本）与命题指令，
  因此使用独立解析器 ``parse_generation_reply``（``GenerateReply`` 的实现），
  **不得**把补题结果塞进整理器的解析器里冒充"来自教材"；
- 补题的产物是 ``question_drafts``（``extraction_method='ai'``、``review_state='needs_review'``）
  与草稿知识点关联（``source='ai'``），随后走既有校对 → 确认链；
  **AI 草稿永远不会绕过确认进入正式题目表**（既有确认闸门一字不改）。

校验（任一不通过 → 整条任务失败，**零可发布半批**）：

- ``GENERATION_INVALID_JSON``：回复不是合法 JSON 对象 / ``questions`` 不是数组；
- ``GENERATION_OUTPUT_TRUNCATED``：``finish_reason == length``（截断输出不可发布）；
- ``GENERATION_CANDIDATE_COUNT_MISMATCH``：候选数与冻结的 ``count`` 不一致；
- ``GENERATION_UNKNOWN_KNOWLEDGE``：``knowledgePointIds`` 引用了输入集合之外的知识点；
- ``GENERATION_UNKNOWN_EVIDENCE``：``evidenceIds`` 引用了输入之外的证据（虚构依据）；
- ``GENERATION_FORBIDDEN_REFERENCE``：题干/选项/答案/解析出现任意 URL（``http(s)://``、
  ``file://``）、盘符路径、UNC 路径或绝对路径；
- ``GENERATION_ASSET_INVALID`` / ``GENERATION_ASSET_NOT_REGISTERED``：``assetIds`` 只允许
  ``blobs/<64 位小写 hex>``，且该原件必须**已登记**（题库内容寻址存储里真实存在、
  读取时重算 sha256 一致）；首版 AI 新题以文字与公式为主，图片由教师提供受管资产；
- ``GENERATION_CONTENT_INVALID``：题目内容不符合题库契约（缺题干/选项结构非法等）。

发布（``JobOutcome.publish``，与任务 ``succeeded`` **同一事务**）：

- ``question_imports``（``state='needs_review'``，原件 = 模型原始回复的受管 blob）+
  每条候选一条 ``question_drafts`` + 草稿知识点关联（``source='ai'``）+
  ``question_import_provenance(source='ai', job_id, model_snapshot_json)`` + 任务终态；
- 失败/取消/失权/旧 attempt 迟到：事务整体回滚或根本不进入事务 → 零批次、零 provenance；
- 知识点快照在**发布前**（事务外、发布协调器内）向知识点库重读：存在、未归档、同学科、
  取**当前**修订与名称（关联时修订一致），冻结时的过期修订不写入草稿关联。

模型语义与整理一致：``modelProfileId`` 是点击时的当前聊天模型 profile id，解析只经注入的
``resolve_frozen_model``（生产走共享 ``services.model_runtime.resolve_frozen_model``）；
本模块不解释 profile id、不列模型清单、不做默认回退。任务进行中用户切换模型不影响已冻结任务，
但**同 profile 的真实配置**（模型/地址/格式）若与冻结指纹不一致，执行前即明确失败
（``MODEL_CONFIG_DRIFT``，零调用、零发布）；旧任务缺可核对指纹 → ``MODEL_FINGERPRINT_MISSING``。
来源记录（批次原件与 provenance）使用本次实际执行句柄的 ``fingerprint_of_handle``。
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.exceptions import AppError
from app.providers.llm.base import FINISH_LENGTH, LLMMessage, LLMRequest
from app.repositories.question_bank.records import DraftInput
from app.services.jobs.engine import FrozenJob, JobContext, JobOutcome
from app.services.model_runtime import ChatModelHandle, fingerprint_of_handle
from app.services.question_bank import fingerprint as fp
from app.services.question_bank import validation
from app.services.question_bank.blobs import QuestionBlobStore
from app.services.question_bank.organizer import job_level_message
from app.services.question_bank.rules import infer_type

#: 冻结输入的契约版本；不是这个形状的任务不自动执行（不猜模型、不猜语义）
GENERATION_CONTRACT_VERSION = 1
#: 单次补题的输出上限；实际请求值 = min(它, 所选模型的 max_output_tokens)
MAX_OUTPUT_TOKENS = 4096
#: 模型原始回复的字节上限（超过按失败处理，不落半截原件）
MAX_REPLY_BYTES = 1_000_000
#: 单条材料文本上限与全部材料合计上限（Unicode 码点）
MAX_MATERIAL_CHARS = 4000
MAX_MATERIALS_TOTAL_CHARS = 8000
#: 证据 id 形状：``m0``、``m1``…（冻结时按顺序生成，提示词里原样给模型）
MATERIAL_ID_PREFIX = "m"

INVALID_JSON = "GENERATION_INVALID_JSON"
OUTPUT_TRUNCATED = "GENERATION_OUTPUT_TRUNCATED"
CANDIDATE_COUNT_MISMATCH = "GENERATION_CANDIDATE_COUNT_MISMATCH"
UNKNOWN_KNOWLEDGE = "GENERATION_UNKNOWN_KNOWLEDGE"
UNKNOWN_EVIDENCE = "GENERATION_UNKNOWN_EVIDENCE"
FORBIDDEN_REFERENCE = "GENERATION_FORBIDDEN_REFERENCE"
ASSET_INVALID = "GENERATION_ASSET_INVALID"
ASSET_NOT_REGISTERED = "GENERATION_ASSET_NOT_REGISTERED"
CONTENT_INVALID = "GENERATION_CONTENT_INVALID"
MATERIAL_INVALID = "GENERATION_MATERIAL_INVALID"
INPUT_INVALID = "GENERATION_INPUT_INVALID"
KNOWLEDGE_UNAVAILABLE = "GENERATION_KNOWLEDGE_UNAVAILABLE"
KNOWLEDGE_SUBJECT_CHANGED = "GENERATION_KNOWLEDGE_SUBJECT_CHANGED"

QUESTION_TYPES = frozenset(
    {
        "single_choice",
        "multiple_choice",
        "true_false",
        "fill_blank",
        "short_answer",
        "other",
    }
)

#: 任意 URL / 文件路径的扫描（题干、选项、答案、解析一律拒绝）。
#: 路径形状刻意收紧到"至少两级、首段以字母开头"，避免把 ``4/5`` 这类普通比值当路径。
_URL_PATTERN = re.compile(r"(?:https?|file|ftp)://", re.IGNORECASE)
_WINDOWS_PATH_PATTERN = re.compile(r"(?:^|[^A-Za-z0-9_])([A-Za-z]:[\\/])")
_UNC_PATH_PATTERN = re.compile(r"\\[A-Za-z0-9_.$-]+[\\/]")
_POSIX_PATH_PATTERN = re.compile(
    r"(?:^|[\s(\[<\"'`=,:;])(/(?:[A-Za-z][A-Za-z0-9_.$-]*/)+[A-Za-z0-9_.$-]*)"
)
_BACKSLASH_PATH_PATTERN = re.compile(
    r"(?:^|[\s(\[<\"'`=,:;])(\\(?:[A-Za-z][A-Za-z0-9_.$-]*\\)+[A-Za-z0-9_.$-]*)"
)
_BLOB_ASSET_PATTERN = re.compile(r"blobs/([0-9a-f]{64})")

INSTRUCTION_TEMPLATE = (
    "你是学科命题助手。根据给定的知识点与可选证据命制 {count} 道题，只输出一个 JSON 对象，"
    "字段固定为："
    '{{"questions":[{{"type":"single_choice|multiple_choice|true_false|fill_blank|short_answer|other",'
    '"stemMarkdown":"题干","options":[{{"key":"A","textMarkdown":"选项"}}],'
    '"answer":{{"choiceKeys":["A"],"accepted":null,"textMarkdown":null}} 或 null,'
    '"explanationMarkdown":"解析或 null",'
    '"knowledgePointIds":["<输入中出现的知识点 id>"],'
    '"evidenceIds":["<输入中出现的证据 id>"],'
    '"assetIds":[]}}]}}。'
    "硬性规则：只允许引用输入中给出的知识点 id 与证据 id，不得编造；"
    "不得出现任何网址或文件路径；assetIds 一律留空数组；"
    "不要输出 JSON 以外的任何文字。"
)

_TASK_LEVEL_MESSAGES: dict[str, str] = {
    "AUTH_REQUIRED": "模型服务认证失败：请在模型设置里检查该模型的凭证后重试。",
    "RATE_LIMITED": "模型服务限流：请稍后重试，或改选其他聊天模型。",
    "MODEL_NOT_CONFIGURED": "所选模型配置当前不可调用：请在模型设置里补全后重试。",
    "MODEL_PROFILE_NOT_FOUND": "所选模型配置已不存在：请重新选择聊天模型后再补题。",
    "MODEL_PURPOSE_MISMATCH": "所选模型配置用途不是聊天：请改选聊天模型后再补题。",
    "SERVICE_UNAVAILABLE": "题库 AI 补题未装配模型解析器（model_resolver）：请检查后端启动配置。",
    "UPSTREAM_UNAVAILABLE": "模型服务当前不可用（网络或上游故障）：请稍后重试，或改选其他聊天模型。",
}


# --------------------------------------------------------------------------- 冻结


@dataclass(frozen=True)
class KnowledgeSnapshot:
    """知识点只读快照（发布前向知识点库重读；``B1`` 只读复用，绝不写入知识点库）。"""

    point_id: str
    subject_id: str
    code: str
    name: str
    revision_id: str

    def frozen_entry(self) -> dict[str, str]:
        return {
            "pointId": self.point_id,
            "subjectId": self.subject_id,
            "code": self.code,
            "name": self.name,
            "revisionId": self.revision_id,
        }


def _invalid(message: str, *, code: str) -> AppError:
    return AppError(message, code=code, status_code=422)


def _conflict(message: str, *, code: str, retryable: bool = False) -> AppError:
    return AppError(message, code=code, status_code=409, retryable=retryable)


def material_entries(materials: Sequence[str]) -> list[dict[str, str]]:
    """可选证据 → 冻结条目 ``[{"id": "m0", "text": ...}]``；形状/预算/引用非法一律 422。"""
    if isinstance(materials, (str, bytes)):
        raise _invalid("materials 必须是字符串数组。", code=MATERIAL_INVALID)
    entries: list[dict[str, str]] = []
    total = 0
    for index, raw in enumerate(materials):
        if not isinstance(raw, str) or not raw.strip():
            raise _invalid(
                f"materials[{index}] 必须是非空文本。", code=MATERIAL_INVALID
            )
        text = raw.strip()
        if len(text) > MAX_MATERIAL_CHARS:
            raise _invalid(
                f"materials[{index}] 超过 {MAX_MATERIAL_CHARS} 字上限。",
                code=MATERIAL_INVALID,
            )
        found = scan_forbidden_reference(text)
        if found is not None:
            raise _invalid(
                f"materials[{index}] 含网址或文件路径（{found}），不接受。",
                code=MATERIAL_INVALID,
            )
        total += len(text)
        entries.append({"id": f"{MATERIAL_ID_PREFIX}{index}", "text": text})
    if total > MAX_MATERIALS_TOTAL_CHARS:
        raise _invalid(
            f"材料合计 {total} 字，超过单次补题预算 {MAX_MATERIALS_TOTAL_CHARS} 字；请拆分后再试。",
            code=MATERIAL_INVALID,
        )
    return entries


def build_frozen_input(
    *,
    model_profile_id: str,
    subject_id: str,
    knowledge: Sequence[KnowledgeSnapshot],
    question_types: Sequence[str],
    difficulty: str,
    count: int,
    instructions: str,
    materials: Sequence[dict[str, str]],
    owner_id: str,
) -> dict[str, Any]:
    """冻结补题输入：允许知识点/证据、题型/难度/数量、指令与模型 profile id。"""
    return {
        "contractVersion": GENERATION_CONTRACT_VERSION,
        "modelProfileId": model_profile_id,
        "subjectId": subject_id,
        "knowledgePoints": [item.frozen_entry() for item in knowledge],
        "questionTypes": [str(item) for item in question_types],
        "difficulty": difficulty,
        "count": count,
        "instructions": instructions,
        "materials": [dict(item) for item in materials],
        "ownerId": owner_id,
    }


def build_model_snapshot(handle: ChatModelHandle) -> dict[str, Any]:
    """非敏感模型快照：只写 profile id 与指纹（绝不写模型名、凭证或完整配置）。

    指纹经共享 ``fingerprint_of_handle`` 计算：任务创建时冻结、执行前核对（RV04），
    来源记录与执行模型因此始终一致。
    """
    return {
        "profileId": handle.profile_id,
        "fingerprint": fingerprint_of_handle(handle),
        "contractVersion": GENERATION_CONTRACT_VERSION,
    }


def task_level_message(code: str) -> str:
    """任务级可读文案：补题专属措辞优先，未知 code 回落到整理器的同一套文案。"""
    return _TASK_LEVEL_MESSAGES.get(code) or job_level_message(code)


def is_current_frozen_input(payload: Any) -> bool:
    """冻结输入是否为当前契约形状（缺版本/缺 profile/缺知识点列表 → 不执行）。"""
    if not isinstance(payload, dict):
        return False
    if payload.get("contractVersion") != GENERATION_CONTRACT_VERSION:
        return False
    profile_id = payload.get("modelProfileId")
    knowledge = payload.get("knowledgePoints")
    return (
        isinstance(profile_id, str)
        and bool(profile_id.strip())
        and isinstance(knowledge, list)
    )


# --------------------------------------------------------------------------- 提示词


def render_user_prompt(frozen: Mapping[str, Any]) -> str:
    """按冻结输入拼出用户消息：知识点（id/编码/名称）+ 证据（id/文本）+ 命题要求。"""
    lines: list[str] = ["[知识点]"]
    knowledge = [item for item in frozen.get("knowledgePoints") or [] if isinstance(item, Mapping)]
    if knowledge:
        for item in knowledge:
            lines.append(
                f"- id={item.get('pointId')} 编码={item.get('code')} 名称={item.get('name')}"
            )
    else:
        lines.append("- （未指定具体知识点：只依据学科要求命题）")
    lines.append("")
    lines.append("[证据]")
    materials = [item for item in frozen.get("materials") or [] if isinstance(item, Mapping)]
    if materials:
        for item in materials:
            lines.append(f"[{item.get('id')}] {item.get('text')}")
    else:
        lines.append("（无外部证据，不要编造依据）")
    lines.append("")
    types = [str(item) for item in frozen.get("questionTypes") or []]
    lines.append(f"[题型] {'、'.join(types) if types else '不限（按题干判断）'}")
    lines.append(f"[难度] {frozen.get('difficulty') or 'unspecified'}")
    subject = str(frozen.get("subjectId") or "")
    if subject:
        lines.append(f"[学科] {subject}")
    instructions = str(frozen.get("instructions") or "").strip()
    if instructions:
        lines.append(f"[补充要求] {instructions}")
    return "\n".join(lines)


def build_instruction(count: int) -> str:
    return INSTRUCTION_TEMPLATE.format(count=count)


def scan_forbidden_reference(text: str) -> str | None:
    """扫描任意 URL / 文件路径；命中返回命中的片段（不回显整段内容），否则 ``None``。"""
    for pattern in (
        _URL_PATTERN,
        _WINDOWS_PATH_PATTERN,
        _UNC_PATH_PATTERN,
        _POSIX_PATH_PATTERN,
        _BACKSLASH_PATH_PATTERN,
    ):
        match = pattern.search(text)
        if match is not None:
            return match.group(0).strip() or match.group(0)
    return None


# --------------------------------------------------------------------------- 解析


@dataclass(frozen=True)
class GenerationCandidate:
    """一条通过的候选：契约内容 + 允许集合内的知识点/证据引用。"""

    content: dict[str, Any]
    knowledge_point_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]

    def raw_item(self) -> dict[str, Any]:
        return {
            "content": dict(self.content),
            "knowledgePointIds": list(self.knowledge_point_ids),
            "evidenceIds": list(self.evidence_ids),
        }


def parse_generation_reply(
    raw: str,
    *,
    allowed_knowledge_ids: Sequence[str],
    allowed_evidence_ids: Sequence[str],
    expected_count: int,
    asset_registered: Callable[[str], bool],
) -> list[GenerationCandidate]:
    """独立 ``GenerateReply``：把模型回复解析为候选；任一处不合法抛对应错误码。

    ``asset_registered`` 由调用方注入（读真实原件字节并校验 sha256 的判定），
    本函数不碰文件系统；未登记/形状非法的 assetId 一律拒绝。
    """
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
        raise _invalid(
            "模型返回内容不是合法 JSON，整批补题已失败；没有生成任何草稿。",
            code=INVALID_JSON,
        ) from exc
    if not isinstance(payload, dict):
        raise _invalid(
            "模型返回的 JSON 不是对象，整批补题已失败；没有生成任何草稿。",
            code=INVALID_JSON,
        )
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        raise _invalid(
            "模型返回缺少 questions 数组，整批补题已失败；没有生成任何草稿。",
            code=INVALID_JSON,
        )
    if len(questions) != expected_count:
        raise _invalid(
            f"模型返回 {len(questions)} 道题，与冻结的 count={expected_count} 不一致，"
            "整批补题已失败；没有生成任何草稿。",
            code=CANDIDATE_COUNT_MISMATCH,
        )
    allowed_knowledge = {str(item) for item in allowed_knowledge_ids}
    allowed_evidence = {str(item) for item in allowed_evidence_ids}
    candidates: list[GenerationCandidate] = []
    for index, item in enumerate(questions):
        candidates.append(
            _parse_candidate(
                item,
                index=index,
                allowed_knowledge=allowed_knowledge,
                allowed_evidence=allowed_evidence,
                asset_registered=asset_registered,
            )
        )
    return candidates


def _parse_candidate(
    item: Any,
    *,
    index: int,
    allowed_knowledge: set[str],
    allowed_evidence: set[str],
    asset_registered: Callable[[str], bool],
) -> GenerationCandidate:
    if not isinstance(item, Mapping):
        raise _invalid(
            f"questions[{index}] 不是对象，整批补题已失败；没有生成任何草稿。",
            code=CONTENT_INVALID,
        )
    stem = _first_text(item, ("stemMarkdown", "stem"))
    if not stem:
        raise _invalid(
            f"questions[{index}] 缺少题干，整批补题已失败；没有生成任何草稿。",
            code=CONTENT_INVALID,
        )
    options = _options(item.get("options"))
    answer = _answer(item.get("answer"))
    explanation = _first_text(item, ("explanationMarkdown", "explanation")) or None
    question_type = item.get("type")
    if not isinstance(question_type, str) or question_type not in QUESTION_TYPES:
        question_type = None

    for label, chunk in (
        ("题干", stem),
        ("解析", explanation or ""),
        ("答案", _answer_text(answer)),
        ("选项", " ".join(option["textMarkdown"] for option in options)),
    ):
        found = scan_forbidden_reference(chunk)
        if found is not None:
            raise _invalid(
                f"questions[{index}] 的{label}含网址或文件路径（{found}），"
                "整批补题已失败；没有生成任何草稿。",
                code=FORBIDDEN_REFERENCE,
            )

    knowledge_ids = _string_list(item.get("knowledgePointIds"))
    unknown_knowledge = [value for value in knowledge_ids if value not in allowed_knowledge]
    if unknown_knowledge:
        raise _invalid(
            f"questions[{index}] 引用了输入之外的知识点：{', '.join(unknown_knowledge[:5])}，"
            "整批补题已失败；没有生成任何草稿。",
            code=UNKNOWN_KNOWLEDGE,
        )
    evidence_ids = _string_list(item.get("evidenceIds"))
    unknown_evidence = [value for value in evidence_ids if value not in allowed_evidence]
    if unknown_evidence:
        raise _invalid(
            f"questions[{index}] 引用了输入之外的依据：{', '.join(unknown_evidence[:5])}，"
            "整批补题已失败；没有生成任何草稿。",
            code=UNKNOWN_EVIDENCE,
        )

    asset_ids = _string_list(item.get("assetIds"))
    for asset_id in asset_ids:
        if _BLOB_ASSET_PATTERN.fullmatch(asset_id) is None:
            raise _invalid(
                f"questions[{index}] 的 assetIds 只允许 blobs/<64 位小写 hex>，"
                f"收到：{asset_id}；整批补题已失败。",
                code=ASSET_INVALID,
            )
        if not asset_registered(asset_id):
            raise _invalid(
                f"questions[{index}] 引用了未登记的资产（{asset_id}）；"
                "整批补题已失败，没有生成任何草稿。",
                code=ASSET_NOT_REGISTERED,
            )

    content: dict[str, Any] = {
        "type": question_type or infer_type(stem, options, answer),
        "stemMarkdown": stem,
        "options": options,
        "answer": answer,
        "explanationMarkdown": explanation,
        "assetIds": asset_ids,
    }
    try:
        validated = validation.parse_content(content).model_dump(mode="json")
    except AppError as exc:
        raise _invalid(
            f"questions[{index}] 的内容不符合题库契约（{exc.code}），"
            "整批补题已失败；没有生成任何草稿。",
            code=CONTENT_INVALID,
        ) from exc
    return GenerationCandidate(
        content=validated,
        knowledge_point_ids=tuple(knowledge_ids),
        evidence_ids=tuple(evidence_ids),
    )


def _first_text(payload: Mapping[str, Any], keys: Sequence[str]) -> str:
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
    if not isinstance(value, list):
        return []
    options: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        key = item.get("key")
        text = _first_text(item, ("textMarkdown", "text"))
        if isinstance(key, str) and key.strip() and text:
            options.append({"key": key.strip(), "textMarkdown": text})
    return options


def _answer_text(answer: Mapping[str, Any] | None) -> str:
    if not answer:
        return ""
    parts = [str(key) for key in answer.get("choiceKeys") or []]
    text = answer.get("textMarkdown")
    if isinstance(text, str):
        parts.append(text)
    if answer.get("accepted") is not None:
        parts.append(str(answer["accepted"]))
    return " ".join(parts)


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
    if not isinstance(value, Mapping):
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


# --------------------------------------------------------------------------- 执行器


class QuestionGenerationRunner:
    """``question:generate`` 执行器：事务外模型调用与解析，发布与任务终态同事务。

    依赖全部由服务层注入（``resolve_frozen_model`` / ``resolve_knowledge``）；本类不读
    模型配置、不解释 profile id、不写知识点库。执行前按**冻结快照**（profileId +
    fingerprint）重新解析并核对真实配置指纹（B2-RV04）：同 profile 改过模型/地址/格式
    → 明确失败（``MODEL_CONFIG_DRIFT``）、零模型调用、零发布；旧任务缺指纹 →
    ``MODEL_FINGERPRINT_MISSING``，不静默放行。
    """

    def __init__(
        self,
        *,
        catalog: Any,
        blobs: QuestionBlobStore,
        resolve_frozen_model: Callable[[Mapping[str, Any]], Awaitable[ChatModelHandle]],
        resolve_knowledge: Callable[[Sequence[str]], Awaitable[dict[str, KnowledgeSnapshot]]],
        owner_id: str,
    ) -> None:
        self.catalog = catalog
        self.blobs = blobs
        self.resolve_frozen_model = resolve_frozen_model
        self.resolve_knowledge = resolve_knowledge
        self.owner_id = owner_id

    # ------------------------------------------------------------------ 校验

    def asset_registered(self, asset_id: str) -> bool:
        """``blobs/<hex>``：真实存在且读取时重算 sha256 一致才算已登记。"""
        match = _BLOB_ASSET_PATTERN.fullmatch(asset_id)
        if match is None:
            return False
        try:
            self.blobs.read(match.group(1))
        except AppError:
            return False
        return True

    # ------------------------------------------------------------------ 执行

    async def __call__(self, frozen: FrozenJob, ctx: JobContext) -> JobOutcome:
        payload = frozen.input if isinstance(frozen.input, dict) else {}
        if not is_current_frozen_input(payload):
            raise _conflict(
                "该补题任务由旧版语义创建，未自动执行：请重新发起 AI 补题。",
                code=INPUT_INVALID,
            )
        snapshot = frozen.model_snapshot if isinstance(frozen.model_snapshot, dict) else {}
        # 执行前核对真实配置指纹（RV04）：漂移/缺指纹 → 抛错，未产生任何模型调用
        handle = await self.resolve_frozen_model(snapshot)
        count = int(payload.get("count") or 1)
        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=build_instruction(count)),
                LLMMessage(role="user", content=render_user_prompt(payload)),
            ],
            maxOutputTokens=self._output_budget(handle),
            params={},
        )
        if await ctx.cancellation_requested():
            return JobOutcome(result={"cancelled": True, "candidateCount": 0}, publish=None)
        response = await handle.provider.complete(handle.config, request)
        if response.finishReason == FINISH_LENGTH:
            raise _invalid(
                "模型输出被截断（结束原因 length），整批补题已失败；没有生成任何草稿。",
                code=OUTPUT_TRUNCATED,
            )
        if await ctx.cancellation_requested():
            return JobOutcome(result={"cancelled": True, "candidateCount": 0}, publish=None)

        knowledge = [
            item for item in payload.get("knowledgePoints") or [] if isinstance(item, Mapping)
        ]
        materials = [
            item for item in payload.get("materials") or [] if isinstance(item, Mapping)
        ]
        candidates = parse_generation_reply(
            response.text,
            allowed_knowledge_ids=[str(item.get("pointId")) for item in knowledge],
            allowed_evidence_ids=[str(item.get("id")) for item in materials],
            expected_count=count,
            asset_registered=self.asset_registered,
        )
        # 发布前重读知识点（事务外）：存在、未归档、同学科，取当前修订与名称
        referenced = sorted(
            {point_id for item in candidates for point_id in item.knowledge_point_ids}
        )
        live = await self.resolve_knowledge(referenced)
        frozen_by_id = {str(item.get("pointId")): item for item in knowledge}
        for point_id in referenced:
            current = live.get(point_id)
            if current is None:
                raise _conflict(
                    f"知识点 {point_id} 在生成期间被归档或删除，整批补题已失败；"
                    "没有生成任何草稿。",
                    code=KNOWLEDGE_UNAVAILABLE,
                )
            expected_subject = str(frozen_by_id.get(point_id, {}).get("subjectId") or "")
            if expected_subject and current.subject_id != expected_subject:
                raise _conflict(
                    f"知识点 {point_id} 的学科在生成期间发生变化，整批补题已失败；"
                    "没有生成任何草稿。",
                    code=KNOWLEDGE_SUBJECT_CHANGED,
                )

        if await ctx.cancellation_requested():
            return JobOutcome(result={"cancelled": True, "candidateCount": 0}, publish=None)

        # 来源快照取**本次实际使用**的句柄指纹（已与冻结值核对一致）：执行与来源同源
        executed_snapshot = {
            "profileId": handle.profile_id,
            "fingerprint": fingerprint_of_handle(handle),
            "contractVersion": GENERATION_CONTRACT_VERSION,
        }
        original = json.dumps(
            {
                "jobId": frozen.job_id,
                "profileId": handle.profile_id,
                "fingerprint": executed_snapshot["fingerprint"],
                "rawReply": response.text,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        if len(original) > MAX_REPLY_BYTES:
            raise _invalid(
                "模型原始回复超过存储上限，整批补题已失败；没有生成任何草稿。",
                code=CONTENT_INVALID,
            )
        blob_id, size = self.blobs.write(original)

        import_id = uuid.uuid4().hex
        subject_id = str(payload.get("subjectId") or "")
        difficulty = str(payload.get("difficulty") or "unspecified")
        rows = self._publish_rows(candidates, live)
        drafts = [
            DraftInput(
                content=item.content,
                metadata={
                    "stageId": "",
                    "gradeId": "",
                    "subjectId": subject_id,
                    "editionId": "",
                    "knowledgeTags": [],
                    "difficulty": difficulty,
                },
                source_spans=[],
                extraction_method="ai",
                review_state="needs_review",
                warnings=(
                    "AI 补题候选：尚未入库，请逐题校对题干、答案与知识点后再确认。",
                ),
                content_fingerprint=fp.content_fingerprint(item.content),
            )
            for item in candidates
        ]

        catalog = self.catalog

        def publish(conn: Any) -> None:
            """与任务 succeeded 同一事务：批次 + 候选草稿 + 草稿关联 + 生成来源。"""
            catalog.create_import_in(
                conn,
                owner_id=self.owner_id,
                file_sha256=blob_id,
                original_blob_id=blob_id,
                uploaded_file_name=f"ai-generation-{frozen.job_id}.json",
                uploaded_bytes=size,
                state="needs_review",
                warnings=["AI 补题批次：候选尚未入库，请逐题校对后用确认接口建账。"],
                import_id=import_id,
            )
            created = catalog.create_drafts_in(conn, import_id, drafts)
            for draft, link_rows in zip(created, rows, strict=True):
                catalog.insert_draft_knowledge_links_in(conn, draft.draft_id, link_rows)
            catalog.save_import_provenance_in(
                conn,
                import_id=import_id,
                source="ai",
                job_id=frozen.job_id,
                model_snapshot=executed_snapshot,
            )

        return JobOutcome(
            result={"importId": import_id, "candidateCount": len(candidates)},
            publish=publish,
        )

    # ------------------------------------------------------------------ 内部

    @staticmethod
    def _output_budget(handle: ChatModelHandle) -> int:
        limit = handle.max_output_tokens
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            return MAX_OUTPUT_TOKENS
        return min(MAX_OUTPUT_TOKENS, limit)

    @staticmethod
    def _publish_rows(
        candidates: Sequence[GenerationCandidate],
        live: Mapping[str, KnowledgeSnapshot],
    ) -> list[list[dict[str, str]]]:
        """每条候选的草稿关联行：首知识点 primary、其余 secondary，快照取当前修订。"""
        rows: list[list[dict[str, str]]] = []
        for candidate in candidates:
            link_rows: list[dict[str, str]] = []
            for index, point_id in enumerate(candidate.knowledge_point_ids):
                current = live.get(point_id)
                if current is None:  # pragma: no cover - 上层已逐点校验
                    raise _conflict(
                        f"知识点 {point_id} 在生成期间被归档或删除，整批补题已失败。",
                        code=KNOWLEDGE_UNAVAILABLE,
                    )
                link_rows.append(
                    {
                        "knowledgePointId": current.point_id,
                        "knowledgeRevisionId": current.revision_id,
                        "subjectIdSnapshot": current.subject_id,
                        "knowledgeNameSnapshot": current.name,
                        "role": "primary" if index == 0 else "secondary",
                        "source": "ai",
                    }
                )
            rows.append(link_rows)
        return rows


__all__ = [
    "ASSET_INVALID",
    "ASSET_NOT_REGISTERED",
    "CANDIDATE_COUNT_MISMATCH",
    "CONTENT_INVALID",
    "FORBIDDEN_REFERENCE",
    "GENERATION_CONTRACT_VERSION",
    "GenerationCandidate",
    "INSTRUCTION_TEMPLATE",
    "INPUT_INVALID",
    "KNOWLEDGE_SUBJECT_CHANGED",
    "KNOWLEDGE_UNAVAILABLE",
    "KnowledgeSnapshot",
    "MATERIAL_ID_PREFIX",
    "MATERIAL_INVALID",
    "MAX_MATERIAL_CHARS",
    "MAX_MATERIALS_TOTAL_CHARS",
    "MAX_OUTPUT_TOKENS",
    "MAX_REPLY_BYTES",
    "OUTPUT_TRUNCATED",
    "QuestionGenerationRunner",
    "task_level_message",
    "UNKNOWN_EVIDENCE",
    "UNKNOWN_KNOWLEDGE",
    "build_frozen_input",
    "build_instruction",
    "build_model_snapshot",
    "is_current_frozen_input",
    "material_entries",
    "parse_generation_reply",
    "render_user_prompt",
    "scan_forbidden_reference",
]
