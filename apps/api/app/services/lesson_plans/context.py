"""Freeze ready report facts without substituting current scores or roster."""
from app.contracts import lesson_plans as lp
from app.core.exceptions import AppError
from app.services.knowledge_refs import KnowledgeReference, require_active_knowledge_references
from .views import validate


def invalid(field, message, code="LESSON_INVALID"):
    return AppError(message, code=code, status_code=422, details={"issues": [{"field": field, "code": code, "message": message}]})


def freeze_context(service, subject_id, class_id, selection):
    with service.catalog.read_connection() as conn:
        klass = conn.execute("SELECT name FROM classes WHERE id=? AND owner_id=?", (class_id, service.owner)).fetchone()
        if klass is None:
            raise AppError("教案或固定版本不存在。", code="NOT_FOUND", status_code=404)
        class_name = klass["name"]
    analysis = None
    if selection is not None:
        report = service.analysis.read_ready_report(selection.analysis_run_id, owner_id=service.owner)
        if hasattr(report, "model_dump"):
            report = report.model_dump(by_alias=True, mode="json")
        if report.get("runId") != selection.analysis_run_id or not report.get("reportReady"):
            raise invalid("context.analysisRunId", "须选择可读的 ready 固定报告。")
        if report.get("subjectId") != subject_id:
            raise invalid("context.analysisRunId", "固定报告与教案学科不一致。")
        points = {point["knowledgePointId"]: point for point in report["knowledgePoints"]}
        if not set(selection.selected_knowledge_point_ids) <= set(points):
            raise invalid("context.selectedKnowledgePointIds", "所选知识点须属于固定报告。")
        selected = [points[key] for key in selection.selected_knowledge_point_ids]
        rows = [row for row in report["classes"] if row["classId"] == class_id
                and row["knowledgePoint"]["knowledgePointId"] in selection.selected_knowledge_point_ids]
        by_point = {row["knowledgePoint"]["knowledgePointId"]: row for row in rows}
        if (len(rows) != len(by_point) or set(by_point) != set(selection.selected_knowledge_point_ids)
                or any(by_point[p["knowledgePointId"]]["knowledgePoint"] != p for p in selected)):
            raise invalid("context.analysisRunId", "固定报告缺少目标班级及所选固定知识点。")
        if not any(p["classId"] == class_id for p in report["participants"]):
            raise invalid("classId", "固定报告不包含目标班级。")
        first = by_point[selection.selected_knowledge_point_ids[0]]
        analysis = dict(analysisRunId=report["runId"], inputHash=report["inputHash"], scoreRevisionId=report["scoreRevisionId"],
            paperRevisionId=report["paperRevisionId"], className=first["className"], classNameNote=first["classNameNote"], knowledgePoints=selected)
    return validate(lp.LessonContextSnapshot, dict(subjectId=subject_id, classId=class_id, classNameAtSave=class_name, analysis=analysis))


def revalidate_context(service, context):
    with service.catalog.read_connection() as conn:
        if conn.execute("SELECT 1 FROM classes WHERE id=? AND owner_id=?", (context["classId"], service.owner)).fetchone() is None:
            raise AppError("教案或固定版本不存在。", code="NOT_FOUND", status_code=404)
    if context["analysis"]:
        refs = [KnowledgeReference(point["knowledgePointId"], point["knowledgeRevisionId"], point["role"])
                for point in context["analysis"]["knowledgePoints"]]
        require_active_knowledge_references(service.knowledge, refs, expected_subject_id=context["subjectId"])
