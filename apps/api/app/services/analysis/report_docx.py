"""学情分析报告 → DOCX 渲染（R6 报告导出）。

内容结构（任务卡冻结的"五项指标数据表"口径）：

1. 标题「学情分析报告」；
2. 概览段：班级（名称优先读路径已补）/ 试卷标题 / 创建时间；
3. 小题得分率表（item-stats 口径：题号 / 满分 / 有效作答数 / 得分率；
   无有效作答显示「无有效作答」，不补 0）；
4. 热力图口径表（学生 × 知识点矩阵摘要：行 = 脱敏代称，列 = 知识点名，
   单元 = 百分比或「尚无」——``scoreRate`` 为 null 时不显示 0）；
5. 知识点排行（knowledge-stats：名次 / 知识点 / 路径 / 得分率 / 小题数，降序）；
6. 分数段分布（低 <60% / 中 60–85% / 高 ≥85%，学生数）；
7. 教师备注（``analysis_teacher_notes``，教师手动「存为备注」的 AI 评价正文随此处呈现；
   未生成过评价则该段缺席，不伪造正文）。

渲染纪律与 ``services/rich_content/renderer_docx`` 一致：每次调用新建 ``Document()``；
失败如实抛错，不返回"看起来成功"的空文档。本模块只做**展示**渲染：数字全部来自
服务层已算好的冻结契约视图，不在这里重算统计口径。
"""

from __future__ import annotations

import io
from typing import Any

__all__ = ["build_report_document"]


def _fmt_rate(rate: float | None) -> str:
    """0–1 得分率 → 百分比文本（两位小数）；None →「尚无」（不补 0）。"""
    if rate is None:
        return "尚无"
    return f"{rate * 100:.1f}%"


def _fmt_units(units: int) -> str:
    """``scoreUnits``（分 ×100）→ 展示分值（最多两位小数）。"""
    if units % 100 == 0:
        return str(units // 100)
    return f"{units / 100:.2f}".rstrip("0").rstrip(".")


def _add_table(document: Any, headers: list[str], rows: list[list[str]]) -> None:
    table = document.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    for column, text in enumerate(headers):
        cell = table.rows[0].cells[column]
        cell.text = text
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for row_index, row in enumerate(rows, start=1):
        for column, text in enumerate(row):
            if column < len(headers):
                table.rows[row_index].cells[column].text = str(text)


def build_report_document(
    *,
    report: dict,
    knowledge_stats: Any,
    student_knowledge: Any,
    distribution: Any,
    item_stats: list[Any],
    notes: list[dict],
) -> bytes:
    """把已读取的报告与聚合视图渲染成 ``.docx`` 字节。

    全部入参是服务层算好的契约视图（dict / pydantic 模型）；本函数只做展示转换，
    不重算口径、不补造数据。返回的字节可直接写入受管 blob（zip 魔数 ``PK``）。
    """
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - 依赖缺失时明确失败
        from app.core.exceptions import AppError

        raise AppError(
            "DOCX 渲染依赖 python-docx 未安装。",
            code="DOCUMENT_PARSER_UNAVAILABLE",
            status_code=500,
        ) from exc

    document = Document()
    document.add_heading("学情分析报告", level=1)

    # 概览：班级 / 试卷 / 时间
    class_names = sorted({
        participant.get("className")
        for participant in report.get("participants", [])
        if isinstance(participant, dict) and isinstance(participant.get("className"), str) and participant.get("className")
    })
    snapshot = report.get("selectionSnapshot") or {}
    overview = document.add_paragraph()
    overview.add_run(f"班级：{('、'.join(class_names)) or '未记录班级'}　　试卷：{report.get('paperTitle') or '（未记录标题）'}")
    created = str(report.get("createdAt") or "").strip()
    if created:
        overview.add_run(f"　　报告时间：{created}")
    document.add_paragraph(
        f"参测：{snapshot.get('participantCount', '?')} 人次 / {snapshot.get('uniqueStudentCount', '?')} 名学生"
        f"　　计分小题：{snapshot.get('leafCount', '?')} 个"
        "　　（空白/缺考/免考一律不补 0，口径见各项表格）"
    )

    # 1) 小题得分率表
    document.add_heading("一、小题得分率", level=2)
    if item_stats:
        _add_table(
            document,
            ["题号", "满分", "有效作答", "得分率"],
            [
                [
                    item.item_path,
                    _fmt_units(item.max_score_units),
                    str(item.recorded_count),
                    _fmt_rate(item.score_rate) if item.score_rate is not None else "无有效作答",
                ]
                for item in item_stats
            ],
        )
    else:
        document.add_paragraph("无计分小题数据。")

    # 2) 热力图口径表（学生 × 知识点矩阵摘要；label 是脱敏代称）
    document.add_heading("二、学生 × 知识点（热力图口径）", level=2)
    knowledge_points = list(getattr(student_knowledge, "knowledge_points", []) or [])
    students = list(getattr(student_knowledge, "students", []) or [])
    if knowledge_points and students:
        headers = ["学生"] + [kp.name for kp in knowledge_points]
        rows = []
        for row in students:
            cell_by_kp = {cell.knowledge_point_id: cell for cell in row.cells}
            rows.append(
                [row.label]
                + [
                    _fmt_rate(cell_by_kp[kp.knowledge_point_id].score_rate)
                    if kp.knowledge_point_id in cell_by_kp
                    else "—"
                    for kp in knowledge_points
                ]
            )
        _add_table(document, headers, rows)
        document.add_paragraph("注：单元为该生在该知识点上的得分率；「尚无」= 无有效作答依据（不补 0）。")
    else:
        document.add_paragraph("无可用矩阵数据（报告未含 primary 知识点链接或无人次）。")

    # 3) 知识点排行
    document.add_heading("三、知识点得分率排行", level=2)
    stat_items = list(getattr(knowledge_stats, "items", []) or [])
    if stat_items:
        _add_table(
            document,
            ["名次", "知识点", "路径", "得分率", "小题数"],
            [
                [
                    str(index + 1),
                    item.name,
                    item.path or "（未分类）",
                    _fmt_rate(item.score_rate),
                    str(item.question_count),
                ]
                for index, item in enumerate(stat_items)
            ],
        )
        document.add_paragraph(
            "注：按小题得分率聚合到知识点（primary 链接，满分加权）；未挂 primary 知识点"
            "的小题不计入，无有效作答的小题不参与该知识点的加权平均。"
        )
    else:
        document.add_paragraph("无知识点聚合数据。")

    # 4) 分数段分布
    document.add_heading("四、分数段分布（学生级得分率）", level=2)
    buckets = list(getattr(distribution, "buckets", []) or [])
    if buckets:
        _add_table(
            document,
            ["分数段", "学生数"],
            [[bucket.label, str(bucket.count)] for bucket in buckets],
        )
        document.add_paragraph(
            "注：学生级得分率 = 该生全部计分小题的得分合计 / 满分合计（只有 recorded 计入）；"
            "无任何有效作答的学生不进任何分档。"
        )
    else:
        document.add_paragraph("无分布数据。")

    # 5) 教师备注（含教师手动保存的 AI 评价正文）
    if notes:
        document.add_heading("五、教师备注", level=2)
        for note in notes:
            created = str(note.get("createdAt") or "").strip()
            prefix = f"{created}　" if created else ""
            paragraph = document.add_paragraph()
            paragraph.add_run(prefix + str(note.get("note") or "")).italic = False

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
