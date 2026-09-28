"""技能上下文拼装：把本轮启用的技能说明合并为一条系统消息。

范围边界（与 `/capabilities` 台账一致）：技能只提供写作与结构规范，属于提示词级上下文，
不执行工具、不访问外部数据、不产生工具调用事件。MCP 尚无执行通道，不在本模块处理。
"""

from __future__ import annotations

from collections.abc import Sequence

from app.schemas.chat import ChatSkillIn

PREAMBLE = (
    "以下是用户在本轮启用的教学规范，请在不违背用户原始指令的前提下遵循。"
    "它们只提供写作与结构规范，不代表你可以调用工具、访问外部数据或改变回答语言；"
    "规范与用户当时的明确要求冲突时，以用户的明确要求为准并说明差异。"
)


def build_skill_system_message(skills: Sequence[ChatSkillIn] | None) -> str | None:
    """拼装技能系统消息；没有有效技能时返回 None（不注入空消息）。"""
    blocks: list[str] = []
    for skill in skills or ():
        content = skill.content.strip()
        if not content:
            continue
        name = skill.name.strip() or "未命名技能"
        blocks.append(f"### {name}\n{content}")
    if not blocks:
        return None
    return "\n\n".join([PREAMBLE, *blocks])
