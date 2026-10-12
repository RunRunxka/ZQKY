"""AI 候选提示词、回复解析与校验（TEACHING-LOOP B1 / T20；R3 LangChain 改造）。

R 系列重建口径（用户裁定：全部教学闭环 LLM 能力必须经 LangChain + LangGraph）：

- 模型解析由服务层注入的 ``model_resolver`` 完成（LangChain 官方包经
  ``app.services.agent.model.resolve_agent_chat_model``，显式注入凭证 + env 断言；
  OAuth 受管认证连接不支持，沿其 ``AGENT_MODEL_UNSUPPORTED`` 错误码与指引）；
- 结构化抽取经 ``app.services.llm.runner.run_structured``：Pydantic schema 严格校验、
  失败自动重试（默认共 2 次），仍失败**不抛异常**——降级为空候选 + 行级标注
  （红线：AI 输出只进候选）；
- 提示词经 ``app.services.llm.prompts.PromptSpec`` 集中登记（id/version 显式），
  归档提示词语义逐字保留，version="v1"；
- 冻结的输入只含教师提供的证据与**非敏感**模型指纹（``profileId`` + ``sha256:…``），
  **绝不含凭证**；
- 归档既有校验逐条保留：候选引用了不在允许集合内的既有知识点 id 或证据 id →
  ``KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE``（由服务层在解析后复核——runner 的
  Pydantic schema 负责结构，跨引用集合校验仍是显式规则）；
- 候选**只进入** ``source="ai"`` 的待确认批次，绝不直接写正式知识点表。

与归档的行为差异（R3 改造，逐条见交付报告）：

- 归档走 ``handle.provider.complete``（裸协议直连），此处走 LangChain
  ``with_structured_output``；``finish_reason == length``（截断）不再以裸响应判定，
  由 runner 的解析失败/空结构降级为「空候选 + 标注」，不再整任务
  ``KNOWLEDGE_SUGGESTION_TRUNCATED`` 失败；
- 解析失败（非法 JSON/结构不符）同理降级为空候选 + ``KNOWLEDGE_SUGGESTION_INVALID_JSON``
  行级标注，不再抛异常失败整个任务（调用方按「候选 + 标注」进入待确认）。
"""

from __future__ import annotations

from typing import Any, Sequence
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.knowledge import (
    KnowledgeSuggestionCandidate,
)
from app.contracts.teaching_loop import ErrorIssue, canonical_hash
from app.services.knowledge.evidence import EvidenceText
from app.services.llm.prompts import PromptSpec, register_prompt

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
#: 解析失败降级标注的问题码（归档以任务失败码出现；R3 起是行级非阻断标注）
SUGGESTION_INVALID_JSON_CODE = "KNOWLEDGE_SUGGESTION_INVALID_JSON"

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

#: 提示词模板里的转义版本（``{``/``}`` → ``{{``/``}}``；渲染后与 SUGGESTION_INSTRUCTION 逐字一致）
SUGGESTION_INSTRUCTION_ESCAPED = SUGGESTION_INSTRUCTION.replace("{", "{{").replace("}", "}}")

# --------------------------------------------------------------------------- 提示词登记

#: AI 候选提示词（归档语义逐字保留；动态内容经 human 变量 ``{instruction}`` 传入，
#: 模板里的 JSON 形状用 ``{{``/``}}`` 转义为字面花括号——语义与归档完全一致）。
SUGGESTION_PROMPT = register_prompt(
    PromptSpec(
        id="knowledge.suggestion.candidates",
        version="v1",
        system=(
            "你是教学知识点整理助手。" + SUGGESTION_INSTRUCTION_ESCAPED
        ),
        human=("证据列表：\n\n{evidence}\n\n整理要求：\n{instruction}"),
    ),
)

#: runner 变量键（evidence = render_evidence 输出；instruction = 动态指令正文）
PROMPT_EVIDENCE_KEY = "evidence"
PROMPT_INSTRUCTION_KEY = "instruction"


# --------------------------------------------------------------------------- 结构化 schema


class SuggestionCandidateSchema(BaseModel):
    """``run_structured`` 的抽取 schema：单条候选（结构校验；跨引用校验在规则层复核）。"""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    parent_code: str | None = Field(default=None, alias="parentCode")
    aliases: list[str] = Field(default_factory=list)
    existing_knowledge_point_id: str | None = Field(
        default=None, alias="existingKnowledgePointId"
    )
    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")
    #: 模型可选给出的置信度（只进校对提示；不参与入库）
    confidence: float | None = None


