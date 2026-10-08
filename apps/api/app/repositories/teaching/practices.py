"""Practice SQL reads on the caller's teaching connection."""
from app.core.exceptions import AppError

PRACTICE_SET_STATUSES = frozenset({"active", "archived"})

#: 受引用守卫：练习集有已审核修订/导出/转换引用时按此码 409 拒绝删除
PRACTICE_IN_USE = "PRACTICE_IN_USE"


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
