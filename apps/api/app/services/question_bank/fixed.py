"""B4 historical confirmed-question port; current pointer is never used by read_revision."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from app.contracts.teaching_loop import canonical_hash
from app.core.exceptions import AppError
from app.core.sqlite import open_readonly
from app.repositories.question_bank.json_fields import read_object
from app.services.question_bank.fingerprint import duplicate_content_fingerprint, DUPLICATE_ALGORITHM_VERSION


@dataclass(frozen=True)
class FixedQuestionSnapshot:
    question_id: str
    question_revision_id: str
    owner_id: str
    question_status: str
    subject_id: str
    content: dict[str, Any]
    metadata: dict[str, Any]
    answer_state: str
    content_hash: str
    surface_fingerprint: str
    algorithm_version: str
    knowledge_links: tuple[dict[str, str], ...]
    source_locators: tuple[dict[str, Any], ...]


class FixedQuestionReader:
    def __init__(self, catalog: Any) -> None:
        self.catalog = catalog

    def read_revision(self, question_revision_id: str, *, owner_id: str = "local") -> FixedQuestionSnapshot:
        conn = open_readonly(self.catalog.db_path, required_tables=("questions", "question_revisions"))
        try:
            row = conn.execute("SELECT r.*,q.owner_id,q.status FROM question_revisions r JOIN questions q ON q.id=r.question_id WHERE r.id=? AND q.owner_id=?", (question_revision_id, owner_id)).fetchone()
            if row is None:
                raise AppError("固定题目修订不存在。", code="QUESTION_NOT_FOUND", status_code=404)
            if not row["confirmed_at"]:
                raise AppError("题目修订尚未正式确认。", code="QUESTION_NOT_CONFIRMED", status_code=422)
            content = read_object(row["content_json"], field="question_revisions.content_json")
            metadata = read_object(row["metadata_json"], field="question_revisions.metadata_json")
            if content is None or metadata is None or not isinstance(metadata.get("subjectId"), str):
                raise AppError("固定题目内容损坏。", code="QUESTION_ROW_CORRUPT", status_code=500)
            links = tuple(dict(knowledge_point_id=x.knowledge_point_id, knowledge_revision_id=x.knowledge_revision_id,
                name_snapshot=x.knowledge_name_snapshot, subject_id_snapshot=x.subject_id_snapshot, role=x.role)
                for x in self.catalog.question_knowledge_links_in(conn, question_revision_id))
            rich = content.get('richContent')
            locators = ()
            if isinstance(rich, dict) and isinstance(rich.get('origin'), dict):
                origin = rich['origin']
                locators = ({'originalAssetId':origin.get('originalAssetId', origin.get('original_asset_id')),
                    'originalSha256':origin.get('originalSha256', origin.get('original_sha256')),
                    'sourceLocator':origin.get('sourceLocator', origin.get('source_locator', {}))},)
            # Original confirmation fingerprint is immutable and does not require file IO.
            return FixedQuestionSnapshot(row["question_id"], row["id"], row["owner_id"], row["status"], metadata["subjectId"],
                content, metadata, row["answer_state"], canonical_hash({"content":content,"metadata":metadata,"links":links}),
                duplicate_content_fingerprint(content), DUPLICATE_ALGORITHM_VERSION, links, locators)
        finally:
            conn.close()

    def list_confirmed(self, *, subject_id: str, owner_id: str = "local") -> list[FixedQuestionSnapshot]:
        conn = open_readonly(self.catalog.db_path, required_tables=("questions", "question_revisions"))
        try:
            ids = [r[0] for r in conn.execute("SELECT q.current_revision_id FROM questions q JOIN question_revisions r ON r.id=q.current_revision_id AND r.question_id=q.id WHERE q.owner_id=? AND q.status='confirmed' AND json_extract(r.metadata_json,'$.subjectId')=? ORDER BY q.id,q.current_revision_id", (owner_id, subject_id))]
        finally:
            conn.close()
        return [self.read_revision(rid, owner_id=owner_id) for rid in ids]

    def list_confirmed_page(self, *, subject_id: str, owner_id: str, offset: int = 0,
                            limit: int = 50) -> tuple[list[FixedQuestionSnapshot], int]:
        """Bounded UI selection; identities are actual immutable revision rows."""
        if (not isinstance(subject_id, str) or not subject_id.strip() or subject_id != subject_id.strip()
                or len(subject_id) > 64 or type(offset) is not int or offset < 0
                or type(limit) is not int or not 1 <= limit <= 200):
            raise AppError("固定题筛选参数不合法。", code="INVALID_REQUEST", status_code=422)
        conn = open_readonly(self.catalog.db_path, required_tables=("questions", "question_revisions"))
        try:
            conn.execute("BEGIN")
            condition = """FROM questions q JOIN question_revisions r
                ON r.id=q.current_revision_id AND r.question_id=q.id
                WHERE q.owner_id=? AND q.status='confirmed' AND r.confirmed_at IS NOT NULL
                AND json_extract(r.metadata_json,'$.subjectId')=?"""
            total = conn.execute("SELECT COUNT(*) " + condition, (owner_id, subject_id)).fetchone()[0]
            ids = [row[0] for row in conn.execute("SELECT r.id " + condition +
                " ORDER BY q.id,r.id LIMIT ? OFFSET ?", (owner_id, subject_id, limit, offset))]
        finally:
            conn.close()
        return [self.read_revision(rid, owner_id=owner_id) for rid in ids], total
