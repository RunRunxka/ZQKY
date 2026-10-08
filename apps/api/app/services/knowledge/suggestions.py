"""AI 候选提示词、回复解析与校验（TEACHING-LOOP B1 / T20）。

模型语义（与题库 AI 整理同一套纪律，见 ``services/question_bank/organizer.py``）：

- ``modelProfileId`` 是聊天模型 profile id；解析由服务层注入的 ``model_resolver``
  （唯一实现 ``services.model_runtime.resolve_chat_model``）完成，本模块不解释
  profile id、不列本机模型、不做默认回退；
- 冻结的输入只含教师提供的证据与**非敏感**模型指纹（``profileId`` + ``sha256:…``），
  **绝不含凭证**；
- 调用是非流式的，指令要求只输出一个 JSON 对象 ``{"candidates":[…]}}``；
- 解析与校验在这里完成：非法 JSON / 非对象 / 结构不符 → ``KNOWLEDGE_SUGGESTION_INVALID_JSON``；
  ``finish_reason == "length"``（截断）由服务层判为 ``KNOWLEDGE_SUGGESTION_TRUNCATED``；
  候选引用了不在允许集合内的既有知识点 id 或证据 id → ``KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE``；
- 候选**只进入** ``source="ai"`` 的待确认批次，绝不直接写正式知识点表。
"""

from __future__ import annotations

import json
from typing import Any, Sequence
from urllib.parse import urlsplit

from app.contracts.knowledge import (
    KNOWLEDGE_SUGGESTION_INVALID_JSON,
    KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE,
    KnowledgeSuggestionCandidate,
)
from app.contracts.teaching_loop import ErrorIssue, canonical_hash
from app.core.exceptions import AppError
from app.services.knowledge.evidence import EvidenceText

#: 冻结输入的契约版本（形状变化时用于拒绝旧任务自动恢复）
SUGGESTION_CONTRACT_VERSION = 1
#: 组织者侧输出上限
MAX_OUTPUT_TOKENS = 2048
#: 教材提取单册候选的输出上限（2026-10-08 真机：整册一次提炼会超出 2048 触发截断拒绝；
#: 推理档档案（reasoning=max）的推理 token 计入输出，故给出有界但足够的预算）
EXTRACTION_MAX_OUTPUT_TOKENS = 16384
#: 单次提取任务的候选条数上限（宁少勿凑；未提取到的部分留给后续批次）
EXTRACTION_MAX_CANDIDATES = 10
#: 提取任务按调用放宽的非流式等待（秒）：整册证据（上限 6 万码点）在默认 30 秒内完不成
#: （2026-10-08 真机：推理档与非推理档都撞 UPSTREAM_TIMEOUT）。任务心跳独立续租，
#: 不受调用时长影响；有界放宽只覆盖提取任务，其余任务保持默认。
EXTRACTION_TIMEOUT_SECONDS = 300
#: 单次候选任务的全部证据文本预算（码点）；超出一律 422，不静默截断
MAX_EVIDENCE_CHARS = 60000
#: 提示词里列出的既有知识点 id 上限（避免把提示词撑爆）
MAX_REFERENCE_IDS = 200
#: AI 候选提示的行级问题码（非阻断，供教师校对）
SUGGESTION_REVIEW_CODE = "KNOWLEDGE_SUGGESTION_REVIEW"

SUGGESTION_INSTRUCTION = (
    "从提供的证据中提炼可供教师建账的**知识点**候选（学科内编码、名称、说明、父级、别名）。"
    "只依据输入证据，不引用输入之外的来源，不编造证据里没有的内容。"
    "每条候选的 evidenceIds 必须来自输入中出现的证据 id。"
    "若某条候选其实是既有知识点的同义说法，可在 existingKnowledgePointId 里引用允许列表中的 id。"
    '只输出一个 JSON 对象，字段固定为：{"candidates":['
    '{"code":"学科内编码","name":"名称","description":"说明","parentCode":null,'
    '"aliases":["别名"],"existingKnowledgePointId":null,"evidenceIds":["证据 id"],'
    '"confidence":0.0}]}。'
    "没有把握的字段留空或 null，不要输出 JSON 以外的任何文字。"
)


