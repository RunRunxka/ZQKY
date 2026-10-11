"""提示词登记与版本指纹（R0-C；LangChain + LangGraph 硬性架构的一部分）。

所有模块的 LLM 提示词都必须集中经 ``register_prompt`` 登记：

- 统一记录 ``id``/``version``；投入生成流程后内容变更必须显式升版（同版本不同内容
  会被拒绝），避免"悄悄改提示词"；
- ``fingerprint`` 可进入产物指纹（分块策略、生成快照等），保证「同输入 + 同提示词」
  才可能复现。

模板使用 LangChain ``ChatPromptTemplate`` 的 f-string 风格：变量写成 ``{name}``，
需要输出字面花括号时用 ``{{``/``}}`` 转义。
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate

__all__ = [
    "PromptNotFound",
    "PromptSpec",
    "get_prompt",
    "prompt_fingerprint",
    "register_prompt",
    "registered_prompts",
]


class PromptNotFound(KeyError):
    """请求了未登记的提示词 id。"""


@dataclass(frozen=True)
class PromptSpec:
    """一条提示词：``human`` 必填，``system`` 可选；``version`` 显式升版。"""

    id: str
    version: str
    human: str
    system: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("id", "version", "human"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"提示词 {field_name} 不能为空（id={self.id!r}）")

    def messages(self, variables: Mapping[str, object] | None = None) -> list[BaseMessage]:
        """按模板渲染出 LangChain 消息列表（system 在前）。"""
        parts: list[tuple[str, str]] = []
        if self.system:
            parts.append(("system", self.system))
        parts.append(("human", self.human))
        template = ChatPromptTemplate.from_messages(parts)
        return template.format_messages(**dict(variables or {}))

    @property
    def fingerprint(self) -> str:
        """id + version + 模板全文的 sha256（十六进制）。"""
        digest = hashlib.sha256()
        for part in (self.id, self.version, self.system or "", self.human):
            digest.update(part.encode("utf-8"))
            digest.update(b"\x00")
        return digest.hexdigest()


_PROMPTS: dict[str, PromptSpec] = {}
_LOCK = threading.Lock()


def register_prompt(spec: PromptSpec) -> PromptSpec:
    """登记提示词；同 id 同版本但内容不同 → 拒绝（必须升版）。"""
    with _LOCK:
        existing = _PROMPTS.get(spec.id)
        if existing is not None and existing.version == spec.version and existing != spec:
            raise ValueError(
                f"提示词 {spec.id} 版本 {spec.version} 已登记且内容不同；"
                "修改提示词必须显式升级 version。"
            )
        _PROMPTS[spec.id] = spec
    return spec


def get_prompt(prompt_id: str) -> PromptSpec:
    try:
        return _PROMPTS[prompt_id]
    except KeyError as exc:  # pragma: no cover - 直接透出缺 id 的语义
        raise PromptNotFound(prompt_id) from exc


def registered_prompts() -> Mapping[str, PromptSpec]:
    """只读快照（按 id 排序不保证顺序，调用方自行排序）。"""
    with _LOCK:
        return MappingProxyType(dict(_PROMPTS))


def prompt_fingerprint(prompt_id: str) -> str:
    return get_prompt(prompt_id).fingerprint
