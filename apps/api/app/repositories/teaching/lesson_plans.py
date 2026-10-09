"""SQL-only B5 lesson storage. The caller owns the publication transaction."""
from __future__ import annotations

import json
import uuid

from app.core.exceptions import AppError
from app.core.sqlite import now_iso


def missing():
    return AppError("教案或固定版本不存在。", code="NOT_FOUND", status_code=404)


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def load(raw):
    try:
        return json.loads(raw)
    except (TypeError, ValueError, RecursionError) as exc:
        raise AppError("固定教案记录损坏，请停止覆盖。", code="LESSON_DATA_CORRUPT", status_code=500) from exc


class LessonPlanRepository:
    def document(self, conn, lesson_id, owner_id):
        row = conn.execute("SELECT * FROM lesson_plans WHERE id=? AND owner_id=?", (lesson_id, owner_id)).fetchone()
        if row is None:
            raise missing()
        return row

    def revision(self, conn, lesson_id, revision_id, owner_id):
        row = conn.execute("""SELECT r.*,v.state AS review_state FROM lesson_plan_revisions r
            JOIN lesson_revision_reviews v ON v.revision_id=r.id AND v.lesson_plan_id=r.lesson_plan_id AND v.owner_id=r.owner_id
            WHERE r.id=? AND r.lesson_plan_id=? AND r.owner_id=?""", (revision_id, lesson_id, owner_id)).fetchone()
        if row is None:
            raise missing()
        return row

    def proposal(self, conn, lesson_id, proposal_id, owner_id):
        row = conn.execute("""SELECT p.*,i.frozen_json FROM lesson_ai_proposals p
            JOIN lesson_generation_inputs i ON i.id=p.generation_input_id AND i.lesson_plan_id=p.lesson_plan_id
              AND i.owner_id=p.owner_id AND i.job_id=p.job_id
            WHERE p.id=? AND p.lesson_plan_id=? AND p.owner_id=?""", (proposal_id, lesson_id, owner_id)).fetchone()
        if row is None:
            raise missing()
        return row

    def decision(self, conn, lesson_id, proposal_id, owner_id):
        return conn.execute("SELECT * FROM lesson_proposal_decisions WHERE proposal_id=? AND lesson_plan_id=? AND owner_id=?",
                            (proposal_id, lesson_id, owner_id)).fetchone()

    def insert_document(self, conn, *, lesson_id, owner_id, subject_id, class_id, revision_id, created_at):
        # The NOT NULL four-column pointer FK is deferred until this transaction
        # inserts its preallocated revision. There is never a null initial head.
        conn.execute("""INSERT INTO lesson_plans(id,owner_id,subject_id,class_id,current_revision_id,revision,created_at,updated_at)
            VALUES(?,?,?,?,?,1,?,?)""", (lesson_id, owner_id, subject_id, class_id, revision_id, created_at, created_at))

    def append_revision(self, conn, *, lesson_id, owner_id, version, data, content_hash, source, context,
                        source_metadata, revision_id=None, created_at=None, import_envelope=None,
                        accepted_proposal_id=None, selected_fields=None, process_metadata=None):
        revision_id, created_at = revision_id or uuid.uuid4().hex, created_at or now_iso()
        analysis = context.get("analysis")
        conn.execute("""INSERT INTO lesson_plan_revisions
            (id,lesson_plan_id,owner_id,version,data_json,content_hash,source,context_snapshot_json,analysis_run_id,
             accepted_proposal_id,import_envelope_json,source_metadata_json,selected_fields_json,process_metadata_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (revision_id, lesson_id, owner_id, version, dump(data), content_hash, source, dump(context),
             analysis["analysisRunId"] if analysis else None, accepted_proposal_id,
             dump(import_envelope) if import_envelope is not None else None, dump(source_metadata),
             dump(selected_fields or []), dump(process_metadata or []), created_at))
        conn.execute("""INSERT INTO lesson_revision_reviews(revision_id,lesson_plan_id,owner_id,state,created_at)
            VALUES(?,?,?,'unreviewed',?)""", (revision_id, lesson_id, owner_id, created_at))
        return revision_id

    def advance(self, conn, *, lesson_id, owner_id, old_revision, revision_id):
        changed = conn.execute("""UPDATE lesson_plans SET current_revision_id=?,revision=revision+1,updated_at=?
            WHERE id=? AND owner_id=? AND revision=?""", (revision_id, now_iso(), lesson_id, owner_id, old_revision)).rowcount
        if changed != 1:
            raise AppError("教案版本已变化。", code="REVISION_CONFLICT", status_code=409,
                           details={"currentRevision": self.document(conn, lesson_id, owner_id)["revision"], "fields": ["expectedRevision"]})

    def set_archived_in(self, conn, *, lesson_id, owner_id, archived, expected_revision):
        """归档/恢复：只写 ``archived_at``，head 指针与 ``revision`` 原样保留。

        ``lesson_plan_identity_fixed`` 触发器要求 current_revision_id 不变时 revision
        不得变化，因此归档不递增 revision；后续写入经 ``_current()`` 的归档守卫
        拒绝，CAS 不依赖 revision 递增也能感知归档动作。expected_revision 乐观锁
        在本事务内先行核对，不符时按既有 CAS 语义报 409。
        """
        document = self.document(conn, lesson_id, owner_id)
        if document["revision"] != expected_revision:
            raise AppError("教案版本已变化。", code="REVISION_CONFLICT", status_code=409,
                           details={"currentRevision": document["revision"], "fields": ["expectedRevision"]})
        conn.execute("UPDATE lesson_plans SET archived_at=?,updated_at=? WHERE id=? AND owner_id=? AND revision=?",
                     (now_iso() if archived else None, now_iso(), lesson_id, owner_id, expected_revision))

    def insert_decision(self, conn, *, lesson_id, owner_id, proposal_id, state, selected_fields=None, revision_id=None):
        conn.execute("""INSERT INTO lesson_proposal_decisions
            (proposal_id,lesson_plan_id,owner_id,state,selected_fields_json,accepted_revision_id,created_at) VALUES(?,?,?,?,?,?,?)""",
            (proposal_id, lesson_id, owner_id, state, dump(selected_fields or []), revision_id, now_iso()))

    def delete_lesson_in(self, conn, lesson_id, owner_id):
        """彻底删除教案行及其自身历史，返回 ``LessonDeleteReceipt`` 计数（dict）。

        FK 图谱（0010 迁移核实）：``lesson_plan_revisions``/``lesson_revision_reviews``/
        ``lesson_generation_inputs``/``lesson_ai_proposals`` 只引用本教案（lesson_plan_id）
        与向外引用（analysis_runs/classes/workflow_jobs），``lesson_proposal_decisions``
        只引用本教案的 proposals/revisions；**没有任何其他表把外键指向教案五表**，
        因此守卫通过后可安全物理删除，不留悬挂引用。

        删除顺序（子行 → 身份行）：``lesson_proposal_decisions`` → ``lesson_ai_proposals``
        → ``lesson_generation_inputs`` → ``lesson_revision_reviews`` →
        ``lesson_plan_revisions`` → ``lesson_plans``。三条指向教案行的外键
        （``lesson_plans.current_revision_id``、``lesson_plan_revisions.accepted_proposal_id``、
        ``lesson_proposal_decisions.accepted_revision_id``）均为 DEFERRABLE INITIALLY
        DEFERRED，同事务内全删后 COMMIT 校验自然成立，**不 UPDATE 教案行**
        （``current_revision_id`` NOT NULL 且 ``lesson_plan_identity_fixed`` 禁止指针无递增变化）。
        本事务只删不改，因此只临时摘除 5 个 DELETE 触发器（四张 IMMUTABLE 表的
        ``*_immutable_delete`` 加 ``lesson_review_no_delete``），与知识点仓储同一先例：
        彻底删除是经守卫的受控行为，同一写事务内临时摘除触发器 → 删除 → 按登记声明
        逐字恢复（DDL 可事务化，任一步失败整体回滚，触发器随事务恢复；BEGIN IMMEDIATE
        下无并发写者可见窗口）。触发器文本与 ``app/core/migrations/lesson_plans.py``
        0010 声明一致，不改登记 SQL。

        行不存在/非本人 → 404，不静默成功。
        """
        document = self.document(conn, lesson_id, owner_id)
        revisions = conn.execute("SELECT id FROM lesson_plan_revisions WHERE lesson_plan_id=? AND owner_id=?",
                                 (lesson_id, owner_id)).fetchall()
        inputs = conn.execute("SELECT count(*) FROM lesson_generation_inputs WHERE lesson_plan_id=? AND owner_id=?",
                              (lesson_id, owner_id)).fetchone()[0]
        proposals = conn.execute("SELECT count(*) FROM lesson_ai_proposals WHERE lesson_plan_id=? AND owner_id=?",
                                 (lesson_id, owner_id)).fetchone()[0]
        # 不可变触发器是固定历史的兜底；受守卫的彻底删除在同一事务内临时摘除再逐字恢复。
        delete_triggers = tuple(
            (f"{table}_immutable_delete",
             f"CREATE TRIGGER {table}_immutable_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'LESSON_FIXED_CONTENT'); END")
            for table in ("lesson_plan_revisions", "lesson_generation_inputs", "lesson_ai_proposals", "lesson_proposal_decisions")
        ) + (("lesson_review_no_delete",
              "CREATE TRIGGER lesson_review_no_delete BEFORE DELETE ON lesson_revision_reviews "
              "BEGIN SELECT RAISE(ABORT,'LESSON_REVIEW_FIXED'); END"),)
        for name, _ in delete_triggers:
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        try:
            conn.execute("""DELETE FROM lesson_proposal_decisions WHERE lesson_plan_id=? AND owner_id=?""", (lesson_id, owner_id))
            conn.execute("""DELETE FROM lesson_ai_proposals WHERE lesson_plan_id=? AND owner_id=?""", (lesson_id, owner_id))
            conn.execute("""DELETE FROM lesson_generation_inputs WHERE lesson_plan_id=? AND owner_id=?""", (lesson_id, owner_id))
            conn.execute("""DELETE FROM lesson_revision_reviews WHERE lesson_plan_id=? AND owner_id=?""", (lesson_id, owner_id))
            conn.execute("""DELETE FROM lesson_plan_revisions WHERE lesson_plan_id=? AND owner_id=?""", (lesson_id, owner_id))
            deleted = conn.execute("DELETE FROM lesson_plans WHERE id=? AND owner_id=?", (lesson_id, owner_id))
            if deleted.rowcount != 1:
                raise AppError("教案或固定版本不存在。", code="NOT_FOUND", status_code=404)
        finally:
            for _, statement in delete_triggers:
                conn.execute(statement)
        return dict(deleted=True, lessonPlanId=lesson_id, removedRevisions=len(revisions),
                    removedProposals=proposals, removedInputs=inputs)

    def list_documents(self, conn, owner_id, *, subject_id=None, class_id=None, archived=False, offset=0, limit=50):
        where, values = ["l.owner_id=?"], [owner_id]
        where.append("l.archived_at IS NULL" if not archived else "l.archived_at IS NOT NULL")
        for column, value in (("l.subject_id", subject_id), ("l.class_id", class_id)):
            if value is not None:
                where.append(column + "=?")
                values.append(value)
        predicate = " AND ".join(where)
        total = conn.execute("SELECT count(*) FROM lesson_plans l WHERE " + predicate, values).fetchone()[0]
        rows = conn.execute("""SELECT l.*,json_extract(r.data_json,'$.title') AS title,r.source,r.analysis_run_id
            FROM lesson_plans l JOIN lesson_plan_revisions r ON r.id=l.current_revision_id
              AND r.lesson_plan_id=l.id AND r.owner_id=l.owner_id AND r.version=l.revision
            WHERE """ + predicate + " ORDER BY l.updated_at DESC,l.id DESC LIMIT ? OFFSET ?", (*values, limit, offset)).fetchall()
        return rows, total

    def list_revisions(self, conn, lesson_id, owner_id, *, offset=0, limit=50):
        self.document(conn, lesson_id, owner_id)
        total = conn.execute("SELECT count(*) FROM lesson_plan_revisions WHERE lesson_plan_id=? AND owner_id=?", (lesson_id, owner_id)).fetchone()[0]
        rows = conn.execute("""SELECT r.id,r.lesson_plan_id,r.version,json_extract(r.data_json,'$.title') AS title,
            r.content_hash,r.source,r.analysis_run_id,r.accepted_proposal_id,r.selected_fields_json,r.created_at,v.state AS review_state
            FROM lesson_plan_revisions r JOIN lesson_revision_reviews v ON v.revision_id=r.id AND v.owner_id=r.owner_id
            WHERE r.lesson_plan_id=? AND r.owner_id=? ORDER BY r.version DESC LIMIT ? OFFSET ?""",
            (lesson_id, owner_id, limit, offset)).fetchall()
        return rows, total
