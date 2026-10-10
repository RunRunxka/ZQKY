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

    def count_references_in(self, conn, run_id):
        """该报告在下游表的引用计数（彻底删除守卫的数据来源）。

        ``practiceSets`` = ``practice_sets.analysis_run_id`` 引用数；
        ``lessonReferences`` = 教案侧三处 ``analysis_run_id`` 引用之和
        （``lesson_plan_revisions`` + ``lesson_generation_inputs`` + ``lesson_ai_proposals``，
        均经 ``(analysis_run_id, owner_id)`` 复合外键指向本报告）。
        """
        return {
            "practiceSets": int(conn.execute(
                "SELECT count(*) FROM practice_sets WHERE analysis_run_id=?", (run_id,)).fetchone()[0]),
            "lessonReferences": int(
                conn.execute("SELECT count(*) FROM lesson_plan_revisions WHERE analysis_run_id=?", (run_id,)).fetchone()[0]
                + conn.execute("SELECT count(*) FROM lesson_generation_inputs WHERE analysis_run_id=?", (run_id,)).fetchone()[0]
                + conn.execute("SELECT count(*) FROM lesson_ai_proposals WHERE analysis_run_id=?", (run_id,)).fetchone()[0]),
        }

    def delete_run_in(self, conn, run_id, owner_id):
        """彻底删除报告自身及其冻结子表行（前置：调用方已通过引用守卫）。

        守卫覆盖下游引用：练习引用（``practice_sets.analysis_run_id``）与教案引用
        （修订/生成输入/AI 候选三处）；报告自身的六张冻结子表随报告一并删除，
        ``workflow_jobs`` 任务行保留不动（任务历史不属于报告内容）。

        FK 图谱（b4 0008/0009 与 0010 迁移核实）：六张子表
        （``analysis_participants``/``analysis_item_snapshots``/``analysis_student_results``/
        ``analysis_class_results``/``analysis_evidence``/``analysis_teacher_notes``）只引用
        本报告与向外引用；下游仅 ``practice_sets`` 与教案三表（守卫已挡）。报告行删除后
        无悬挂引用。

        删除顺序（子行 → 身份行）：``analysis_evidence`` → ``analysis_student_results``
        → ``analysis_teacher_notes`` → ``analysis_class_results`` →
        ``analysis_item_snapshots`` → ``analysis_participants`` → ``analysis_runs``。

        ``analysis_no_delete``、五个子表 freeze 触发器的 delete 版与
        ``immutable_analysis_teacher_notes_delete`` 是固定历史的兜底；受守卫的彻底删除
        是经守卫的受控行为，与教案/知识点仓储同一先例：同一写事务内临时摘除触发器
        → 删除 → 按登记声明**逐字**恢复（DDL 可事务化，任一步失败整体回滚，触发器随
        事务恢复；BEGIN IMMEDIATE 下无并发写者可见窗口）。触发器文本与
        ``app/core/migrations/b4.py`` 0008 登记声明逐字一致（0011 只升级了 UPDATE 版的
        ``analysis_inputs_fixed``，全部 DELETE 触发器未被重写），不改登记 SQL。
        行不存在/非本人 → 404，不静默成功。
        """
        self.require_in(conn, run_id, owner_id)
        delete_triggers = (
            ("analysis_no_delete",
             "CREATE TRIGGER analysis_no_delete BEFORE DELETE ON analysis_runs BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
            ("freeze_analysis_participants_delete",
             "CREATE TRIGGER freeze_analysis_participants_delete BEFORE DELETE ON analysis_participants WHEN (SELECT report_ready FROM analysis_runs WHERE id=OLD.run_id)=1 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
            ("freeze_analysis_item_snapshots_delete",
             "CREATE TRIGGER freeze_analysis_item_snapshots_delete BEFORE DELETE ON analysis_item_snapshots WHEN (SELECT report_ready FROM analysis_runs WHERE id=OLD.run_id)=1 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
            ("freeze_analysis_student_results_delete",
             "CREATE TRIGGER freeze_analysis_student_results_delete BEFORE DELETE ON analysis_student_results WHEN (SELECT report_ready FROM analysis_runs WHERE id=OLD.run_id)=1 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
            ("freeze_analysis_class_results_delete",
             "CREATE TRIGGER freeze_analysis_class_results_delete BEFORE DELETE ON analysis_class_results WHEN (SELECT report_ready FROM analysis_runs WHERE id=OLD.run_id)=1 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
            ("freeze_analysis_evidence_delete",
             "CREATE TRIGGER freeze_analysis_evidence_delete BEFORE DELETE ON analysis_evidence WHEN (SELECT report_ready FROM analysis_runs WHERE id=OLD.run_id)=1 BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
            ("immutable_analysis_teacher_notes_delete",
             "CREATE TRIGGER immutable_analysis_teacher_notes_delete BEFORE DELETE ON analysis_teacher_notes BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
        )
        for name, _ in delete_triggers:
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        try:
            conn.execute("DELETE FROM analysis_evidence WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM analysis_student_results WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM analysis_teacher_notes WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM analysis_class_results WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM analysis_item_snapshots WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM analysis_participants WHERE run_id=?", (run_id,))
            deleted = conn.execute("DELETE FROM analysis_runs WHERE id=? AND owner_id=?", (run_id, owner_id))
            if deleted.rowcount != 1:
                raise AppError("分析报告不存在。", code="ANALYSIS_NOT_FOUND", status_code=404)
        finally:
            for _, statement in delete_triggers:
                conn.execute(statement)
