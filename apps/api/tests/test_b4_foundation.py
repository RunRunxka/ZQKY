"""B4 append/rebuild and same-transaction ports, using filled isolated old databases."""
from dataclasses import replace
import hashlib
import json
import sqlite3
import pytest
from app.core.migrations import REGISTERED_MIGRATIONS, apply_migrations, applied_migrations
from app.core.migrations.base import Migration
from app.core.sqlite import connect
from app.repositories.teaching.catalog import TeachingCatalog
from app.repositories.jobs.repository import JobStore
from tests.test_b3_score_migrations import _seed_b2_business

OLD_DIGESTS = (
    'bf78fb3fb702b6f65f3d9802dfd9b53b6628d14e58d33380a9a7da8936b8612a',
    'a23c6c59982f7f57737f00e8cb815a471dd7de83e9de81abe78416fde8692f42',
    'd948738226b3a3ff564dd9ba3e98fb71e04772339d1854540b7c466901bfdb5a',
    '5817a05f33a0b15bd5780b59aaa2c43a83a30833b429753d1e066595827a8f58',
    'a06f042ab0b769d4fec9e9a5f172a1e6a6d5f75875301b6a26517b0fa6756961',
    '94dbbae151c636397bb328adca26513e2af11712d644a2226d7a4bdb43ee558c',
    'd550b603788885a47347039f5c96996d025e749f662bd629e2db06b76d291682',
)


def old_rows(conn):
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN('schema_migrations') ORDER BY name")]
    return {t:[tuple(r) for r in conn.execute(f'SELECT * FROM {t} ORDER BY 1')] for t in tables}


def digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def seed_old(conn, monkeypatch):
    # This historical 0009 rebuild experiment includes exactly the B4 stage;
    # B5's new tables and upgrade are exercised in test_b5_public_foundation.
    full = tuple(m for m in REGISTERED_MIGRATIONS['teaching'] if m.id[:4] <= '0009')
    monkeypatch.setitem(REGISTERED_MIGRATIONS, 'teaching', full[:7])
    apply_migrations(conn, database='teaching')
    _seed_b2_business(conn)
    monkeypatch.setitem(REGISTERED_MIGRATIONS, 'teaching', full)
    return full


def test_b4_old_seven_declarations_frozen():
    assert tuple(m.sha256 for m in REGISTERED_MIGRATIONS['teaching'][:7]) == OLD_DIGESTS


def test_filled_old0007_preserves_all_rows_and_file_source(tmp_path, monkeypatch):
    conn = connect(tmp_path/'teaching.sqlite3')
    try:
        seed_old(conn, monkeypatch)
        before = old_rows(conn)
        assert apply_migrations(conn, database='teaching') == ['0008','0009']
        for table, rows in before.items():
            assert [tuple(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY 1')] == rows
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        assert [r[0] for r in conn.execute('PRAGMA integrity_check')] == ['ok']
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert apply_migrations(conn, database='teaching') == []
        with pytest.raises(sqlite3.IntegrityError, match='PAPER_SOURCE_FIXED'):
            conn.execute("UPDATE paper_revisions SET source_file_id=NULL WHERE id='pr1'")
    finally:
        conn.close()


class FaultConnection(sqlite3.Connection):
    fault = ''
    def execute(self, sql, parameters=()):
        if self.fault == 'register' and sql.startswith('INSERT INTO schema_migrations') and parameters[0] == '0009':
            raise sqlite3.OperationalError('injected registration failure')
        if self.fault == 'integrity' and sql == 'PRAGMA integrity_check':
            return super().execute("SELECT 'ok' UNION ALL SELECT 'injected second integrity failure'")
        return super().execute(sql, parameters)


@pytest.mark.parametrize('stage', ['copy','rename','trigger','register','orphan','integrity'])
def test_rebuild_faults_rollback_filled_data_triggers_and_retry(tmp_path, monkeypatch, stage):
    conn = sqlite3.connect(tmp_path/'old.sqlite3', isolation_level=None, factory=FaultConnection)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        full = seed_old(conn, monkeypatch)
        monkeypatch.setitem(REGISTERED_MIGRATIONS, 'teaching', full[:8])
        apply_migrations(conn, database='teaching')
        before = digest(old_rows(conn))
        triggers = [tuple(r) for r in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")]
        plan = full[-1].rebuild
        if stage == 'copy':
            plan = replace(plan, copy_sql=plan.copy_sql.replace('SELECT ', 'SELECT nonexistent,', 1))
        elif stage == 'rename':
            plan = replace(plan, drop_and_rename=plan.drop_and_rename[:-1]+('ALTER TABLE nonexistent RENAME TO paper_revisions',))
        elif stage == 'trigger':
            plan = replace(plan, restore=plan.restore+('CREATE TRIGGER fault AFTER INSERT ON nonexistent BEGIN SELECT 1; END',))
        elif stage == 'orphan':
            plan = replace(plan, restore=plan.restore+('CREATE TABLE fault(child TEXT REFERENCES classes(id))', "INSERT INTO fault VALUES('missing-1'),('missing-2')"))
        else:
            conn.fault = stage
        monkeypatch.setitem(REGISTERED_MIGRATIONS, 'teaching', full[:8]+(Migration('0009','fault',rebuild=plan),))
        with pytest.raises(Exception):
            apply_migrations(conn, database='teaching')
        conn.fault = ''
        assert digest(old_rows(conn)) == before
        assert [tuple(r) for r in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")] == triggers
        assert '0009' not in applied_migrations(conn)
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        monkeypatch.setitem(REGISTERED_MIGRATIONS, 'teaching', full)
        assert apply_migrations(conn, database='teaching') == ['0009']
        assert digest(old_rows(conn)) == before
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    finally:
        conn.close()


def test_job_create_in_rolls_back_with_business_and_reuses_validation(tmp_path):
    catalog = TeachingCatalog(tmp_path/'teaching.sqlite3')
    catalog.migrate()
    store = JobStore(catalog, domain='teaching', table='workflow_jobs', kinds=frozenset({'analysis'}))
    with pytest.raises(RuntimeError):
        with catalog.write_transaction() as conn:
            job = store.create_in(conn, kind='analysis', frozen_input={'scoreRevisionId':'fixed'}, job_id='j1')
            assert job.state == 'queued' and job.input_hash
            conn.execute("INSERT INTO command_submissions VALUES('local','test','s1','hash','{}','now')")
            raise RuntimeError('fault after job/business')
    with catalog.read_connection() as conn:
        assert conn.execute('SELECT count(*) FROM workflow_jobs').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM command_submissions').fetchone()[0] == 0
    assert store.create(kind='analysis', frozen_input={'scoreRevisionId':'fixed'}).state == 'queued'
