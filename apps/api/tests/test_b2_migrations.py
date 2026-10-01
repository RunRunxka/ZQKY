"""B2 迁移与路径兼容测试（TEACHING-LOOP B2 / 验收 A1）。

覆盖：新库 / 仅 B0 结构旧库 / B1 结构旧库三条升级路径；重复应用幂等；中途失败整体回滚；
foreign_key_check 全库为空；B0/B1 已登记散列不得改写；B2 触发器（确认闸门、确认后冻结、
父子环、施测只用已确认卷、施测不换卷）与分期 CHECK（未来引用列只能为空）生效；
启动门控对旧库放行。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.core.database_gate import DatabaseExpectation, verify_existing_databases
from app.core.migrations import (
    REGISTERED_MIGRATIONS,
    Migration,
    applied_migrations,
    apply_migrations,
)
from app.core.sqlite import connect, now_iso
from app.repositories.teaching.schema import REQUIRED_TABLES as TEACHING_REQUIRED

#: B0/B1 冻结的声明散列：改写即回归（既有库会判 SCHEMA_MIGRATION_DRIFT）。
FROZEN_DIGESTS = {
    "teaching": {
        "0001_teaching_baseline": "bf78fb3fb702b6f65f3d9802dfd9b53b6628d14e58d33380a9a7da8936b8612a",
        "0002_teaching_business_tables": "a23c6c59982f7f57737f00e8cb815a471dd7de83e9de81abe78416fde8692f42",
    },
    "question_bank": {
        "0001_question_bank_baseline": "b7025e4ad9e2b042c5cc943927bf5b17a40a3dc01116bb99dadbb8b573298156",
        "0002_question_jobs_engine_columns": "61e5595258709835d269b84c3b6d96594124ac818a5f67168c6af2bfe3fb9ee1",
        "0003_question_jobs_engine_state_index": "b4e4aa295b7bd8f004f8d80f6680792dc74fc8a17a26d7ac747d82795a0cb1fb",
    },
}

B2_APPLIED = {
    "teaching": [
        "0001_teaching_baseline",
        "0002_teaching_business_tables",
        "0003_teaching_paper_tables",
        "0004_teaching_assessment_tables",
    ],
    "question_bank": [
        "0001_question_bank_baseline",
        "0002_question_jobs_engine_columns",
        "0003_question_jobs_engine_state_index",
        "0004_question_knowledge_links",
    ],
}

B2_TABLES = {
    "teaching": {
        "papers",
        "paper_revisions",
        "paper_items",
        "paper_item_knowledge",
        "paper_source_blocks",
        "paper_issues",
        "ai_proposals",
        "assessments",
        "assessment_classes",
        "assessment_participants",
    },
    "question_bank": {
        "question_knowledge_links",
        "question_draft_knowledge_links",
        "question_import_provenance",
        "question_content_fingerprints",
    },
}

REGISTERED_FULL = {
    database: tuple(migrations) for database, migrations in REGISTERED_MIGRATIONS.items()
}


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _triggers(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    }


def test_frozen_digests_unchanged() -> None:
    for database, expected in FROZEN_DIGESTS.items():
        actual = {m.id: m.sha256 for m in REGISTERED_MIGRATIONS[database]}
        for migration_id, digest in expected.items():
            assert actual[migration_id] == digest, (database, migration_id)


def test_fresh_database_applies_b2_and_is_idempotent(tmp_path: Path) -> None:
    for database in B2_APPLIED:
        connection = connect(tmp_path / f"{database}.sqlite3")
        try:
            # 动态期望：当前登记的全部迁移（后续批次继续追加，不改本用例）
            assert apply_migrations(connection, database=database) == [
                migration.id for migration in REGISTERED_MIGRATIONS[database]
            ]
            assert apply_migrations(connection, database=database) == []
            assert B2_TABLES[database] <= _tables(connection)
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        finally:
            connection.close()


def test_upgrade_paths_from_b0_and_b1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """仅 B0 结构 / B1 结构旧库都能升级：门控放行 → 增量迁移 → 结构齐备。"""
    for database in ("teaching", "question_bank"):
        for prefix_len in (1, len(REGISTERED_FULL[database]) - 1):
            path = tmp_path / f"{database}-{prefix_len}.sqlite3"
            monkeypatch.setitem(
                REGISTERED_MIGRATIONS, database, REGISTERED_FULL[database][:prefix_len]
            )
            connection = connect(path)
            try:
                applied = apply_migrations(connection, database=database)
                assert applied == [
                    migration.id for migration in REGISTERED_FULL[database]
                ][:prefix_len]
            finally:
                connection.close()
            # 尚未应用 B2 迁移的合法旧库：门控必须放行（REQUIRED_TABLES 仍是 B0 基础表）
            verify_existing_databases(
                [DatabaseExpectation(path, database, TEACHING_REQUIRED if database == "teaching" else ())]
            )
            monkeypatch.setitem(REGISTERED_MIGRATIONS, database, REGISTERED_FULL[database])
            connection = connect(path)
            try:
                assert apply_migrations(connection, database=database) == [
                    migration.id for migration in REGISTERED_FULL[database]
                ][prefix_len:]
                assert B2_TABLES[database] <= _tables(connection)
                assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            finally:
                connection.close()


def test_mid_failure_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    connection = connect(tmp_path / "teaching.sqlite3")
    original = REGISTERED_MIGRATIONS["teaching"]
    try:
        apply_migrations(connection, database="teaching")
        broken = Migration(
            id="0005_broken",
            description="故意失败：第二条语句不是 SQL",
            statements=(
                "CREATE TABLE should_roll_back_b2 (id TEXT PRIMARY KEY)",
                "THIS IS NOT VALID SQL",
            ),
        )
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", (*original, broken))
        with pytest.raises(sqlite3.Error):
            apply_migrations(connection, database="teaching")
        assert "should_roll_back_b2" not in _tables(connection)
        assert "0005_broken" not in applied_migrations(connection)
    finally:
        connection.close()


def test_paper_triggers_and_gates(tmp_path: Path) -> None:
    connection = connect(tmp_path / "teaching.sqlite3")
    try:
        apply_migrations(connection, database="teaching")
        connection.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) VALUES ('a1','local','paper','blobs/'||?, ?,"
            "'paper.docx','application/vnd',10, ?)",
            ("c" * 64, "c" * 64, now_iso()),
        )
        connection.execute(
            "INSERT INTO papers (id, owner_id, subject_id, title) VALUES ('p1','local','math','月考')"
        )
        # 直接插已封存修订 → 拒绝
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
                "total_score_units, state, confirmed_at, created_at) "
                "VALUES ('rX','p1',1,'a1',100,'confirmed',?,?)",
                (now_iso(), now_iso()),
            )
        # 未来引用列只能为空
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
                "source_practice_revision_id, total_score_units, created_at) "
                "VALUES ('rY','p1',1,'a1','practice-1',100,?)",
                (now_iso(),),
            )
        connection.execute(
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
            "total_score_units, created_at) VALUES ('r1','p1',1,'a1',0,?)",
            (now_iso(),),
        )
        connection.execute("UPDATE papers SET current_revision_id='r1' WHERE id='p1'")
        # 无计分小题 → 确认被触发器拒绝
        with pytest.raises(sqlite3.IntegrityError) as error:
            connection.execute(
                "UPDATE paper_revisions SET state='confirmed', confirmed_at=? WHERE id='r1'",
                (now_iso(),),
            )
        assert "NO_SCORED_ITEMS" in str(error.value)
        # 补齐：一道计分叶 + 知识点关联 + 总分一致后才可确认
        connection.execute(
            "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
            "max_score_units, content_json) VALUES ('i1','r1','16(1)',1,1,200,'{}')"
        )
        with pytest.raises(sqlite3.IntegrityError) as missing_kp:
            connection.execute(
                "UPDATE paper_revisions SET total_score_units=200, state='confirmed', "
                "confirmed_at=? WHERE id='r1'",
                (now_iso(),),
            )
        assert "ITEM_KNOWLEDGE_MISSING" in str(missing_kp.value)
        connection.execute(
            "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
            "knowledge_revision_id, knowledge_name_snapshot, role, source) "
            "VALUES ('i1','r1','kp1','kpr1','函数单调性','primary','human')"
        )
        connection.execute(
            "UPDATE paper_revisions SET total_score_units=200, state='confirmed', "
            "confirmed_at=? WHERE id='r1'",
            (now_iso(),),
        )
        # 确认后：改题/删题/插题/改块/改问题全部被冻结触发器拒绝
        for statement in (
            "UPDATE paper_items SET question_no='16(2)' WHERE id='i1'",
            "DELETE FROM paper_items WHERE id='i1'",
            "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
            "max_score_units, content_json) VALUES ('i2','r1','17',2,1,300,'{}')",
            "INSERT INTO paper_source_blocks (id, paper_revision_id, ordinal, kind, block_json) "
            "VALUES ('b1','r1',1,'paragraph','{}')",
            f"INSERT INTO paper_issues (id, paper_revision_id, code, severity, message, created_at) "
            f"VALUES ('x1','r1','C','warning','m','{now_iso()}')",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)
        assert {"paper_confirm", "freeze_paper_items_update"} <= _triggers(connection)
    finally:
        connection.close()


def test_assessment_triggers_and_phasing(tmp_path: Path) -> None:
    connection = connect(tmp_path / "teaching.sqlite3")
    try:
        apply_migrations(connection, database="teaching")
        connection.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) VALUES ('a1','local','paper','blobs/'||?, ?,"
            "'paper.docx','application/vnd',10, ?)",
            ("d" * 64, "d" * 64, now_iso()),
        )
        connection.execute(
            "INSERT INTO papers (id, owner_id, subject_id, title) VALUES ('p1','local','math','月考')"
        )
        connection.execute(
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, "
            "created_at) VALUES ('r1','p1',1,'a1',100,?)",
            (now_iso(),),
        )
        connection.execute("UPDATE papers SET current_revision_id='r1' WHERE id='p1'")
        connection.execute(
            "INSERT INTO classes (id, owner_id, code, name, school_year, grade_id) "
            "VALUES ('c1','local','A1','高一(1)班','2026-2027','senior-1')"
        )
        # draft 修订不得建施测
        with pytest.raises(sqlite3.IntegrityError) as error:
            connection.execute(
                "INSERT INTO assessments (id, owner_id, paper_revision_id, title, "
                "assessment_type, held_on, created_at) "
                "VALUES ('as1','local','r1','月考','exam','2026-10-08',?)",
                (now_iso(),),
            )
        assert "PAPER_NOT_CONFIRMED" in str(error.value)
        # 未确认卷不能通过；先把修订置 confirmed（补最小结构）
        connection.execute(
            "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
            "max_score_units, content_json) VALUES ('i1','r1','16(1)',1,1,100,'{}')"
        )
        connection.execute(
            "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
            "knowledge_revision_id, knowledge_name_snapshot, role, source) "
            "VALUES ('i1','r1','kp1','kpr1','K','primary','human')"
        )
        connection.execute(
            "UPDATE paper_revisions SET state='confirmed', confirmed_at=? WHERE id='r1'",
            (now_iso(),),
        )
        connection.execute(
            "INSERT INTO assessments (id, owner_id, paper_revision_id, title, assessment_type, "
            "held_on, created_at) VALUES ('as1','local','r1','月考','exam','2026-10-08',?)",
            (now_iso(),),
        )
        connection.execute(
            "INSERT INTO assessment_classes (assessment_id, class_id) VALUES ('as1','c1')"
        )
        connection.execute(
            "INSERT INTO students (id, owner_id, student_no, name) VALUES ('s1','local','0012','张伟')"
        )
        connection.execute(
            "INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, "
            "attendance, name_snapshot, class_confirmed, class_confirmation_note) "
            "VALUES ('pt1','as1','s1','c1','present','张伟',1,'名单今日导入，历史归属不覆盖')"
        )
        # 施测不能换卷
        with pytest.raises(sqlite3.IntegrityError) as fixed:
            connection.execute(
                "UPDATE assessments SET paper_revision_id='other' WHERE id='as1'"
            )
        assert "ASSESSMENT_PAPER_FIXED" in str(fixed.value)
        # 未来引用列只能为空
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE assessments SET active_score_revision_id='score-1' WHERE id='as1'"
            )
        # 班级范围外的人次被复合外键拒绝
        connection.execute(
            "INSERT INTO classes (id, owner_id, code, name, school_year, grade_id) "
            "VALUES ('c2','local','A2','高一(2)班','2026-2027','senior-1')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, "
                "attendance, name_snapshot) VALUES ('pt2','as1','s1','c2','present','张伟')"
            )
        # class_confirmed=1 必须给依据
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, "
                "attendance, name_snapshot, class_confirmed) "
                "VALUES ('pt3','as1','s1','c1','present','张伟',1)"
            )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_question_links_immutable(tmp_path: Path) -> None:
    connection = connect(tmp_path / "question-bank.sqlite3")
    try:
        apply_migrations(connection, database="question_bank")
        # questions.current_revision_id ↔ question_revisions.question_id 是环形外键：
        # 与仓储同一纪律，在显式事务内用 defer_foreign_keys 延后校验
        connection.execute("PRAGMA defer_foreign_keys = ON")
        connection.execute("BEGIN")
        connection.execute(
            "INSERT INTO question_imports (id, owner_id, file_sha256, original_blob_id, "
            "uploaded_file_name, uploaded_bytes, state, created_at, updated_at) "
            "VALUES ('imp1','local','x','blob1','q.md',1,'needs_review',?,?)",
            (now_iso(), now_iso()),
        )
        connection.execute(
            "INSERT INTO questions (id, owner_id, current_revision_id, status, created_at) "
            "VALUES ('q1','local','qr1','confirmed',?)",
            (now_iso(),),
        )
        connection.execute(
            "INSERT INTO question_revisions (id, question_id, content_json, metadata_json, "
            "answer_state, content_fingerprint, confirmed_at) "
            "VALUES ('qr1','q1','{}','{}','provided','fp',?)",
            (now_iso(),),
        )
        connection.execute(
            "INSERT INTO question_knowledge_links (question_revision_id, knowledge_point_id, "
            "knowledge_revision_id, subject_id_snapshot, knowledge_name_snapshot, role) "
            "VALUES ('qr1','kp1','kpr1','math','函数单调性','primary')"
        )
        connection.execute("COMMIT")
        for statement in (
            "UPDATE question_knowledge_links SET role='secondary' WHERE question_revision_id='qr1'",
            "DELETE FROM question_knowledge_links WHERE question_revision_id='qr1'",
        ):
            with pytest.raises(sqlite3.IntegrityError) as error:
                connection.execute(statement)
            assert "IMMUTABLE_REVISION" in str(error.value)
        # 草稿关联可改（非不可变）
        connection.execute(
            "INSERT INTO question_drafts (id, import_id, revision, content_json, metadata_json, "
            "extraction_method, review_state) VALUES ('d1','imp1',0,'{}','{}','ai','needs_review')"
        )
        connection.execute(
            "INSERT INTO question_draft_knowledge_links (draft_id, knowledge_point_id, "
            "knowledge_revision_id, subject_id_snapshot, knowledge_name_snapshot, role, source, "
            "created_at) VALUES ('d1','kp1','kpr1','math','函数单调性','primary','human',?)",
            (now_iso(),),
        )
        connection.execute(
            "UPDATE question_draft_knowledge_links SET role='secondary' WHERE draft_id='d1'"
        )
    finally:
        connection.close()

def test_title_snapshot_backfill_handles_confirmed_revisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V00-G0 阻塞项回归：含**已确认修订**的 B2 旧库升级 0005 必须成功。

    0003 的 `immutable_paper_revisions_update` 会拒绝任何 UPDATE（含回填标题快照），
    0005 的 adjust 钩子因此显式 DROP TRIGGER → 回填 → CREATE TRIGGER（同事务、逐字恢复）；
    声明集合与散列不变。
    """
    path = tmp_path / "teaching-b2.sqlite3"
    prefix = REGISTERED_FULL["teaching"][:4]  # 0001–0004（B2 现场）
    monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", prefix)
    connection = connect(path)
    try:
        apply_migrations(connection, database="teaching")
        now = now_iso()
        connection.execute(
            "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
            "media_type, byte_size, created_at) VALUES ('a1','local','paper','blobs/'||?, ?,"
            "'paper.docx','application/vnd',10, ?)",
            ("e" * 64, "e" * 64, now),
        )
        # 直接插入已确认行会被 0003 的 USE_CONFIRM_TRANSITION 拒绝（正确行为）：
        # 走合法确认路径构造"已确认修订"现场（draft → 计分叶 + 知识点 → UPDATE 确认）。
        with pytest.raises(sqlite3.IntegrityError) as direct:
            connection.execute(
                "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
                "total_score_units, state, confirmed_at, created_at) "
                "VALUES ('rX','p1',1,'a1',100,'confirmed',?,?)",
                (now, now),
            )
        assert "USE_CONFIRM_TRANSITION" in str(direct.value)
        connection.execute("PRAGMA defer_foreign_keys = ON")
        connection.execute("BEGIN")
        connection.execute(
            "INSERT INTO papers (id, owner_id, subject_id, title, current_revision_id) "
            "VALUES ('p1','local','math','原始标题','r1')"
        )
        connection.execute(
            "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, "
            "total_score_units, created_at) VALUES ('r1','p1',1,'a1',200,?)",
            (now,),
        )
        connection.execute(
            "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
            "max_score_units, content_json) VALUES ('i1','r1','16(1)',1,1,200,'{}')"
        )
        connection.execute(
            "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
            "knowledge_revision_id, knowledge_name_snapshot, role, source) "
            "VALUES ('i1','r1','kp1','kr1','K','primary','human')"
        )
        connection.execute(
            "UPDATE paper_revisions SET state='confirmed', confirmed_at=? WHERE id='r1'", (now,)
        )
        connection.execute("COMMIT")
    finally:
        connection.close()

    monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", REGISTERED_FULL["teaching"])
    connection = connect(path)
    try:
        # B3 起后续迁移（0006/0007）不在本用例范围内：只放开到 0005，验证回填与触发器恢复
        full = REGISTERED_MIGRATIONS["teaching"]
        monkeypatch.setitem(
            REGISTERED_MIGRATIONS,
            "teaching",
            tuple(
                m
                for m in full
                if m.id.startswith(("0001_", "0002_", "0003_", "0004_", "0005_"))
            ),
        )
        assert apply_migrations(connection, database="teaching") == [
            "0005_teaching_paper_revision_titles"
        ]
        row = connection.execute(
            "SELECT title_snapshot, title_snapshot_source FROM paper_revisions WHERE id='r1'"
        ).fetchone()
        assert row["title_snapshot"] == "原始标题"
        assert row["title_snapshot_source"] == "backfilled_from_paper"
        # 触发器逐字恢复：再 UPDATE 已确认修订仍被拒
        with pytest.raises(sqlite3.IntegrityError) as error:
            connection.execute("UPDATE paper_revisions SET total_score_units=200 WHERE id='r1'")
        assert "IMMUTABLE_REVISION" in str(error.value)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()
