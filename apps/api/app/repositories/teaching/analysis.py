"""Analysis SQL primitives. Transactions and business rules belong to service/engine."""
import json
import uuid
from app.core.exceptions import AppError
from app.core.sqlite import now_iso
from app.repositories.teaching.triggers import (
    ANALYSIS_FROZEN_TRIGGERS,
    suspend_triggers,
)


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

        R10-BE（2026-10-13「舍弃归档只留删除 + 拆开交叉引用」）把四种引用分成两类：

        - **可拆**（删除报告时一并处理，不再 409）：
          ``practiceSets`` = ``practice_sets.analysis_run_id`` 引用数（报告的下游产物，
          随报告级联彻底删除）；``lessonRevisions`` = ``lesson_plan_revisions.analysis_run_id``
          引用数（可空来源指针，置 NULL 摘除来源，教案本体保留）；
        - **不可拆**（NOT NULL 的冻结 AI 输入，409 逐项列出）：
          ``lessonGenerationInputs`` = ``lesson_generation_inputs.analysis_run_id``、
          ``lessonProposals`` = ``lesson_ai_proposals.analysis_run_id``——两表受
          ``lesson_*_immutable_*`` 触发器与 NOT NULL 复合外键双重保护，删报告即破坏
          已应用 AI 教案的血缘，拒绝并如实列出。
        """
        return {
            "practiceSets": int(conn.execute(
                "SELECT count(*) FROM practice_sets WHERE analysis_run_id=?", (run_id,)).fetchone()[0]),
            "lessonRevisions": int(conn.execute(
                "SELECT count(*) FROM lesson_plan_revisions WHERE analysis_run_id=?", (run_id,)).fetchone()[0]),
            "lessonGenerationInputs": int(conn.execute(
                "SELECT count(*) FROM lesson_generation_inputs WHERE analysis_run_id=?", (run_id,)).fetchone()[0]),
            "lessonProposals": int(conn.execute(
                "SELECT count(*) FROM lesson_ai_proposals WHERE analysis_run_id=?", (run_id,)).fetchone()[0]),
        }

    def practice_set_ids_in(self, conn, run_id) -> list[str]:
        """引用该报告的练习集 id（删除报告的级联顺序：先练习、后报告）。"""
        rows = conn.execute(
            "SELECT id FROM practice_sets WHERE analysis_run_id=? ORDER BY created_at, id",
            (run_id,)).fetchall()
        return [row["id"] for row in rows]

    def unlink_lesson_revisions_in(self, conn, run_id) -> int:
        """把教案修订的 ``analysis_run_id`` 来源指针置 NULL（教案保留，只摘除来源）。

        前置：调用方已摘除 ``lesson_plan_revisions_immutable_update``（见
        ``triggers.LESSON_REVISION_TRIGGERS``）——教案修订平时整行不可写，
        摘除来源是本次删除的受控例外。返回受影响修订数。
        """
        return conn.execute(
            "UPDATE lesson_plan_revisions SET analysis_run_id=NULL WHERE analysis_run_id=?",
            (run_id,)).rowcount

    def delete_run_in(self, conn, run_id, owner_id):
        """彻底删除报告自身及其冻结子表行（前置：调用方已通过引用守卫）。

        守卫覆盖下游引用：不可拆的教案冻结输入（``lesson_generation_inputs`` /
        ``lesson_ai_proposals``）由服务层先行判定；可拆引用（练习集、教案修订来源）
        由服务层在同一写事务内先行处理。报告自身六张冻结子表随报告一并删除，
        ``workflow_jobs`` 任务行保留不动（任务历史不属于报告内容）。

        FK 图谱（b4 0008/0009 与 0010 迁移核实）：六张子表
        （``analysis_participants``/``analysis_item_snapshots``/``analysis_student_results``/
        ``analysis_class_results``/``analysis_evidence``/``analysis_teacher_notes``）只引用
        本报告与向外引用；下游仅 ``practice_sets`` 与教案三表（守卫/级联已挡）。报告行
        删除后无悬挂引用。

        删除顺序（子行 → 身份行）：``analysis_evidence`` → ``analysis_student_results``
        → ``analysis_teacher_notes`` → ``analysis_class_results`` →
        ``analysis_item_snapshots`` → ``analysis_participants`` → ``analysis_runs``。

        ``analysis_no_delete``、五个子表 freeze 触发器的 delete 版与
        ``immutable_analysis_teacher_notes_delete`` 是固定历史的兜底；受守卫的彻底删除
        是经守卫的受控行为：同事务摘除（``triggers.suspend_triggers``，恢复文本取自
        ``sqlite_master``）→ 删除 → 恢复（DDL 可事务化，任一步失败整体回滚，触发器随
        事务恢复；BEGIN IMMEDIATE 下无并发写者可见窗口）。嵌套在更大级联里时由最外层
        统一恢复，本层退化为空操作。行不存在/非本人 → 404，不静默成功。
        """
        self.require_in(conn, run_id, owner_id)
        with suspend_triggers(conn, ANALYSIS_FROZEN_TRIGGERS):
            conn.execute("DELETE FROM analysis_evidence WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM analysis_student_results WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM analysis_teacher_notes WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM analysis_class_results WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM analysis_item_snapshots WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM analysis_participants WHERE run_id=?", (run_id,))
            deleted = conn.execute("DELETE FROM analysis_runs WHERE id=? AND owner_id=?", (run_id, owner_id))
            if deleted.rowcount != 1:
                raise AppError("分析报告不存在。", code="ANALYSIS_NOT_FOUND", status_code=404)
