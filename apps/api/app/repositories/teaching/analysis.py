"""Analysis SQL primitives. Transactions and business rules belong to service/engine."""
import json
import uuid
from app.core.exceptions import AppError
from app.core.sqlite import now_iso


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load(value):
    try:
        result = json.loads(value)
        if not isinstance(result, dict):
            raise ValueError("object required")
        return result
    except (TypeError, ValueError) as exc:
        raise AppError("分析快照损坏。", code="ANALYSIS_ROW_CORRUPT", status_code=500) from exc


class AnalysisRepository:
    def require_in(self, conn, run_id, owner_id):
        row = conn.execute("SELECT * FROM analysis_runs WHERE id=? AND owner_id=?", (run_id, owner_id)).fetchone()
        if row is None:
            raise AppError("分析报告不存在。", code="ANALYSIS_NOT_FOUND", status_code=404)
        return row

    def create_in(self, conn, *, run_id, owner_id, input_hash, facts, job_id):
        conn.execute("INSERT INTO analysis_runs(id,owner_id,assessment_id,score_revision_id,paper_revision_id,"
                     "subject_id,rule_code,input_hash,input_json,job_id,selected_count,leaf_count,knowledge_count,class_count,created_at) "
                     "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (run_id, owner_id, facts["assessmentId"], facts["scoreRevisionId"], facts["paperRevisionId"],
                      facts["subjectId"], facts["ruleCode"], input_hash, dump(facts), job_id,
                      len(facts["participants"]), len(facts["items"]), len(facts["knowledgePoints"]),
                      len({p["classId"] for p in facts["participants"]}), now_iso()))

    def publish_in(self, conn, run_id, facts, result):
        conn.executemany("INSERT INTO analysis_participants(run_id,participant_id,student_id,class_id,snapshot_json) VALUES(?,?,?,?,?)",
                         [(run_id, p["participantId"], p["studentId"], p["classId"], dump(p)) for p in facts["participants"]])
        conn.executemany("INSERT INTO analysis_item_snapshots(run_id,item_id,paper_revision_id,snapshot_json) VALUES(?,?,?,?)",
                         [(run_id, i["itemId"], facts["paperRevisionId"], dump(i)) for i in facts["items"]])
        conn.executemany("INSERT INTO analysis_student_results(run_id,participant_id,knowledge_point_id,payload_json) VALUES(?,?,?,?)",
                         [(run_id, r["participant"]["participantId"], r["knowledgePoint"]["knowledgePointId"], dump(r)) for r in result["students"]])
        conn.executemany("INSERT INTO analysis_class_results(run_id,class_id,knowledge_point_id,payload_json) VALUES(?,?,?,?)",
                         [(run_id, r["classId"], r["knowledgePoint"]["knowledgePointId"], dump(r)) for r in result["classes"]])
        conn.executemany("INSERT INTO analysis_evidence(id,run_id,participant_id,item_id,status,score_units) VALUES(?,?,?,?,?,?)",
                         [(uuid.uuid4().hex, run_id, c["participantId"], c["itemId"], c["status"], c["scoreUnits"]) for c in facts["cells"]])
        conn.execute("UPDATE analysis_runs SET report_ready=1,ready_at=? WHERE id=? AND report_ready=0", (now_iso(), run_id))
