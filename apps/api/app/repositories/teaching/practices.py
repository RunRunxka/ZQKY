"""Practice SQL reads on the caller's teaching connection."""
from app.core.exceptions import AppError

PRACTICE_SET_STATUSES = frozenset({"active", "archived"})

#: 受引用守卫：练习集有已审核修订/导出/转换引用时按此码 409 拒绝删除
PRACTICE_IN_USE = "PRACTICE_IN_USE"

#: 连带历史彻底删除（``includeHistory``）需在同一写事务内临时摘除的 10 个触发器，
#: ``(名称, 恢复原文)`` 形式；摘除顺序无关紧要，恢复在 ``finally`` 中逐字执行。
#: 文本已用真实迁移库核对：除 ``immutable_paper_revisions_update``（迁移声明带
#: ``IF NOT EXISTS``，sqlite_master 存储不含该字样）外，其余 9 条与
#: b4 0008/0009、teaching 0003 声明逐字一致，恢复语句一律以 sqlite_master
#: 存储文本为准。DDL 可事务化，任一步失败整体回滚，触发器随事务恢复；
#: BEGIN IMMEDIATE 下无并发写者可见窗口。先例：``scores.delete_revision_in``、
#: ``practices.delete_conversion_in``。
_HISTORY_DELETE_TRIGGERS = (
    ("practice_revision_delete",
     "CREATE TRIGGER practice_revision_delete BEFORE DELETE ON practice_revisions "
     "WHEN OLD.state='reviewed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
    ("freeze_practice_selections_delete",
     "CREATE TRIGGER freeze_practice_selections_delete BEFORE DELETE ON practice_selections "
     "WHEN (SELECT state FROM practice_revisions WHERE id=OLD.practice_revision_id)='reviewed' "
     "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
    ("freeze_practice_items_delete",
     "CREATE TRIGGER freeze_practice_items_delete BEFORE DELETE ON practice_items "
     "WHEN (SELECT state FROM practice_revisions WHERE id=OLD.practice_revision_id)='reviewed' "
     "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
    ("freeze_practice_item_knowledge_delete",
     "CREATE TRIGGER freeze_practice_item_knowledge_delete BEFORE DELETE ON practice_item_knowledge "
     "WHEN (SELECT state FROM practice_revisions WHERE id=OLD.practice_revision_id)='reviewed' "
     "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
    ("immutable_practice_exports_delete",
     "CREATE TRIGGER immutable_practice_exports_delete BEFORE DELETE ON practice_exports "
     "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
    ("immutable_export_artifacts_delete",
     "CREATE TRIGGER immutable_export_artifacts_delete BEFORE DELETE ON export_artifacts "
     "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
    ("immutable_practice_conversions_delete",
     "CREATE TRIGGER immutable_practice_conversions_delete BEFORE DELETE ON practice_conversions "
     "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
    ("immutable_practice_paper_item_mappings_delete",
     "CREATE TRIGGER immutable_practice_paper_item_mappings_delete BEFORE DELETE ON practice_paper_item_mappings "
     "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
    ("immutable_paper_revisions_update",
     "CREATE TRIGGER immutable_paper_revisions_update BEFORE UPDATE ON paper_revisions "
     "WHEN OLD.state='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
    ("paper_source_fixed",
     "CREATE TRIGGER paper_source_fixed "
     "BEFORE UPDATE OF paper_id,source_file_id,source_practice_revision_id ON paper_revisions "
     "WHEN NEW.paper_id IS NOT OLD.paper_id OR NEW.source_file_id IS NOT OLD.source_file_id "
     "OR NEW.source_practice_revision_id IS NOT OLD.source_practice_revision_id "
     "BEGIN SELECT RAISE(ABORT,'PAPER_SOURCE_FIXED'); END"),
)


class PracticeRepository:
    def __init__(self, catalog):
        self.catalog = catalog

    def set_in(self, conn, set_id: str, owner_id: str):
        row = conn.execute("SELECT * FROM practice_sets WHERE id=? AND owner_id=?", (set_id, owner_id)).fetchone()
        if row is None:
            raise AppError("练习不存在。", code="PRACTICE_NOT_FOUND", status_code=404)
        return row

    def source_view_in(self, conn, analysis_run_id: str, owner_id: str) -> tuple[str | None, str | None]:
        """练习来源的展示名（只读派生）：analysis_runs → paper_revisions.title_snapshot / created_at。

        owner 校验经 ``analysis_runs.owner_id``（练习集引用的运行必属同一 owner，见
        ``practice_source_subject`` 触发器同口径）；运行或来源原卷修订缺失时返回
        ``(None, None)``（读失败不伪造名称），由调用方落 null。
        """
        row = conn.execute(
            "SELECT pr.title_snapshot AS paper_title, a.created_at AS run_created_at "
            "FROM analysis_runs a LEFT JOIN paper_revisions pr ON pr.id = a.paper_revision_id "
            "WHERE a.id=? AND a.owner_id=?",
            (analysis_run_id, owner_id)).fetchone()
        if row is None:
            return None, None
        title = row["paper_title"]
        created_at = row["run_created_at"]
        return (title if isinstance(title, str) and title else None,
                created_at if isinstance(created_at, str) and created_at else None)

    def count_references_in(self, conn, set_id: str) -> dict[str, int]:
        """该练习集在下游表里的引用计数（整体删除守卫的数据来源）。

        ``reviewedRevisions`` = 已审核修订数（DB 触发器禁止删除 reviewed，只能归档）；
        ``exports`` = ``practice_exports`` 引用数；``conversions`` = ``practice_conversions`` 引用数。
        """
        set_id = str(set_id)
        return {
            "reviewedRevisions": int(conn.execute(
                "SELECT COUNT(*) FROM practice_revisions WHERE practice_set_id=? AND state='reviewed'",
                (set_id,)).fetchone()[0]),
            "exports": int(conn.execute(
                "SELECT COUNT(*) FROM practice_exports e JOIN practice_revisions r ON r.id=e.practice_revision_id "
                "WHERE r.practice_set_id=?", (set_id,)).fetchone()[0]),
            "conversions": int(conn.execute(
                "SELECT COUNT(*) FROM practice_conversions c JOIN practice_revisions r ON r.id=c.practice_revision_id "
                "WHERE r.practice_set_id=?", (set_id,)).fetchone()[0]),
        }

    def draft_revision_ids_in(self, conn, set_id: str) -> list[str]:
        """该集合全部 draft 修订 id（触发器只保护 reviewed；draft 可删）。"""
        rows = conn.execute(
            "SELECT id FROM practice_revisions WHERE practice_set_id=? AND state='draft' ORDER BY version",
            (set_id,)).fetchall()
        return [row["id"] for row in rows]

    def delete_set_in(self, conn, set_id: str) -> None:
        """在同一写事务内删除该集合全部 draft 修订的子行、修订行与 ``practice_sets`` 行。

        前置：调用方已通过受引用守卫（无 reviewed 修订/导出/转换引用）。
        子行按 ``practice_revision_id`` 先删 ``practice_item_knowledge``/``practice_items``/
        ``practice_selections``，再删 ``practice_revisions``（draft），最后删集合行。
        ``practice_sets.current_revision_id`` 指回修订（DEFERRABLE），删除前先置 NULL。
        """
        self.delete_draft_revisions_in(conn, set_id)
        deleted = conn.execute("DELETE FROM practice_sets WHERE id=?", (set_id,))
        if deleted.rowcount != 1:
            raise AppError("练习不存在。", code="PRACTICE_NOT_FOUND", status_code=404)

    def delete_set_with_history_in(self, conn, set_id: str) -> dict[str, int]:
        """连带全部历史彻底删除练习集（``includeHistory=true`` 路径，单写事务内执行）。

        前置：调用方已完成 CAS 与 404 校验（本方法内集合行消失时同样按 404 兜底）。
        严格顺序：同事务摘除 10 个不可变触发器（见 ``_HISTORY_DELETE_TRIGGERS``，
        ``finally`` 逐字恢复）→ 清 ``current_revision_id`` → 转换生成的原卷修订来源
        指针置 NULL（``paper_revisions.source_practice_revision_id`` 是实外键；行与
        内容一律保留）→ 映射/工件/导出/转换 → 题叶知识/题目/选题 → 修订行 → 集合行。

        来源指针置 NULL 在登记迁移 0013（``paper_source_relaxed_rebuild``）后合法：
        0009 的"恰一非空"互斥 CHECK 已放宽为"至多一源"（``source_file_id IS NULL OR
        source_practice_revision_id IS NULL``），练习被连带历史彻底删除后，其转换
        生成的原卷修订允许无来源；禁的只是"两个来源同时非空"。

        **保留不动**（边界，不属于本删除）：``file_assets``（blob 本体，受管资产不
        物理删除，导出工件登记行删除后资产仍归受管资产体系管）、``workflow_jobs``
        （任务历史）、paper/assessment/analysis 一切行（转换生成的原卷修订仅摘除
        来源指针，其余字段原样）。

        返回 ``removedRevisions``/``removedExports``/``removedConversions``/
        ``removedArtifacts`` 四个计数（回执用）。
        """
        revision_ids = [row["id"] for row in conn.execute(
            "SELECT id FROM practice_revisions WHERE practice_set_id=?", (set_id,)).fetchall()]
        for name, _ in _HISTORY_DELETE_TRIGGERS:
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        try:
            conn.execute("UPDATE practice_sets SET current_revision_id=NULL WHERE id=?", (set_id,))
            conn.execute(
                "UPDATE paper_revisions SET source_practice_revision_id=NULL WHERE source_practice_revision_id IN "
                "(SELECT id FROM practice_revisions WHERE practice_set_id=?)", (set_id,))
            removed_conversions = 0
            if revision_ids:
                conn.execute(
                    "DELETE FROM practice_paper_item_mappings WHERE practice_revision_id IN "
                    f"({','.join('?' * len(revision_ids))})", revision_ids)
                removed_artifacts = conn.execute(
                    "DELETE FROM export_artifacts WHERE practice_revision_id IN "
                    f"({','.join('?' * len(revision_ids))})", revision_ids).rowcount
                removed_exports = conn.execute(
                    "DELETE FROM practice_exports WHERE practice_revision_id IN "
                    f"({','.join('?' * len(revision_ids))})", revision_ids).rowcount
                removed_conversions = conn.execute(
                    "DELETE FROM practice_conversions WHERE practice_revision_id IN "
                    f"({','.join('?' * len(revision_ids))})", revision_ids).rowcount
                for revision_id in revision_ids:
                    conn.execute("DELETE FROM practice_item_knowledge WHERE practice_revision_id=?", (revision_id,))
                    conn.execute("DELETE FROM practice_items WHERE practice_revision_id=?", (revision_id,))
                    conn.execute("DELETE FROM practice_selections WHERE practice_revision_id=?", (revision_id,))
                removed_revisions = conn.execute(
                    "DELETE FROM practice_revisions WHERE practice_set_id=?", (set_id,)).rowcount
            else:
                removed_revisions = removed_exports = removed_artifacts = 0
            deleted = conn.execute("DELETE FROM practice_sets WHERE id=?", (set_id,))
            if deleted.rowcount != 1:
                raise AppError("练习不存在。", code="PRACTICE_NOT_FOUND", status_code=404)
        finally:
            for _, statement in _HISTORY_DELETE_TRIGGERS:
                conn.execute(statement)
        return dict(removedRevisions=int(removed_revisions), removedExports=int(removed_exports),
                    removedConversions=int(removed_conversions), removedArtifacts=int(removed_artifacts))

    def delete_draft_revisions_in(self, conn, set_id: str) -> list[str]:
        """删除集合下全部 draft 修订及其子行；返回被删的修订 id 列表（测试断言用）。"""
        conn.execute(
            "UPDATE practice_sets SET current_revision_id=NULL WHERE id=? AND current_revision_id IN "
            "(SELECT id FROM practice_revisions WHERE practice_set_id=? AND state='draft')",
            (set_id, set_id))
        revision_ids = self.draft_revision_ids_in(conn, set_id)
        for revision_id in revision_ids:
            conn.execute("DELETE FROM practice_item_knowledge WHERE practice_revision_id=?", (revision_id,))
            conn.execute("DELETE FROM practice_items WHERE practice_revision_id=?", (revision_id,))
            conn.execute("DELETE FROM practice_selections WHERE practice_revision_id=?", (revision_id,))
        for revision_id in revision_ids:
            conn.execute("DELETE FROM practice_revisions WHERE id=? AND state='draft'", (revision_id,))
        return revision_ids

    def latest_conversion_assessment_id_in(self, conn, revision_id: str, owner_id: str) -> str | None:
        """该修订最新一条转换的施测 id（只读派生）：无转换落 ``None``，不伪造。

        排序口径与 ``delete_conversion_in`` 取最新一条完全一致（``created_at DESC,
        rowid DESC LIMIT 1``），保证"展示与解除"看到的是同一条回流关联。
        """
        row = conn.execute(
            "SELECT assessment_id FROM practice_conversions WHERE practice_revision_id=? AND owner_id=? "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (revision_id, owner_id)).fetchone()
        return row["assessment_id"] if row is not None else None

    def delete_conversion_in(self, conn, revision_id: str, owner_id: str) -> dict[str, str]:
        """删除该审核修订**最新一条**练习转换关联行及其映射子行，返回被删身份。

        范围（受控解除回流）：只删 ``practice_conversions`` 一行（按创建时间取最新，
        多条时重复调用逐条解除）与该行在 ``practice_paper_item_mappings`` 的全部子行；
        **不动** ``assessments``/``paper_revisions``/``practice_revisions``/``practice_exports``/
        ``export_artifacts``——施测、原卷与成绩保留，之后由施测自己的删除守卫链处理。
        同一修订存在多条转换时每次只删一条，回执身份与实际删除行一一对应。

        触发器说明：``immutable_practice_conversions_delete`` 与
        ``immutable_practice_paper_item_mappings_delete`` 是固定历史的兜底；解除回流
        关联是**经 owner 校验的受控行为**，同一写事务内临时摘除两个 DELETE 触发器 →
        删除 → 按登记声明逐字恢复（DDL 可事务化，任一步失败整体回滚，触发器随事务
        恢复；BEGIN IMMEDIATE 下无并发写者可见窗口）。触发器文本与
        ``app/core/migrations/b4.py`` 0008 声明（``immutable_{t}_{op}`` 循环生成处）
        逐字一致，不改登记 SQL。先例：``lesson_plans.delete_lesson_in``、
        ``knowledge.points.delete_point``。

        行不存在/非本人 → 404 ``PRACTICE_CONVERSION_NOT_FOUND``，不静默成功。
        """
        row = conn.execute(
            "SELECT c.id AS conversion_id, c.assessment_id AS assessment_id FROM practice_conversions c "
            "WHERE c.practice_revision_id=? AND c.owner_id=? ORDER BY c.created_at DESC, c.rowid DESC LIMIT 1",
            (revision_id, owner_id)).fetchone()
        if row is None:
            raise AppError("该审核修订没有转换记录。", code="PRACTICE_CONVERSION_NOT_FOUND", status_code=404)
        delete_triggers = (
            ("immutable_practice_paper_item_mappings_delete",
             "CREATE TRIGGER immutable_practice_paper_item_mappings_delete BEFORE DELETE ON practice_paper_item_mappings "
             "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
            ("immutable_practice_conversions_delete",
             "CREATE TRIGGER immutable_practice_conversions_delete BEFORE DELETE ON practice_conversions "
             "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"),
        )
        # 不可变触发器是固定历史的兜底；受控解除在同一事务内临时摘除再逐字恢复。
        for name, _ in delete_triggers:
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        try:
            conn.execute("DELETE FROM practice_paper_item_mappings WHERE conversion_id=?", (row["conversion_id"],))
            deleted = conn.execute("DELETE FROM practice_conversions WHERE id=? AND owner_id=?",
                                   (row["conversion_id"], owner_id))
            if deleted.rowcount != 1:
                raise AppError("练习转换记录不存在。", code="PRACTICE_CONVERSION_NOT_FOUND", status_code=404)
        finally:
            for _, statement in delete_triggers:
                conn.execute(statement)
        return dict(conversion_id=row["conversion_id"], assessment_id=row["assessment_id"])

    def set_archived_in(self, conn, set_id: str, owner_id: str, *, expected_revision: int, archived: bool):
        """归档/恢复：一条 UPDATE 同时改 ``status`` 并原子递增 ``revision``；历史修订原样保留。"""
        status = "archived" if archived else "active"
        if status not in PRACTICE_SET_STATUSES:
            raise AppError("status 只能是 active 或 archived。", code="INVALID_REQUEST", status_code=422)
        current = self.set_in(conn, set_id, owner_id)
        if current["revision"] != expected_revision:
            raise AppError("数据已被其他操作更新，请刷新后重试。", code="REVISION_CONFLICT", status_code=409,
                details={"currentRevision": current["revision"], "fields": ["expectedRevision"]})
        conn.execute("UPDATE practice_sets SET status=?, revision=revision+1 WHERE id=? AND owner_id=? AND revision=?",
            (status, set_id, owner_id, expected_revision))
        return self.set_in(conn, set_id, owner_id)

    def revision_in(self, conn, set_id: str, revision_id: str, owner_id: str):
        self.set_in(conn, set_id, owner_id)
        row = conn.execute("SELECT * FROM practice_revisions WHERE id=? AND practice_set_id=?", (revision_id, set_id)).fetchone()
        if row is None:
            raise AppError("练习修订不存在。", code="PRACTICE_NOT_FOUND", status_code=404)
        return row

    def selections_in(self, conn, revision_id):
        return conn.execute("SELECT * FROM practice_selections WHERE practice_revision_id=? ORDER BY ordinal", (revision_id,)).fetchall()

    def items_in(self, conn, revision_id):
        return conn.execute("SELECT i.*,s.item_key,s.question_id,s.question_revision_id,s.reason_json,s.answer_state FROM practice_items i JOIN practice_selections s ON s.id=i.selection_id AND s.practice_revision_id=i.practice_revision_id WHERE i.practice_revision_id=? ORDER BY i.ordinal", (revision_id,)).fetchall()

    def knowledge_in(self, conn, item_id):
        return conn.execute("SELECT * FROM practice_item_knowledge WHERE item_id=? ORDER BY knowledge_point_id", (item_id,)).fetchall()
