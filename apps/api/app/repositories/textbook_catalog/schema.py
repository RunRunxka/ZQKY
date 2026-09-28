"""教材目录建库 DDL：表名、字段与顺序严格对应 RAG-REBUILD v1.0 数据库规格。

约束：
- 迁移幂等：只用 ``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF NOT EXISTS``，
  不重建、不删除、不改写既有行；``catalog_state`` 的 id=1 行用 ``INSERT OR IGNORE`` 补齐。
- ``documents.current_metadata_revision_id`` 与 ``document_metadata_revisions.document_id`` 互为环形外键，
  写入方在同一事务内用 ``PRAGMA defer_foreign_keys`` 延后校验。
"""

from __future__ import annotations

import sqlite3

_TABLES: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS catalog_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        active_generation_id TEXT NULL,
        rebuild_job_id TEXT NULL,
        catalog_version INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embedding_profiles (
        id TEXT PRIMARY KEY,
        fingerprint TEXT UNIQUE NOT NULL,
        adapter TEXT NOT NULL,
        native_base_url TEXT NOT NULL,
        model_name TEXT NOT NULL,
        model_manifest_digest TEXT NOT NULL,
        dimensions INTEGER NOT NULL,
        distance TEXT NOT NULL,
        query_prefix TEXT NOT NULL DEFAULT '',
        document_prefix TEXT NOT NULL DEFAULT '',
        normalization TEXT NOT NULL DEFAULT 'none',
        options_json TEXT NOT NULL DEFAULT '{}',
        verified_at TEXT NOT NULL,
        retired_at TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS index_generations (
        id TEXT PRIMARY KEY,
        profile_id TEXT NOT NULL REFERENCES embedding_profiles(id),
        collection_name TEXT UNIQUE NOT NULL,
        chunk_policy_json TEXT NOT NULL DEFAULT '{}',
        state TEXT NOT NULL,
        created_at TEXT NOT NULL,
        published_at TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS libraries (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        grade_id TEXT NULL,
        subject_id TEXT NOT NULL,
        edition_id TEXT NOT NULL,
        display_name TEXT NOT NULL,
        revision INTEGER NOT NULL DEFAULT 0,
        deleted_at TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        origin_key TEXT NULL,
        current_revision_id TEXT NULL REFERENCES document_revisions(id),
        current_metadata_revision_id TEXT NOT NULL REFERENCES document_metadata_revisions(id),
        revision INTEGER NOT NULL DEFAULT 0,
        deleted_at TEXT NULL,
        UNIQUE(owner_id, origin_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS library_documents (
        library_id TEXT NOT NULL REFERENCES libraries(id),
        document_id TEXT NOT NULL REFERENCES documents(id),
        PRIMARY KEY(library_id, document_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_metadata_revisions (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL REFERENCES documents(id),
        title TEXT NOT NULL,
        stage_id TEXT NOT NULL,
        grade_ids_json TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        edition_id TEXT NOT NULL,
        publication_label TEXT NOT NULL DEFAULT '',
        volume_label TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_revisions (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL REFERENCES documents(id),
        original_file_sha256 TEXT NOT NULL,
        normalized_text_sha256 TEXT NOT NULL,
        parser_version TEXT NOT NULL,
        original_blob_id TEXT NOT NULL,
        normalized_blob_id TEXT NOT NULL,
        source_map_blob_id TEXT NOT NULL,
        char_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunk_sets (
        id TEXT PRIMARY KEY,
        document_revision_id TEXT NOT NULL REFERENCES document_revisions(id),
        policy_fingerprint TEXT NOT NULL,
        manifest_sha256 TEXT NOT NULL,
        chunk_count INTEGER NOT NULL DEFAULT 0,
        sealed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
        chunk_set_id TEXT NOT NULL REFERENCES chunk_sets(id),
        ordinal INTEGER NOT NULL,
        char_start INTEGER NOT NULL,
        char_end INTEGER NOT NULL,
        region TEXT NOT NULL,
        chapter_path_json TEXT NOT NULL DEFAULT '[]',
        text_sha256 TEXT NOT NULL,
        legacy_chunk_id TEXT NULL,
        PRIMARY KEY(chunk_set_id, ordinal)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS generation_revisions (
        generation_id TEXT NOT NULL REFERENCES index_generations(id),
        document_revision_id TEXT NOT NULL REFERENCES document_revisions(id),
        chunk_set_id TEXT NOT NULL REFERENCES chunk_sets(id),
        state TEXT NOT NULL,
        expected_chunk_count INTEGER NOT NULL DEFAULT 0,
        manifest_sha256 TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(generation_id, document_revision_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS import_drafts (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        target_document_id TEXT NULL,
        expected_current_revision_id TEXT NULL,
        metadata_json TEXT NULL,
        uploaded_blob_id TEXT NOT NULL,
        uploaded_file_name TEXT NOT NULL,
        uploaded_bytes INTEGER NOT NULL DEFAULT 0,
        parsed_artifacts_json TEXT NULL,
        state TEXT NOT NULL,
        revision INTEGER NOT NULL DEFAULT 0,
        warnings_json TEXT NOT NULL DEFAULT '[]',
        error_code TEXT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS index_jobs (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        input_revision_id TEXT NULL,
        document_id TEXT NULL,
        metadata_revision_id TEXT NULL,
        target_generation_id TEXT NULL,
        base_generation_id TEXT NULL,
        state TEXT NOT NULL,
        idempotency_key TEXT UNIQUE,
        request_fingerprint TEXT NOT NULL DEFAULT '',
        attempt INTEGER NOT NULL DEFAULT 0,
        lease_token TEXT NULL,
        lease_until TEXT NULL,
        checkpoint_json TEXT NOT NULL DEFAULT '{}',
        error_code TEXT NULL,
        error_message TEXT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cleanup_queue (
        document_id TEXT PRIMARY KEY,
        enqueued_at TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS teaching_settings (
        owner_id TEXT PRIMARY KEY,
        selection_json TEXT NULL,
        revision INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NULL
    )
    """,
)

_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_libraries_scope "
    "ON libraries(kind, grade_id, subject_id, edition_id)",
    "CREATE INDEX IF NOT EXISTS idx_library_documents_document "
    "ON library_documents(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_metadata_revisions_document "
    "ON document_metadata_revisions(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_document_revisions_document "
    "ON document_revisions(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_chunk_sets_revision "
    "ON chunk_sets(document_revision_id)",
    "CREATE INDEX IF NOT EXISTS idx_generation_revisions_generation "
    "ON generation_revisions(generation_id, state)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_state ON index_jobs(state, kind)",
    "CREATE INDEX IF NOT EXISTS idx_imports_target ON import_drafts(target_document_id)",
)


def migrate(connection: sqlite3.Connection) -> None:
    """建表并补齐单行 catalog_state；重复调用不改变既有数据。"""
    for statement in _TABLES:
        connection.execute(statement)
    connection.execute(
        "INSERT OR IGNORE INTO catalog_state "
        "(id, active_generation_id, rebuild_job_id, catalog_version) VALUES (1, NULL, NULL, 0)"
    )
    for statement in _INDEXES:
        connection.execute(statement)
