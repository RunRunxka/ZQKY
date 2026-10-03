"""B3 成绩迁移测试（TEACHING-LOOP B3 / CTRL）。

覆盖：全新库 0001–0007；成绩四表的封存闸门（按**该修订自己的**快照核完整性）、
已确认成绩不可变、active 只指向已确认且同施测；B2 旧库（含已确认卷/施测/参测/名单数据）
升级 0006+0007 —— 数据逐行保留、外键与触发器恢复、foreign_key_check/integrity_check 全绿。

对应任务卡 §3「迁移」与预先登记第 4 条（受控重建在含业务数据的 B2 旧库上验证）。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.core.migrations import REGISTERED_MIGRATIONS, apply_migrations
from app.core.sqlite import connect, now_iso

NOW = "2026-10-01T00:00:00Z"


def _prefix(database: str, up_to: str) -> tuple:
    """取到 `up_to` 为止的迁移前缀（模拟旧库已应用范围）。"""
    return tuple(
        m for m in REGISTERED_MIGRATIONS[database] if m.id[:4] <= up_to[:4]
    )


def _seed_b2_business(connection: sqlite3.Connection) -> None:
    """B2 时代真实业务数据：已确认卷（含知识点与计分叶）+ 两个施测 + 参测人次 + 名单。"""
    connection.execute(
        "INSERT INTO file_assets (id, owner_id, kind, blob_key, sha256, original_name, "
        "media_type, byte_size, created_at) VALUES "
        "('fa1','local','score_sheet','blobs/aa',?,'scores.xlsx','application/vnd.ms-excel',10,?)",
        ("a" * 64, NOW),
    )
    connection.execute(
        "INSERT INTO papers (id, owner_id, subject_id, title) "
        "VALUES ('pp1','local','math','第一次月考')"
    )
    connection.execute(
        "INSERT INTO paper_revisions (id, paper_id, version, source_file_id, total_score_units, "
        "state, title_snapshot, title_snapshot_source, created_at) "
        "VALUES ('pr1','pp1',1,'fa1',500,'draft','第一次月考','human',?)",
        (NOW,),
    )
    connection.execute(
        "INSERT INTO paper_items (id, paper_revision_id, question_no, ordinal, is_scored, "
        "max_score_units, content_json) VALUES "
        "('it1','pr1','1',1,1,200,'{}'), ('it2','pr1','2',2,1,300,'{}')"
    )
    for item in ("it1", "it2"):
        connection.execute(
            "INSERT INTO paper_item_knowledge (item_id, paper_revision_id, knowledge_point_id, "
            "knowledge_revision_id, knowledge_name_snapshot, role, source) "
            "VALUES (?,'pr1','kp1','kpv1','一次函数','primary','human')",
            (item,),
        )
    connection.execute(
        "UPDATE paper_revisions SET state='confirmed', confirmed_at=? WHERE id='pr1'", (NOW,)
    )
    connection.execute(
        "INSERT INTO classes (id, owner_id, code, name, school_year, grade_id) "
        "VALUES ('c1','local','C1','一班','2026','g1')"
    )
    connection.execute(
        "INSERT INTO students (id, owner_id, student_no, name) VALUES ('st1','local','0012','甲')"
    )
    connection.execute(
        "INSERT INTO class_memberships (id, student_id, class_id, joined_on) "
        "VALUES ('cm1','st1','c1','2026-09-01')"
    )
    connection.execute(
        "INSERT INTO assessments (id, owner_id, paper_revision_id, title, assessment_type, "
        "held_on, revision) VALUES ('as1','local','pr1','月考','exam','2026-09-30',3)"
    )
    connection.execute("INSERT INTO assessment_classes (assessment_id, class_id) VALUES ('as1','c1')")
    connection.execute(
        "INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, attempt_no, "
        "attendance, name_snapshot, student_no_snapshot, class_confirmed, class_confirmation_note) "
        "VALUES ('pt1','as1','st1','c1',1,'present','甲','0012',1,'名单外确认')"
    )
    connection.execute(
        "INSERT INTO assessments (id, owner_id, paper_revision_id, title, assessment_type, held_on) "
        "VALUES ('as2','local','pr1','月考-补','quiz','2026-09-30')"
    )
    connection.execute("INSERT INTO assessment_classes (assessment_id, class_id) VALUES ('as2','c1')")
    connection.execute(
        "INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, attempt_no, "
        "attendance, name_snapshot) VALUES ('pt2','as2','st1','c1',1,'absent','甲')"
    )


def _make_draft_revision(
    connection: sqlite3.Connection,
    revision_id: str,
    *,
    participant_ids: tuple[str, ...] = ("pt1",),
    item_ids: tuple[str, ...] = ("it1",),
) -> None:
    participants = json.dumps([{"participantId": pid} for pid in participant_ids])
    items = json.dumps([{"itemId": iid} for iid in item_ids])
    connection.execute(
        "INSERT INTO score_revisions (id, assessment_id, version, state, "
        "participant_snapshot_json, item_snapshot_json) VALUES "
        "(?,'as1',(SELECT coalesce(max(version),0)+1 FROM score_revisions WHERE assessment_id='as1'),"
        "'draft',?,?)",
        (revision_id, participants, items),
    )


def test_fresh_database_applies_b3_and_restores_active_score_fk(tmp_path: Path) -> None:
    connection = connect(tmp_path / "teaching.sqlite3")
    try:
        applied = apply_migrations(connection, database="teaching")
        assert applied[-5:] == [
            "0006_teaching_score_tables",
            "0007_teaching_assessment_active_score_fk",
            "0008", "0009", "0010",
        ]
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','trigger')"
            )
        }
        assert {
            "score_imports",
            "score_import_rows",
            "score_revisions",
            "student_item_scores",
            "score_revision_corrections",
            "score_revision_confirm_gate",
            "immutable_score_revisions_update",
            "immutable_item_scores_insert",
            "assessment_active_score_confirmed",
            "assessment_confirmed_paper_insert",
            "assessment_paper_fixed",
        } <= names
        fk = [
            row
            for row in connection.execute("PRAGMA foreign_key_list(assessments)")
            if row[2] == "score_revisions"
        ]
        assert len(fk) == 2  # 复合外键的两列
        assert {row[3] for row in fk} == {"active_score_revision_id", "id"}
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        # 幂等
        assert apply_migrations(connection, database="teaching") == []
    finally:
        connection.close()


def test_confirm_gate_uses_revision_own_snapshot(tmp_path: Path) -> None:
    connection = connect(tmp_path / "teaching.sqlite3")
    try:
        apply_migrations(connection, database="teaching")
        _seed_b2_business(connection)
        connection.execute(
            "INSERT INTO score_imports (id, assessment_id, file_id, state) "
            "VALUES ('si1','as1','fa1','reviewing')"
        )
        _make_draft_revision(connection, "sr1")
        with pytest.raises(sqlite3.IntegrityError) as error:
            connection.execute(
                "UPDATE score_revisions SET state='confirmed', confirmed_at=? WHERE id='sr1'",
                (NOW,),
            )
        assert "SCORE_MATRIX_INCOMPLETE" in str(error.value)
        # 补齐矩阵（该修订快照内的 人次 × 叶）后可确认
        connection.execute(
            "INSERT INTO student_item_scores (score_revision_id, assessment_id, paper_revision_id, "
            "participant_id, item_id, score_units, status) "
            "VALUES ('sr1','as1','pr1','pt1','it1',150,'recorded')"
        )
        connection.execute(
            "UPDATE score_revisions SET state='confirmed', confirmed_at=? WHERE id='sr1'", (NOW,)
        )
        assert (
            connection.execute("SELECT state FROM score_revisions WHERE id='sr1'").fetchone()[0]
            == "confirmed"
        )
        # 已确认：矩阵行与修订本身不可增删改
        for sql, token in (
            ("UPDATE student_item_scores SET score_units=100 WHERE score_revision_id='sr1'", "SCORE_REVISION_IMMUTABLE"),
            ("DELETE FROM student_item_scores WHERE score_revision_id='sr1'", "SCORE_REVISION_IMMUTABLE"),
            ("UPDATE score_revisions SET version=9 WHERE id='sr1'", "SCORE_REVISION_IMMUTABLE"),
            ("DELETE FROM score_revisions WHERE id='sr1'", "SCORE_REVISION_IMMUTABLE"),
        ):
            with pytest.raises(sqlite3.IntegrityError) as error:
                connection.execute(sql)
            assert token in str(error.value)
        # 快照**包含**新人次时，闸门按快照核完整性：缺 pt9 单元 → 拒绝；补齐后通过
        connection.execute(
            "INSERT INTO assessment_participants (id, assessment_id, student_id, class_id, "
            "attempt_no, attendance, name_snapshot) "
            "VALUES ('pt9','as1','st1','c1',2,'present','甲')"
        )
        _make_draft_revision(connection, "sr2", participant_ids=("pt1", "pt9"))
        connection.execute(
            "INSERT INTO student_item_scores (score_revision_id, assessment_id, paper_revision_id, "
            "participant_id, item_id, score_units, status) "
            "VALUES ('sr2','as1','pr1','pt1','it1',180,'recorded')"
        )
        with pytest.raises(sqlite3.IntegrityError) as error:
            connection.execute(
                "UPDATE score_revisions SET state='confirmed', confirmed_at=? WHERE id='sr2'",
                (NOW,),
            )
        assert "SCORE_MATRIX_INCOMPLETE" in str(error.value)
        connection.execute(
            "INSERT INTO student_item_scores (score_revision_id, assessment_id, paper_revision_id, "
            "participant_id, item_id, score_units, status) "
            "VALUES ('sr2','as1','pr1','pt9','it1',0,'recorded')"
        )
        connection.execute(
            "UPDATE score_revisions SET state='confirmed', confirmed_at=? WHERE id='sr2'", (NOW,)
        )
        assert (
            connection.execute("SELECT state FROM score_revisions WHERE id='sr2'").fetchone()[0]
            == "confirmed"
        )
    finally:
        connection.close()


def test_active_score_revision_must_be_confirmed_and_same_assessment(tmp_path: Path) -> None:
    connection = connect(tmp_path / "teaching.sqlite3")
    try:
        apply_migrations(connection, database="teaching")
        _seed_b2_business(connection)
        connection.execute(
            "INSERT INTO score_imports (id, assessment_id, file_id, state) "
            "VALUES ('si1','as1','fa1','reviewing')"
        )
        _make_draft_revision(connection, "sr1")
        with pytest.raises(sqlite3.IntegrityError) as error:
            connection.execute("UPDATE assessments SET active_score_revision_id='sr1' WHERE id='as1'")
        assert "SCORE_REVISION_NOT_CONFIRMED" in str(error.value)
        connection.execute(
            "INSERT INTO student_item_scores (score_revision_id, assessment_id, paper_revision_id, "
            "participant_id, item_id, score_units, status) "
            "VALUES ('sr1','as1','pr1','pt1','it1',150,'recorded')"
        )
        connection.execute(
            "UPDATE score_revisions SET state='confirmed', confirmed_at=? WHERE id='sr1'", (NOW,)
        )
        connection.execute("UPDATE assessments SET active_score_revision_id='sr1' WHERE id='as1'")
        assert (
            connection.execute("SELECT active_score_revision_id FROM assessments WHERE id='as1'").fetchone()[0]
            == "sr1"
        )
        # 跨施测（sr2 属 as2）被复合外键拒绝
        connection.execute(
            "INSERT INTO score_revisions (id, assessment_id, version, state, confirmed_at) "
            "VALUES ('sr2','as2',1,'confirmed',?)",
            (NOW,),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE assessments SET active_score_revision_id='sr2' WHERE id='as1'")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_b2_database_upgrades_with_business_data_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "teaching.sqlite3"
    full = REGISTERED_MIGRATIONS["teaching"]
    connection = connect(path)
    try:
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", _prefix("teaching", "0005_"))
        applied = apply_migrations(connection, database="teaching")
        assert applied[-1] == "0005_teaching_paper_revision_titles"
        _seed_b2_business(connection)
        before = {
            table: [
                tuple(row)
                for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")
            ]
            for table in ("assessments", "assessment_classes", "assessment_participants", "students", "classes")
        }
    finally:
        connection.close()

    monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", full)
    connection = connect(path)
    try:
        assert apply_migrations(connection, database="teaching") == [
            "0006_teaching_score_tables",
            "0007_teaching_assessment_active_score_fk",
            "0008", "0009", "0010",
        ]
        after = {
            table: [
                tuple(row)
                for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")
            ]
            for table in ("assessments", "assessment_classes", "assessment_participants", "students", "classes")
        }
        assert before == after
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        }
        assert {
            "assessment_confirmed_paper_insert",
            "assessment_paper_fixed",
            "assessment_active_score_confirmed",
            "score_revision_confirm_gate",
        } <= names
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        # 施测不换卷触发器在重建后仍生效
        with pytest.raises(sqlite3.IntegrityError) as error:
            connection.execute(
                "UPDATE assessments SET paper_revision_id='other' WHERE id='as1'"
            )
        assert "ASSESSMENT_PAPER_FIXED" in str(error.value)
    finally:
        connection.close()


def test_rebuild_verifications_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """重建校验任一不通过 → 回滚、不登记、可重跑（用篡改计划文本模拟对账失败）。"""
    from dataclasses import replace

    from app.core.migrations import teaching as teaching_module
    from app.core.migrations.base import Migration

    plan = replace(
        teaching_module._ASSESSMENTS_REBUILD,
        verifications=(("intentional_mismatch", "SELECT 1"),),
    )
    broken = Migration(
        id="0007_teaching_assessment_active_score_fk",
        description="test",
        rebuild=plan,
    )
    path = tmp_path / "teaching.sqlite3"
    full = REGISTERED_MIGRATIONS["teaching"]
    connection = connect(path)
    try:
        monkeypatch.setitem(
            REGISTERED_MIGRATIONS,
            "teaching",
            _prefix("teaching", "0006_") + (broken,),
        )
        with pytest.raises(Exception) as error:
            apply_migrations(connection, database="teaching")
        assert "数据对账未通过" in str(error.value)
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        # 未登记，可重跑（修正版）
        monkeypatch.setitem(REGISTERED_MIGRATIONS, "teaching", full)
        assert apply_migrations(connection, database="teaching") == [
            "0007_teaching_assessment_active_score_fk", "0008", "0009", "0010"
        ]
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()