class SuggestionListSchema(BaseModel):
    """候选集合：与归档 ``{"candidates":[…]}`` 顶层形状一致。"""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    candidates: list[SuggestionCandidateSchema] = Field(default_factory=list)


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
    """动态指令正文（传入提示词模板的 ``{instruction}`` 变量）。

    归档语义逐字保留：固定 JSON 形状 + 允许引用的既有知识点 id（只提示，不猜）+
    提取任务约束 + 教师附加要求。
    """
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


def prompt_variables(frozen_input: dict[str, Any]) -> dict[str, str]:
    """``run_structured`` 的提示词变量：证据正文 + 动态指令。"""
    return {
        PROMPT_EVIDENCE_KEY: render_evidence(frozen_input),
        PROMPT_INSTRUCTION_KEY: system_instruction(frozen_input),
    }


# --------------------------------------------------------------------------- 解析与降级


def candidates_from_outcome(
    outcome: Any,
    *,
    allowed_point_ids: Sequence[str],
    allowed_evidence_ids: Sequence[str],
) -> tuple[list[KnowledgeSuggestionCandidate], list[dict[str, Any]], tuple[ErrorIssue, ...]]:
    """把 ``run_structured`` 的 outcome 变成 ``(候选, 原始对象, 降级标注)``。

    - 成功：schema → 契约候选 + 原始对象（供校对提示/资产登记）；跨引用集合校验
      （既有知识点 id / 证据 id 必须在允许集合内）在这里复核——归档语义逐字保留，
      引用越界 → ``KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE``（同归档：整任务失败）；
    - 失败（解析/传输/超时降级）：**不抛异常**，返回空候选 + 原文预览 +
      ``KNOWLEDGE_SUGGESTION_INVALID_JSON`` 标注（任务仍可 succeeded 发布空批次，
      由调用方决定是否发布；红线：AI 输出只进候选）。
    """
    if not outcome.ok or outcome.parsed is None:
        issue = ErrorIssue(
            code=SUGGESTION_INVALID_JSON_CODE,
            message=(
                "模型输出无法解析为候选结构，本次未生成候选；"
                f"模型原始输出预览：{(outcome.raw_text or '')[:200]}。"
            ),
        )
        return [], [], (issue,)

    allowed_points = {str(item) for item in allowed_point_ids}
    allowed_evidence = {str(item) for item in allowed_evidence_ids}
    candidates: list[KnowledgeSuggestionCandidate] = []
    raw_items: list[dict[str, Any]] = []
    from app.core.exceptions import AppError
    from app.contracts.knowledge import KNOWLEDGE_SUGGESTION_UNKNOWN_REFERENCE

    for item in outcome.parsed.candidates:
        existing = item.existing_knowledge_point_id or None
        evidence_ids = [text for text in item.evidence_ids if text.strip()]
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
        candidate = KnowledgeSuggestionCandidate.model_validate(
            {
                "code": item.code.strip(),
                "name": item.name.strip(),
                "description": (item.description or "").strip(),
                "parentCode": (item.parent_code or "").strip() or None,
                "aliases": [text.strip() for text in item.aliases if text.strip()],
                "existingKnowledgePointId": existing,
                "evidenceIds": evidence_ids,
            }
        )
        candidates.append(candidate)
        raw_items.append(item.model_dump(by_alias=True, exclude_none=True))
    return candidates, raw_items, ()


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


__all__ = [
    "EXTRACTION_INSTRUCTION_SUFFIX",
    "EXTRACTION_MAX_CANDIDATES",
    "EXTRACTION_MAX_OUTPUT_TOKENS",
    "EXTRACTION_TIMEOUT_SECONDS",
    "MAX_EVIDENCE_CHARS",
    "MAX_OUTPUT_TOKENS",
    "MAX_REFERENCE_IDS",
    "PROMPT_EVIDENCE_KEY",
    "PROMPT_INSTRUCTION_KEY",
    "SUGGESTION_CONTRACT_VERSION",
    "SUGGESTION_INSTRUCTION",
    "SUGGESTION_INVALID_JSON_CODE",
    "SUGGESTION_PROMPT",
    "SUGGESTION_REVIEW_CODE",
    "SuggestionCandidateSchema",
    "SuggestionListSchema",
    "candidates_from_outcome",
    "evidence_id_for_textbook",
    "hint_issues",
    "material_entry",
    "model_fingerprint",
    "prompt_variables",
    "render_evidence",
    "system_instruction",
    "textbook_entry",
]
