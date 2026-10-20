"""对话教案草稿：七模块结果 → LessonPlanData 的确定性组装。

全部为纯函数/假运行器，不触网、不写库：
- 完整/部分模块都能通过契约严格校验（部分失败不丢整份）；
- 教学目标/重难点按前端工作台的「知识：/能力：/思政：」「教学重点：/教学难点：」口径编码；
- 教学过程按阶段稳定排序、行 id 唯一。
"""

from __future__ import annotations

import pytest

from app.contracts import lesson_plans as lp
from app.services.lesson_streaming import draft
from app.services.llm.runner import StructuredOutcome


def _full_sections() -> dict[str, dict]:
    return {
        "analysis": {
            "learning": "学生已具备函数基础。",
            "textbook": "本节承接函数概念。",
            "content": "函数单调性。",
            "ideological": "体会数学的严谨性。",
        },
        "objectives": {
            "knowledge": "理解单调性定义。",
            "ability": "能判断简单函数的单调性。",
            "ideological": "形成严谨推理习惯。",
            "key_points": "单调性定义。",
            "difficulty": "用定义证明单调性。",
        },
        "strategy": {
            "design_thinking": "从图像直观到定义证明。",
            "teaching_flow": "情境—探究—练习—总结。",
            "methods": "启发式与小组讨论。",
            "teaching_design": "板书：定义—例题—方法。",
        },
        "process": {
            "rows": [
                {"phase": "practice", "title": "练习", "teacher_activity": "巡视", "student_activity": "做题", "intent": "巩固"},
                {"phase": "introduction", "title": "导入", "teacher_activity": "提问", "student_activity": "回答", "intent": "唤醒"},
                {"phase": "课前热身", "title": "热身", "teacher_activity": "口算", "student_activity": "口答", "intent": "预热"},
            ]
        },
        "exercises": {"text": "教材练习 1-3 题。"},
        "evaluation": {"after_class_test": "当堂检测 5 题。", "homework": "课后作业 1-2 题。"},
        "reflection": {"text": "目标达成度较高，需加强证明书写。"},
    }


def test_compose_full_sections_is_valid_lesson_data() -> None:
    data = draft.compose_lesson_data(course_name="函数的单调性", class_name="高一（1）班", sections=_full_sections())
    parsed = lp.LessonPlanData.model_validate(data)
    assert parsed.title == "函数的单调性"
    assert parsed.core_competencies.splitlines()[0] == "知识：理解单调性定义。"
    assert parsed.key_points.splitlines()[0] == "教学重点：单调性定义。"
    assert parsed.teaching_design == "板书：定义—例题—方法。"
    assert parsed.basic is not None and parsed.basic.audience == "高一（1）班"
    assert parsed.analysis is not None and parsed.analysis.learning.startswith("学生已具备")
    assert parsed.strategy is not None and parsed.strategy.methods == "启发式与小组讨论。"
    assert parsed.evaluation is not None and parsed.evaluation.homework == "课后作业 1-2 题。"
    assert parsed.exercises == "教材练习 1-3 题。"
    assert parsed.reflection.startswith("目标达成度")
    # 阶段按 warmup→introduction→exploration→practice→conclusion 稳定排序，标签随之分组
    assert [row.phase for row in parsed.process_v2] == ["warmup", "introduction", "practice"]
    assert parsed.process_v2[0].phase_label == "课前热身"
    assert len({row.id for row in parsed.process_v2}) == 3


def test_compose_partial_sections_still_valid() -> None:
    data = draft.compose_lesson_data(
        course_name="荷塘月色",
        class_name="高二（2）班",
        sections={"reflection": {"text": "朗读指导有效。"}},
    )
    parsed = lp.LessonPlanData.model_validate(data)
    assert parsed.core_competencies == ""
    assert parsed.key_points == ""
    assert parsed.analysis is not None and parsed.analysis.learning == ""
    assert parsed.process_v2 == []
    assert parsed.reflection == "朗读指导有效。"


def test_compose_truncates_title_by_utf16() -> None:
    data = draft.compose_lesson_data(course_name="课" * 100, class_name="班", sections={})
    parsed = lp.LessonPlanData.model_validate(data)
    assert lp.utf16_length(parsed.title) == 80


@pytest.mark.asyncio
async def test_generate_sections_marks_internal_llm_events(monkeypatch: pytest.MonkeyPatch) -> None:
    """工具内部七模块生成必须带内部标签，Agent 运行时据此不把 token 写进聊天。"""
    from app.services.llm.tags import INTERNAL_TOOL_LLM_TAG

    captured: list[dict] = []

    async def fake_run_structured(chat_model, *, schema, **kwargs):  # noqa: ANN001, ANN003
        captured.append(kwargs.get("config") or {})
        return StructuredOutcome(parsed=schema(), raw_text="{}", attempts=1)

    monkeypatch.setattr(draft, "run_structured", fake_run_structured)
    await draft.generate_sections(object(), context="固定数据")
    assert len(captured) == len(draft.MODULE_ORDER)
    assert all(config.get("tags") == [INTERNAL_TOOL_LLM_TAG] for config in captured)
    assert all(config.get("callbacks") == [] for config in captured)

    """单模块失败不抛异常：成功模块返回、失败模块带原因。"""

    async def fake_run_structured(chat_model, *, schema, **_kwargs):  # noqa: ANN001, ANN003
        if schema is draft.AnalysisSection:
            return StructuredOutcome(parsed=schema(learning="学情"), raw_text="{}", attempts=1)
        return StructuredOutcome(parsed=None, raw_text="", attempts=2, error="结构化解析失败")

    monkeypatch.setattr(draft, "run_structured", fake_run_structured)
    sections, failures = await draft.generate_sections(object(), context="固定数据")
    assert sections == {"analysis": {"learning": "学情", "textbook": "", "content": "", "ideological": ""}}
    assert set(failures) == set(draft.MODULE_ORDER) - {"analysis"}
    assert all("结构化解析失败" in reason for reason in failures.values())
