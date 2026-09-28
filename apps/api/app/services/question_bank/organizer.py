"""AI 整理的可注入模型端口、批packing 与回复校验（不自动下载、不调用云端）。

模型语义（v1.2 起唯一化，不再有第二种解释）：

- **AI 整理只用本机 Ollama 的本地模型，绝不调用云端聊天模型**（教材与题面不得转给云端）；
- ``OrganizeRequest.modelProfileId`` 只是**可选的本地模型名覆盖**：省略或空串 → 服务端默认整理模型；
  给了本机已安装的模型名 → 用它；不在本机列表里 → 422 ``ORGANIZER_MODEL_MISSING``（不把任意字符串
  当模型名发给上游，UUID 之类的 profile 标识永远不进 ``/api/chat``）；
- 在场校验走本机 ``/api/tags``，tag 归一复用 B1 的 ``normalize_model_tag`` /
  ``model_names_match``（绝不做"包含即命中"）；
- 解析与校验由服务层（``QuestionBankService._resolve_local_model``）完成，端口只接收已解析的
  本地模型名（``OrganizerCall.model_name``）。

其余约束：

- 输入按完整原文块打包，每批不超过 ``MAX_BATCH_INPUT_CHARS``；单个超长块按行切成多批，
  每批仍带同一块 id，来源可回溯；
- 输出预算不超过 ``MAX_OUTPUT_TOKENS``；
- 指令固定：整理试题原文，返回题干、选项、原文已有答案与解析以及 sourceBlockIds；
  不推断原文缺失的答案，不引用输入之外的来源；
- 非法 JSON、截断输出、未知 sourceBlockIds 一律判该批失败，原文保留；
- 默认实现只连本机回环 Ollama；测试与总控通过 ``OrganizerModel`` 替身注入。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol, Sequence
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.exceptions import AppError
from app.providers.embeddings.ollama_embedding import model_names_match
from app.services.question_bank import validation
from app.services.question_bank.fingerprint import canonical_json
from app.services.question_bank.rules import infer_type

MAX_BATCH_INPUT_CHARS = 6000
MAX_OUTPUT_TOKENS = 2048
DEFAULT_TIMEOUT_SECONDS = 180.0
TAGS_TIMEOUT_SECONDS = 10.0
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

#: 服务端默认整理模型；与 RAG 知识点概括的默认保持一致（qwen2.5:7b），可通过构造参数覆盖
DEFAULT_ORGANIZE_MODEL = "qwen2.5:7b"
#: 面向用户的固定语义说明；错误信息里只出现它，不回显请求里的字符串
LOCAL_MODEL_POLICY = "AI 整理只使用本机 Ollama 模型"

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

#: 模型/传输层错误：整条整理任务失败（不是某批的内容问题），可稍后重试
JOB_LEVEL_ORGANIZER_ERRORS = frozenset(
    {"ORGANIZER_UNAVAILABLE", "ORGANIZER_TIMEOUT", "ORGANIZER_MODEL_MISSING"}
)
#: 单批内容错误：该批失败，原文保留，其余批次继续
BATCH_LEVEL_ORGANIZER_ERRORS = frozenset(
    {
        "ORGANIZER_INVALID_JSON",
        "ORGANIZER_TRUNCATED",
        "ORGANIZER_UNKNOWN_SOURCE_BLOCK",
        "ORGANIZER_INVALID_CONTENT",
    }
)


@dataclass(frozen=True)
class OrganizerCall:
    job_id: str
    batch_index: int
    #: 已由服务层解析并校验在场的本机 Ollama 模型名（不是 profile 标识）
    model_name: str
    instruction: str
    input_text: str
    max_output_tokens: int


@dataclass(frozen=True)
class Batch:
    index: int
    draft_id: str
    block_ids: tuple[str, ...]
    input_text: str
    char_count: int


class OrganizerModel(Protocol):
    """可注入的模型端口；替身只需实现 ``organize(call) -> str``。"""

    def organize(self, call: OrganizerCall) -> str:  # pragma: no cover - 协议声明
        ...


class LocalModelCatalog(Protocol):
    """本机已安装模型清单端口（默认实现读 Ollama ``/api/tags``，测试注入替身）。"""

    def installed_models(self) -> list[str]:  # pragma: no cover - 协议声明
        ...


class OllamaModelCatalog:
    """本机 Ollama ``/api/tags`` 的最小只读客户端：只列已安装模型，不下载、不外呼。"""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = TAGS_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        # 只允许回环地址：本机模型清单不允许取远程/容器地址
        self.base_url = normalize_loopback_base_url(base_url)
        self.timeout_seconds = float(timeout_seconds)
        self._transport = transport

    def installed_models(self) -> list[str]:
        """GET /api/tags → 已安装模型名（保留 Ollama 给出的原始 tag）。"""
        client_kwargs: dict[str, Any] = {
            "timeout": self.timeout_seconds,
            "trust_env": False,
            "follow_redirects": False,
        }
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        try:
            with httpx.Client(**client_kwargs) as client:
                response = client.get(f"{self.base_url}/api/tags")
        except httpx.TimeoutException as exc:
            raise AppError(
                "读取本机模型列表超时，请确认 Ollama 状态后重试。",
                code="ORGANIZER_TIMEOUT",
                status_code=503,
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                "本机 Ollama 不可用，无法确认已安装模型；请启动 Ollama 后重试。",
                code="ORGANIZER_UNAVAILABLE",
                status_code=503,
                retryable=True,
            ) from exc
        if response.status_code in _REDIRECT_STATUSES or response.status_code >= 400:
            raise AppError(
                f"读取本机模型列表失败（HTTP {response.status_code}），该次整理未执行。",
                code="ORGANIZER_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise AppError(
                "本机模型列表不是 JSON，无法确认模型是否在场。",
                code="ORGANIZER_UNAVAILABLE",
                status_code=503,
                retryable=True,
            ) from exc
        entries = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            raise AppError(
                "本机模型列表缺少 models 数组，无法确认模型是否在场。",
                code="ORGANIZER_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        names: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("model")
            if isinstance(name, str) and name.strip() and name not in names:
                names.append(name)
        return names


def match_installed_model(requested: str, installed: Sequence[str]) -> str | None:
    """按 B1 的 tag 归一在已安装列表里找等价模型；返回命中的已安装名（找不到返回 None）。

    只做 tag 归一 + 全等，绝不做"包含即命中"：``qwen2.5:7b`` 不匹配 ``qwen2.5-coder:7b``。
    """
    target = (requested or "").strip()
    if not target:
        return None
    for name in installed:
        if model_names_match(target, name):
            return name
    return None


def render_block(block_id: str, text: str) -> str:
    return f"[块 {block_id}]\n{text.strip()}"


def pack_batches(
    draft_id: str,
    blocks: Sequence[tuple[str, str]],
    *,
    start_index: int = 0,
    max_chars: int = MAX_BATCH_INPUT_CHARS,
) -> list[Batch]:
    """把完整原文块按输入上限打包；单块超限时按行切批（块 id 不变）。"""
    batches: list[Batch] = []
    pending: list[str] = []
    pending_ids: list[str] = []
    pending_chars = 0

    def flush() -> None:
        nonlocal pending, pending_ids, pending_chars
        if not pending:
            return
        index = start_index + len(batches)
        batches.append(
            Batch(
                index=index,
                draft_id=draft_id,
                block_ids=tuple(pending_ids),
                input_text="\n\n".join(pending),
                char_count=pending_chars,
            )
        )
        pending = []
        pending_ids = []
        pending_chars = 0

    for block_id, text in blocks:
        rendered = render_block(block_id, text)
        if len(rendered) <= max_chars:
            if pending and pending_chars + len(rendered) + 2 > max_chars:
                flush()
            pending.append(rendered)
            pending_ids.append(block_id)
            pending_chars += len(rendered) + (2 if len(pending) > 1 else 0)
            continue
        flush()
        for slice_text in _slice_block(text, max_chars):
            index = start_index + len(batches)
            batches.append(
                Batch(
                    index=index,
                    draft_id=draft_id,
                    block_ids=(block_id,),
                    input_text=render_block(block_id, slice_text),
                    char_count=len(render_block(block_id, slice_text)),
                )
            )
    flush()
    return batches


def _slice_block(text: str, max_chars: int) -> list[str]:
    lines = text.split("\n")
    slices: list[str] = []
    current: list[str] = []
    current_chars = 0
    for line in lines:
        if current and current_chars + len(line) + 1 > max_chars:
            slices.append("\n".join(current))
            current = []
            current_chars = 0
        if len(line) > max_chars:
            # 极端单行：按字符硬切，保证每片不超上限
            step = max(1, max_chars)
            for start in range(0, len(line), step):
                slices.append(line[start : start + step])
            continue
        current.append(line)
        current_chars += len(line) + 1
    if current:
        slices.append("\n".join(current))
    return slices or [text]


def normalize_reply(raw: str, allowed_block_ids: Sequence[str]) -> dict[str, Any]:
    """把模型回复规范化为题库内容与来源；任一处不合法抛对应错误码。"""
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
            "AI 返回内容不是合法 JSON，该批已失败，原文保留。",
            code="ORGANIZER_INVALID_JSON",
            status_code=422,
        ) from exc
    if not isinstance(payload, dict):
        raise AppError(
            "AI 返回的 JSON 不是对象，该批已失败，原文保留。",
            code="ORGANIZER_INVALID_JSON",
            status_code=422,
        )

    block_ids = _string_list(payload.get("sourceBlockIds"))
    if not block_ids:
        raise AppError(
            "AI 未返回 sourceBlockIds，无法核验来源，该批已失败，原文保留。",
            code="ORGANIZER_UNKNOWN_SOURCE_BLOCK",
            status_code=422,
        )
    unknown = [block_id for block_id in block_ids if block_id not in allowed]
    if unknown:
        raise AppError(
            f"AI 引用了输入之外的来源块：{', '.join(unknown[:5])}，该批已失败，原文保留。",
            code="ORGANIZER_UNKNOWN_SOURCE_BLOCK",
            status_code=422,
        )

    stem = _first_text(payload, ("stem", "stemMarkdown"))
    options = _options(payload.get("options"))
    answer = _answer(payload.get("answer"))
    explanation = _first_text(payload, ("explanation", "explanationMarkdown")) or None
    question_type = payload.get("type")
    if not isinstance(question_type, str) or question_type not in {
        "single_choice",
        "multiple_choice",
        "true_false",
        "fill_blank",
        "short_answer",
        "other",
    }:
        question_type = None
    if not stem:
        raise AppError(
            "AI 返回内容缺少题干，该批已失败，原文保留。",
            code="ORGANIZER_INVALID_CONTENT",
            status_code=422,
        )

    content: dict[str, Any] = {
        "type": question_type
        or _infer_type_fallback(stem, options, answer),
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
            "AI 返回内容不符合题库契约，该批已失败，原文保留。",
            code="ORGANIZER_INVALID_CONTENT",
            status_code=422,
        ) from exc
    return {"content": content, "source_block_ids": block_ids}


def _infer_type_fallback(
    stem: str, options: Sequence[dict[str, str]], answer: dict[str, Any] | None
) -> str:
    return infer_type(stem, options, answer)


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
        return {"choiceKeys": [], "accepted": None, "textMarkdown": stripped} if stripped else None
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


class OllamaOrganizerModel:
    """本机 Ollama ``/api/chat`` 默认实现；只允许回环地址，绝不调用云端。

    模型名由服务层解析（已在本机 ``/api/tags`` 校验在场）：``OrganizerCall.model_name``。
    本适配器不接收、也不解释 profile 标识；空模型名直接失败，不做任何"兜底猜模型"。
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = normalize_loopback_base_url(base_url)
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    def organize(self, call: OrganizerCall) -> str:
        model = (call.model_name or "").strip()
        if not model:
            raise AppError(
                f"{LOCAL_MODEL_POLICY}；未解析到可用的本地整理模型，该次整理未执行。",
                code="ORGANIZER_MODEL_MISSING",
                status_code=422,
            )
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": call.instruction},
                {"role": "user", "content": call.input_text},
            ],
            "stream": False,
            "format": "json",
            "options": {"num_predict": min(call.max_output_tokens, MAX_OUTPUT_TOKENS), "temperature": 0},
        }
        client_kwargs: dict[str, Any] = {
            "timeout": self.timeout_seconds,
            "trust_env": False,
            "follow_redirects": False,
        }
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        try:
            with httpx.Client(**client_kwargs) as client:
                response = client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.TimeoutException as exc:
            raise AppError(
                "本机整理模型调用超时，可稍后重试。",
                code="ORGANIZER_TIMEOUT",
                status_code=503,
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                "本机整理模型不可用，请确认 Ollama 已启动。",
                code="ORGANIZER_UNAVAILABLE",
                status_code=503,
                retryable=True,
            ) from exc
        if response.status_code in _REDIRECT_STATUSES:
            raise AppError(
                "整理模型地址发生重定向，已拒绝跟随。",
                code="ORGANIZER_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        if response.status_code == 404:
            raise AppError(
                f"本机没有名为「{model}」的模型，且不会自动下载。",
                code="ORGANIZER_MODEL_MISSING",
                status_code=422,
            )
        if response.status_code >= 400:
            raise AppError(
                f"整理模型返回 HTTP {response.status_code}，该次调用失败。",
                code="ORGANIZER_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise AppError(
                "整理模型返回的不是 JSON。",
                code="ORGANIZER_UNAVAILABLE",
                status_code=503,
                retryable=True,
            ) from exc
        if not isinstance(body, dict):
            raise AppError(
                "整理模型返回结构异常。",
                code="ORGANIZER_UNAVAILABLE",
                status_code=503,
                retryable=True,
            )
        if body.get("done_reason") == "length":
            raise AppError(
                "整理模型输出被截断，该批已失败，原文保留。",
                code="ORGANIZER_TRUNCATED",
                status_code=422,
            )
        message = body.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise AppError(
                "整理模型没有返回内容，该批已失败，原文保留。",
                code="ORGANIZER_INVALID_JSON",
                status_code=422,
            )
        return content


def normalize_loopback_base_url(base_url: str) -> str:
    raw = (base_url or "").strip()
    if not raw:
        raise AppError(
            "整理模型地址不能为空。",
            code="ORGANIZER_BASE_URL_INVALID",
            status_code=422,
        )
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"}:
        raise AppError(
            "整理模型地址必须是 http 或 https。",
            code="ORGANIZER_BASE_URL_INVALID",
            status_code=422,
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AppError(
            "整理模型地址不允许携带凭证、查询串或片段。",
            code="ORGANIZER_BASE_URL_INVALID",
            status_code=422,
        )
    host = parsed.hostname
    if host is None or host not in LOOPBACK_HOSTS:
        raise AppError(
            "整理模型只允许本机回环地址（127.0.0.1 / localhost / ::1），"
            f"收到：{host or raw}。",
            code="ORGANIZER_BASE_URL_NOT_LOCAL",
            status_code=422,
        )
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


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
