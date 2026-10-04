"""本轮补足原授权的有数据重建阶段故障；已登记计划与散列不改。"""
from dataclasses import replace
import hashlib
import json
import sqlite3

import pytest

from app.core.migrations import REGISTERED_MIGRATIONS, apply_migrations
from app.core.migrations.base import Migration
from app.core.migrations.teaching import _ASSESSMENTS_REBUILD
from app.core.sqlite import connect
from tests.test_b3_score_migrations import _seed_b2_business

TABLES = ('papers', 'paper_revisions', 'paper_items', 'paper_item_knowledge',
          'classes', 'students', 'class_memberships', 'assessments',
          'assessment_classes', 'assessment_participants')

def fingerprint(connection):
    rows = {table: [tuple(row) for row in connection.execute(f'SELECT * FROM {table} ORDER BY 1')]
            for table in TABLES}
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def seed(connection):
    _seed_b2_business(connection)
    connection.execute("INSERT INTO classes (id,owner_id,code,name,school_year,grade_id) VALUES ('c2','local','C2','二班','2026','g1')")
    connection.execute("INSERT INTO students (id,owner_id,student_no,name) VALUES ('st2','local','0002','乙')")
    connection.execute("INSERT INTO class_memberships (id,student_id,class_id,joined_on) VALUES ('cm2','st2','c2','2026-09-01')")
    connection.execute("INSERT INTO assessment_classes (assessment_id,class_id) VALUES ('as2','c2')")
    connection.execute("INSERT INTO assessment_participants (id,assessment_id,student_id,class_id,attempt_no,attendance,name_snapshot,student_no_snapshot) VALUES ('pt3','as2','st2','c2',1,'absent','乙','0002')")

@pytest.mark.parametrize('stage', ['copy', 'rename', 'trigger', 'foreign_keys'])
def test_rebuild_failure_preserves_all_b2_rows_and_can_rerun(tmp_path, monkeypatch, stage):
    full = REGISTERED_MIGRATIONS['teaching']
    prefix = tuple(m for m in full if m.id[:4] <= '0006')
    connection = connect(tmp_path / 'old.sqlite3')
    try:
        monkeypatch.setitem(REGISTERED_MIGRATIONS, 'teaching', prefix)
        apply_migrations(connection, database='teaching')
        seed(connection)
        before = fingerprint(connection)
        original_triggers = list(connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name"))
        plan = _ASSESSMENTS_REBUILD
        if stage == 'copy':
            plan = replace(plan, copy_sql=plan.copy_sql.replace('SELECT', 'SELECT no_such_column,', 1))
        elif stage == 'rename':
            plan = replace(plan, drop_and_rename=(plan.drop_and_rename[0], 'ALTER TABLE no_such_table RENAME TO assessments'))
        elif stage == 'trigger':
            plan = replace(plan, restore=plan.restore + ('CREATE TRIGGER bad_trigger AFTER INSERT ON no_such_table BEGIN SELECT 1; END',))
        else:
            plan = replace(plan, restore=plan.restore + (
                'CREATE TABLE injected_bad (child TEXT REFERENCES classes(id))',
                "INSERT INTO injected_bad(child) VALUES ('not-a-class')",
            ))
        broken = Migration('0007_teaching_assessment_active_score_fk', 'stage fault', rebuild=plan)
        monkeypatch.setitem(REGISTERED_MIGRATIONS, 'teaching', prefix + (broken,))
        with pytest.raises(Exception):
            apply_migrations(connection, database='teaching')
        assert fingerprint(connection) == before
        assert list(connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")) == original_triggers
        assert connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        assert connection.execute('PRAGMA integrity_check').fetchall()[0][0] == 'ok'
        assert connection.execute("SELECT 1 FROM schema_migrations WHERE id='0007_teaching_assessment_active_score_fk'").fetchone() is None
        monkeypatch.setitem(REGISTERED_MIGRATIONS, 'teaching', full)
        assert apply_migrations(connection, database='teaching') == ['0007_teaching_assessment_active_score_fk', '0008', '0009', '0010']
        assert fingerprint(connection) == before
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    finally:
        connection.close()

class IntegrityFaultConnection(sqlite3.Connection):
    inject = False
    def execute(self, sql, parameters=()):
        if self.inject and sql == 'PRAGMA integrity_check':
            # 第一行ok不足以通过；第二行的错误也必须读取并拒绝。
            return super().execute("SELECT 'ok' UNION ALL SELECT 'fixture integrity violation'")
        return super().execute(sql, parameters)

def test_integrity_non_ok_after_ok_row_rolls_back_and_restores_foreign_keys(tmp_path, monkeypatch):
    full = REGISTERED_MIGRATIONS['teaching']
    connection = sqlite3.connect(tmp_path / 'integrity.sqlite3', isolation_level=None, factory=IntegrityFaultConnection)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    try:
        monkeypatch.setitem(REGISTERED_MIGRATIONS, 'teaching', tuple(m for m in full if m.id[:4] <= '0006'))
        apply_migrations(connection, database='teaching')
        seed(connection)
        before = fingerprint(connection)
        monkeypatch.setitem(REGISTERED_MIGRATIONS, 'teaching', full)
        connection.inject = True
        with pytest.raises(Exception, match='integrity_check'):
            apply_migrations(connection, database='teaching')
        assert fingerprint(connection) == before
        assert connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        connection.inject = False
        assert apply_migrations(connection, database='teaching') == ['0007_teaching_assessment_active_score_fk', '0008', '0009', '0010']
        assert fingerprint(connection) == before
        assert connection.execute('PRAGMA integrity_check').fetchall()[0][0] == 'ok'
    finally:
        connection.close()
