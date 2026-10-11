"""知识点库迁移（B0 基础表 + B1 业务表，2026-09-30 登记）。

B0（``0001``）只含公共基础（提交幂等 + 任务）。B1（``0002``）按设计
``docs/design/teaching-loop-v1/sql/knowledge.sql`` 逐字登记 5 张设计表与索引/触发器，
并补齐设计未定义、由 B1 任务卡冻结的导入批次表
（``knowledge_imports`` / ``knowledge_import_rows``；AI 候选复用同一批次与确认流程）。

追加纪律：``0001`` 的声明语句与散列**不得改写**；结构变化一律新增迁移。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from app.core.migrations.base import Migration

_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS knowledge_submissions (
        owner_id TEXT NOT NULL,
        operation TEXT NOT NULL,
        submission_id TEXT NOT NULL,
        request_hash TEXT NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (owner_id, operation, submission_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_jobs (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL DEFAULT 'local',
        kind TEXT NOT NULL,
        state TEXT NOT NULL CHECK (
            state IN ('queued','running','succeeded','failed','cancelled','interrupted')
        ),
        frozen_input_json TEXT NOT NULL DEFAULT '{}',
        input_hash TEXT NOT NULL DEFAULT '',
        model_snapshot_json TEXT NOT NULL DEFAULT '{}',
        attempt INTEGER NOT NULL DEFAULT 0,
        lease_token TEXT NULL,
        lease_expires_at TEXT NULL,
        cancel_requested INTEGER NOT NULL DEFAULT 0,
        checkpoint_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT NULL,
        error_code TEXT NULL,
        error_json TEXT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        started_at TEXT NULL,
        finished_at TEXT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_knowledge_jobs_state ON knowledge_jobs(state, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_jobs_kind ON knowledge_jobs(kind, state)",
)

#: B1 业务表：设计 SQL 逐字（含 CHECK/UNIQUE/复合外键/可延迟外键/触发器）
_BUSINESS_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS subjects (
        id TEXT PRIMARY KEY NOT NULL,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_points (
        id TEXT PRIMARY KEY NOT NULL,
        subject_id TEXT NOT NULL REFERENCES subjects(id),
        code TEXT NOT NULL,
        parent_id TEXT,
        current_revision_id TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        UNIQUE(subject_id,code),
        UNIQUE(id,subject_id),
        FOREIGN KEY(parent_id,subject_id) REFERENCES knowledge_points(id,subject_id),
        FOREIGN KEY(current_revision_id,id) REFERENCES knowledge_point_revisions(id,knowledge_point_id) DEFERRABLE INITIALLY DEFERRED,
        CHECK(parent_id IS NULL OR parent_id<>id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_point_revisions (
        id TEXT PRIMARY KEY NOT NULL,
        knowledge_point_id TEXT NOT NULL REFERENCES knowledge_points(id),
        version INTEGER NOT NULL CHECK(version>0),
        name TEXT NOT NULL CHECK(length(trim(name))>0),
        description TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        UNIQUE(knowledge_point_id,version),
        UNIQUE(id,knowledge_point_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_aliases (
        id TEXT PRIMARY KEY NOT NULL,
        knowledge_point_id TEXT NOT NULL REFERENCES knowledge_points(id),
        alias TEXT NOT NULL CHECK(length(trim(alias))>0),
        normalized_alias TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        UNIQUE(knowledge_point_id,normalized_alias)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS textbook_knowledge_links (
        id TEXT PRIMARY KEY NOT NULL,
        knowledge_point_id TEXT NOT NULL,
        knowledge_revision_id TEXT NOT NULL,
        document_revision_id TEXT NOT NULL,
        locator_json TEXT NOT NULL CHECK(json_valid(locator_json)),
        locator_hash TEXT NOT NULL,
        title_snapshot TEXT NOT NULL,
        source TEXT NOT NULL CHECK(source IN ('human','ai_confirmed')),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        FOREIGN KEY(knowledge_revision_id,knowledge_point_id) REFERENCES knowledge_point_revisions(id,knowledge_point_id),
        UNIQUE(knowledge_revision_id,document_revision_id,locator_hash)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_kp_parent ON knowledge_points(parent_id)",
    "CREATE INDEX IF NOT EXISTS ix_alias_search ON knowledge_aliases(normalized_alias)",
    "CREATE INDEX IF NOT EXISTS ix_textbook_doc ON textbook_knowledge_links(document_revision_id)",
    """
    CREATE TRIGGER IF NOT EXISTS kp_cycle_update BEFORE UPDATE OF parent_id ON knowledge_points WHEN NEW.parent_id IS NOT NULL BEGIN
     SELECT CASE WHEN EXISTS(WITH RECURSIVE ancestors(id,parent_id) AS (SELECT id,parent_id FROM knowledge_points WHERE id=NEW.parent_id UNION SELECT p.id,p.parent_id FROM knowledge_points p JOIN ancestors a ON p.id=a.parent_id) SELECT 1 FROM ancestors WHERE id=NEW.id) THEN RAISE(ABORT,'KNOWLEDGE_CYCLE') END;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS kp_cycle_insert AFTER INSERT ON knowledge_points WHEN NEW.parent_id IS NOT NULL BEGIN
     SELECT CASE WHEN EXISTS(WITH RECURSIVE ancestors(id,parent_id) AS (SELECT id,parent_id FROM knowledge_points WHERE id=NEW.parent_id UNION SELECT p.id,p.parent_id FROM knowledge_points p JOIN ancestors a ON p.id=a.parent_id) SELECT 1 FROM ancestors WHERE id=NEW.id) THEN RAISE(ABORT,'KNOWLEDGE_CYCLE') END;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS immutable_knowledge_point_revisions_update BEFORE UPDATE ON knowledge_point_revisions BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS immutable_knowledge_point_revisions_delete BEFORE DELETE ON knowledge_point_revisions BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    # ---- B1 冻结补齐：导入批次与预览行（设计未定义；人工导入与 AI 候选共用）
    """
    CREATE TABLE IF NOT EXISTS knowledge_imports (
        id TEXT PRIMARY KEY NOT NULL,
        owner_id TEXT NOT NULL DEFAULT 'local',
        source TEXT NOT NULL CHECK(source IN ('file','ai')),
        subject_id TEXT NOT NULL REFERENCES subjects(id),
        file_asset_id TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'uploaded'
            CHECK(state IN ('uploaded','reviewing','confirmed','failed','cancelled')),
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
        mapping_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(mapping_json)),
        warnings_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(warnings_json)),
        error_code TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_import_rows (
        import_id TEXT NOT NULL REFERENCES knowledge_imports(id),
        row_no INTEGER NOT NULL CHECK(row_no>0),
        name TEXT NOT NULL DEFAULT '',
        code TEXT NOT NULL DEFAULT '',
        parent_code TEXT NULL,
        description TEXT NOT NULL DEFAULT '',
        aliases_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(aliases_json)),
        target_knowledge_point_id TEXT NULL REFERENCES knowledge_points(id),
        base_revision INTEGER NULL,
        base_revision_id TEXT NULL,
        decision TEXT NULL CHECK(decision IN ('create','update','ignore')),
        raw_cells_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(raw_cells_json)),
        issues_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(issues_json)),
        PRIMARY KEY(import_id, row_no)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_knowledge_imports_state "
    "ON knowledge_imports(state, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_knowledge_import_rows_point "
    "ON knowledge_import_rows(target_knowledge_point_id)",
    "CREATE INDEX IF NOT EXISTS ix_knowledge_import_rows_code "
    "ON knowledge_import_rows(code)",
)

#: B1 补齐（0003）：批次级 issues 的独立列。0002 冻结时只给了 mapping/warnings，
#: 批次级问题（缺列/未知列）无列可落，实现者一度塞进 ``mapping_json`` 的保留键——
#: 语义混装。按"只追加迁移"补列，调用方改用本列（外部视图形状不变）。
#: ``adjust`` 钩子按"列已存在则跳过 ALTER"过滤（V00 O1：手工加列/部分恢复的库不致
#: 因 duplicate column 抛原始 sqlite3 错误）；声明集合不变，散列不变。
_IMPORT_ISSUES_COLUMN: tuple[str, ...] = (
    "ALTER TABLE knowledge_imports ADD COLUMN issues_json TEXT NOT NULL DEFAULT '[]'",
)


def _skip_existing_issues_column(connection: sqlite3.Connection) -> Sequence[str]:
    present = {
        row[1] for row in connection.execute("PRAGMA table_info(knowledge_imports)")
    }
    if "issues_json" in present:
        return ()
    return _IMPORT_ISSUES_COLUMN

MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        id="0001_knowledge_baseline",
        description="知识点库基础表（提交幂等 + 任务）",
        statements=_BASELINE_STATEMENTS,
    ),
    Migration(
        id="0002_knowledge_business_tables",
        description=(
            "知识点业务表（设计 5 表 + 索引/触发器）+ 导入批次表"
            "（knowledge_imports/knowledge_import_rows，B1 冻结补齐）"
        ),
        statements=_BUSINESS_STATEMENTS,
    ),
    Migration(
        id="0003_knowledge_import_issues_column",
        description="knowledge_imports 补齐批次级 issues_json 列（导入预览的批次问题独立落列）",
        statements=_IMPORT_ISSUES_COLUMN,
        adjust=_skip_existing_issues_column,
    ),
)

