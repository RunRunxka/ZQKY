"""对话生成教案（C 批）：图级 interrupt → 确认 → 续跑 → 写草稿。

用假模型（首次返回工具调用、续跑后返回文本）+ 假服务验证：
- 工具在确认前不生成、不写库（wait-confirm 先挂起）；
- 恢复 approve 后才生成并调用 create_lesson，submissionId 来自确认请求；
- 续跑事件把工具结果与最终文本写回流。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import aiosqlite
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.services.agent import runtime, tools_write
from app.services.agent.graph import AgentDeps, build_agent
from app.services.agent.tools_write import build_confirm_tools


class _ToolThenTextModel(GenericFakeChatModel):
    replies: ClassVar[list[AIMessage]] = []

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001, ANN003
        return self

    def _generate(self, messages, stop=None, **kwargs):  # noqa: ANN001, ANN003
        reply = type(self).replies.pop(0)
        return ChatResult(generations=[ChatGeneration(message=reply)])

    async def _agenerate(self, messages, stop=None, **kwargs):  # noqa: ANN001, ANN003
        return self._generate(messages, stop, **kwargs)


class _Roster:
    def get_class(self, class_id: str):  # noqa: ANN201
        assert class_id == "class-1"
        return type("_K", (), {"name": "高一（1）班"})()


class _Lessons:
    def __init__(self) -> None:
        self.created: list[dict] = []

    def create_lesson(self, body: dict) -> dict:
        self.created.append(body)
        return {"lessonPlanId": "lesson-1", "revision": 1}


def _state(**services: Any) -> Any:
    class _S:
        pass

    state = _S()
    for key, value in services.items():
        setattr(state, key, value)
    return state


@pytest.mark.asyncio
async def test_create_lesson_interrupt_resume_writes_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lessons = _Lessons()
    state = _state(lesson_plan_service=lessons, roster_service=_Roster())
    model = _ToolThenTextModel(messages=iter([]), disable_streaming=True)
    _ToolThenTextModel.replies = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "create_lesson_plan_draft",
                    "args": {
                        "subject_id": "math",
                        "class_id": "class-1",
                        "course_name": "函数的单调性",
                        "requirements": "1 课时",
                    },
                    "id": "call-1",
                }
            ],
        ),
        AIMessage(content="教案草稿已保存，可在教案工作台中打开。"),
    ]

    async def fake_generate_sections(chat_model, *, context):  # noqa: ANN001, ANN202, ARG001
        return (
            {
                "analysis": {"learning": "学情", "textbook": "", "content": "", "ideological": ""},
                "objectives": {"knowledge": "知识目标", "ability": "", "ideological": "", "key_points": "", "difficulty": ""},
            },
            {},
        )

    monkeypatch.setattr(tools_write, "generate_sections", fake_generate_sections)

    conn = await aiosqlite.connect(str(tmp_path / "ck.sqlite3"))
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    try:
        handle = type("_Handle", (), {"chat_model": model})()
        agent = build_agent(
            AgentDeps(
                chat_model=model,
                tools=build_confirm_tools(state, handle=handle),
                checkpointer=saver,
            )
        )

        first = [
            event
            async for event in runtime.run_turn(agent, thread_id="thread-1", user_text="生成函数的单调性教案")
        ]
        assert lessons.created == [], "确认前不得写库"
        wait = [event for event in first if event["type"] == "wait-confirm"]
        assert len(wait) == 1
        payload = wait[0]["payload"]
        assert payload["action"] == "create_lesson_plan"
        assert payload["subjectId"] == "math" and payload["classId"] == "class-1"

        resumed = [
            event
            async for event in runtime.resume_turn(
                agent,
                thread_id="thread-1",
                decision={"decision": "approve", "submissionId": "sub-12345678"},
            )
        ]
        assert len(lessons.created) == 1
        body = lessons.created[0]
        assert body["submissionId"] == "sub-12345678"
        assert body["subjectId"] == "math" and body["classId"] == "class-1"
        assert body["data"]["title"] == "函数的单调性"
        assert any(
            event["type"] == "tool_result" and "lessonId=lesson-1" in event["output"]
            for event in resumed
        )
        # 工具返回后图继续跑完（假模型不流式，正文由 on_chat_model_stream 承载，
        # 这里用「第二次模型调用已消费」+ 收尾事件证明图正常结束）。
        assert _ToolThenTextModel.replies == []
        assert any(event["type"] == "end" for event in resumed)
        assert not any(event["type"] == "wait-confirm" for event in resumed), "恢复后不应再弹旧确认卡"
    finally:
        await conn.close()
