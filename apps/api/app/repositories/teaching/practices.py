"""Practice SQL reads on the caller's teaching connection."""
from app.core.exceptions import AppError


class PracticeRepository:
    def __init__(self, catalog):
        self.catalog = catalog

    def set_in(self, conn, set_id: str, owner_id: str):
        row = conn.execute("SELECT * FROM practice_sets WHERE id=? AND owner_id=?", (set_id, owner_id)).fetchone()
        if row is None:
            raise AppError("练习不存在。", code="PRACTICE_NOT_FOUND", status_code=404)
        return row

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
