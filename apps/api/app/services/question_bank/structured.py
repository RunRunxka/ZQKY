"""题库 LangChain 结构化输出的 Pydantic schema（R4 改造）。

与 ``services.llm.runner.run_structured`` 配套：``with_structured_output`` 的严格
校验只管**形状**（模型输出对象 → schema），字段语义约束（题型枚举回退、来源块
集合核验、题库契约 parse_content、URL/路径扫描）仍由既有解析层显式执行——
解析层的错误码与文案逐字保留，本模块不新增语义。

``extra="ignore"``：模型多输出的字段由解析层按归档口径处理（忽略未知键），
结构层不因多余字段拒绝整批（避免把「多写了一个键」升级成批级失败）。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "GenerationReplySchema",
    "OrganizeReplySchema",
    "looks_truncated",
    "looks_truncated_failure",
]


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _OptionSchema(_Loose):
    key: str = ""
    text: str | None = None
    textMarkdown: str | None = None


class _AnswerSchema(_Loose):
    choiceKeys: list[str] = Field(default_factory=list)
    accepted: bool | None = None
    text: str | None = None
    textMarkdown: str | None = None


class OrganizeReplySchema(_Loose):
    """AI 整理单批回复（归档 JSON 契约的同构形状）。"""

    type: str | None = None
    stem: str | None = None
    stemMarkdown: str | None = None
    options: list[_OptionSchema] = Field(default_factory=list)
    answer: _AnswerSchema | None = None
    explanation: str | None = None
    explanationMarkdown: str | None = None
    sourceBlockIds: list[str] = Field(default_factory=list)


class _GenerationQuestionSchema(_Loose):
    type: str | None = None
    stem: str | None = None
    stemMarkdown: str | None = None
    options: list[_OptionSchema] = Field(default_factory=list)
    answer: _AnswerSchema | None = None
    explanation: str | None = None
    explanationMarkdown: str | None = None
    knowledgePointIds: list[str] = Field(default_factory=list)
    evidenceIds: list[str] = Field(default_factory=list)
    assetIds: list[str] = Field(default_factory=list)


class GenerationReplySchema(_Loose):
    """AI 补题整批回复：``{"questions":[…]}``（``GENERATION_OUTPUT_TRUNCATED`` 等
    语义由解析层按归档口径判定）。"""

    questions: list[_GenerationQuestionSchema] = Field(default_factory=list)


def looks_truncated(raw: str | None) -> bool:
    """把「截断」从裸 ``finish_reason == length`` 适配到 LangChain 路径（R4）。

    LangChain ``with_structured_output`` 没有裸 ``finish_reason``；模型输出被输出
    上限截断时表现为 JSON 半截（解析失败）。形状判定：文本以 ``{``/``[`` 开头、
    未以配对字符收尾 → 判为截断（与 R5 papers 的 ``TRUNCATED_REPLY`` 同一适配口径）。
    其余解析失败不判截断（按 ``*_INVALID_JSON`` 处理）。
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            _head, _, tail = text.partition("\n")
            if _head.strip().lower() in {"json", ""}:
                text = tail
        text = text.strip()
    if not text:
        return False
    open_char = text[0]
    if open_char == "{":
        closed, payload = text.endswith("}"), text[1:-1 if text.endswith("}") else None]
    elif open_char == "[":
        closed, payload = text.endswith("]"), text[1:-1 if text.endswith("]") else None]
    else:
        return False
    if closed:
        return False
    # 截断 = 合法 JSON 片段被掐断：已写入部分不得出现结构性非法字符（CJK 胡言、
    # 控制字符等），否则按非法内容处理（不冤枉为截断）。
    return _payload_is_structural(payload or "")


def looks_truncated_failure(raw: str | None, error: str | None) -> bool:
    """对降级 outcome 的截断判定（``error`` 形参保留诊断用途；判定以原始文本为准）。

    ``run_structured`` 的解析失败路径 ``raw`` 就是模型原始输出（include_raw 链路
    保留），形状判定（``looks_truncated``）即完整判定：合法 JSON 前缀被掐断 →
    截断；其余（含``{不是 JSON`` 类提示词回显）→ 非法内容。
    """
    _ = error
    return looks_truncated(raw)


def _payload_is_structural(payload: str) -> bool:
    """已写入的载荷是否全是结构字符（ASCII 结构/字符串内容，无 CJK 胡言/控制字符）。

    截断的载荷是「合法 JSON 片段被掐断」——引号内的字符串内容可以是任意可打印
    文本（含 CJK，如中文题干写一半）；但**结构位置**上不能出现提示词回显（如
    ``{不是 JSON``）。近似判别：载荷不含会立刻破坏 JSON 的字符（裸 CJK 出现在
    键位、控制字符、反引号），且整体仍是「前缀可续写」的形状。
    """
    if not payload.strip():
        return True
    stripped = payload
    # 去掉完整引号包裹的字符串内容（内容可以是任意可打印文本，含 CJK）
    result: list[str] = []
    in_string = False
    escaped = False
    for ch in stripped:
        if escaped:
            escaped = False
            continue
        if in_string:
            if ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            elif ord(ch) < 0x20:
                return False
            continue
        if ch == '"':
            in_string = True
            continue
        result.append(ch)
        if not ch.isascii():
            return False
        if ch not in '{}[]",:0123456789.-+eE \t\r\n':
            return False
    return True
