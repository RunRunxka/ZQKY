"""Freeze public fixed readers into protected facts and a separate whitelist."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass

from app.contracts.lesson_plans import AnalysisContextSnapshot, LessonContextSnapshot, LessonGenerateRequest, LessonView
from app.contracts.teaching_loop import canonical_hash
from app.core.exceptions import AppError
from app.services.knowledge_refs import require_active_knowledge_references, KnowledgeReference
from app.services.model_runtime import fingerprint_of_handle
from .common import invalid, snapshot
from .privacy import check_model_payload, personal_tokens, check_text


@dataclass(frozen=True)
class PreparedGeneration:
    frozen_input: dict
    model_snapshot: dict
    context_snapshot: dict


def content_text(content: dict) -> str:
    """Text/formula/table whitelist; never forwards origins, IDs or asset URLs."""
    rich = content.get("richContent")
    if not isinstance(rich, dict) and content.get("version") == 2:
        rich = content
    if isinstance(rich, dict):
        text = []
        def blocks(items):
            for block in items:
                kind = block.get("kind")
                if kind == "paragraph":
                    text.append(block.get("text", ""))
                elif kind == "formula":
                    text.append(block.get("latex") or block.get("plainText") or "[固定公式]")
                elif kind == "table":
                    text.extend(cell.get("text", "") for cell in block.get("cells", []))
                elif kind == "image":
                    # Binary images are not sent to the text-only model.
                    text.append("[固定题面含图片，请教师对照原题]")
        for material in rich.get("sharedMaterials", []):
            blocks(material.get("blocks", []))
        for field in ("stemBlocks", "answerBlocks", "explanationBlocks"):
            blocks(rich.get(field, []))
        for items in rich.get("optionBlocks", {}).values():
            blocks(items)
        return "\n".join(text)
    text = [content.get("stemMarkdown", "")]
    text.extend(item.get("textMarkdown", "") for item in content.get("options", []))
    answer = content.get("answer")
    if isinstance(answer, dict):
        text.append(answer.get("textMarkdown", ""))
    text.append(content.get("explanationMarkdown") or "")
    return "\n".join(text)


def _knowledge_refs(points):
    return [KnowledgeReference(x["knowledgePointId"], x["knowledgeRevisionId"], x.get("role", "primary")) for x in points]


def require_reference_set(catalog, points, subject_id):
    # The shared reader caches by point identity within one call; separate
    # duplicate IDs at distinct revisions so each historical revision is checked.
    groups = []
    seen = set()
    for ref in _knowledge_refs(points):
        identity = (ref.knowledge_point_id, ref.knowledge_revision_id)
        if identity in seen:
            continue
        seen.add(identity)
        target = next((group for group in groups if ref.knowledge_point_id not in group), None)
        if target is None:
            target = {}
            groups.append(target)
        target[ref.knowledge_point_id] = ref.knowledge_revision_id
    for group in groups:
        require_active_knowledge_references(catalog, group, expected_subject_id=subject_id)


def prepare(service, body: LessonGenerateRequest, lesson: LessonView, owner_id: str) -> PreparedGeneration:
    body = LessonGenerateRequest.model_validate(snapshot(body))
    lesson = LessonView.model_validate(snapshot(lesson))
    if body.base_revision_id != lesson.current_revision_id or body.base_server_revision != lesson.revision:
        raise AppError("生成必须基于当前已保存的固定教案版本。", code="LESSON_PROPOSAL_STALE", status_code=409)
    if body.class_id != lesson.class_id:
        raise invalid("classId", "目标班级必须与教案班级一致。", "LESSON_INVALID")
    report = snapshot(service.analysis.read_ready_report(body.analysis_run_id, owner_id=owner_id))
    if report.get("runId") != body.analysis_run_id or not report.get("reportReady"):
        raise invalid("analysisRunId", "必须选择可读的 ready 固定报告。", "LESSON_INVALID")
    if report.get("subjectId") != lesson.subject_id:
        raise invalid("analysisRunId", "固定报告与教案学科不一致。", "LESSON_INVALID")
    points = {x["knowledgePointId"]: x for x in report["knowledgePoints"]}
    if not set(body.selected_knowledge_point_ids) <= set(points):
        raise invalid("selectedKnowledgePointIds", "所选知识点必须属于该固定报告。", "LESSON_INVALID")
    selected = [points[key] for key in body.selected_knowledge_point_ids]
    target_rows = [row for row in report["classes"] if row["classId"] == body.class_id
                   and row["knowledgePoint"]["knowledgePointId"] in body.selected_knowledge_point_ids]
    rows = {row["knowledgePoint"]["knowledgePointId"]: row for row in target_rows}
    if len(rows) != len(target_rows) or set(rows) != set(body.selected_knowledge_point_ids):
        raise invalid("classId", "固定报告中缺少目标班级的完整知识点计数。", "LESSON_INVALID")
    for point in selected:
        if rows[point["knowledgePointId"]]["knowledgePoint"] != point:
            raise invalid("analysisRunId", "固定报告的班级知识点修订不一致。", "LESSON_INVALID")
    require_active_knowledge_references(service.knowledge, _knowledge_refs(selected), expected_subject_id=lesson.subject_id)
    if body.scope_snapshot.selection.subjectId != lesson.subject_id:
        raise invalid("scopeSnapshot", "教材范围与教案学科不一致。", "LESSON_INVALID")
    textbooks = [snapshot(x) for x in service.evidence.verify_selected_evidence(body.scope_snapshot, body.evidence_refs)]
    expected_refs = [snapshot(ref) for ref in body.evidence_refs]
    actual_refs = [{key: item[key] for key in expected_refs[0]} for item in textbooks]
    if actual_refs != expected_refs or any(not x["text"].strip() or x["isSuperseded"] for x in textbooks):
        raise invalid("evidenceRefs", "教材证据未按所选固定引用完整验证。", "LESSON_INVALID")
    tokens = personal_tokens(report)
    evidence = []
    for index, item in enumerate(textbooks, 1):
        evidence.append(dict(alias=f"E{index}", kind="textbook", referenceId=item["evidenceId"], title=item["title"],
                             sha256=item["normalizedTextSha256"], locator=item["locator"], text=item["text"]))
    questions, practices = [], []
    refs = list(selected)
    for index, revision_id in enumerate(body.question_revision_ids, 1):
        question = service.questions.read_revision(revision_id, owner_id=service.question_owner_id)
        if question.question_status != "confirmed" or question.subject_id != lesson.subject_id:
            raise invalid("questionRevisionIds", "必须选择同学科未归档的正式固定题。", "LESSON_INVALID")
        links = [dict(knowledgePointId=x["knowledge_point_id"], knowledgeRevisionId=x["knowledge_revision_id"],
                      name=x["name_snapshot"], role=x["role"]) for x in question.knowledge_links]
        if not set(body.selected_knowledge_point_ids) & {x["knowledgePointId"] for x in links}:
            raise invalid("questionRevisionIds", "固定题必须关联所选报告知识点。", "LESSON_INVALID")
        refs.extend(links)
        questions.append(snapshot(asdict(question)))
        evidence.append(dict(alias=f"Q{index}", kind="question", referenceId=revision_id,
                             title="固定课堂题", sha256=question.content_hash,
                             locator={"questionRevisionId": revision_id}, text=content_text(question.content)))
    for index, revision_id in enumerate(body.practice_revision_ids, 1):
        practice = snapshot(service.practices.read_reviewed_revision(revision_id, owner_id=owner_id))
        if practice["practiceRevisionId"] != revision_id or practice["state"] != "reviewed" or practice["subjectId"] != lesson.subject_id:
            raise invalid("practiceRevisionIds", "必须选择同学科已审核固定练习。", "LESSON_INVALID")
        if not set(body.selected_knowledge_point_ids) & {x["knowledgePointId"] for x in practice["targetKnowledgePoints"]}:
            raise invalid("practiceRevisionIds", "固定练习必须覆盖所选报告知识点。", "LESSON_INVALID")
        refs.extend(practice["targetKnowledgePoints"])
        for item in practice["items"]:
            refs.extend(item["knowledgePoints"])
        practices.append(practice)
        text = "\n".join(content_text(item["content"]) for item in practice["items"])
        evidence.append(dict(alias=f"R{index}", kind="practice", referenceId=revision_id, title=practice["title"],
                             sha256=canonical_hash(practice), locator={"practiceRevisionId": revision_id}, text=text))
    # Every new source reference, not just the selected report KPs, is checked.
    require_reference_set(service.knowledge, refs, lesson.subject_id)
    base_data = snapshot(lesson.current_revision.data)
    process_map, model_process = {}, []
    for index, item in enumerate(base_data["process"], 1):
        alias = f"P{index}"
        try:
            check_text(item["id"], tokens)
            safe = bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item["id"]))
        except AppError:
            safe = False
        stable = item["id"] if safe else "lp_" + hashlib.sha256(
            (lesson.current_revision_id + "\0" + item["id"]).encode("utf-8")).hexdigest()[:32]
        process_map[alias] = stable
        model_process.append({**item, "id": alias})
    count_fields = ("selectedCount", "validCount", "needsCount", "incompleteCount", "noEvidenceCount", "fullCreditCount", "numerator", "denominator")
    model_points = []
    knowledge_map = {}
    for index, point in enumerate(selected, 1):
        alias = f"K{index}"
        knowledge_map[alias] = point
        row = rows[point["knowledgePointId"]]
        counts = {key: row[key] for key in count_fields}
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise invalid("analysisRunId", "固定报告的班级计数非法。", "LESSON_INVALID")
        model_points.append(dict(alias=alias, name=point["name"], counts=counts))
    model_payload = dict(lesson={**{key: base_data[key] for key in ("coreCompetencies", "keyPoints", "teachingDesign", "exercises")},
                                 "process": model_process},
                         classSummary={"knowledgePoints": model_points}, requirements=body.requirements,
                         durationMinutes=body.duration_minutes,
                         evidence=[{key: item[key] for key in ("alias", "kind", "title", "text")} for item in evidence],
                         processAliases=list(process_map), newProcessAliases=[f"new:N{n}" for n in range(1, 13)])
    check_model_payload(model_payload, tokens)
    handle = service.model_resolver(body.model_profile_id)
    model_snapshot = {"profileId": body.model_profile_id, "fingerprint": fingerprint_of_handle(handle)}
    if handle.profile_id != body.model_profile_id:
        raise invalid("modelProfileId", "模型解析结果与明确选择的 profile 不一致。", "LESSON_INVALID")
    with service.catalog.read_connection() as conn:
        class_row = conn.execute("SELECT name FROM classes WHERE id=? AND owner_id=?", (body.class_id, owner_id)).fetchone()
        if class_row is None:
            raise AppError("对象不存在。", code="NOT_FOUND", status_code=404)
    first_row = target_rows[0]
    analysis_context = AnalysisContextSnapshot(analysisRunId=body.analysis_run_id, inputHash=report["inputHash"],
        scoreRevisionId=report["scoreRevisionId"], paperRevisionId=report["paperRevisionId"],
        className=first_row.get("className"), classNameNote=first_row.get("classNameNote", "该成绩未记录班名"), knowledgePoints=selected)
    context = snapshot(LessonContextSnapshot(subjectId=lesson.subject_id, classId=body.class_id,
                                           classNameAtSave=class_row["name"], analysis=analysis_context))
    frozen = dict(contractVersion=1, lessonPlanId=lesson.lesson_plan_id, ownerId=owner_id, subjectId=lesson.subject_id,
                  classId=body.class_id, baseRevisionId=body.base_revision_id, baseServerRevision=body.base_server_revision,
                  analysisRunId=body.analysis_run_id, contextSnapshot=context, scopeSnapshot=snapshot(body.scope_snapshot),
                  evidenceRefs=expected_refs, durationMinutes=body.duration_minutes, requirements=body.requirements,
                  modelProfileId=body.model_profile_id, modelPayload=model_payload,
                  source=dict(report=report, selectedKnowledgePoints=selected, textbooks=textbooks, questions=questions,
                              practices=practices, referenceKnowledge=refs, evidence=evidence,
                              knowledgeAliases=knowledge_map, processAliases=process_map, personalTokens=tokens))
    # Validate the final message budget and all three provider body semantics now.
    service.build_request(frozen, handle)
    return PreparedGeneration(snapshot(frozen), snapshot(model_snapshot), snapshot(context))
