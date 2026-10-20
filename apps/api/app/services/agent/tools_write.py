"""Agent 写侧工具（A4 确认闸门批）：上传导入（产候选）+ 写操作确认（interrupt）。

设计红线（与"AI 只进候选，教师审核后才发布"一致）：

- **导入类工具（import_*）**：按 assetRef 从 AssetStore 读字节，调既有 ``create_import``
  建**导入草稿**——草稿本就是"候选"，不入正式库，教师在对应工作台预览/确认。因此
  导入工具**不需要** interrupt，直接返回草稿 ID 与预览摘要。
- **确认类工具（confirm_*）**：真正把候选落库的写操作，内部 ``interrupt(payload)``
  挂起等教师在界面上确认；``resume`` 收到 ``{"decision": "approve"|"reject"}`` 后
  执行或放弃。submissionId 由 confirm 请求透传，保证幂等。

学生个人信息：工具入参/出参不携带姓名/学号（与读工具同一脱敏纪律）。
"""

from __future__ import annotations

import uuid
from typing import Any

import anyio
from langchain_core.tools import BaseTool, tool
from langgraph.types import interrupt

from app.contracts.lesson_plans import ALLOWED_FIELDS
from app.services.agent.tools import _clip, _dump
from app.services.lesson_streaming.draft import (
    MODULE_LABELS,
    MODULE_ORDER,
    compose_lesson_data,
    generate_sections,
)
from app.services.lesson_streaming.service import build_context
from app.services.textbook_ingest.taxonomy import SUBJECTS


def _blob_key(asset_id: str) -> str:
    return f"blobs/{asset_id}"


def _read_upload(app_state: Any, asset_id: str) -> bytes:
    assets = getattr(app_state, "asset_store", None)
    if assets is None:
        raise RuntimeError("资产存储未装配，无法读取上传文件。")
    return assets.read(_blob_key(asset_id))


def build_import_tools(app_state: Any) -> list[BaseTool]:
    """上传导入类工具（建草稿、产候选，不需 interrupt）。服务缺失不注册。"""
    tools: list[BaseTool] = []

    papers = getattr(app_state, "paper_service", None)
    roster = getattr(app_state, "roster_service", None)
    scores = getattr(app_state, "score_service", None)
    questions = getattr(app_state, "question_bank_service", None)

    if papers is not None:
        @tool
        def import_paper(asset_id: str, file_name: str, subject_id: str, title: str | None = None) -> str:
            """把上传的 DOCX 原卷建成导入草稿（拆题为候选，不入正式库）。
            asset_id 来自随附文件；subject_id 必填（学科须已存在）。返回 paperId 供教师预览确认。"""
            data = _read_upload(app_state, asset_id)
            view = papers.create_import(
                file_name=file_name, content=data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                subject_id=subject_id, title=title,
            )
            paper = _dump(view.paper) if hasattr(view, "paper") else _dump(view)
            warnings = getattr(view, "warnings", None) or []
            out = f"原卷导入草稿已建：paperId={paper.get('paperId')}，题目数={paper.get('itemCount')}，状态={paper.get('status')}。"
            if warnings:
                out += f" 警告 {len(warnings)} 条。"
            out += " 请到施测与成绩工作台的「原卷」页预览并确认入库。"
            return _clip(out)

        tools.append(import_paper)

    if roster is not None:
        @tool
        def import_roster(asset_id: str, file_name: str, class_id: str) -> str:
            """把上传的 Excel/CSV 名单建成导入草稿（候选，不入正式库）。
            class_id 必填（班级须已存在）。返回 importId 供教师预览确认。"""
            data = _read_upload(app_state, asset_id)
            view = roster.create_roster_import(
                class_id=class_id, file_name=file_name, content=data, media_type="",
            )
            v = _dump(view)
            out = (
                f"名单导入草稿已建：importId={v.get('importId')}，状态={v.get('state')}。"
                " 请到施测与成绩工作台的「名单」页预览并确认入库。"
            )
            return _clip(out)

        tools.append(import_roster)

    if scores is not None:
        @tool
        def import_scores(asset_id: str, file_name: str, assessment_id: str) -> str:
            """把上传的 Excel 成绩表建成导入草稿（候选，不入正式库）。
            assessment_id 必填（施测须已存在）。返回 importId 供教师预览确认。"""
            data = _read_upload(app_state, asset_id)
            view = scores.create_score_import(
                assessment_id, file_name=file_name, content=data, media_type="",
            )
            v = _dump(view)
            out = (
                f"成绩导入草稿已建：importId={v.get('importId')}。"
                " 请到施测与成绩工作台预览矩阵并确认入库。"
            )
            return _clip(out)

        tools.append(import_scores)

    if questions is not None:
        @tool
        def import_questions(asset_id: str, file_name: str, subject_id: str = "", grade_id: str = "") -> str:
            """把上传的题目文件（md/txt/pdf/docx）建成题库导入草稿（拆出题目候选，不入正式库）。
            返回 importId 供教师校对确认。"""
            data = _read_upload(app_state, asset_id)
            view = questions.create_import(
                file_name=file_name, data=data, subject_id=subject_id, grade_id=grade_id,
            )
            v = _dump(view)
            out = (
                f"题库导入草稿已建：importId={v.get('importId')}，状态={v.get('state')}。"
                " 请到题库工作台的导入批校对页确认入库。"
            )
            return _clip(out)

        tools.append(import_questions)

    return tools


