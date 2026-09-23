"""技能上下文拼装：只生成提示词级系统消息，不执行工具、不访问外部数据。"""

from __future__ import annotations

from app.schemas.chat import ChatSkillIn
from app.services.skill_context import PREAMBLE, build_skill_system_message


def test_no_skills_returns_none():
    assert build_skill_system_message(None) is None
    assert build_skill_system_message([]) is None


def test_blank_content_does_not_produce_message():
    assert build_skill_system_message([ChatSkillIn(name="空技能", content="   ")]) is None


def test_single_skill_keeps_preamble_and_name():
    message = build_skill_system_message(
        [ChatSkillIn(name="教案规范", content="按七个栏目输出。")]
    )
    assert message is not None
    assert message.startswith(PREAMBLE)
    assert "### 教案规范\n按七个栏目输出。" in message


def test_multiple_skills_preserve_order():
    message = build_skill_system_message(
        [
            ChatSkillIn(name="甲", content="第一条"),
            ChatSkillIn(name="乙", content="第二条"),
        ]
    )
    assert message is not None
    assert message.index("### 甲") < message.index("### 乙")


def test_blank_names_fall_back_without_faking_a_name():
    message = build_skill_system_message([ChatSkillIn(name="  ", content="正文")])
    assert message is not None
    assert "### 未命名技能" in message
