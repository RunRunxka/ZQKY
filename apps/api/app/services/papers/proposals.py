"""原卷 AI 知识点建议：提示词、回复解析/校验与任务执行器（TEACHING-LOOP B2 / T40）。

模型语义（与题库 AI 整理、知识点 AI 候选同一套纪律）：

- ``modelProfileId`` 是**聊天模型 profile id**；解析由服务层注入的 ``model_resolver``
  （唯一实现 ``services.model_runtime.resolve_chat_model``）完成，本模块不解释 profile id、
  不列本机模型、不做默认回退；任务冻结的模型失效时执行器**失败**而不是换模型；
  执行前核对冻结指纹（``fingerprint_of_handle``）：缺指纹 → 422
  ``MODEL_FINGERPRINT_MISSING``，同 profile 改模型/地址/格式 → 409 ``MODEL_CONFIG_DRIFT``
  （不调用模型、不发布、不把新模型的输出记成旧来源）；
- 冻结输入只含教师可见的题目信息与**非敏感**模型指纹（``profileId`` + ``sha256:…``），
  绝不含凭证；
- 调用是**非流式**的，指令要求只输出一个 JSON 对象；输出校验覆盖非法 JSON / 非对象 /
  结构不符 / ``finish_reason == "length"``（截断）/ 未知知识点 / 未知题目 /
  证据越界（证据 id 必须来自冻结的题目集合），任一失败都带 ``row``/``field`` 可定位；
- 建议**只进入** ``ai_proposals``（pending），绝不直接写试卷知识点关联；应用时由服务层
  复核草稿版本（过期 → stale）并把已有知识点写成 ``source="ai_confirmed"``；
  ``proposedCode``/``proposedName`` 只是待确认的新知识点候选，先走 T20 候选确认，
  再由教师单独绑定（本模块不创建知识点）。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Awaitable, Callable, Sequence

from app.contracts.papers import PAPER_PROPOSAL_INVALID
from app.contracts.teaching_loop import ErrorIssue, error_details
from app.core.exceptions import AppError
from app.providers.llm.base import FINISH_LENGTH, LLMMessage, LLMRequest
from app.services.jobs.engine import FrozenJob, JobContext, JobOutcome
from app.services.knowledge.suggestions import model_fingerprint as _model_fingerprint
from app.services.model_runtime import (
    MODEL_CONFIG_DRIFT,
    MODEL_FINGERPRINT_MISSING,
    ChatModelHandle,
    fingerprint_of_handle,
)

#: 冻结输入的契约版本（形状变化时用于拒绝旧任务自动恢复）
PROPOSAL_CONTRACT_VERSION = 1
#: 非流式输出上限
MAX_OUTPUT_TOKENS = 2048
#: 允许出现在提示词里的题目数量上限（超出 422，不静默截断）
MAX_ITEMS = 200
#: 允许出现在提示词里的知识点数量上限
MAX_ALLOWED_POINTS = 300
#: 单条建议的证据条数上限
MAX_EVIDENCE_PER_ITEM = 20
#: 证据文本（题目 id）长度上限
MAX_EVIDENCE_TEXT_CHARS = 200

PROPOSAL_INSTRUCTION = (
    "你是教学备课助手。下面给出原卷的**计分小题**（含题号、满分与题干文本）、"
    "允许引用的**已有知识点**列表，以及允许作为证据引用的**题目 id**。"
    "请判断每个小题考查的知识点：能对应到列表中的既有知识点时填 knowledgePointId；"
    "找不到合适的既有知识点时，给出待教师确认的新知识点候选 proposedCode / proposedName"
    "（不要编造 id）。evidence 只能填输入中出现过的题目 id（表示该小题的题干/答案支撑"
    "这条判断的依据），不要引用输入之外的来源。没有把握时把 ambiguity 设为 true，"
    "并尽量少填字段。每个小题最多输出一条。"
    '只输出一个 JSON 对象，字段固定为：{"items":[{"itemId":"题目 id",'
    '"knowledgePointId":"既有知识点 id 或 null","proposedCode":"新知识点编码或 null",'
    '"proposedName":"新知识点名称或 null","evidence":["题目 id"],"ambiguity":false}]}。'
    "不确定的字段留空或 null，不要输出 JSON 以外的任何文字。"
)


# --------------------------------------------------------------------------- 错误


def proposal_invalid(
    message: str, *, issues: Sequence[ErrorIssue] | None = None, status_code: int = 422
) -> AppError:
    return AppError(
        message,
        code=PAPER_PROPOSAL_INVALID,
        status_code=status_code,
        details=error_details(issues=list(issues)) if issues else None,
    )


def _issue(
    row: int | None, *, code: str, message: str, field_name: str | None = None
) -> ErrorIssue:
    return ErrorIssue(
        row=row, column=field_name, field=field_name, code=code, message=message
    )


# --------------------------------------------------------------------------- 冻结输入


def model_fingerprint(
    *, model_id: str, protocol: str, base_url: str, api_format: str
) -> str:
    """非敏感模型指纹（与知识点候选**同一公式**，不复制第二套口径）。"""
    return _model_fingerprint(
        model_id=model_id, protocol=protocol, base_url=base_url, api_format=api_format
    )


@dataclass(frozen=True)
class ProposedItem:
    """模型对一道小题的一条建议（待教师应用）。"""

    item_id: str
    question_no: str
    knowledge_point_id: str | None
    proposed_code: str | None
    proposed_name: str | None
    evidence: tuple[str, ...]
    ambiguity: bool

    def payload(self) -> dict[str, Any]:
        return {
            "itemId": self.item_id,
            "questionNo": self.question_no,
            "knowledgePointId": self.knowledge_point_id,
            "proposedCode": self.proposed_code,
            "proposedName": self.proposed_name,
            "evidence": list(self.evidence),
            "ambiguity": self.ambiguity,
        }


def render_items(frozen_input: dict[str, Any]) -> str:
    """把冻结的题目列表渲染成模型输入（题干文本截断到 800 字，不吞掉题号/满分）。"""
    lines: list[str] = []
    for item in frozen_input.get("items") or []:
        if not isinstance(item, dict):
            continue
        stem = str(item.get("stemText") or "").strip()
        if len(stem) > 800:
            stem = f"{stem[:800]}…"
        lines.append(
            f"[题目 {item.get('itemId')}] 题号 {item.get('questionNo')} "
            f"满分 {item.get('maxScore')}：{stem}"
        )
    return "\n".join(lines)


def system_instruction(frozen_input: dict[str, Any]) -> str:
    """系统指令：固定 JSON 形状 + 允许引用的题目 id 与既有知识点 id（只提示，不猜）。"""
    item_ids = [str(item) for item in (frozen_input.get("allowedItemIds") or [])]
    points = [
        item
        for item in (frozen_input.get("allowedKnowledgePoints") or [])
        if isinstance(item, dict)
    ]
    instruction = PROPOSAL_INSTRUCTION
    if item_ids:
        instruction = (
            f"{instruction}\n允许作为 evidence 的题目 id（只能从这里选）："
            f"{', '.join(item_ids[:MAX_ITEMS])}。"
        )
    if points:
        rendered = [
            f"{item.get('id')}（{item.get('code')} {item.get('name')}）" for item in points
        ]
        instruction = (
            f"{instruction}\n允许引用的既有知识点（只能从这里选，或留 null）："
            f"{'；'.join(rendered[:MAX_ALLOWED_POINTS])}。"
        )
    return instruction


# --------------------------------------------------------------------------- 解析


def parse_reply(
    raw: str,
    *,
    allowed_item_ids: Sequence[str],
    allowed_point_ids: Sequence[str],
) -> tuple[list[ProposedItem], list[dict[str, Any]]]:
    """解析模型回复；返回 ``(建议, 原始对象)``，任一处不合法抛稳定错误码。"""
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
        raise proposal_invalid("模型返回内容不是合法 JSON，建议未生成。") from exc
    if not isinstance(payload, dict):
        raise proposal_invalid("模型返回的 JSON 不是对象，建议未生成。")
    entries = payload.get("items")
    if not isinstance(entries, list):
        raise proposal_invalid("模型返回缺少 items 数组，建议未生成。")
    if len(entries) > MAX_ITEMS:
        raise proposal_invalid(f"模型返回的建议条数超过上限 {MAX_ITEMS}，建议未生成。")

    allowed_items = {str(item) for item in allowed_item_ids}
    allowed_points = {str(item) for item in allowed_point_ids}
    seen: set[str] = set()
    items: list[ProposedItem] = []
    raw_items: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise proposal_invalid(
                "items 里存在非对象条目，建议未生成。",
                issues=[_issue(index, code=PAPER_PROPOSAL_INVALID, message="条目必须是 JSON 对象。")],
            )
        item_id = entry.get("itemId")
        if not isinstance(item_id, str) or not item_id.strip():
            raise proposal_invalid(
                "建议缺少 itemId，建议未生成。",
                issues=[
                    _issue(
                        index,
                        code=PAPER_PROPOSAL_INVALID,
                        message="itemId 必须是非空字符串。",
                        field_name="itemId",
                    )
                ],
            )
        item_id = item_id.strip()
        if item_id not in allowed_items:
            raise proposal_invalid(
                f"建议引用了不在允许集合内的题目 id：{item_id}。",
                issues=[
                    _issue(
                        index,
                        code=PAPER_PROPOSAL_INVALID,
                        message=f"itemId {item_id} 不在冻结的计分小题集合内。",
                        field_name="itemId",
                    )
                ],
            )
        if item_id in seen:
            raise proposal_invalid(
                f"题目 {item_id} 出现了多条建议，无法判定采用哪条。",
                issues=[
                    _issue(
                        index,
                        code=PAPER_PROPOSAL_INVALID,
                        message=f"itemId {item_id} 重复。",
                        field_name="itemId",
                    )
                ],
            )
        seen.add(item_id)

        point_id = _optional_text(entry.get("knowledgePointId"))
        if point_id is not None and point_id not in allowed_points:
            raise proposal_invalid(
                f"建议引用了不在允许集合内的知识点 id：{point_id}。",
                issues=[
                    _issue(
                        index,
                        code=PAPER_PROPOSAL_INVALID,
                        message=f"knowledgePointId {point_id} 不属于该卷学科的可用知识点。",
                        field_name="knowledgePointId",
                    )
                ],
            )
        code = _optional_text(entry.get("proposedCode"))
        name = _optional_text(entry.get("proposedName"))
        if point_id is None and (code is None or name is None):
            raise proposal_invalid(
                "建议既没有既有知识点也没有新知识点候选，建议未生成。",
                issues=[
                    _issue(
                        index,
                        code=PAPER_PROPOSAL_INVALID,
                        message="knowledgePointId 与 proposedCode/proposedName 至少要有一组。",
                        field_name="knowledgePointId",
                    )
                ],
            )
        evidence = _string_list(entry.get("evidence"))
        unknown = [value for value in evidence if value not in allowed_items]
        if unknown:
            raise proposal_invalid(
                f"建议引用了输入之外的证据 id：{', '.join(unknown[:5])}。",
                issues=[
                    _issue(
                        index,
                        code=PAPER_PROPOSAL_INVALID,
                        message=f"evidence 含不在允许集合内的题目 id：{', '.join(unknown[:5])}。",
                        field_name="evidence",
                    )
                ],
            )
        ambiguity = entry.get("ambiguity", False)
        if not isinstance(ambiguity, bool):
            raise proposal_invalid(
                "ambiguity 必须是布尔值。",
                issues=[
                    _issue(
                        index,
                        code=PAPER_PROPOSAL_INVALID,
                        message="ambiguity 必须是 true/false。",
                        field_name="ambiguity",
                    )
                ],
            )
        question_no = str(entry.get("questionNo") or "").strip()
        items.append(
            ProposedItem(
                item_id=item_id,
                question_no=question_no,
                knowledge_point_id=point_id,
                proposed_code=code,
                proposed_name=name,
                evidence=tuple(evidence),
                ambiguity=ambiguity,
            )
        )
        raw_items.append(dict(entry))
    return items, raw_items


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise proposal_invalid("字段必须是字符串或 null。")
    text = value.strip()
    return text or None


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise proposal_invalid(
            "evidence 必须是字符串数组。",
            issues=[
                _issue(
                    None,
                    code=PAPER_PROPOSAL_INVALID,
                    message="evidence 必须是字符串数组。",
                    field_name="evidence",
                )
            ],
        )
    values: list[str] = []
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            raise proposal_invalid("evidence 里的每一项必须是非空字符串。")
        text = entry.strip()
        if len(text) > MAX_EVIDENCE_TEXT_CHARS:
            raise proposal_invalid(
                f"单条证据超过 {MAX_EVIDENCE_TEXT_CHARS} 字，建议未生成。"
            )
        values.append(text)
    if len(values) > MAX_EVIDENCE_PER_ITEM:
        raise proposal_invalid(
            f"单题证据条数超过上限 {MAX_EVIDENCE_PER_ITEM}，建议未生成。"
        )
    return values


# --------------------------------------------------------------------------- 执行器


@dataclass(frozen=True)
class ProposalDraft:
    """一次执行器产出的建议草稿；``proposal_id`` 在发布事务之前确定，便于写入任务结果。"""

    proposal_id: str
    job_id: str
    paper_id: str
    paper_revision_id: str
    base_revision: int
    subject_id: str
    allowed_item_ids: tuple[str, ...]
    allowed_point_ids: tuple[str, ...]
    items: tuple[ProposedItem, ...]
    raw_items: tuple[dict[str, Any], ...]
    model: dict[str, Any]


PublishProposal = Callable[[sqlite3.Connection, ProposalDraft], None]
#: 解析本次调用的模型句柄；参数是**冻结快照**（含 profileId + fingerprint），
#: 由调用方用公共 ``resolve_frozen_model`` 或等价的指纹核对实现
ResolveModel = Callable[[Mapping[str, object]], Awaitable[ChatModelHandle]]


def resolve_model_for_job(resolver: Any, profile_id: str) -> ChatModelHandle:
    """按冻结的 profileId 解析模型；失效即失败（不换模型、不回退默认）。

    同步函数（只调用同步的 ``resolver``）：调用方在**有界线程**里执行它，
    避免把配置读取阻塞在事件循环上。
    """
    if resolver is None:
        raise AppError(
            "原卷 AI 建议未装配模型解析器（model_resolver）。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            retryable=True,
        )
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise AppError(
            "该任务没有冻结模型配置，无法继续；请重新发起建议。",
            code="MODEL_PROFILE_NOT_FOUND",
            status_code=404,
        )
    try:
        handle = resolver(profile_id)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001 - 未知解析故障按上游不可用处理
        raise AppError(
            "模型配置解析失败：请检查模型设置后重试。",
            code="UPSTREAM_UNAVAILABLE",
            status_code=503,
            retryable=True,
        ) from exc
    if not isinstance(handle, ChatModelHandle):
        raise AppError(
            "模型解析器返回的句柄不符合契约，已停止建议。",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
        )
    return handle


@dataclass
class ProposalRunner:
    """任务执行器：事务外解析模型并调用；``publish`` 在结果发布事务内写 ``ai_proposals``。

    **模型冻结（B3/G0 · B2-RV04）**：快照里必须有 ``fingerprint``，缺指纹 → 422
    ``MODEL_FINGERPRINT_MISSING``（旧任务不静默放行）；解析出句柄后用
    ``fingerprint_of_handle`` 与冻结值比对，漂移 → 409 ``MODEL_CONFIG_DRIFT``，
    **不调用模型、不发布**；发布记录里的来源指纹取解析句柄的真实指纹（执行与来源一致）。
    """

    resolve_model: ResolveModel
    publish_proposal: PublishProposal
    contract_version: int = PROPOSAL_CONTRACT_VERSION

    async def __call__(self, frozen: FrozenJob, ctx: JobContext) -> JobOutcome:
        snapshot = frozen.model_snapshot if isinstance(frozen.model_snapshot, dict) else {}
        profile_id = str(
            snapshot.get("profileId") or snapshot.get("modelProfileId") or ""
        ).strip()
        frozen_fingerprint = str(
            snapshot.get("fingerprint") or snapshot.get("modelFingerprint") or ""
        ).strip()
        if not frozen_fingerprint:
            raise AppError(
                "该任务没有冻结的模型指纹，无法核对本次调用的真实配置；"
                "请重新发起建议（旧任务不自动重放）。",
                code=MODEL_FINGERPRINT_MISSING,
                status_code=422,
            )
        handle = await self.resolve_model(snapshot)
        actual = fingerprint_of_handle(handle)
        if actual != frozen_fingerprint:
            raise AppError(
                "模型配置自任务创建后已变化（与冻结指纹不一致）；本次调用已停止，"
                "请重新发起建议。",
                code=MODEL_CONFIG_DRIFT,
                status_code=409,
            )
        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=system_instruction(frozen.input)),
                LLMMessage(role="user", content=render_items(frozen.input)),
            ],
            maxOutputTokens=MAX_OUTPUT_TOKENS,
            params={},
        )
        response = await handle.provider.complete(handle.config, request)
        if response.finishReason == FINISH_LENGTH:
            raise proposal_invalid(
                "模型输出被截断（结束原因 length），建议未生成；"
                "请提高该模型的输出上限或缩小题目范围后重试。"
            )
        allowed_items = [str(item) for item in frozen.input.get("allowedItemIds") or []]
        allowed_points = [
            str(item) for item in frozen.input.get("allowedKnowledgePointIds") or []
        ]
        items, raw_items = parse_reply(
            response.text,
            allowed_item_ids=allowed_items,
            allowed_point_ids=allowed_points,
        )
        if await ctx.cancellation_requested():
            # 取消优先于迟到结果：不写建议；引擎随后置 cancelled
            return JobOutcome(
                result={"cancelled": True, "proposalId": None, "itemCount": 0},
                publish=None,
            )
        question_no = {
            str(item.get("itemId")): str(item.get("questionNo") or "")
            for item in frozen.input.get("items") or []
            if isinstance(item, dict)
        }
        filled = tuple(
            replace(item, question_no=question_no.get(item.item_id, ""))
            for item in items
        )
        draft = ProposalDraft(
            proposal_id=uuid.uuid4().hex,
            job_id=frozen.job_id,
            paper_id=str(frozen.input.get("paperId") or ""),
            paper_revision_id=str(frozen.input.get("paperRevisionId") or ""),
            base_revision=int(frozen.input.get("baseRevision") or 0),
            subject_id=str(frozen.input.get("subjectId") or ""),
            allowed_item_ids=tuple(allowed_items),
            allowed_point_ids=tuple(allowed_points),
            items=filled,
            raw_items=tuple(dict(item) for item in raw_items),
            model={
                "profileId": profile_id or handle.profile_id,
                # 来源指纹 = 本次真实调用模型的指纹（与冻结值一致，漂移已在上面拒绝）
                "fingerprint": actual,
                "contractVersion": self.contract_version,
            },
        )

        def publish(conn: sqlite3.Connection) -> None:
            self.publish_proposal(conn, draft)

        return JobOutcome(
            result={
                "proposalId": draft.proposal_id,
                "itemCount": len(draft.items),
                "paperRevisionId": frozen.input.get("paperRevisionId"),
                "baseRevision": frozen.input.get("baseRevision"),
            },
            publish=publish,
        )


__all__ = [
    "MAX_ALLOWED_POINTS",
    "MAX_ITEMS",
    "MAX_OUTPUT_TOKENS",
    "PROPOSAL_CONTRACT_VERSION",
    "PROPOSAL_INSTRUCTION",
    "ProposalDraft",
    "ProposalRunner",
    "ProposedItem",
    "model_fingerprint",
    "parse_reply",
    "proposal_invalid",
    "render_items",
    "resolve_model_for_job",
    "system_instruction",
]
