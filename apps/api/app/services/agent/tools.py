"""Agent 工具表（A3 工具扩展批）：核心闭环只读工具。

红线落地（PROJECT_GUIDE §1 / AGENT_SYSTEM_PROMPT）：
- 只读工具自动执行；写类/生成类工具在 A4 经确认闸门（interrupt）后才落库。
- **学生姓名、学号、人员 ID 不进模型**：名单/施测/成绩/学情工具只返回**匿名计数与
  业务 ID**（classId、assessmentId、participantId、knowledgePointId 等），剥掉 name/student_no。
  教师要看具体学生，应去对应工作台，而不是让模型复述个人信息。
- 教材/题目证据只用工具返回的固定数据；工具内部不触网（除既有 RAG/服务自身行为）。

工具是闭包，捕获 app.state 上已装配的只读服务；服务缺失时不注册该工具
（Agent 会如实说明不可用，而不是返回空结果冒充成功）。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.tools import BaseTool, tool

#: 单工具返回给模型的文本预算（防超长把上下文撑爆）；超出截断并标注。
_MAX_TOOL_OUTPUT_CHARS = 6000


def _clip(text: str) -> str:
    if len(text) <= _MAX_TOOL_OUTPUT_CHARS:
        return text
    return text[:_MAX_TOOL_OUTPUT_CHARS] + f"\n…（已截断，共 {len(text)} 字符，仅展示前 {_MAX_TOOL_OUTPUT_CHARS}）"


def _dump(item: Any) -> dict:
    """pydantic 模型 → dict（by_alias camelCase）；其余原样。"""
    if hasattr(item, "model_dump"):
        return item.model_dump(by_alias=True, mode="json")
    return item


#: 学生个人身份字段（剥掉后不进模型）。**不含通用 ``name``**：班级名/知识点名/原卷标题等
#: 是教师必需的合法业务信息；学生姓名只会出现在学生/参与者语境的 ``nameSnapshot`` 等
#: 专用字段里（名单工具本身只返回计数，不列出学生 ``name``）。
_PERSON_FIELDS = frozenset({
    "studentNo", "student_no", "studentNoSnapshot", "nameSnapshot",
    "studentName", "parentName", "phone", "idCard",
})


def _strip_person(fields: dict) -> dict:
    """递归剥掉学生个人身份字段（学号/学生姓名快照），保留业务 ID、计数与班级名等。"""
    out: dict = {}
    for key, value in fields.items():
        if key in _PERSON_FIELDS:
            continue
        if isinstance(value, dict):
            out[key] = _strip_person(value)
        elif isinstance(value, list):
            out[key] = [_strip_person(v) if isinstance(v, dict) else v for v in value]
        else:
            out[key] = value
    return out


def _page_summary(items: list[dict], total: int, *, offset: int, limit: int, noun: str) -> str:
    head = f"{noun}：共 {total} 条（本页 offset={offset} limit={limit}，返回 {len(items)} 条）。"
    if not items:
        return head
    body = "\n".join(f"- {_compact(i)}" for i in items)
    return _clip(head + "\n" + body)


def _compact(item: dict) -> str:
    """把单条视图压成一行要点（取关键字段），避免整 JSON 灌进上下文。"""
    keys = (
        "id", "classId", "code", "title", "paperId", "assessmentId", "runId", "lessonPlanId",
        "practiceSetId", "knowledgePointId", "questionId", "name", "gradeId", "subjectId",
        "status", "state", "revision", "studentCount", "itemCount", "heldOn", "reportReady",
        "needsCount", "validCount", "createdAt", "total", "count", "coverage",
    )
    parts = [f"{k}={item[k]}" for k in keys if k in item and item[k] is not None]
    return "，".join(parts) if parts else str(item)[:200]


def build_read_tools(app_state: Any) -> list[BaseTool]:
    """按 app.state 装配核心闭环读工具；服务缺失的工具不注册。"""
    tools: list[BaseTool] = []

    roster = getattr(app_state, "roster_service", None)
    papers = getattr(app_state, "paper_service", None)
    assessments = getattr(app_state, "assessment_service", None)
    scores = getattr(app_state, "score_service", None)
    analysis = getattr(app_state, "analysis_service", None)
    practices = getattr(app_state, "practice_service", None)
    lessons = getattr(app_state, "lesson_plan_service", None)
    knowledge = getattr(app_state, "knowledge_service", None)
    questions = getattr(app_state, "question_bank_service", None)
    textbook_search = getattr(app_state, "textbook_search", None)

    @tool
    def list_capabilities() -> str:
        """列出本 Agent 已装配的教学闭环服务，帮助判断当前能做什么。"""
        assembled = [label for svc, label in (
            (textbook_search, "教材检索"), (roster, "名单/班级"), (papers, "原卷"),
            (assessments, "施测"), (scores, "成绩"), (analysis, "学情分析"),
            (practices, "针对练习"), (lessons, "教案"), (knowledge, "知识点库"),
            (questions, "题库"),
        ) if svc is not None]
        if not assembled:
            return "当前未装配任何教学闭环服务。"
        return "已装配的教学闭环服务：" + "、".join(assembled) + "。"

    tools.append(list_capabilities)

    if textbook_search is not None:

        @tool
        async def search_textbooks(
            query: str,
            limit: int = 4,
            subject_id: str | None = None,
        ) -> str:
            """按自然语言问题检索教材原文（当前为高中数学·人教A版），返回章节路径与原文片段。回答"教材/课本/书上怎么说"这类需要教材依据的问题时使用；不要编造教材内容。"""
            try:
                hits = await asyncio.to_thread(
                    textbook_search.search,
                    query,
                    limit=max(1, min(int(limit), 10)),
                    subject_id=subject_id,
                )
            except Exception as exc:  # 未就绪/服务异常：如实报告，不冒充成功
                return _clip(f"教材检索当前不可用：{exc}")
            if not hits:
                return "教材中没有检索到相关内容（可能是该内容不在已入库教材中，或换一种说法再试）。"
            lines = []
            for index, hit in enumerate(hits, start=1):
                path = " / ".join(hit.chapter_path) if hit.chapter_path else "（无章节路径）"
                lines.append(
                    f"{index}. 《{hit.document_title}》（{hit.edition_label}·{hit.subject_label}）"
                    f"{path}｜原文：{hit.excerpt}"
                )
            header = f"教材检索结果：共 {len(hits)} 条命中。"
            return _clip(header + "\n" + "\n".join(lines))

        tools.append(search_textbooks)

    if knowledge is not None:
        @tool
        def list_knowledge_points(subject_id: str | None = None, query: str | None = None, limit: int = 30) -> str:
            """列出独立知识点库的知识点（可按学科/关键字筛选）。返回知识点 ID、名称、编码、年级。"""
            result = knowledge.list_points(subject_id=subject_id, q=query, limit=min(limit, 50))
            items = [_dump(i) for i in result.items]
            return _page_summary(items, result.total, offset=result.offset, limit=result.limit, noun="知识点")

        @tool
        def get_knowledge_point(knowledge_point_id: str) -> str:
            """取单个知识点详情（名称、编码、描述、年级、别名）。"""
            point = _dump(knowledge.get_point(knowledge_point_id))
            return _clip(str({k: point.get(k) for k in ("id", "code", "name", "description", "gradeIds", "aliases", "subjectId")}))

        tools.extend([list_knowledge_points, get_knowledge_point])

    if roster is not None:
        @tool
        def list_classes(status: str | None = None, limit: int = 30) -> str:
            """列出班级（ID、名称、年级、学生数）。不返回任何学生个人信息。"""
            result = roster.list_classes(status=status, limit=min(limit, 50))
            items = [_strip_person(_dump(i)) for i in result.items]
            return _page_summary(items, result.total, offset=result.offset, limit=result.limit, noun="班级")

        @tool
        def get_class_student_count(class_id: str) -> str:
            """取某班学生人数（匿名计数）。不返回姓名或学号。"""
            students = roster.list_class_students(class_id)
            return f"班级 {class_id} 共有 {students.total} 名学生。"

        tools.extend([list_classes, get_class_student_count])

    if papers is not None:
        @tool
        def list_papers(subject_id: str | None = None, query: str | None = None, limit: int = 30) -> str:
            """列出原卷（ID、标题、题目数、总分、状态）。"""
            result = papers.list_papers(subject_id=subject_id, q=query, limit=min(limit, 50))
            items = [_dump(i) for i in result.items]
            return _page_summary(items, result.total, offset=result.offset, limit=result.limit, noun="原卷")

        tools.append(list_papers)

    if assessments is not None:
        @tool
        def list_assessments(class_id: str | None = None, subject_id: str | None = None, limit: int = 30) -> str:
            """列出施测（ID、标题、原卷、日期、参考人数、状态）。可按班级/学科筛选。"""
            result = assessments.list_assessments(class_id=class_id, subject_id=subject_id, limit=min(limit, 50))
            items = [_dump(i) for i in result.items]
            return _page_summary(items, result.total, offset=result.offset, limit=result.limit, noun="施测")

        tools.append(list_assessments)

    if analysis is not None:
        @tool
        def list_analysis_runs(assessment_id: str | None = None, limit: int = 20) -> str:
            """列出学情分析运行（ID、关联施测、规则、报告是否就绪）。可按施测筛选。"""
            result = analysis.list_runs(assessment_id=assessment_id, limit=min(limit, 50))
            items = [_dump(i) for i in result.items]
            return _page_summary(items, result.total, offset=result.offset, limit=result.limit, noun="学情分析运行")

        @tool
        def get_needs_consolidation(run_id: str) -> str:
            """取某次学情分析的"需巩固知识点"（班级维度）：各知识点的需巩固人数与有效人数。"""
            rows = analysis.list_report_rows(run_id, "classes", limit=200)
            lines = []
            for row in rows.items:
                r = _dump(row)
                kp = r.get("knowledgePoint") or {}
                needs = r.get("needsCount", 0)
                valid = r.get("validCount", 0)
                if needs:
                    lines.append(f"- {kp.get('name', kp.get('knowledgePointId'))}：需巩固 {needs}/{valid} 人")
            if not lines:
                return "本次学情分析没有需巩固的知识点。"
            return _clip(f"需巩固知识点（共 {len(lines)} 个）：\n" + "\n".join(lines))

        tools.extend([list_analysis_runs, get_needs_consolidation])

    if practices is not None:
        @tool
        def list_practice_sets(analysis_run_id: str | None = None, limit: int = 20) -> str:
            """列出针对练习集（ID、标题、目标知识点、状态）。可按学情分析运行筛选。"""
            result = practices.list_practices(analysis_run_id=analysis_run_id, limit=min(limit, 50))
            items = [_dump(i) for i in result.items]
            return _page_summary(items, result.total, offset=result.offset, limit=result.limit, noun="针对练习集")

        tools.append(list_practice_sets)

    if lessons is not None:
        @tool
        def list_lesson_plans(subject_id: str | None = None, class_id: str | None = None, limit: int = 20) -> str:
            """列出教案（ID、标题、学科、关联学情分析、最近更新时间）。"""
            result = lessons.list_lessons(subject_id=subject_id, class_id=class_id, limit=min(limit, 50))
            items = [_dump(i) for i in result["items"]] if isinstance(result, dict) else [_dump(i) for i in result.items]
            total = result["total"] if isinstance(result, dict) else result.total
            return _page_summary(items, total, offset=0, limit=limit, noun="教案")

        tools.append(list_lesson_plans)

    if questions is not None:
        @tool
        def list_questions(knowledge_point_id: str | None = None, subject_id: str | None = None, limit: int = 20) -> str:
            """列出题库题目（ID、题干预览、题型、难度、知识点标签）。可按知识点/学科筛选。"""
            result = questions.list_questions(
                knowledge_point_id=knowledge_point_id, subject_id=subject_id, limit=min(limit, 50)
            )
            items = [_dump(i) for i in result.questions]
            return _page_summary(items, result.total, offset=result.offset, limit=result.limit, noun="题库题目")

        tools.append(list_questions)

    return tools


__all__ = ["build_read_tools"]
