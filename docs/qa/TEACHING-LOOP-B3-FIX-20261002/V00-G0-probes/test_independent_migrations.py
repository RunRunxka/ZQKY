"""Independent populated-B2 migration failure acceptance, isolated before imports."""
from __future__ import annotations
import atexit
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

_temporary=tempfile.TemporaryDirectory(prefix='zqky-v00-migration-bootstrap-')
atexit.register(_temporary.cleanup)
os.environ['ZQKY_DATA_DIR']=str(Path(_temporary.name)/'data')
os.environ['ZQKY_ENV']='test'
os.environ.pop('ZQKY_CREDENTIALS_FILE',None)
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'apps'/'api'))
import pytest
from app.core.migrations import REGISTERED_MIGRATIONS,apply_migrations,verify_migrations
from app.core.migrations.teaching import _ASSESSMENTS_REBUILD
from app.core.migrations.base import Migration
from app.core.exceptions import AppError


class FaultConnection(sqlite3.Connection):
    fault=None
    injected=False
    def execute(self,sql,parameters=()):
        normalized=' '.join(sql.split())
        if self.fault=='integrity_later' and normalized=='PRAGMA integrity_check':
            self.injected=True
            return super().execute("SELECT 'ok' UNION ALL SELECT 'independent corrupted second row'")
        result=super().execute(sql,parameters)
        triggers={
            'copy': normalized.startswith('INSERT INTO assessments_rebuilt '),
            'rename': normalized=='ALTER TABLE assessments_rebuilt RENAME TO assessments',
            'trigger': normalized.startswith('CREATE TRIGGER IF NOT EXISTS assessment_active_score_confirmed '),
            'registry': normalized.startswith('INSERT INTO schema_migrations ') and parameters and parameters[0]=='0007_teaching_assessment_active_score_fk',
        }
        if self.fault in triggers and triggers[self.fault] and not self.injected:
            self.injected=True
            raise sqlite3.OperationalError('independent fault AFTER '+self.fault+' statement completed')
        return result


def snapshot(c):
    schema=[tuple(r) for r in c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]
    tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    rows={t:sorted([tuple(r) for r in c.execute(f'SELECT * FROM "{t}"')],key=repr) for t in tables}
    return {'schema':schema,'rows':rows}


def seed_actual_b2(c):
    # Deliberately seed the 0004 schema, before title snapshot and score tables.
    c.execute("INSERT INTO file_assets(id,owner_id,kind,blob_key,sha256,original_name,media_type,byte_size,created_at) VALUES ('fa','local','paper','blobs/probe',?,'paper.docx','application/octet-stream',1,'2026-09-30T00:00:00Z')",('a'*64,))
    c.execute("INSERT INTO papers(id,owner_id,subject_id,title) VALUES ('p','local','math','B2 原始标题')")
    c.execute("INSERT INTO paper_revisions(id,paper_id,version,source_file_id,total_score_units,state) VALUES ('r','p',1,'fa',500,'draft')")
    c.execute("INSERT INTO paper_items(id,paper_revision_id,question_no,ordinal,is_scored,max_score_units,content_json) VALUES ('i1','r','1',1,1,200,'{}'),('i2','r','2',2,1,300,'{}')")
    for item in ('i1','i2'):
        c.execute("INSERT INTO paper_item_knowledge(item_id,paper_revision_id,knowledge_point_id,knowledge_revision_id,knowledge_name_snapshot,role,source) VALUES (?,'r','kp','kpr','一次函数','primary','human')",(item,))
    c.execute("UPDATE paper_revisions SET state='confirmed',confirmed_at='2026-09-30T00:00:00Z' WHERE id='r'")
    for i in (1,2):
        c.execute("INSERT INTO classes(id,owner_id,code,name,school_year,grade_id) VALUES (?,'local',?,?, '2026','g1')",('c'+str(i),'C'+str(i),'班'+str(i)))
    for i in (1,2,3):
        sid='s'+str(i); cid='c1' if i<3 else 'c2'
        c.execute("INSERT INTO students(id,owner_id,student_no,name) VALUES (?,'local',?,?)",(sid,'000'+str(i),'学生'+str(i)))
        c.execute("INSERT INTO class_memberships(id,student_id,class_id,joined_on) VALUES (?,?,?,'2026-09-01')",('m'+str(i),sid,cid))
    for a in (1,2):
        c.execute("INSERT INTO assessments(id,owner_id,paper_revision_id,title,assessment_type,held_on,revision) VALUES (?,'local','r',?,'exam','2026-09-30',?)",('a'+str(a),'B2考试'+str(a),a+1))
        for cls in ('c1','c2'): c.execute('INSERT INTO assessment_classes(assessment_id,class_id) VALUES (?,?)',('a'+str(a),cls))
    for n,(a,s,cid,attempt,attendance) in enumerate([('a1','s1','c1',1,'present'),('a1','s2','c1',1,'absent'),('a1','s1','c1',2,'exempt'),('a2','s3','c2',1,'present')]):
        c.execute("INSERT INTO assessment_participants(id,assessment_id,student_id,class_id,attempt_no,attendance,name_snapshot,student_no_snapshot,class_confirmed,class_confirmation_note) VALUES (?,?,?,?,?,?,?, ?,1,'过去本班教师已确认')",('pt'+str(n),a,s,cid,attempt,attendance,'冻结'+s,'000'+s[-1]))


