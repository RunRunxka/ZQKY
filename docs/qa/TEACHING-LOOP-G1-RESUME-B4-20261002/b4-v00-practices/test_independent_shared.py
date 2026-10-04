"""Independent shared migration/source/backup oracles; no T70 aggregation assertions."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import uuid
import pytest
from probe_support import scene, rows, database_snapshot, record, NEW_TABLES, open_api_scene, seed_api_loop, http, Scene
from app.core.exceptions import AppError
from app.core.migrations import REGISTERED_MIGRATIONS, apply_migrations, applied_migrations
from app.core.migrations.base import Migration
from app.core.sqlite import connect

OLD_SHA=(
 'bf78fb3fb702b6f65f3d9802dfd9b53b6628d14e58d33380a9a7da8936b8612a',
 'a23c6c59982f7f57737f00e8cb815a471dd7de83e9de81abe78416fde8692f42',
 'd948738226b3a3ff564dd9ba3e98fb71e04772339d1854540b7c466901bfdb5a',
 '5817a05f33a0b15bd5780b59aaa2c43a83a30833b429753d1e066595827a8f58',
 'a06f042ab0b769d4fec9e9a5f172a1e6a6d5f75875301b6a26517b0fa6756961',
 '94dbbae151c636397bb328adca26513e2af11712d644a2226d7a4bdb43ee558c',
 'd550b603788885a47347039f5c96996d025e749f662bd629e2db06b76d291682')


def independent_declaration_sha(migration):
    if migration.rebuild:
        p=migration.rebuild
        lines=[p.table,p.new_table_sql,p.copy_sql,*p.drop_and_rename,*p.restore,
               *[label for label,_ in p.verifications],*[query for _,query in p.verifications]]
        statements=['\n'.join(lines)]
    else:statements=migration.statements
    chain=hashlib.sha256()
    for statement in statements:chain.update(statement.strip().encode('utf-8')+b'\0')
    return chain.hexdigest()


def test_old_seven_literal_hash_and_new_database_twice(tmp_path):
    migrations=REGISTERED_MIGRATIONS['teaching']
    assert tuple(independent_declaration_sha(m) for m in migrations[:7])==OLD_SHA
    conn=connect(tmp_path/'fresh.sqlite3')
    try:
        assert apply_migrations(conn,database='teaching')==[m.id for m in migrations]
        assert apply_migrations(conn,database='teaching')==[]
        names={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert set(NEW_TABLES)<=names
        assert [r[0] for r in conn.execute('PRAGMA integrity_check')]==['ok'] and conn.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0]==1
    finally:conn.close()
    record('migration-literal-hash',dict(expected=OLD_SHA,actual=[independent_declaration_sha(m) for m in migrations],newTables=NEW_TABLES))


def seed_old7(conn):
    # Independent literal rows exercising file paper, roster, confirmed score and active composite FK.
    conn.execute("INSERT INTO file_assets(id,owner_id,kind,blob_key,sha256,original_name,media_type,byte_size,created_at) VALUES('old-file','local','paper','blobs/old',?,'old.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',8,'2026-10-02T00:00:00Z')",('a'*64,))
    conn.execute("INSERT INTO papers(id,owner_id,subject_id,title) VALUES('old-paper','local','math','独立旧卷')")
    conn.execute("INSERT INTO paper_revisions(id,paper_id,version,source_file_id,total_score_units,title_snapshot) VALUES('old-pr','old-paper',1,'old-file',125,'独立旧卷')")
    conn.execute("INSERT INTO paper_items(id,paper_revision_id,question_no,ordinal,is_scored,max_score_units,content_json) VALUES('old-item','old-pr','Q1',1,1,125,'{}')")
    conn.execute("INSERT INTO paper_item_knowledge(item_id,paper_revision_id,knowledge_point_id,knowledge_revision_id,knowledge_name_snapshot,role,source) VALUES('old-item','old-pr','old-kp','old-kr','独立旧知识点','primary','human')")
    conn.execute("UPDATE paper_revisions SET state='confirmed',confirmed_at='2026-10-02T00:00:00Z' WHERE id='old-pr'")
    conn.execute("INSERT INTO classes(id,owner_id,code,name,school_year,grade_id) VALUES('old-class','local','OLD','独立旧班','2026','g')")
    conn.execute("INSERT INTO students(id,owner_id,student_no,name) VALUES('old-student','local','00009','旧学生')")
    conn.execute("INSERT INTO class_memberships(id,class_id,student_id,joined_on) VALUES('old-membership','old-class','old-student','2026-01-01')")
    conn.execute("INSERT INTO assessments(id,owner_id,paper_revision_id,title,assessment_type,held_on) VALUES('old-assessment','local','old-pr','独立旧施测','exam','2026-10-02')")
    conn.execute("INSERT INTO assessment_classes(assessment_id,class_id) VALUES('old-assessment','old-class')")
    conn.execute("INSERT INTO assessment_participants(id,assessment_id,student_id,class_id,attempt_no,attendance,name_snapshot,student_no_snapshot) VALUES('old-participant','old-assessment','old-student','old-class',1,'present','旧学生','00009')")
    conn.execute("INSERT INTO score_revisions(id,assessment_id,version,participant_snapshot_json,item_snapshot_json) VALUES('old-score','old-assessment',1,'[{\"participantId\":\"old-participant\"}]','[{\"itemId\":\"old-item\"}]')")
    conn.execute("INSERT INTO student_item_scores(score_revision_id,assessment_id,paper_revision_id,participant_id,item_id,score_units,status) VALUES('old-score','old-assessment','old-pr','old-participant','old-item',0,'recorded')")
    conn.execute("UPDATE score_revisions SET state='confirmed',confirmed_at='2026-10-02T00:00:00Z' WHERE id='old-score'")
    conn.execute("UPDATE assessments SET active_score_revision_id='old-score' WHERE id='old-assessment'")


def current_rows(conn):
    names=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name<>'schema_migrations' ORDER BY name")]
    return {name:rows(conn,name) for name in names}


class FaultConnection:
    """Delegates actual unified SQLite; injects bounded SQL failures, not data or oracle."""
    def __init__(self,conn):self.conn,self.fault=conn,''
    def __getattr__(self,name):return getattr(self.conn,name)
    def execute(self,sql,parameters=()):
        if self.fault=='registry' and sql.startswith('INSERT INTO schema_migrations') and parameters[0]=='0009':
            raise sqlite3.OperationalError('independent registration fault')
        if self.fault=='integrity' and sql=='PRAGMA integrity_check':
            return self.conn.execute("SELECT 'ok' UNION ALL SELECT 'independent second integrity error'")
        return self.conn.execute(sql,parameters)


@pytest.mark.parametrize('fault',[None,'copy','rename','restore','registry','foreign-keys','integrity'])
def test_filled0007_upgrade_fault_rollback_and_retry(tmp_path,monkeypatch,fault):
    full=REGISTERED_MIGRATIONS['teaching'];conn=FaultConnection(connect(tmp_path/'filled.sqlite3'))
    try:
        monkeypatch.setitem(REGISTERED_MIGRATIONS,'teaching',full[:7]);apply_migrations(conn,database='teaching');seed_old7(conn)
        original=current_rows(conn)
        monkeypatch.setitem(REGISTERED_MIGRATIONS,'teaching',full[:8]);assert apply_migrations(conn,database='teaching')==['0008']
        before=current_rows(conn);triggers=[tuple(r) for r in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")]
        if fault:
            plan=full[-1].rebuild
            if fault=='copy':plan=replace(plan,copy_sql=plan.copy_sql.replace('SELECT ','SELECT nonexistent,',1))
            elif fault=='rename':plan=replace(plan,drop_and_rename=plan.drop_and_rename[:-1]+('ALTER TABLE missing RENAME TO paper_revisions',))
            elif fault=='restore':plan=replace(plan,restore=plan.restore+('CREATE TRIGGER qa AFTER INSERT ON missing BEGIN SELECT 1; END',))
            elif fault=='foreign-keys':plan=replace(plan,restore=plan.restore+('CREATE TABLE qa_orphans(id TEXT REFERENCES classes(id))',"INSERT INTO qa_orphans VALUES('absent-a'),('absent-b')"))
            else:conn.fault=fault
            monkeypatch.setitem(REGISTERED_MIGRATIONS,'teaching',full[:8]+(Migration('0009','independent failure',rebuild=plan),))
            with pytest.raises((AppError,sqlite3.DatabaseError)):apply_migrations(conn,database='teaching')
            conn.fault=''
            assert current_rows(conn)==before
            assert [tuple(r) for r in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")]==triggers
            assert '0009' not in applied_migrations(conn)
            assert conn.execute('PRAGMA foreign_keys').fetchone()[0]==1
        monkeypatch.setitem(REGISTERED_MIGRATIONS,'teaching',full)
        assert apply_migrations(conn,database='teaching')==['0009']
        actual=current_rows(conn)
        assert all(actual[name]==data for name,data in original.items())
        assert conn.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert [r[0] for r in conn.execute('PRAGMA integrity_check')]==['ok']
        with pytest.raises(sqlite3.IntegrityError,match='PAPER_SOURCE_FIXED'):
            conn.execute("UPDATE paper_revisions SET source_file_id=NULL WHERE id='old-pr'")
        record('filled-old7-'+str(fault),dict(oldRows=original,oldRowCount=sum(map(len,original.values())),fault=fault,rolledBack=bool(fault),retryApplied='0009',integrity='ok',fkRows=0))
    finally:conn.close()


def test_real_compound_fk_and_recursive_cycle(scene):
    s=scene;q=s.question('独立复合FK')
    first=s.save(s.create(),[s.item(q)]);second=s.save(s.create(),[s.item(q)])
    one=first['currentRevision'];two=second['currentRevision']
    with pytest.raises(sqlite3.IntegrityError,match='FOREIGN KEY constraint failed'):
        with s.catalog.write_transaction() as conn:
            conn.execute("INSERT INTO practice_item_knowledge VALUES(?,?,'foreign-kp','foreign-kr','name','math','primary')",(one['items'][0]['practiceItemId'],two['practiceRevisionId']))
    rid=one['practiceRevisionId'];source=one['items'][0]['practiceItemId']
    # Three containers, each real same-revision parent FK. Final edge makes an indirect cycle.
    with s.catalog.write_transaction() as conn:
        template=conn.execute('SELECT * FROM practice_items WHERE id=?',(source,)).fetchone()
        for n,parent in ((1,None),(2,'cycle-1'),(3,'cycle-2')):
            conn.execute('INSERT INTO practice_items VALUES(?,?,?,?,?,?,?,?,?,?,?)',(f'cycle-{n}',rid,template['selection_id'],f'cycle-{n}',parent,f'cycle-{n}',n+10,0,None,template['content_json'],'{}'))
    with pytest.raises(sqlite3.IntegrityError,match='ITEM_CYCLE'):
        with s.catalog.write_transaction() as conn:conn.execute("UPDATE practice_items SET parent_item_id='cycle-3' WHERE id='cycle-1'")
    with s.catalog.read_connection() as conn:assert conn.execute("SELECT parent_item_id FROM practice_items WHERE id='cycle-1'").fetchone()[0] is None


@pytest.mark.parametrize('identity',['analysis_run_id','subject_id','owner_id','id'])
def test_reviewed_practice_parent_cannot_reassign_frozen_source_identity(scene,identity):
    s=scene;practice=s.seed['practice'];before=http(s.client,'get',s.path(practice))
    replacement={'analysis_run_id':s.seed['returnedAnalysis']['runId'],'subject_id':'english','owner_id':'other-owner','id':'moved-parent'}[identity]
    # The other run really is ready, same owner; changing FK to it must not rewrite historical lineage.
    if identity=='analysis_run_id':
        assert http(s.client,'get','/analysis-runs/'+replacement)['reportReady']
    staged=None;rejected=False;error=None
    try:
        with s.catalog.write_transaction() as conn:
            conn.execute('UPDATE practice_sets SET '+identity+'=? WHERE id=?',(replacement,practice['practiceSetId']))
            staged=dict(conn.execute('SELECT * FROM practice_sets WHERE id=?',(replacement if identity=='id' else practice['practiceSetId'],)).fetchone())
    except sqlite3.IntegrityError as exc:rejected=True;error=str(exc)
    with s.catalog.read_connection() as conn:
        after=conn.execute('SELECT * FROM practice_sets WHERE id=?',(replacement if identity=='id' else practice['practiceSetId'],)).fetchone()
        fk=[tuple(r) for r in conn.execute('PRAGMA foreign_key_check')]
    record('parent-commit-'+identity,dict(identity=identity,newValue=replacement,staged=staged,rejected=rejected,error=error,
        committed=not rejected,after=dict(after) if after else None,fkRows=fk,fixedRevision=before))
    assert rejected,'Frozen practice parent identity reassignment committed: '+identity
    assert http(s.client,'get',s.path(practice))==before


@pytest.mark.parametrize('mismatch',['practice-source','owner'])
def test_conversion_insert_requires_actual_practice_paper_assessment_owner_source(scene,mismatch):
    s=scene;different=s.reviewed(text='独立转换跨来源')
    original=s.seed['conversion'];source_practice=s.seed['practice']['currentRevision']['practiceRevisionId']
    fresh=http(s.client,'post','/assessments',201,json=dict(submissionId='new-source-boundary',paperRevisionId=original['paperRevisionId'],title='真实新施测',
        assessmentType='practice',heldOn='2026-10-02',classIds=[s.seed['classId']],participants=[dict(studentId=s.seed['studentId'],classId=s.seed['classId'])]))
    before=s.counts(('practice_conversions',))
    staged=None;rejected=False;error=None
    try:
        with s.catalog.write_transaction() as conn:
            conn.execute('INSERT INTO practice_conversions VALUES(?,?,?,?,?,?,?,?)',('independent-mismatch','other-owner' if mismatch=='owner' else 'local',
                different['currentRevision']['practiceRevisionId'] if mismatch=='practice-source' else source_practice,original['paperRevisionId'],fresh['assessment']['assessmentId'],
                hashlib.sha256(json.dumps(fresh['participants'],sort_keys=True,ensure_ascii=False).encode()).hexdigest(),json.dumps(fresh['participants'],ensure_ascii=False),'2026-10-02T00:00:00Z'))
            staged=dict(conn.execute("SELECT * FROM practice_conversions WHERE id='independent-mismatch'").fetchone())
    except sqlite3.IntegrityError as exc:rejected=True;error=str(exc)
    with s.catalog.read_connection() as conn:
        after=conn.execute("SELECT * FROM practice_conversions WHERE id='independent-mismatch'").fetchone()
        fk=[tuple(r) for r in conn.execute('PRAGMA foreign_key_check')]
    record('conversion-commit-'+mismatch,dict(mismatch=mismatch,staged=staged,rejected=rejected,error=error,committed=not rejected,
        after=dict(after) if after else None,fkRows=fk,paperSourcePractice=source_practice))
    assert rejected,'Conversion source/owner mismatch committed: '+mismatch
    assert s.counts(('practice_conversions',))==before


def test_same_practice_same_paper_mapping_cannot_swap_valid_source_leaf(scene):
    """Both endpoints exist in the same source revision: FK validity is not source identity."""
    s=scene
    from test_independent_practices import multileaf
    from app.repositories.teaching.papers import PaperRepository
    practice=multileaf(s);original=s.convert(practice);rid=practice['currentRevision']['practiceRevisionId']
    with s.catalog.read_connection() as conn:
        source=[dict(r) for r in conn.execute('SELECT * FROM paper_items WHERE paper_revision_id=? ORDER BY ordinal',(original['paperRevisionId'],))]
        knowledge=[dict(r) for r in conn.execute('SELECT * FROM paper_item_knowledge WHERE paper_revision_id=?',(original['paperRevisionId'],))]
        blocks=[dict(r) for r in conn.execute('SELECT * FROM paper_source_blocks WHERE paper_revision_id=? ORDER BY ordinal',(original['paperRevisionId'],))]
    ids={r['id']:uuid.uuid4().hex for r in source};repository=PaperRepository(s.catalog)
    with s.catalog.write_transaction() as conn:
        paper=repository.create_paper_in(conn,subject_id='math',title='同卷错叶独立种子')
        pr=repository.create_revision_in(conn,paper_id=paper.paper_id,version=1,source_file_id=None,source_practice_revision_id=rid,total_score_units=250,title_snapshot='同卷错叶独立种子')
        for table,records in (('paper_items',source),('paper_item_knowledge',knowledge),('paper_source_blocks',blocks)):
            for original_row in records:
                value=dict(original_row,paper_revision_id=pr.revision_id)
                if table=='paper_items':value.update(id=ids[value['id']],parent_item_id=ids.get(value['parent_item_id']))
                elif table=='paper_item_knowledge':value['item_id']=ids[value['item_id']]
                else:value.update(id=uuid.uuid4().hex,item_id=ids.get(value['item_id']))
                columns=list(value);conn.execute('INSERT INTO '+table+'('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',[value[k] for k in columns])
        repository.confirm_revision_in(conn,pr.revision_id)
        repository.set_current_revision_in(conn,paper.paper_id,pr.revision_id)
    assessment=http(s.client,'post','/assessments',201,json=dict(submissionId='same-volume-real-assessment',paperRevisionId=pr.revision_id,title='同卷映射边界',
        assessmentType='practice',heldOn='2026-10-02',classIds=[s.seed['classId']],participants=[dict(studentId=s.seed['studentId'],classId=s.seed['classId'])]))
    conversion_id=uuid.uuid4().hex
    with s.catalog.write_transaction() as conn:
        frozen=dict(practiceRevisionId=rid,paperRevisionId=pr.revision_id,participants=assessment['participants'])
        conn.execute('INSERT INTO practice_conversions VALUES(?,?,?,?,?,?,?,?)',(conversion_id,'local',rid,pr.revision_id,assessment['assessment']['assessmentId'],
            hashlib.sha256(json.dumps(frozen,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),json.dumps(assessment['participants'],ensure_ascii=False),'2026-10-02T00:00:00Z'))
    leaves=[r for r in source if r['is_scored']]
    a=json.loads(leaves[0]['source_locator_json'])['practiceItemId']
    b=json.loads(leaves[1]['source_locator_json'])['practiceItemId']
    assert a!=b
    target=ids[leaves[1]['id']];rejected=False;error=None
    try:
        with s.catalog.write_transaction() as conn:
            conn.execute('INSERT INTO practice_paper_item_mappings VALUES(?,?,?,?,?)',(conversion_id,rid,a,target,pr.revision_id))
    except sqlite3.IntegrityError as exc:rejected=True;error=str(exc)
    with s.catalog.read_connection() as conn:
        after=[dict(r) for r in conn.execute('SELECT * FROM practice_paper_item_mappings WHERE conversion_id=?',(conversion_id,))]
        target_row=dict(conn.execute('SELECT * FROM paper_items WHERE id=?',(target,)).fetchone())
        fk=[tuple(r) for r in conn.execute('PRAGMA foreign_key_check')]
    record('mapping-wrong-leaf-commit',dict(rejected=rejected,error=error,committed=not rejected,sourcePracticeRevision=rid,sourceA=a,actualSourceB=b,
        targetPaperItem=target_row,insertedMappings=after,fkRows=fk,conversionId=conversion_id))
    assert rejected,'Same-revision mapping A to paper item whose fixed source is B committed'


def test_initial_practice_subject_must_match_actual_ready_run(scene):
    s=scene;set_id=uuid.uuid4().hex;revision_id=uuid.uuid4().hex
    run=http(s.client,'get','/analysis-runs/'+s.seed['analysis']['runId'])
    assert run['subjectId']=='math' and run['reportReady']
    rejected=False;error=None
    try:
        with s.catalog.write_transaction() as conn:
            conn.execute("INSERT INTO practice_sets(id,owner_id,analysis_run_id,subject_id,title,created_at) VALUES(?,'local',?,'english','不匹配学科独立种子','2026-10-02T00:00:00Z')",(set_id,run['runId']))
            original_row=dict(conn.execute('SELECT * FROM practice_revisions WHERE id=?',(s.seed['practice']['currentRevision']['practiceRevisionId'],)).fetchone())
            value=dict(original_row,id=revision_id,practice_set_id=set_id,version=1,state='draft',reviewed_at=None)
            columns=list(value);conn.execute('INSERT INTO practice_revisions('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',[value[k] for k in columns])
            conn.execute('UPDATE practice_sets SET current_revision_id=? WHERE id=?',(revision_id,set_id))
    except sqlite3.IntegrityError as exc:rejected=True;error=str(exc)
    with s.catalog.read_connection() as conn:
        after=conn.execute('SELECT * FROM practice_sets WHERE id=?',(set_id,)).fetchone()
        fk=[tuple(r) for r in conn.execute('PRAGMA foreign_key_check')]
    exposed=None if rejected else http(s.client,'get','/practice-sets/'+set_id)
    record('initial-parent-subject-commit',dict(rejected=rejected,error=error,committed=not rejected,expectedSubject=run['subjectId'],
        after=dict(after) if after else None,actualPracticeHTTP=exposed,fkRows=fk))
    assert rejected,'Initial english practice pointing at a ready math run committed'


@pytest.mark.parametrize('mutation',['none','both-source','wrong-owner','question-no','ordinal','question-revision','content','max-score','kp-revision','kp-name','kp-role','extra-kp','lost-kp','duplicate-source','parent'])
def test_actual_paper_practice_source_gate_all_fixed_fields(scene,mutation):
    s=scene
    from test_independent_practices import multileaf
    practice=multileaf(s);conversion=s.convert(practice);rid=practice['currentRevision']['practiceRevisionId']
    from app.repositories.teaching.papers import PaperRepository
    repository=PaperRepository(s.catalog)
    baseline=s.counts(('papers','paper_revisions','paper_items','paper_item_knowledge'))
    with s.catalog.read_connection() as conn:
        source=[dict(r) for r in conn.execute('SELECT * FROM paper_items WHERE paper_revision_id=? ORDER BY ordinal',(conversion['paperRevisionId'],))]
        knowledge=[dict(r) for r in conn.execute('SELECT * FROM paper_item_knowledge WHERE paper_revision_id=?',(conversion['paperRevisionId'],))]
    identifiers={r['id']:uuid.uuid4().hex for r in source}
    invalid=mutation!='none'
    @contextmanager
    def guard():
        if invalid:
            with pytest.raises(sqlite3.IntegrityError):yield
        else:yield
    with guard():
        with s.catalog.write_transaction() as conn:
            paper=repository.create_paper_in(conn,subject_id='math',title='独立来源闸门',owner_id='wrong' if mutation=='wrong-owner' else 'local')
            pr=repository.create_revision_in(conn,paper_id=paper.paper_id,version=1,source_file_id=s.seed['exports'][0]['fileAssetId'] if mutation=='both-source' else None,
                source_practice_revision_id=rid,total_score_units=250,title_snapshot='独立来源闸门')
            for item in source:
                value=dict(item,id=identifiers[item['id']],paper_revision_id=pr.revision_id,parent_item_id=identifiers.get(item['parent_item_id']))
                columns=list(value)
                conn.execute('INSERT INTO paper_items('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',[value[k] for k in columns])
            for link in knowledge:
                value=dict(link,item_id=identifiers[link['item_id']],paper_revision_id=pr.revision_id)
                columns=list(value);conn.execute('INSERT INTO paper_item_knowledge('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',[value[k] for k in columns])
            leaf=identifiers[source[0]['id']]
            if mutation=='question-no':conn.execute("UPDATE paper_items SET question_no='different' WHERE id=?",(leaf,))
            elif mutation=='ordinal':conn.execute('UPDATE paper_items SET ordinal=98 WHERE id=?',(leaf,))
            elif mutation=='question-revision':conn.execute("UPDATE paper_items SET question_revision_id='not-fixed' WHERE id=?",(leaf,))
            elif mutation=='content':conn.execute("UPDATE paper_items SET content_json='{}' WHERE id=?",(leaf,))
            elif mutation=='max-score':conn.execute('UPDATE paper_items SET max_score_units=126 WHERE id=?',(leaf,));conn.execute('UPDATE paper_revisions SET total_score_units=251 WHERE id=?',(pr.revision_id,))
            elif mutation in ('kp-revision','kp-name','kp-role'):
                field={'kp-revision':'knowledge_revision_id','kp-name':'knowledge_name_snapshot','kp-role':'role'}[mutation]
                conn.execute('UPDATE paper_item_knowledge SET '+field+'=? WHERE item_id=?',('secondary' if mutation=='kp-role' else 'wrong-fixed',leaf))
            elif mutation=='extra-kp':conn.execute("INSERT INTO paper_item_knowledge VALUES(?,?,'extra','extra','extra','primary','human')",(leaf,pr.revision_id))
            elif mutation=='lost-kp':conn.execute('DELETE FROM paper_item_knowledge WHERE item_id=? AND knowledge_point_id=?',(leaf,s.kps[0]))
            elif mutation=='duplicate-source':
                locator=source[0]['source_locator_json'];conn.execute('UPDATE paper_items SET source_locator_json=? WHERE id=?',(locator,identifiers[source[2]['id']]))
            elif mutation=='parent':conn.execute('UPDATE paper_items SET parent_item_id=NULL WHERE id=?',(identifiers[source[2]['id']],))
            repository.confirm_revision_in(conn,pr.revision_id)
    if invalid:assert s.counts(tuple(baseline))==baseline
    record('paper-source-gate-'+mutation,dict(mutation=mutation,rejected=invalid,baseline=baseline,after=s.counts(tuple(baseline))))


def test_actual_all_b4_tables_assets_offline_backup_verify_restore(tmp_path):
    repo=Path(__file__).resolve().parents[4]
    spec=importlib.util.spec_from_file_location('independent_b4_backup',repo/'scripts/rag/backup.py')
    backup=importlib.util.module_from_spec(spec);sys.modules[spec.name]=backup;spec.loader.exec_module(backup)
    # Explicitly authorized existing MockTransport; not a real vector service assertion.
    from tests.test_backup_restore import FakeQdrantServer
    server=FakeQdrantServer();admin=backup.QdrantAdmin('http://127.0.0.1:16333',transport=server.transport())
    root=tmp_path/'source';destination=tmp_path/'backup';restored=tmp_path/'restored'
    with open_api_scene(root) as (app,client,settings):
        seed=seed_api_loop(app,client,tag='p-backup-'+uuid.uuid4().hex[:8])
        snapshots={domain:database_snapshot(path) for domain,path in seed['catalogPaths'].items()}
        assert all(snapshots['teaching'][table] for table in NEW_TABLES)
        downloads={a['artifactId']:client.get(a['downloadUrl']).content for a in seed['exports']}
        assert all(hashlib.sha256(downloads[a['artifactId']]).hexdigest()==a['sha256'] for a in seed['exports'])
        with pytest.raises(AppError) as busy:backup.create_backup(data_dir=settings.data_dir,target=tmp_path/'refused-live',qdrant_client=admin)
        assert busy.value.code=='DATA_LOCK_BUSY' and not (tmp_path/'refused-live').exists()
        source_dir=settings.data_dir
    # Standard app exited: four catalogs and shared data-root lock released before backup.
    manifest=backup.create_backup(data_dir=source_dir,target=destination,label='B4-independent-all-tables',qdrant_client=admin)
    assert manifest['status']=='complete'
    failures,notes=backup.verify_backup(destination,qdrant_client=admin)
    assert failures==[],(failures,notes)
    restore=backup.restore_backup(destination,restored,isolated_qdrant=admin)
    assert restore['status']=='ready'
    actual={domain:database_snapshot(restored/Path(path).relative_to(source_dir)) for domain,path in seed['catalogPaths'].items()}
    assert actual==snapshots
    # Own per-row/all-asset oracle independent of backup implementation.
    assets={str(p.relative_to(source_dir)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source_dir/'assets'/'blobs').iterdir() if p.is_file()}
    for relative,digest in assets.items():assert hashlib.sha256((restored/relative).read_bytes()).hexdigest()==digest
    from app.core.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient
    settings=Settings(host='127.0.0.1',port=8001,env='test',data_dir=restored,credentials_file=None,allowed_origins=frozenset({'http://127.0.0.1:5174'}),
        qdrant_url='http://127.0.0.1:16333',embedding_base_url='http://127.0.0.1:9',textbook_source_dir=root/'empty-textbooks')
    with TestClient(create_app(settings),base_url='http://127.0.0.1:8001') as client:
        practice=http(client,'get','/practice-sets/'+seed['practice']['practiceSetId'])
        assert practice==seed['practice']
        for artifact in seed['exports']:
            assert http(client,'get','/export-artifacts/'+artifact['artifactId'])==artifact
            response=client.get(artifact['downloadUrl']);assert response.status_code==200 and response.content==downloads[artifact['artifactId']]
        report=http(client,'get','/analysis-runs/'+seed['returnedAnalysis']['runId'])
        assert report['reportReady']
        evidence=http(client,'get','/analysis-runs/'+seed['returnedAnalysis']['runId']+'/evidence')
        assert evidence==seed['returnedEvidence']
        assert all(r['practiceRevisionId']==practice['currentRevision']['practiceRevisionId'] and r['practiceItemId'] for r in evidence['items'])
    record('all-b4-backup-restore',dict(manifest=manifest,verifyFailures=failures,verifyNotes=notes,restore=restore,
        roots={'source':source_dir,'backup':destination,'restore':restored},newTableCounts={t:len(actual['teaching'][t]) for t in NEW_TABLES},
        fourDatabaseTableCounts={d:len(tables) for d,tables in actual.items()},allNewRowsIdentical=True,assets=assets,
        artifactByteSHAs={a['artifactId']:a['sha256'] for a in seed['exports']},restoredLineage=evidence,qdrant='authorized MockTransport only',listenersCreated=0))
