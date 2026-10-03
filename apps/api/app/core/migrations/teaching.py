"""教学业务库迁移（B0 基础表 + B1 业务表 + B2 原卷/施测表，2026-09-30 登记）。

B0（``0001``）只含公共基础：提交幂等、受管资产登记（``file_assets``）与通用任务。
B1（``0002``）按设计 ``docs/design/teaching-loop-v1/sql/teaching.sql`` 逐字登记班级、
学生与归属历史三表及其索引，并补齐设计未定义、由 B1 任务卡冻结的名单导入批次表
（``roster_imports`` / ``roster_import_rows``）。
B2（``0003``/``0004``）登记原卷四表与施测三表，并补齐全套触发器（父子环、确认闸门、
确认后冻结、只用已确认卷、施测不换卷）。

**B2 分期偏差（相对设计参考 SQL，均由 B2 任务卡冻结）**：

- ``paper_revisions.source_file_id`` **NOT NULL**（设计可空 + 「原卷/练习二选一」CHECK）：
  本批原卷只能来自受管原件，来源完整性不放宽；
- ``paper_revisions.source_practice_revision_id`` 保留列但 ``CHECK(... IS NULL)`` 且**不建外键**
  （``practice_revisions`` 属未来批次）——本批拒绝非空写入；
- ``paper_revisions.total_score_units`` 允许 0（设计 ``>0``）：草稿在教师补分前可能尚无计分叶子，
  **确认闸门**（触发器 + 服务）要求 >0 且等于计分叶子合计；
- ``paper_confirm`` 触发器去掉了 ``PRACTICE_NOT_REVIEWED`` 分支（同因未来表）；
- ``assessments.active_score_revision_id`` 保留列但 ``CHECK(... IS NULL)`` 且**不建外键**
  （``score_revisions`` 属 B3）；
- ``assessment_participants`` 增加 ``class_confirmed``/``class_confirmation_note``/
  ``class_confirmation_at``（B2 要求：施测日期未被历史归属覆盖时教师显式确认并保存依据）；
- B2 新增表 ``paper_source_blocks``、``paper_issues``（设计未定义，B2 冻结补齐）与设计表 ``ai_proposals``；
  确认后它们同样被冻结触发器保护。

追加纪律：``0001``/``0002`` 的声明语句与散列**不得改写**；结构变化一律新增迁移。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from app.core.migrations.base import Migration, RebuildPlan

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

#: B2（0003）：原卷四表（设计逐字，分期偏差见模块 docstring）+ B2 补齐结构
#: （原文块、问题处置、AI 建议）与触发器（父子环、确认闸门、确认后冻结）。
_PAPER_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS papers (
        id TEXT PRIMARY KEY NOT NULL,
        owner_id TEXT NOT NULL DEFAULT 'local',
        subject_id TEXT NOT NULL,
        title TEXT NOT NULL,
        current_revision_id TEXT,
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        FOREIGN KEY(current_revision_id,id) REFERENCES paper_revisions(id,paper_id) DEFERRABLE INITIALLY DEFERRED
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_revisions (
        id TEXT PRIMARY KEY NOT NULL,
        paper_id TEXT NOT NULL REFERENCES papers(id),
        version INTEGER NOT NULL CHECK(version>0),
        source_file_id TEXT NOT NULL REFERENCES file_assets(id),
        -- 分期：指向未来 practice_revisions；B2 不建外键，且以 CHECK 拒绝非空写入
        source_practice_revision_id TEXT NULL CHECK(source_practice_revision_id IS NULL),
        total_score_units INTEGER NOT NULL CHECK(total_score_units>=0),
        state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','confirmed')),
        confirmed_at TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        UNIQUE(paper_id,version),
        UNIQUE(id,paper_id),
        CHECK((state='draft' AND confirmed_at IS NULL) OR (state='confirmed' AND confirmed_at IS NOT NULL))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_items (
        id TEXT PRIMARY KEY NOT NULL,
        paper_revision_id TEXT NOT NULL REFERENCES paper_revisions(id),
        parent_item_id TEXT,
        question_no TEXT NOT NULL,
        ordinal INTEGER NOT NULL CHECK(ordinal>0),
        is_scored INTEGER NOT NULL CHECK(is_scored IN (0,1)),
        max_score_units INTEGER,
        question_revision_id TEXT,
        content_json TEXT NOT NULL CHECK(json_valid(content_json)),
        source_locator_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(source_locator_json)),
        UNIQUE(paper_revision_id,question_no),
        UNIQUE(paper_revision_id,ordinal),
        UNIQUE(id,paper_revision_id),
        FOREIGN KEY(parent_item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id),
        CHECK(parent_item_id IS NULL OR parent_item_id<>id),
        CHECK((is_scored=1 AND max_score_units IS NOT NULL AND max_score_units>0) OR (is_scored=0 AND max_score_units IS NULL))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_item_knowledge (
        item_id TEXT NOT NULL,
        paper_revision_id TEXT NOT NULL,
        knowledge_point_id TEXT NOT NULL,
        knowledge_revision_id TEXT NOT NULL,
        knowledge_name_snapshot TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('primary','secondary')),
        source TEXT NOT NULL CHECK(source IN ('human','ai_confirmed','bank_confirmed')),
        PRIMARY KEY(item_id,knowledge_point_id),
        FOREIGN KEY(item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id)
    )
    """,
    # ---- B2 补齐：原文块（归属/排除）、问题清单（可解决/可排除）、AI 建议（设计 ai_proposals）
    """
    CREATE TABLE IF NOT EXISTS paper_source_blocks (
        id TEXT PRIMARY KEY NOT NULL,
        paper_revision_id TEXT NOT NULL REFERENCES paper_revisions(id),
        ordinal INTEGER NOT NULL CHECK(ordinal>0),
        kind TEXT NOT NULL CHECK(kind IN ('paragraph','table','formula','image','unknown')),
        block_json TEXT NOT NULL CHECK(json_valid(block_json)),
        locator_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(locator_json)),
        disposition TEXT NOT NULL DEFAULT 'unassigned'
            CHECK(disposition IN ('item','shared_material','excluded','unassigned')),
        item_id TEXT NULL,
        exclude_reason TEXT NULL,
        UNIQUE(paper_revision_id,ordinal),
        FOREIGN KEY(item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id),
        CHECK(disposition<>'excluded' OR (exclude_reason IS NOT NULL AND length(trim(exclude_reason))>0)),
        CHECK(disposition='item' OR item_id IS NULL),
        CHECK(disposition='item' OR disposition='excluded' OR exclude_reason IS NULL)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_issues (
        id TEXT PRIMARY KEY NOT NULL,
        paper_revision_id TEXT NOT NULL REFERENCES paper_revisions(id),
        code TEXT NOT NULL,
        severity TEXT NOT NULL CHECK(severity IN ('info','warning','blocking')),
        message TEXT NOT NULL,
        block_id TEXT NULL,
        locator_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(locator_json)),
        status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','excluded')),
        resolution_json TEXT NULL CHECK(resolution_json IS NULL OR json_valid(resolution_json)),
        created_at TEXT NOT NULL,
        UNIQUE(id,paper_revision_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_proposals (
        id TEXT PRIMARY KEY NOT NULL,
        job_id TEXT NOT NULL REFERENCES workflow_jobs(id),
        target_kind TEXT NOT NULL CHECK(target_kind IN ('paper_revision','lesson_revision')),
        target_id TEXT NOT NULL,
        base_revision INTEGER NOT NULL CHECK(base_revision>=0),
        payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
        state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','applied','rejected','stale')),
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_paper_kp ON paper_item_knowledge(knowledge_point_id,item_id)",
    "CREATE INDEX IF NOT EXISTS idx_paper_blocks_revision "
    "ON paper_source_blocks(paper_revision_id, disposition)",
    "CREATE INDEX IF NOT EXISTS idx_paper_issues_revision "
    "ON paper_issues(paper_revision_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_ai_proposals_target ON ai_proposals(target_kind,target_id,state)",
    """
    CREATE TRIGGER IF NOT EXISTS paper_cycle_update BEFORE UPDATE OF parent_item_id ON paper_items WHEN NEW.parent_item_id IS NOT NULL BEGIN
     SELECT CASE WHEN EXISTS(WITH RECURSIVE ancestors(id,parent_item_id) AS (SELECT id,parent_item_id FROM paper_items WHERE id=NEW.parent_item_id UNION SELECT p.id,p.parent_item_id FROM paper_items p JOIN ancestors a ON p.id=a.parent_item_id) SELECT 1 FROM ancestors WHERE id=NEW.id) THEN RAISE(ABORT,'ITEM_CYCLE') END;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS paper_cycle_insert AFTER INSERT ON paper_items WHEN NEW.parent_item_id IS NOT NULL BEGIN
     SELECT CASE WHEN EXISTS(WITH RECURSIVE ancestors(id,parent_item_id) AS (SELECT id,parent_item_id FROM paper_items WHERE id=NEW.parent_item_id UNION SELECT p.id,p.parent_item_id FROM paper_items p JOIN ancestors a ON p.id=a.parent_item_id) SELECT 1 FROM ancestors WHERE id=NEW.id) THEN RAISE(ABORT,'ITEM_CYCLE') END;
    END
    """,
    # 确认闸门：draft→confirmed 时校验计分叶子/总分/知识点/叶子性；分期去掉了
    # PRACTICE_NOT_REVIEWED 分支（practice_revisions 属未来批次，本批来源只能是原卷文件）
    """
    CREATE TRIGGER IF NOT EXISTS paper_confirm BEFORE UPDATE OF state ON paper_revisions WHEN NEW.state='confirmed' AND OLD.state='draft' BEGIN
     SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM paper_items WHERE paper_revision_id=NEW.id AND is_scored=1) THEN RAISE(ABORT,'NO_SCORED_ITEMS') END;
     SELECT CASE WHEN NEW.total_score_units<>(SELECT coalesce(sum(max_score_units),0) FROM paper_items WHERE paper_revision_id=NEW.id AND is_scored=1) THEN RAISE(ABORT,'PAPER_TOTAL_MISMATCH') END;
     SELECT CASE WHEN EXISTS(SELECT 1 FROM paper_items i WHERE i.paper_revision_id=NEW.id AND i.is_scored=1 AND NOT EXISTS(SELECT 1 FROM paper_item_knowledge k WHERE k.item_id=i.id)) THEN RAISE(ABORT,'ITEM_KNOWLEDGE_MISSING') END;
     SELECT CASE WHEN EXISTS(SELECT 1 FROM paper_items p JOIN paper_items c ON c.parent_item_id=p.id WHERE p.paper_revision_id=NEW.id AND p.is_scored=1) THEN RAISE(ABORT,'SCORED_ITEM_MUST_BE_LEAF') END;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS immutable_paper_revisions_update BEFORE UPDATE ON paper_revisions WHEN OLD.state='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS immutable_paper_revisions_delete BEFORE DELETE ON paper_revisions WHEN OLD.state='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS no_direct_sealed_paper_revisions BEFORE INSERT ON paper_revisions WHEN NEW.state='confirmed' BEGIN SELECT RAISE(ABORT,'USE_CONFIRM_TRANSITION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_items_insert BEFORE INSERT ON paper_items WHEN (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_items_update BEFORE UPDATE ON paper_items WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' OR (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_items_delete BEFORE DELETE ON paper_items WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_item_knowledge_insert BEFORE INSERT ON paper_item_knowledge WHEN (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_item_knowledge_update BEFORE UPDATE ON paper_item_knowledge WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' OR (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_item_knowledge_delete BEFORE DELETE ON paper_item_knowledge WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    # B2 补齐表同样冻结（确认后块归属/处置记录不可增删改，覆盖 UPDATE 改归属与 DELETE）
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_source_blocks_insert BEFORE INSERT ON paper_source_blocks WHEN (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_source_blocks_update BEFORE UPDATE ON paper_source_blocks WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' OR (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_source_blocks_delete BEFORE DELETE ON paper_source_blocks WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_issues_insert BEFORE INSERT ON paper_issues WHEN (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_issues_update BEFORE UPDATE ON paper_issues WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' OR (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS freeze_paper_issues_delete BEFORE DELETE ON paper_issues WHEN (SELECT state FROM paper_revisions WHERE id=OLD.paper_revision_id)='confirmed' BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END
    """,
)

#: B2（0004）：施测三表（设计逐字，分期偏差见模块 docstring：active_score_revision_id 只允许空、
#: 无 score_revisions 外键；assessment_participants 增加"本次班级显式确认"落库列）。
_ASSESSMENT_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS assessments (
        id TEXT PRIMARY KEY NOT NULL,
        owner_id TEXT NOT NULL DEFAULT 'local',
        paper_revision_id TEXT NOT NULL REFERENCES paper_revisions(id),
        title TEXT NOT NULL,
        assessment_type TEXT NOT NULL CHECK(assessment_type IN ('exam','quiz','practice')),
        held_on TEXT NOT NULL,
        -- 分期：指向未来 score_revisions；B2 不建外键，且以 CHECK 拒绝非空写入
        active_score_revision_id TEXT NULL CHECK(active_score_revision_id IS NULL),
        state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','closed','archived')),
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        UNIQUE(id,paper_revision_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS assessment_classes (
        assessment_id TEXT NOT NULL REFERENCES assessments(id),
        class_id TEXT NOT NULL REFERENCES classes(id),
        PRIMARY KEY(assessment_id,class_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS assessment_participants (
        id TEXT PRIMARY KEY NOT NULL,
        assessment_id TEXT NOT NULL,
        student_id TEXT NOT NULL REFERENCES students(id),
        class_id TEXT NOT NULL,
        attempt_no INTEGER NOT NULL DEFAULT 1 CHECK(attempt_no>0),
        attendance TEXT NOT NULL CHECK(attendance IN ('present','absent','exempt')),
        name_snapshot TEXT NOT NULL,
        student_no_snapshot TEXT,
        -- B2 补齐：施测日期未被历史归属覆盖时，教师显式确认本次班级并保存依据
        class_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(class_confirmed IN (0,1)),
        class_confirmation_note TEXT NULL,
        class_confirmation_at TEXT NULL,
        FOREIGN KEY(assessment_id,class_id) REFERENCES assessment_classes(assessment_id,class_id),
        UNIQUE(assessment_id,student_id,attempt_no),
        UNIQUE(id,assessment_id),
        CHECK(class_confirmed=0 OR (class_confirmation_note IS NOT NULL AND length(trim(class_confirmation_note))>0))
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_participant_student "
    "ON assessment_participants(student_id,assessment_id)",
    "CREATE INDEX IF NOT EXISTS idx_participants_assessment "
    "ON assessment_participants(assessment_id, attempt_no)",
    """
    CREATE TRIGGER IF NOT EXISTS assessment_confirmed_paper_insert BEFORE INSERT ON assessments BEGIN
     SELECT CASE WHEN (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)<>'confirmed' THEN RAISE(ABORT,'PAPER_NOT_CONFIRMED') END;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS assessment_paper_fixed BEFORE UPDATE OF paper_revision_id ON assessments WHEN NEW.paper_revision_id<>OLD.paper_revision_id BEGIN SELECT RAISE(ABORT,'ASSESSMENT_PAPER_FIXED'); END
    """,
)

#: B3/G0（0005 · B2-RV11）：修订级标题快照。固定修订必须读自己的标题；
#: 旧数据回填自当前 ``papers.title`` 并标注来源（``backfilled_from_paper``），
#: 不声称还原"当时标题"。``adjust`` 钩子按列存在与否过滤 ALTER（含回填报备）。
_TITLE_SNAPSHOT_COLUMNS: tuple[tuple[str, str], ...] = (
    (
        "title_snapshot",
        "ALTER TABLE paper_revisions ADD COLUMN title_snapshot TEXT NOT NULL DEFAULT ''",
    ),
    (
        "title_snapshot_source",
        "ALTER TABLE paper_revisions ADD COLUMN title_snapshot_source TEXT NULL",
    ),
)
_TITLE_BACKFILL = (
    "UPDATE paper_revisions SET "
    "title_snapshot = (SELECT title FROM papers WHERE papers.id = paper_revisions.paper_id), "
    "title_snapshot_source = 'backfilled_from_paper' "
    "WHERE title_snapshot = ''"
)
_TITLE_SNAPSHOT_STATEMENTS: tuple[str, ...] = tuple(
    statement for _column, statement in _TITLE_SNAPSHOT_COLUMNS
) + (_TITLE_BACKFILL,)


#: 与 0003 逐字一致的不可变触发器：回填已确认修订的标题快照时必须临时卸下再原样恢复。
#: 声明集合**不变**（0005 已登记的散列因此不变）；钩子只调整实际执行语句。
_IMMUTABLE_REVISIONS_UPDATE_TRIGGER = (
    "CREATE TRIGGER IF NOT EXISTS immutable_paper_revisions_update "
    "BEFORE UPDATE ON paper_revisions WHEN OLD.state='confirmed' "
    "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END"
)
_DROP_IMMUTABLE_REVISIONS_UPDATE_TRIGGER = (
    "DROP TRIGGER IF EXISTS immutable_paper_revisions_update"
)


def _skip_existing_title_columns(connection: sqlite3.Connection) -> Sequence[str]:
    """按列存在情况过滤 ALTER；回填前后临时卸下/恢复不可变触发器（同事务内）。

    回填必须能写已确认修订（`title_snapshot` 是新增的展示快照，不是内容修订），
    而 0003 的 `immutable_paper_revisions_update` 会拒绝任何 UPDATE；因此：
    过滤后的 ALTER → DROP TRIGGER（IF EXISTS）→ 回填 UPDATE → CREATE TRIGGER（逐字恢复）。
    声明集合与散列不变（V00-G0 发现的"已确认修订旧库启动失败"由此关闭）。
    """
    present = {row[1] for row in connection.execute("PRAGMA table_info(paper_revisions)")}
    statements = [
        statement for column, statement in _TITLE_SNAPSHOT_COLUMNS if column not in present
    ]
    statements.append(_DROP_IMMUTABLE_REVISIONS_UPDATE_TRIGGER)
    statements.append(_TITLE_BACKFILL)
    statements.append(_IMMUTABLE_REVISIONS_UPDATE_TRIGGER)
    return tuple(statements)


# --------------------------------------------------------------------------- 0006 成绩四表（T60）


_SCORE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS score_imports (
        id TEXT PRIMARY KEY NOT NULL,
        assessment_id TEXT NOT NULL REFERENCES assessments(id),
        file_id TEXT NOT NULL REFERENCES file_assets(id),
        base_score_revision_id TEXT,
        mapping_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(mapping_json)),
        state TEXT NOT NULL CHECK(state IN ('uploaded','reviewing','confirmed','failed','cancelled')),
        revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
        -- B3 冻结补齐：预览版本（映射/行定位/校正每次生效递增）、工作表名与预览摘要
        preview_version INTEGER NOT NULL DEFAULT 0 CHECK(preview_version>=0),
        work_sheet TEXT,
        summary_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(summary_json)),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        UNIQUE(id,assessment_id),
        FOREIGN KEY(base_score_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS score_import_rows (
        import_id TEXT NOT NULL REFERENCES score_imports(id),
        row_no INTEGER NOT NULL CHECK(row_no>0),
        participant_id TEXT REFERENCES assessment_participants(id),
        raw_cells_json TEXT NOT NULL CHECK(json_valid(raw_cells_json)),
        issues_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(issues_json)),
        PRIMARY KEY(import_id,row_no)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS score_revisions (
        id TEXT PRIMARY KEY NOT NULL,
        assessment_id TEXT NOT NULL REFERENCES assessments(id),
        version INTEGER NOT NULL CHECK(version>0),
        source_import_id TEXT,
        base_revision_id TEXT,
        state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','confirmed')),
        -- B3 冻结补齐：确认/修正时的参测人次快照与固定计分叶快照（封存闸门按此核完整性）
        participant_snapshot_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(participant_snapshot_json)),
        item_snapshot_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(item_snapshot_json)),
        confirmed_at TEXT,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        UNIQUE(assessment_id,version),
        UNIQUE(id,assessment_id),
        FOREIGN KEY(source_import_id,assessment_id) REFERENCES score_imports(id,assessment_id),
        FOREIGN KEY(base_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id),
        CHECK(base_revision_id IS NULL OR base_revision_id<>id),
        CHECK((state='draft' AND confirmed_at IS NULL) OR (state='confirmed' AND confirmed_at IS NOT NULL))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS student_item_scores (
        score_revision_id TEXT NOT NULL,
        assessment_id TEXT NOT NULL,
        paper_revision_id TEXT NOT NULL,
        participant_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        score_units INTEGER,
        status TEXT NOT NULL CHECK(status IN ('recorded','missing','absent','exempt')),
        PRIMARY KEY(score_revision_id,participant_id,item_id),
        FOREIGN KEY(score_revision_id,assessment_id) REFERENCES score_revisions(id,assessment_id),
        FOREIGN KEY(participant_id,assessment_id) REFERENCES assessment_participants(id,assessment_id),
        FOREIGN KEY(assessment_id,paper_revision_id) REFERENCES assessments(id,paper_revision_id),
        FOREIGN KEY(item_id,paper_revision_id) REFERENCES paper_items(id,paper_revision_id),
        CHECK((status='recorded' AND score_units IS NOT NULL AND score_units>=0) OR (status<>'recorded' AND score_units IS NULL))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS score_revision_corrections (
        revision_id TEXT NOT NULL,
        seq INTEGER NOT NULL CHECK(seq>0),
        participant_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        old_status TEXT NOT NULL CHECK(old_status IN ('recorded','missing','absent','exempt')),
        old_score_units INTEGER,
        new_status TEXT NOT NULL CHECK(new_status IN ('recorded','missing','absent','exempt')),
        new_score_units INTEGER,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        PRIMARY KEY(revision_id,seq),
        FOREIGN KEY(revision_id) REFERENCES score_revisions(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_score_imports_assessment "
    "ON score_imports(assessment_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_score_revisions_assessment "
    "ON score_revisions(assessment_id, version)",
    "CREATE INDEX IF NOT EXISTS ix_item_scores_participant "
    "ON student_item_scores(score_revision_id, participant_id)",
    # 已确认修订不可变（只允许确认动作本身写 confirmed_at/state 的那一次 UPDATE）
    """
    CREATE TRIGGER IF NOT EXISTS immutable_score_revisions_update
    BEFORE UPDATE ON score_revisions
    WHEN OLD.state='confirmed' AND NOT (
        NEW.state=OLD.state AND NEW.confirmed_at IS OLD.confirmed_at
        AND NEW.version=OLD.version AND NEW.assessment_id=OLD.assessment_id
        AND NEW.source_import_id IS OLD.source_import_id
        AND NEW.base_revision_id IS OLD.base_revision_id
        AND NEW.participant_snapshot_json=OLD.participant_snapshot_json
        AND NEW.item_snapshot_json=OLD.item_snapshot_json
        AND NEW.created_at=OLD.created_at
    )
    BEGIN SELECT RAISE(ABORT,'SCORE_REVISION_IMMUTABLE'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS immutable_score_revisions_delete
    BEFORE DELETE ON score_revisions WHEN OLD.state='confirmed'
    BEGIN SELECT RAISE(ABORT,'SCORE_REVISION_IMMUTABLE'); END
    """,
    # 封存闸门：确认必须按“该修订自己的”快照核完整性（人次 × 计分叶 全覆盖）
    """
    CREATE TRIGGER IF NOT EXISTS score_revision_confirm_gate
    BEFORE UPDATE OF state ON score_revisions
    WHEN NEW.state='confirmed' AND OLD.state<>'confirmed'
    BEGIN
     SELECT CASE WHEN json_array_length(NEW.participant_snapshot_json)=0
        OR json_array_length(NEW.item_snapshot_json)=0
      THEN RAISE(ABORT,'SCORE_MATRIX_INCOMPLETE') END;
     SELECT CASE WHEN EXISTS (
       SELECT 1 FROM json_each(NEW.participant_snapshot_json) p, json_each(NEW.item_snapshot_json) i
       WHERE NOT EXISTS (
         SELECT 1 FROM student_item_scores s
         WHERE s.score_revision_id=NEW.id
           AND s.participant_id=json_extract(p.value,'$.participantId')
           AND s.item_id=json_extract(i.value,'$.itemId')
       )
     ) THEN RAISE(ABORT,'SCORE_MATRIX_INCOMPLETE') END;
    END
    """,
    # 已确认修订的矩阵行不可增删改
    """
    CREATE TRIGGER IF NOT EXISTS immutable_item_scores_insert
    BEFORE INSERT ON student_item_scores
    WHEN (SELECT state FROM score_revisions WHERE id=NEW.score_revision_id)='confirmed'
    BEGIN SELECT RAISE(ABORT,'SCORE_REVISION_IMMUTABLE'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS immutable_item_scores_update
    BEFORE UPDATE ON student_item_scores
    WHEN (SELECT state FROM score_revisions WHERE id=OLD.score_revision_id)='confirmed'
      OR (SELECT state FROM score_revisions WHERE id=NEW.score_revision_id)='confirmed'
    BEGIN SELECT RAISE(ABORT,'SCORE_REVISION_IMMUTABLE'); END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS immutable_item_scores_delete
    BEFORE DELETE ON student_item_scores
    WHEN (SELECT state FROM score_revisions WHERE id=OLD.score_revision_id)='confirmed'
    BEGIN SELECT RAISE(ABORT,'SCORE_REVISION_IMMUTABLE'); END
    """,
    # active 只能指向本施测已确认的成绩修订（复合外键保证同施测；此处保证 confirmed）
    """
    CREATE TRIGGER IF NOT EXISTS assessment_active_score_confirmed
    BEFORE UPDATE OF active_score_revision_id ON assessments
    WHEN NEW.active_score_revision_id IS NOT OLD.active_score_revision_id
      AND NEW.active_score_revision_id IS NOT NULL
      AND (SELECT state FROM score_revisions WHERE id=NEW.active_score_revision_id)<>'confirmed'
    BEGIN SELECT RAISE(ABORT,'SCORE_REVISION_NOT_CONFIRMED'); END
    """,
)


# --------------------------------------------------------------------------- 0007 assessments 受控重建（恢复 active 成绩外键）

#: 设计版 assessments（去分期 CHECK，恢复 DEFERRABLE 复合外键到 score_revisions）
_ASSESSMENTS_REBUILT_SQL = """
CREATE TABLE assessments_rebuilt (
    id TEXT PRIMARY KEY NOT NULL,
    owner_id TEXT NOT NULL DEFAULT 'local',
    paper_revision_id TEXT NOT NULL REFERENCES paper_revisions(id),
    title TEXT NOT NULL,
    assessment_type TEXT NOT NULL CHECK(assessment_type IN ('exam','quiz','practice')),
    held_on TEXT NOT NULL,
    active_score_revision_id TEXT,
    state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','closed','archived')),
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(id,paper_revision_id),
    FOREIGN KEY(active_score_revision_id,id) REFERENCES score_revisions(id,assessment_id) DEFERRABLE INITIALLY DEFERRED
)
"""

_ASSESSMENTS_REBUILD = RebuildPlan(
    table="assessments",
    new_table_sql=_ASSESSMENTS_REBUILT_SQL,
    copy_sql=(
        "INSERT INTO assessments_rebuilt "
        "(id,owner_id,paper_revision_id,title,assessment_type,held_on,"
        "active_score_revision_id,state,revision,created_at) "
        "SELECT id,owner_id,paper_revision_id,title,assessment_type,held_on,"
        "active_score_revision_id,state,revision,created_at FROM assessments"
    ),
    drop_and_rename=(
        "DROP TABLE assessments",
        "ALTER TABLE assessments_rebuilt RENAME TO assessments",
    ),
    restore=(
        """
        CREATE TRIGGER IF NOT EXISTS assessment_confirmed_paper_insert BEFORE INSERT ON assessments BEGIN
         SELECT CASE WHEN (SELECT state FROM paper_revisions WHERE id=NEW.paper_revision_id)<>'confirmed' THEN RAISE(ABORT,'PAPER_NOT_CONFIRMED') END;
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS assessment_paper_fixed BEFORE UPDATE OF paper_revision_id ON assessments WHEN NEW.paper_revision_id<>OLD.paper_revision_id BEGIN SELECT RAISE(ABORT,'ASSESSMENT_PAPER_FIXED'); END
        """,
        # 重建会删除原表上的触发器：0006 的 active 指向闸门必须一并恢复
        """
        CREATE TRIGGER IF NOT EXISTS assessment_active_score_confirmed
        BEFORE UPDATE OF active_score_revision_id ON assessments
        WHEN NEW.active_score_revision_id IS NOT OLD.active_score_revision_id
          AND NEW.active_score_revision_id IS NOT NULL
          AND (SELECT state FROM score_revisions WHERE id=NEW.active_score_revision_id)<>'confirmed'
        BEGIN SELECT RAISE(ABORT,'SCORE_REVISION_NOT_CONFIRMED'); END
        """,
    ),
    verifications=(
        # 子表仍能解析到 assessments（证明 DROP+RENAME 未破坏引用名）
        (
            "orphan_participants",
            "SELECT count(*) FROM assessment_participants p "
            "LEFT JOIN assessments a ON a.id=p.assessment_id WHERE a.id IS NULL",
        ),
        (
            "orphan_classes",
            "SELECT count(*) FROM assessment_classes c "
            "LEFT JOIN assessments a ON a.id=c.assessment_id WHERE a.id IS NULL",
        ),
        # 复合外键已恢复
        (
            "active_score_fk_restored",
            "SELECT CASE WHEN (SELECT count(*) FROM pragma_foreign_key_list('assessments') "
            "WHERE \"table\"='score_revisions' AND \"from\"='active_score_revision_id')=1 "
            "THEN 0 ELSE 1 END",
        ),
        # 分期 CHECK 已移除
        (
            "placeholder_check_removed",
            "SELECT CASE WHEN (SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='assessments') LIKE '%active_score_revision_id IS NULL%' "
            "THEN 1 ELSE 0 END",
        ),
        # 两个确认/固定触发器已恢复
        (
            "triggers_restored",
            "SELECT CASE WHEN (SELECT count(*) FROM sqlite_master WHERE type='trigger' "
            "AND name IN ('assessment_confirmed_paper_insert','assessment_paper_fixed'))=2 "
            "THEN 0 ELSE 1 END",
        ),
    ),
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
    Migration(
        id="0003_teaching_paper_tables",
        description=(
            "原卷四表（设计逐字，分期偏差：source_file_id 非空、练习来源列仅允许空、"
            "总分允许 0 供草稿）+ 原文块/问题处置/ai_proposals 与确认冻结触发器"
        ),
        statements=_PAPER_STATEMENTS,
    ),
    Migration(
        id="0004_teaching_assessment_tables",
        description=(
            "施测三表（设计逐字，分期偏差：active_score_revision_id 仅允许空）+ "
            "参测班级显式确认列 + confirmed 原卷闸门触发器"
        ),
        statements=_ASSESSMENT_STATEMENTS,
    ),
    Migration(
        id="0005_teaching_paper_revision_titles",
        description="paper_revisions 增加修订级标题快照（含旧数据回填与来源标注）",
        statements=_TITLE_SNAPSHOT_STATEMENTS,
        adjust=_skip_existing_title_columns,
    ),
    Migration(
        id="0006_teaching_score_tables",
        description=(
            "成绩四表（设计逐字 + 预览版本/快照列/修正审计）+ 确认封存闸门与 "
            "不可变触发器；active 只允许指向已确认修订"
        ),
        statements=_SCORE_STATEMENTS,
    ),
    Migration(
        id="0007_teaching_assessment_active_score_fk",
        description=(
            "受控重建 assessments：移除 active_score_revision_id 分期 CHECK，"
            "恢复 DEFERRABLE 复合外键（id,assessment_id）→score_revisions"
        ),
        rebuild=_ASSESSMENTS_REBUILD,
    ),
)

# B4 append only. The seven registered declarations and their digests stay intact.
from app.core.migrations.b4 import migrations as _b4_migrations

MIGRATIONS = MIGRATIONS + _b4_migrations(_PAPER_STATEMENTS, _ASSESSMENT_STATEMENTS + _SCORE_STATEMENTS)

# B5 append only: the nine previously registered declarations stay intact.
from app.core.migrations.lesson_plans import MIGRATION as _lesson_plans_migration

MIGRATIONS = MIGRATIONS + (_lesson_plans_migration,)