# --------------------------------------------------------------------------- 冻结与提示词


def model_fingerprint(
    *, model_id: str, protocol: str, base_url: str, api_format: str
) -> str:
    """非敏感模型指纹：``sha256:`` + 规范化 JSON 的 sha256（不含凭证/完整 URL）。"""
    payload = {
        "modelId": model_id or "",
        "protocol": protocol or "",
        "baseHost": urlsplit(base_url or "").hostname or "",
        "apiFormat": api_format or "",
    }
    return f"sha256:{canonical_hash(payload)}"


def evidence_id_for_textbook(document_revision_id: str, char_start: int, char_end: int) -> str:
    """教材证据的稳定 id（教材证据输入没有 id 字段，用它冻结进证据集合）。"""
    return f"textbook:{document_revision_id}:{char_start}:{char_end}"


def textbook_entry(evidence: EvidenceText) -> dict[str, Any]:
    return {
        "id": evidence_id_for_textbook(
            evidence.document_revision_id, evidence.char_start, evidence.char_end
        ),
        "documentRevisionId": evidence.document_revision_id,
        "charStart": evidence.char_start,
        "charEnd": evidence.char_end,
        "title": evidence.title,
        "sha256": evidence.sha256,
        "text": evidence.text,
        "locator": dict(evidence.locator),
    }


def material_entry(material_id: str, text: str) -> dict[str, Any]:
    return {"id": material_id, "text": text}


def render_evidence(frozen_input: dict[str, Any]) -> str:
    """把冻结证据渲染成模型输入（每条证据带 ``[证据 id]`` 标签，便于模型回引）。

    教材证据在标签之后另起一行给出教材标题：材料与教材证据对模型是同一套引用语法
    （``[证据 id]`` 单独成行），模型回引时才不会把标题混进 id。
    """
    parts: list[str] = []
    for item in frozen_input.get("materials") or []:
        parts.append(f"[证据 {item.get('id')}]\n{item.get('text', '')}")
    for item in frozen_input.get("textbookEvidence") or []:
        title = item.get("title") or ""
        location = f"（教材：{title}）\n" if title else ""
        parts.append(f"[证据 {item.get('id')}]\n{location}{item.get('text', '')}")
    return "\n\n".join(parts)


EXTRA_INSTRUCTION_SUFFIX = "教师附加要求："
#: 提取任务专用约束：整册证据必须**有界输出**，否则候选 JSON 会被输出上限截断而整批失败
EXTRACTION_INSTRUCTION_SUFFIX = (
    f"\n本次是教材提取任务：只覆盖下面给出的教材切片，最多提炼 {EXTRACTION_MAX_CANDIDATES} 条"
    "最重要、最可复用的知识点候选（宁少勿凑；其余内容留给后续批次再提取），"
    "并优先合并同义说法，避免为同一概念输出多条候选。"
)


def system_instruction(frozen_input: dict[str, Any]) -> str:
    """系统指令：固定 JSON 形状 + 允许引用的既有知识点 id（只提示，不猜）。"""
    allowed = [str(item) for item in (frozen_input.get("allowedKnowledgePointIds") or [])]
    instruction = SUGGESTION_INSTRUCTION
    if isinstance(frozen_input.get("extraction"), dict):
        instruction = f"{instruction}{EXTRACTION_INSTRUCTION_SUFFIX}"
    if allowed:
        joined = ", ".join(allowed[:MAX_REFERENCE_IDS])
        instruction = (
            f"{instruction}\n允许引用的既有知识点 id（只能从这个列表里选，或留 null）：{joined}。"
        )
    extra = str(frozen_input.get("instructions") or "").strip()
    if extra:
        instruction = f"{instruction}\n{EXTRA_INSTRUCTION_SUFFIX}{extra}"
    return instruction


# --------------------------------------------------------------------------- 解析