async def _resolve_lesson_target(app_state: Any, subject_id: str, class_id: str):
    """校验学科/班级并取班级名；返回 ``(subject, class_name, error)``。"""
    subject = next((item for item in SUBJECTS if item.id == subject_id), None)
    if subject is None:
        return None, None, "学科 id 无效：请调用 list_subjects 获取可用 id（如 math/chinese）。"
    roster = getattr(app_state, "roster_service", None)
    if roster is None:
        return subject, class_id, None
    try:
        klass = await anyio.to_thread.run_sync(roster.get_class, class_id)
    except Exception:  # noqa: BLE001 - 不存在/服务异常都归为可读提示，不中断图
        return None, None, "班级不存在：请先调用 list_classes 或 confirm_context(need=class) 获取 classId。"
    return subject, klass.name, None


async def _execute_create_lesson(
    app_state: Any,
    handle: Any,
    *,
    subject_id: str,
    subject_label: str,
    class_id: str,
    class_name: str,
    course_name: str,
    requirements: str,
    analysis_run_id: str,
    submission_id: str,
) -> str:
    """确认后的执行段：生成七模块 → 组装 → 创建第 1 版教案草稿（独立可单测）。"""
    lessons = getattr(app_state, "lesson_plan_service", None)
    if lessons is None:
        return "教案服务未装配，无法保存草稿。"
    chat_model = getattr(handle, "chat_model", None)
    if chat_model is None:
        return "当前模型配置无法生成教案（缺少 LangChain chat model）。"

    report = None
    if analysis_run_id:
        analysis = getattr(app_state, "analysis_service", None)
        if analysis is None:
            return "学情分析服务未装配，无法读取 analysis_run_id。"
        try:
            report = await anyio.to_thread.run_sync(analysis.read_ready_report, analysis_run_id)
        except Exception as exc:  # noqa: BLE001 - 报告不可读时如实返回，不写半成品
            return f"学情报告读取失败：{exc}；请换一个报告或去掉 analysis_run_id。"

    context = f"学科：{subject_label}\n班级：{class_name}\n" + build_context(
        report, [], course_name, requirements
    )
    sections, failures = await generate_sections(chat_model, context=context)
    if not sections:
        return "教案生成失败（七个模块均未返回可用内容），未写入任何数据。请稍后重试或更换模型。"

    data = compose_lesson_data(course_name=course_name, class_name=class_name, sections=sections)
    body = {
        "submissionId": submission_id,
        "subjectId": subject_id,
        "classId": class_id,
        "data": data,
        "context": None,
        "source": "manual",
    }
    try:
        result = await anyio.to_thread.run_sync(lessons.create_lesson, body)
    except Exception as exc:  # noqa: BLE001 - 业务异常（404/409/422）转成可读工具结果
        code = getattr(exc, "code", "") or type(exc).__name__
        return f"教案保存失败（{code}）：{exc}；未写入任何数据。"

    lesson_id = str(result.get("lessonPlanId") or "") if isinstance(result, dict) else ""
    revision = result.get("revision", 1) if isinstance(result, dict) else 1
    missing = "、".join(MODULE_LABELS[module] for module in MODULE_ORDER if module in failures)
    out = f"教案草稿已保存：lessonId={lesson_id}，标题《{data['title']}》，第 {revision} 版。"
    if missing:
        out += f" 未生成模块：{missing}（可在工作台补写）。"
    out += " 请在「教案工作台」→「本地教案」中打开继续编辑。"
    return _clip(out)


