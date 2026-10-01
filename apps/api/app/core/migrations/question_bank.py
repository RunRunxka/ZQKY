"""题库库迁移（冻结基线 + 任务引擎增量 + B2 知识点关联，2026-09-30 登记）。

``0001`` 与 RAG-REBUILD v1.0 的 ``app/repositories/question_bank/schema.py`` 逐字一致；
``0002`` 按计划书 §二.2 给既有 ``question_jobs`` 补齐任务引擎列（冻结输入、输入散列、
attempt、租约、取消标志、结果、更新时间）。``ALTER TABLE`` 的幂等由 ``adjust`` 钩子
按 ``PRAGMA table_info`` 过滤已存在的列；**声明语句集合**（散列对象）不含钩子结果。
``0004``（B2）登记正式题修订—知识点关联（设计 ``sql/question_bank_extension.sql`` 逐字 +
不可变触发器），并补齐设计未定义的草稿关联、生成来源与版本化内容指纹。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from app.core.migrations.base import Migration

_BASELINE_STATEMENTS: tuple[str, ...] = (
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

#: 0002 增量：任务引擎列（列名 → ALTER 语句）。声明集合据此生成，顺序固定。
_JOB_ENGINE_COLUMNS: tuple[tuple[str, str], ...] = (
    (
        "owner_id",
        "ALTER TABLE question_jobs ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'local'",
    ),
    (
        "frozen_input_json",
        "ALTER TABLE question_jobs ADD COLUMN frozen_input_json TEXT NOT NULL DEFAULT '{}'",
    ),
    (
        "input_hash",
        "ALTER TABLE question_jobs ADD COLUMN input_hash TEXT NOT NULL DEFAULT ''",
    ),
    (
        "model_snapshot_json",
        "ALTER TABLE question_jobs ADD COLUMN model_snapshot_json TEXT NOT NULL DEFAULT '{}'",
    ),
    (
        "attempt",
        "ALTER TABLE question_jobs ADD COLUMN attempt INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "lease_token",
        "ALTER TABLE question_jobs ADD COLUMN lease_token TEXT NULL",
    ),
    (
        "lease_expires_at",
        "ALTER TABLE question_jobs ADD COLUMN lease_expires_at TEXT NULL",
    ),
    (
        "cancel_requested",
        "ALTER TABLE question_jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "result_json",
        "ALTER TABLE question_jobs ADD COLUMN result_json TEXT NULL",
    ),
    (
        "error_json",
        "ALTER TABLE question_jobs ADD COLUMN error_json TEXT NULL",
    ),
    (
        "started_at",
        "ALTER TABLE question_jobs ADD COLUMN started_at TEXT NULL",
    ),
    (
        "finished_at",
        "ALTER TABLE question_jobs ADD COLUMN finished_at TEXT NULL",
    ),
)

_ENGINE_INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_question_jobs_engine_state "
    "ON question_jobs(state, created_at)",
)

_ENGINE_STATEMENTS: tuple[str, ...] = tuple(
    statement for _column, statement in _JOB_ENGINE_COLUMNS
) + _ENGINE_INDEX_STATEMENTS


def _skip_existing_columns(connection: sqlite3.Connection) -> Sequence[str]:
    """按库现状过滤 ALTER 语句；**非 ALTER 的声明语句一律保留**。

    T00-a-02（V00 独立验收发现）：本钩子最初只返回 ALTER，把声明集合里的
    ``CREATE INDEX ... idx_question_jobs_engine_state`` 一起丢掉——语句从未执行，
    而登记散列覆盖的是声明集合，漂移校验也不会揭示。这里显式保留索引语句；
    已应用过 0002 的既有库由 ``0003_question_jobs_engine_state_index`` 补齐。
    """
    present = {row[1] for row in connection.execute("PRAGMA table_info(question_jobs)")}
    statements = [
        statement
        for column, statement in _JOB_ENGINE_COLUMNS
        if column not in present
    ]
    statements.extend(_ENGINE_INDEX_STATEMENTS)
    return tuple(statements)


#: B2（0004）：正式关联表为设计 ``sql/question_bank_extension.sql`` 逐字（含不可变触发器）；
#: 其余三张为设计未定义、由 B2 任务卡冻结补齐（草稿关联、生成来源、版本化派生指纹）。
_B2_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS question_knowledge_links (
        question_revision_id TEXT NOT NULL REFERENCES question_revisions(id),
        knowledge_point_id TEXT NOT NULL,
        knowledge_revision_id TEXT NOT NULL,
        subject_id_snapshot TEXT NOT NULL,
        knowledge_name_snapshot TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('primary','secondary')),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        PRIMARY KEY(question_revision_id,knowledge_point_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_question_knowledge "
    "ON question_knowledge_links(knowledge_point_id,question_revision_id)",
    """
    CREATE TRIGGER IF NOT EXISTS immutable_question_knowledge_links_update BEFORE UPDATE ON question_knowledge_links BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS immutable_question_knowledge_links_delete BEFORE DELETE ON question_knowledge_links BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TABLE IF NOT EXISTS question_draft_knowledge_links (
        draft_id TEXT NOT NULL REFERENCES question_drafts(id),
        knowledge_point_id TEXT NOT NULL,
        knowledge_revision_id TEXT NOT NULL,
        subject_id_snapshot TEXT NOT NULL,
        knowledge_name_snapshot TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('primary','secondary')),
        source TEXT NOT NULL CHECK(source IN ('human','ai')),
        created_at TEXT NOT NULL,
        PRIMARY KEY(draft_id, knowledge_point_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_draft_knowledge "
    "ON question_draft_knowledge_links(knowledge_point_id)",
    """
    CREATE TABLE IF NOT EXISTS question_import_provenance (
        import_id TEXT PRIMARY KEY REFERENCES question_imports(id),
        source TEXT NOT NULL CHECK(source IN ('upload','ai','rule','manual')),
        job_id TEXT NULL,
        model_snapshot_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(model_snapshot_json)),
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS question_content_fingerprints (
        question_revision_id TEXT NOT NULL REFERENCES question_revisions(id),
        algorithm_version TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(question_revision_id, algorithm_version)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_question_fingerprint "
    "ON question_content_fingerprints(fingerprint)",
)


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        id="0001_question_bank_baseline",
        description="题库基线（RAG-REBUILD v1.0 九表结构，冻结）",
        statements=_BASELINE_STATEMENTS,
    ),
    Migration(
        id="0002_question_jobs_engine_columns",
        description="question_jobs 补齐任务引擎列（B0 冻结输入/租约/取消/结果）",
        statements=_ENGINE_STATEMENTS,
        adjust=_skip_existing_columns,
    ),
    Migration(
        id="0003_question_jobs_engine_state_index",
        description="question_jobs 补齐 (state, created_at) 索引（修复 0002 钩子漏执行；既有库由此补齐）",
        statements=_ENGINE_INDEX_STATEMENTS,
    ),
    Migration(
        id="0004_question_knowledge_links",
        description=(
            "正式题修订—知识点关联（设计逐字 + 不可变触发器）+ 草稿关联、"
            "生成来源与版本化内容指纹（B2 冻结补齐）"
        ),
        statements=_B2_STATEMENTS,
    ),
)