@pytest.mark.parametrize('fault',['none','copy','rename','trigger','registry','foreign_keys','integrity_later','verification'])
def test_populated_b2_preservation_rollback_every_stage_and_rerun(tmp_path,monkeypatch,fault):
    full=REGISTERED_MIGRATIONS['teaching']
    prefix4=tuple(m for m in full if m.id[:4]<='0004')
    prefix6=tuple(m for m in full if m.id[:4]<='0006')
    c=sqlite3.connect(tmp_path/'b2.sqlite3',isolation_level=None,factory=FaultConnection); c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA busy_timeout=5000')
    try:
        monkeypatch.setitem(REGISTERED_MIGRATIONS,'teaching',prefix4); apply_migrations(c,database='teaching'); seed_actual_b2(c)
        b2=snapshot(c)['rows']
        b2_revision_columns=[r[1] for r in c.execute('PRAGMA table_info(paper_revisions)')]
        monkeypatch.setitem(REGISTERED_MIGRATIONS,'teaching',prefix6); applied=apply_migrations(c,database='teaching')
        assert applied==['0005_teaching_paper_revision_titles','0006_teaching_score_tables']
        # All historic B2 rows survive 0005+0006; only title snapshot appends two
        # explicit values to paper_revisions. No claim of original-title recovery.
        assert c.execute("SELECT title_snapshot,title_snapshot_source FROM paper_revisions WHERE id='r'").fetchone()[0]=='B2 原始标题'
        old_column_projection=','.join('"'+name+'"' for name in b2_revision_columns)
        assert sorted([tuple(r) for r in c.execute('SELECT '+old_column_projection+' FROM paper_revisions')],key=repr)==b2['paper_revisions']
        for table,rows in b2.items():
            if table in ('schema_migrations','paper_revisions'): continue
            assert sorted([tuple(r) for r in c.execute(f'SELECT * FROM "{table}"')],key=repr)==rows
        before=snapshot(c)
        plan=_ASSESSMENTS_REBUILD
        if fault=='foreign_keys':
            plan=replace(plan,restore=plan.restore+('CREATE TABLE independent_orphan(child TEXT REFERENCES students(id))',"INSERT INTO independent_orphan VALUES ('unknown')"))
        elif fault=='verification':
            plan=replace(plan,verifications=plan.verifications+(('independent deliberate mismatch','SELECT 1'),))
        m=full[-1] if plan is _ASSESSMENTS_REBUILD else Migration(full[-1].id,'independent fault',rebuild=plan)
        monkeypatch.setitem(REGISTERED_MIGRATIONS,'teaching',prefix6+(m,)); c.fault=fault
        if fault=='none':
            assert apply_migrations(c,database='teaching')==[full[-1].id]
        else:
            with pytest.raises((sqlite3.Error,AppError)):
                apply_migrations(c,database='teaching')
            if fault in ('copy','rename','trigger','registry','integrity_later'): assert c.injected
            c.fault=None
            assert snapshot(c)==before
            assert c.execute('PRAGMA foreign_keys').fetchone()[0]==1
            assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
            assert c.execute('PRAGMA integrity_check').fetchall()[0][0]=='ok'
            monkeypatch.setitem(REGISTERED_MIGRATIONS,'teaching',full)
            assert apply_migrations(c,database='teaching')==[full[-1].id]
        assert c.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert c.execute('PRAGMA integrity_check').fetchall()[0][0]=='ok'
        after=snapshot(c)
        assert {k:v for k,v in after['rows'].items() if k!='schema_migrations'}=={k:v for k,v in before['rows'].items() if k!='schema_migrations'}
        assert c.execute('SELECT count(*) FROM assessment_participants').fetchone()[0]==4
        with pytest.raises(sqlite3.IntegrityError): c.execute("UPDATE paper_items SET max_score_units=1 WHERE id='i1'")
        with pytest.raises(sqlite3.IntegrityError): c.execute("UPDATE assessments SET paper_revision_id='missing' WHERE id='a1'")
        # Registered migration digest mismatch must refuse without any writes.
        stable=snapshot(c)
        changed=replace(full[-1],rebuild=replace(_ASSESSMENTS_REBUILD,copy_sql=_ASSESSMENTS_REBUILD.copy_sql+' -- independent hash drift'))
        monkeypatch.setitem(REGISTERED_MIGRATIONS,'teaching',prefix6+(changed,))
        with pytest.raises(AppError) as drift: verify_migrations(c,database='teaching')
        assert drift.value.code=='SCHEMA_MIGRATION_DRIFT'
        assert snapshot(c)==stable
        print(json.dumps({'case':'migration '+fault,'B2RowsKept':True,'participants':4,'failureRollback':fault!='none','rerun':True,'foreignKeys':1,'triggerPreserved':True,'hashDriftRefused':True},ensure_ascii=False))
    finally: c.close()