async def _execute_apply_lesson_proposal(
    lessons: Any, *, lesson_id: str, proposal_id: str, submission_id: str
) -> str:
    """确认后的执行段：按当前教案版本与候选 patch 组装完整 apply 请求（独立可单测）。"""
    try:
        lesson = await anyio.to_thread.run_sync(lessons.get_lesson, lesson_id)
        proposal = await anyio.to_thread.run_sync(lessons.get_proposal, lesson_id, proposal_id)
        patch = proposal.get("patch") if isinstance(proposal, dict) else None
        selected = [
            field
            for field in ALLOWED_FIELDS
            if isinstance(patch, dict) and patch.get(field) is not None
        ]
        if not selected:
            return "该建议没有可应用的字段。"
        await lessons.apply_proposal(
            lesson_id,
            proposal_id,
            {
                "submissionId": submission_id,
                "expectedRevision": lesson.get("revision"),
                "baseRevisionId": lesson.get("currentRevisionId"),
                "selectedFields": selected,
            },
        )
    except Exception as exc:  # noqa: BLE001 - 版本冲突/候选过期转成可读工具结果
        code = getattr(exc, "code", "") or type(exc).__name__
        return f"应用教案调整失败（{code}）：{exc}"
    return f"已应用教案调整（proposalId={proposal_id}，应用字段：{'、'.join(selected)}）。"


def build_confirm_tools(app_state: Any, *, handle: Any = None) -> list[BaseTool]:
    """写确认类工具（interrupt 等教师确认后才落库）。服务缺失不注册。

    ``handle`` 是本轮解析出的 LangChain 模型句柄（``AgentService.prepare`` 注入）；
    缺失时不注册 ``create_lesson_plan_draft``（读/应用类工具不受影响）。
    """
    tools: list[BaseTool] = []

    lessons = getattr(app_state, "lesson_plan_service", None)

    if lessons is not None:
        @tool
        async def apply_lesson_proposal(lesson_id: str, proposal_id: str, summary: str) -> str:
            """把 AI 教案调整建议应用到教案（写操作，需教师确认后才执行）。
            summary 是给教师看的调整摘要（改了哪些字段/环节）。"""
            decision = interrupt({
                "action": "apply_lesson_proposal",
                "kind": "confirm",
                "lessonId": lesson_id,
                "proposalId": proposal_id,
                "summary": summary,
                "prompt": "应用以上教案调整建议？",
            })
            if not isinstance(decision, dict) or decision.get("decision") != "approve":
                return "教师未确认，未应用教案调整。"
            submission_id = str(decision.get("submissionId") or uuid.uuid4().hex)
            return await _execute_apply_lesson_proposal(
                lessons, lesson_id=lesson_id, proposal_id=proposal_id, submission_id=submission_id
            )

        tools.append(apply_lesson_proposal)

        if handle is not None:
            @tool
            async def create_lesson_plan_draft(
                subject_id: str,
                class_id: str,
                course_name: str,
                requirements: str = "",
                analysis_run_id: str = "",
            ) -> str:
                """生成一份完整教案草稿并保存到本机后端（写操作，需教师确认后才执行）。
                subject_id 用 list_subjects 返回的 id（如 math）；class_id 用 list_classes 或
                confirm_context(need=class) 返回的 id；course_name 是课题（如《荷塘月色》）。
                确认后按教学分析/目标/策略/过程/练习/评价/反思七个模块生成正文并创建第 1 版教案，
                返回 lessonId。生成约需 1-3 分钟。"""
                subject, class_name, error = await _resolve_lesson_target(app_state, subject_id, class_id)
                if error:
                    return error
                title = (course_name or "").strip()
                if not title:
                    return "缺少课题名（course_name），请先向教师确认要生成哪一课。"
                decision = interrupt({
                    "action": "create_lesson_plan",
                    "kind": "confirm",
                    "subjectId": subject_id,
                    "classId": class_id,
                    "summary": (
                        f"将生成《{title[:80]}》的完整教案并保存为本机教案草稿"
                        f"（{subject.label} · {class_name}）。生成需要 1-3 分钟。"
                    ),
                    "prompt": "生成并保存这份教案草稿？",
                })
                if not isinstance(decision, dict) or decision.get("decision") != "approve":
                    return "教师未确认，未生成教案。"
                submission_id = str(decision.get("submissionId") or uuid.uuid4().hex)
                return await _execute_create_lesson(
                    app_state,
                    handle,
                    subject_id=subject_id,
                    subject_label=subject.label,
                    class_id=class_id,
                    class_name=class_name,
                    course_name=title,
                    requirements=requirements,
                    analysis_run_id=analysis_run_id,
                    submission_id=submission_id,
                )

            tools.append(create_lesson_plan_draft)

    return tools


