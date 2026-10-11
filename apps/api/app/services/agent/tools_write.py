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

from langchain_core.tools import BaseTool, tool
from langgraph.types import interrupt

from app.services.agent.tools import _clip, _dump


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


def build_confirm_tools(app_state: Any) -> list[BaseTool]:
    """写确认类工具（interrupt 等教师确认后才落库）。服务缺失不注册。"""
    tools: list[BaseTool] = []

    lessons = getattr(app_state, "lesson_plan_service", None)

    if lessons is not None:
        @tool
        def apply_lesson_proposal(lesson_id: str, proposal_id: str, summary: str) -> str:
            """把 AI 教案调整建议应用到教案（写操作，需教师确认后才执行）。
            summary 是给教师看的调整摘要（改了哪些字段/环节）。"""
            decision = interrupt({
                "action": "apply_lesson_proposal",
                "lessonId": lesson_id,
                "proposalId": proposal_id,
                "summary": summary,
                "prompt": "应用以上教案调整建议？",
            })
            if not isinstance(decision, dict) or decision.get("decision") != "approve":
                return "教师未确认，未应用教案调整。"
            submission_id = decision.get("submissionId") or uuid.uuid4().hex
            lessons.apply_proposal(lesson_id, proposal_id, {
                "submissionId": submission_id,
            })
            return f"已应用教案调整（proposalId={proposal_id}）。"

        tools.append(apply_lesson_proposal)

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
        """需要教师补充选择时调用（弹窗选择卡）。need 取值：class=选班级；assessment=选学情报告来源（施测）；analysis_run=选已有学情分析运行。
        返回教师选定的 ID（如 classId/assessmentId/runId）；教师放弃时返回"未选择"。"""
        options: list[dict[str, str]] = []
        title = need
        if need == "class" and roster is not None:
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
