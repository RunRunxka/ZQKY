"""教学业务库迁移（B0 基础表 + B1 业务表，2026-09-30 登记）。

B0（``0001``）只含公共基础：提交幂等、受管资产登记（``file_assets``）与通用任务。
B1（``0002``）按设计 ``docs/design/teaching-loop-v1/sql/teaching.sql`` 逐字登记班级、
学生与归属历史三表及其索引，并补齐设计未定义、由 B1 任务卡冻结的名单导入批次表
（``roster_imports`` / ``roster_import_rows``）。

施测三表（``assessments`` / ``assessment_classes`` / ``assessment_participants``）**不在本迁移**：
真实施测创建依赖已确认原卷修订（B2-T40），其 DDL 含指向 ``paper_revisions`` 的复合外键与触发器，
由 T30-b 与 T40 一并登记，避免冻结一个无法校验的半结构；本批只冻结请求/人次/快照**契约**。

偏差记录（相对设计参考 SQL）：``roster_import_rows`` 额外保存可查询的 ``name``/``student_no``
（身份匹配与重复行检测需要按值查询，raw_cells_json 只作审计原文）；``roster_imports`` 的
``file_asset_id`` 是本库 ``file_assets(id)`` 的真实外键（同库）。

追加纪律：``0001`` 的声明语句与散列**不得改写**；结构变化一律新增迁移。
"""

from __future__ import annotations

from app.core.migrations.base import Migration

_BASELINE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS command_submissions (
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
    CREATE TABLE IF NOT EXISTS file_assets (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL DEFAULT 'local',
        kind TEXT NOT NULL CHECK (
            kind IN ('roster','score_sheet','paper','export','attachment')
        ),
        blob_key TEXT NOT NULL,
        sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
        original_name TEXT NOT NULL,
        media_type TEXT NOT NULL,
        byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workflow_jobs (
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
    "CREATE INDEX IF NOT EXISTS idx_workflow_jobs_state ON workflow_jobs(state, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_workflow_jobs_kind ON workflow_jobs(kind, state)",
    "CREATE INDEX IF NOT EXISTS idx_file_assets_kind ON file_assets(kind, created_at)",
)

#: B1 业务表：设计三表逐字 + 索引；名单导入批次表为 B1 冻结补齐。
_BUSINESS_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS classes (
        id TEXT PRIMARY KEY NOT NULL,
        owner_id TEXT NOT NULL DEFAULT 'local',
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        school_year TEXT NOT NULL,
        grade_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        UNIQUE(owner_id,school_year,code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY NOT NULL,
        owner_id TEXT NOT NULL DEFAULT 'local',
        student_no TEXT,
        name TEXT NOT NULL CHECK(length(trim(name))>0),
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        UNIQUE(owner_id,student_no),
        CHECK(student_no IS NULL OR length(trim(student_no))>0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS class_memberships (
        id TEXT PRIMARY KEY NOT NULL,
        class_id TEXT NOT NULL REFERENCES classes(id),
        student_id TEXT NOT NULL REFERENCES students(id),
        joined_on TEXT NOT NULL,
        left_on TEXT,
        CHECK(left_on IS NULL OR left_on>=joined_on),
        UNIQUE(class_id,student_id,joined_on)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS roster_imports (
        id TEXT PRIMARY KEY NOT NULL,
        owner_id TEXT NOT NULL DEFAULT 'local',
        class_id TEXT NOT NULL REFERENCES classes(id),
        file_asset_id TEXT NOT NULL REFERENCES file_assets(id),
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
    CREATE TABLE IF NOT EXISTS roster_import_rows (
        import_id TEXT NOT NULL REFERENCES roster_imports(id),
        row_no INTEGER NOT NULL CHECK(row_no>0),
        name TEXT NOT NULL DEFAULT '',
        student_no TEXT NULL,
        matched_student_id TEXT NULL REFERENCES students(id),
        decision TEXT NULL CHECK(decision IN ('link','create','ignore')),
        raw_cells_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(raw_cells_json)),
        issues_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(issues_json)),
        PRIMARY KEY(import_id, row_no)
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_active_membership "
    "ON class_memberships(class_id,student_id) WHERE left_on IS NULL",
    "CREATE INDEX IF NOT EXISTS ix_membership_student ON class_memberships(student_id)",
    "CREATE INDEX IF NOT EXISTS idx_classes_status ON classes(status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_students_status ON students(status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_roster_imports_class ON roster_imports(class_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_roster_imports_state ON roster_imports(state, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_roster_import_rows_student "
    "ON roster_import_rows(matched_student_id)",
    "CREATE INDEX IF NOT EXISTS idx_roster_import_rows_no ON roster_import_rows(student_no)",
)

MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        id="0001_teaching_baseline",
        description="教学库基础表（提交幂等 + 受管资产登记 + 通用任务）",
        statements=_BASELINE_STATEMENTS,
    ),
    Migration(
        id="0002_teaching_business_tables",
        description=(
            "班级/学生/归属历史（设计三表）+ 名单导入批次表"
            "（roster_imports/roster_import_rows，B1 冻结补齐）；施测三表留待 T30-b"
        ),
        statements=_BUSINESS_STATEMENTS,
    ),
)