def parse_candidates(
    raw: str,
    *,
    allowed_point_ids: Sequence[str],
    allowed_evidence_ids: Sequence[str],
) -> tuple[list[KnowledgeSuggestionCandidate], list[dict[str, Any]]]:
    """解析模型回复；返回 ``(候选, 原始对象)``，任一处不合法抛稳定错误码。"""
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
        raise _invalid_json("模型返回内容不是合法 JSON，候选批次未生成。") from exc
    if not isinstance(payload, dict):
        raise _invalid_json("模型返回的 JSON 不是对象，候选批次未生成。")
    items = payload.get("candidates")
    if not isinstance(items, list):
        raise _invalid_json("模型返回缺少 candidates 数组，候选批次未生成。")

    allowed_points = {str(item) for item in allowed_point_ids}
    allowed_evidence = {str(item) for item in allowed_evidence_ids}
    candidates: list[KnowledgeSuggestionCandidate] = []
    raw_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise _invalid_json("candidates 里存在非对象条目，候选批次未生成。")
        code = _required_text(item.get("code"), field="code")
        name = _required_text(item.get("name"), field="name")
        description = _optional_text(item.get("description"))
        parent_code = _optional_text(item.get("parentCode")) or None
        aliases = _string_list(item.get("aliases"))
        existing = _optional_text(item.get("existingKnowledgePointId")) or None
        evidence_ids = _string_list(item.get("evidenceIds"))
        if existing is not None and existing not in allowed_points:
            raise AppError(
                f"候选引用了不在允许集合内的既有知识点 id：{existing}。",
                code=KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE,
                status_code=422,
            )
        unknown = [item_id for item_id in evidence_ids if item_id not in allowed_evidence]
        if unknown:
            raise AppError(
                f"候选引用了输入之外的证据 id：{', '.join(unknown[:5])}。",
                code=KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE,
                status_code=422,
            )
        candidates.append(
            KnowledgeSuggestionCandidate.model_validate(
                {
                    "code": code,
                    "name": name,
                    "description": description,
                    "parentCode": parent_code,
                    "aliases": aliases,
                    "existingKnowledgePointId": existing,
                    "evidenceIds": evidence_ids,
                }
            )
        )
        raw_items.append(dict(item))
    return candidates, raw_items


def hint_issues(
    candidate: KnowledgeSuggestionCandidate, raw: dict[str, Any]
) -> tuple[ErrorIssue, ...]:
    """AI 候选的校对提示（非阻断）：证据 id + 置信度，入库前必须人工确认。"""
    confidence = raw.get("confidence")
    confidence_text = ""
    if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
        confidence_text = f"置信度 {float(confidence):.2f}；"
    evidence_text = (
        "、".join(candidate.evidence_ids) if candidate.evidence_ids else "未标注证据"
    )
    return (
        ErrorIssue(
            code=SUGGESTION_REVIEW_CODE,
            message=(
                f"{confidence_text}证据：{evidence_text}。"
                "这是 AI 候选，确认入库前必须人工校对。"
            ),
        ),
    )


# --------------------------------------------------------------------------- 内部


def _invalid_json(message: str) -> AppError:
    return AppError(message, code=KNOWLEDGE_SUGGESTION_INVALID_JSON, status_code=422)


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _invalid_json(f"候选缺少必填字段 {field}。")
    return value.strip()


def _optional_text(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise _invalid_json("候选字段类型不符（应为字符串或 null）。")
    return value.strip()


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if not isinstance(value, list):
        raise _invalid_json("候选字段类型不符（应为字符串数组）。")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise _invalid_json("候选字段类型不符（应为字符串数组）。")
        text = item.strip()
        if text:
            result.append(text)
    return result


__all__ = [
    "EXTRACTION_INSTRUCTION_SUFFIX",
    "EXTRACTION_MAX_CANDIDATES",
    "EXTRACTION_MAX_OUTPUT_TOKENS",
    "EXTRACTION_TIMEOUT_SECONDS",
    "MAX_EVIDENCE_CHARS",
    "MAX_OUTPUT_TOKENS",
    "MAX_REFERENCE_IDS",
    "SUGGESTION_CONTRACT_VERSION",
    "SUGGESTION_INSTRUCTION",
    "SUGGESTION_REVIEW_CODE",
    "evidence_id_for_textbook",
    "hint_issues",
    "material_entry",
    "model_fingerprint",
    "parse_candidates",
    "render_evidence",
    "system_instruction",
    "textbook_entry",
]