def build_interaction_tools(app_state: Any) -> list[BaseTool]:
    """交互类工具（C1-4 关键词触发弹窗选择）：缺关键上下文时向教师发选择卡。

    Agent 判断要做学情/教案/练习但缺少班级/试卷/知识点时调用 ``confirm_context``；
    工具内部从业务服务组装候选，``interrupt(kind='select')`` 在对话框弹选择卡，
    教师选定后 resume 返回对应的业务 ID 供后续工具使用。
    """
    tools: list[BaseTool] = []

    roster = getattr(app_state, "roster_service", None)
    assessments = getattr(app_state, "assessment_service", None)
    analysis = getattr(app_state, "analysis_service", None)

    @tool
    def confirm_context(need: str) -> str:
        """需要教师补充选择时调用（弹窗选择卡）。need 取值：subject=选学科；class=选班级；
        assessment=选学情报告来源（施测）；analysis_run=选已有学情分析运行。
        返回教师选定的 ID（如 subjectId/classId/assessmentId/runId）；教师放弃时返回"未选择"。"""
        options: list[dict[str, str]] = []
        title = need
        if need == "subject":
            title = "选择学科"
            options = [
                {"label": item.label, "description": f"id={item.id}"}
                for item in SUBJECTS
            ]
        elif need == "class" and roster is not None:
            title = "选择班级"
            page = roster.list_classes(limit=50)
            options = [
                {"label": item.name or item.id, "description": f"{item.student_count} 名学生，id={item.id}"}
                for item in page.items
            ]
        elif need == "assessment" and assessments is not None:
            title = "选择施测（出学情的来源）"
            page = assessments.list_assessments(limit=50)
            options = [
                {"label": item.title or item.assessment_id, "description": f"id={item.assessment_id}，{item.paper_title}"}
                for item in page.items
            ]
        elif need == "analysis_run" and analysis is not None:
            title = "选择学情分析运行"
            page = analysis.list_runs(limit=50)
            options = [
                {"label": f"运行 {item.run_id[:8]}", "description": f"runId={item.run_id}，施测={item.assessment_id}，报告就绪={item.report_ready}"}
                for item in page.items
            ]
        else:
            return f"无法为 need={need} 组装候选（服务未装配或不支持）。"

        if not options:
            return f"当前没有任何可选的 {title} 候选；请教师先建立对应数据。"

        decision = interrupt({
            "kind": "select",
            "prompt": title,
            "options": options,
        })
        if not isinstance(decision, dict) or decision.get("decision") != "approve":
            return "教师未选择。"
        picked = decision.get("value") or ""
        # 从选项 label 反查业务 ID（description 末尾 id=xxx）
        for opt in options:
            if opt["label"] == picked:
                desc = opt.get("description", "")
                marker = "id="
                idx = desc.rfind(marker)
                if idx >= 0:
                    return f"教师已选定：{desc[idx + len(marker):].strip()}"
        return f"教师已选定：{picked}（未匹配到 ID，请用该名称继续）。"

    tools.append(confirm_context)

    return tools


__all__ = ["build_confirm_tools", "build_import_tools", "build_interaction_tools"]
