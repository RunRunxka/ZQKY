"""题库建库 DDL：表名、字段与顺序严格对应 RAG-REBUILD v1.0 §8.2 题库数据库规格。

约束：
- 迁移幂等：只用 ``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF NOT EXISTS``，
  不重建、不删除、不改写既有行；
- ``questions.current_revision_id`` 与 ``question_revisions.question_id`` 互为环形外键，
  写入方在同一事务内用 ``PRAGMA defer_foreign_keys`` 延后校验；
- 题库数据库独立于教材目录：这里不引用任何教材表，也没有指向教材向量库的路径。
"""

from __future__ import annotations

import sqlite3

_TABLES: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS question_imports (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        file_sha256 TEXT NOT NULL,
        original_blob_id TEXT NOT NULL,
        uploaded_file_name TEXT NOT NULL,
        uploaded_bytes INTEGER NOT NULL,
        state TEXT NOT NULL,
        revision INTEGER NOT NULL DEFAULT 0,
        warnings_json TEXT NOT NULL DEFAULT '[]',
        error_code TEXT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS question_source_blocks (
        id TEXT PRIMARY KEY,
        import_id TEXT NOT NULL REFERENCES question_imports(id),
        ordinal INTEGER NOT NULL,
        text TEXT NOT NULL,
        locator_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS question_drafts (
        id TEXT PRIMARY KEY,
        import_id TEXT NOT NULL REFERENCES question_imports(id),
        revision INTEGER NOT NULL DEFAULT 0,
        content_json TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        source_spans_json TEXT NOT NULL DEFAULT '[]',
        extraction_method TEXT NOT NULL,
        review_state TEXT NOT NULL,
        missing_answer_acknowledged INTEGER NOT NULL DEFAULT 0,
        warnings_json TEXT NOT NULL DEFAULT '[]',
        content_fingerprint TEXT NOT NULL DEFAULT '',
        duplicate_of_question_id TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS question_suggestions (
        id TEXT PRIMARY KEY,
        organization_job_id TEXT NOT NULL,
        target_draft_id TEXT NOT NULL REFERENCES question_drafts(id),
        base_draft_revision INTEGER NOT NULL,
        proposed_content_json TEXT NOT NULL,
        proposed_metadata_json TEXT NOT NULL,
        source_block_ids_json TEXT NOT NULL DEFAULT '[]',
        state TEXT NOT NULL,
        note TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        current_revision_id TEXT NOT NULL REFERENCES question_revisions(id),
        status TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS question_revisions (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES questions(id),
        content_json TEXT NOT NULL,
        metadata_json TEXT NOT NULL,
        answer_state TEXT NOT NULL,
        content_fingerprint TEXT NOT NULL,
        confirmed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS question_sources (
        question_id TEXT NOT NULL REFERENCES questions(id),
        source_span_json TEXT NOT NULL,
        import_id TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS question_submissions (
        submission_id TEXT PRIMARY KEY,
        request_fingerprint TEXT NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS question_jobs (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        state TEXT NOT NULL,
        checkpoint_json TEXT NOT NULL DEFAULT '{}',
        error_code TEXT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
)

_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_question_source_blocks_import "
    "ON question_source_blocks(import_id, ordinal)",
    "CREATE INDEX IF NOT EXISTS idx_question_drafts_import ON question_drafts(import_id)",
    "CREATE INDEX IF NOT EXISTS idx_question_suggestions_job "
    "ON question_suggestions(organization_job_id, state)",
    "CREATE INDEX IF NOT EXISTS idx_question_suggestions_draft "
    "ON question_suggestions(target_draft_id)",
    "CREATE INDEX IF NOT EXISTS idx_question_revisions_question "
    "ON question_revisions(question_id)",
    "CREATE INDEX IF NOT EXISTS idx_question_sources_question ON question_sources(question_id)",
    "CREATE INDEX IF NOT EXISTS idx_questions_owner ON questions(owner_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_question_jobs_state ON question_jobs(kind, state)",
)


def migrate(connection: sqlite3.Connection) -> None:
    """建表建索引；重复调用不改变既有数据。"""
    for statement in _TABLES:
        connection.execute(statement)
    for statement in _INDEXES:
        connection.execute(statement)
