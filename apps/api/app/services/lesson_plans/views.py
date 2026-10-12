"""Validated public views of owned immutable SQL rows."""
from pydantic import ValidationError
from app.contracts import lesson_plans as lp
from app.core.exceptions import AppError
from app.repositories.teaching.lesson_plans import load


def validate(kind, value):
    try:
        return kind.model_validate(value).model_dump(by_alias=True, mode="json")
    except (ValidationError, TypeError, ValueError) as exc:
        raise AppError("固定教案记录损坏，请停止覆盖。", code="LESSON_DATA_CORRUPT", status_code=500) from exc


def revision_view(row):
    return validate(lp.LessonRevisionView, dict(
        lessonPlanId=row["lesson_plan_id"], revisionId=row["id"], version=row["version"], data=load(row["data_json"]),
        contentHash=row["content_hash"], source=row["source"], contextSnapshot=load(row["context_snapshot_json"]),
        analysisRunId=row["analysis_run_id"], acceptedProposalId=row["accepted_proposal_id"],
        importEnvelope=load(row["import_envelope_json"]) if row["import_envelope_json"] is not None else None,
        selectedFields=load(row["selected_fields_json"]), processMetadata=load(row["process_metadata_json"]),
        reviewState=row["review_state"], createdAt=row["created_at"]))


def lesson_view(repo, conn, lesson_id, owner_id):
    doc = repo.document(conn, lesson_id, owner_id)
    return validate(lp.LessonView, dict(lessonPlanId=lesson_id, subjectId=doc["subject_id"], classId=doc["class_id"],
        revision=doc["revision"], currentRevisionId=doc["current_revision_id"],
        currentRevision=revision_view(repo.revision(conn, lesson_id, doc["current_revision_id"], owner_id))))


def proposal_view(repo, conn, lesson_id, proposal_id, owner_id):
    doc = repo.document(conn, lesson_id, owner_id)
    row = repo.proposal(conn, lesson_id, proposal_id, owner_id)
    decision = repo.decision(conn, lesson_id, proposal_id, owner_id)
    state = decision["state"] if decision else (
        "pending" if doc["current_revision_id"] == row["base_revision_id"] and doc["revision"] == row["base_server_revision"] else "stale")
    payload = load(row["payload_json"])
    if not isinstance(payload, dict) or set(payload) != {"patch", "budget", "evidence", "generationSource"}:
        raise AppError("固定建议记录损坏。", code="LESSON_DATA_CORRUPT", status_code=500)
    return validate(lp.LessonProposalView, dict(lessonPlanId=lesson_id, proposalId=proposal_id, jobId=row["job_id"],
        baseRevisionId=row["base_revision_id"], baseServerRevision=row["base_server_revision"], inputHash=row["input_hash"],
        modelFingerprint=row["model_fingerprint"], state=state, **payload,
        selectedFields=load(decision["selected_fields_json"]) if decision else [],
        acceptedRevisionId=decision["accepted_revision_id"] if decision else None,
        createdAt=row["created_at"], decidedAt=decision["created_at"] if decision else None))
