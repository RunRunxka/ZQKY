"""B5 pre-registration DDL probe on new OS TEMP; old declarations remain intact."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sample = Path(tempfile.mkdtemp(prefix="zqky-b5-ddl-"))
(sample / "empty-textbooks").mkdir()
os.environ.update(ZQKY_DATA_DIR=str(sample / "data"), ZQKY_ENV="test", PYTHONUTF8="1",
    ZQKY_QDRANT_URL="http://127.0.0.1:16333", ZQKY_EMBEDDING_BASE_URL="http://127.0.0.1:9",
    ZQKY_TEXTBOOK_SOURCE_DIR=str(sample / "empty-textbooks"))
sys.path.insert(0,str(ROOT / "apps/api"))
from app.core.migrations import REGISTERED_MIGRATIONS, apply_migrations, applied_migrations, Migration
from app.core.migrations.lesson_plans import MIGRATION, REQUIRED_TABLES
from app.core.sqlite import connect, transaction

target = OUT / "B5-DDL-PROBE-v1.json"
if target.exists(): raise FileExistsError("new label required")
old = REGISTERED_MIGRATIONS["teaching"]
assert len(old)==9
checks = []
connections = []
def check(label,condition):
    assert condition,label
    checks.append(label)
def make_class(conn):
    with transaction(conn,immediate=True):
        conn.execute("INSERT INTO classes(id,owner_id,code,name,school_year,grade_id) VALUES('class-demo','local','DEMO','隔离班','2026','grade-8')")
def fixed(conn,doc,rid,cas=1,owner="local"):
    conn.execute("INSERT INTO lesson_plans(id,owner_id,subject_id,class_id,current_revision_id,revision,created_at,updated_at) VALUES(?,?,'math','class-demo',?,?,?,?)",(doc,owner,rid,cas,"t","t"))
    context = json.dumps(dict(subjectId="math",classId="class-demo",classNameAtSave="隔离班",analysis=None))
    conn.execute("INSERT INTO lesson_plan_revisions(id,lesson_plan_id,owner_id,version,data_json,content_hash,source,context_snapshot_json,source_metadata_json,selected_fields_json,process_metadata_json,created_at) VALUES(?,?,?,1,'{}','hash','manual',?,'{}','[]','[]','t')",(rid,doc,owner,context))
try:
    for kind in ("new","populated","rollback"):
        conn = connect(sample / (kind+".sqlite3")); connections.append(conn)
        REGISTERED_MIGRATIONS["teaching"]=old
        apply_migrations(conn,database="teaching")
        if kind!="new": make_class(conn)
        prior=dict(applied_migrations(conn))
        if kind=="rollback":
            broken=Migration("0010","fault injection only in isolated process",MIGRATION.statements+("B5 DELIBERATE INVALID SQL",))
            REGISTERED_MIGRATIONS["teaching"]=old+(broken,)
            try: apply_migrations(conn,database="teaching")
            except sqlite3.Error: pass
            else: raise AssertionError("injected migration unexpectedly succeeded")
            check("failed_0010_registry_absent",applied_migrations(conn)==prior)
            present={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            check("failed_0010_all_new_tables_rolled_back",not set(REQUIRED_TABLES)&present)
            check("failed_0010_existing_class_preserved",conn.execute("SELECT name FROM classes WHERE id='class-demo'").fetchone()[0]=="隔离班")
        REGISTERED_MIGRATIONS["teaching"]=old+(MIGRATION,)
        check(kind+"_0010_applied",apply_migrations(conn,database="teaching")==["0010"])
        check(kind+"_rerun_no_changes",apply_migrations(conn,database="teaching")==[])
        check(kind+"_old_nine_hashes_preserved",all(applied_migrations(conn)[m.id]==m.sha256 for m in old))
        if kind=="new": make_class(conn)
        with transaction(conn,immediate=True): fixed(conn,"doc-demo","rev-demo")
        for label,func in (
            ("initial_pointer_cas_version_mismatch",lambda: fixed(conn,"doc-wrong-cas","rev-wrong-cas",2)),
            ("class_owner_mismatch",lambda: fixed(conn,"doc-wrong-owner","rev-wrong-owner",1,"foreign")),
            ("fixed_revision_update",lambda:conn.execute("UPDATE lesson_plan_revisions SET data_json='{}' WHERE id='rev-demo'")),
            ("fixed_revision_delete",lambda:conn.execute("DELETE FROM lesson_plan_revisions WHERE id='rev-demo'")),
        ):
            try:
                with transaction(conn,immediate=True): func()
            except sqlite3.IntegrityError: pass
            else: raise AssertionError(label+" not blocked by DB")
            checks.append(kind+"_"+label+"_blocked")
        check(kind+"_integrity",conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok")
        check(kind+"_fk",not conn.execute("PRAGMA foreign_key_check").fetchall())
finally:
    REGISTERED_MIGRATIONS["teaching"]=old
    for conn in connections: conn.close()
record=dict(status="AUTHOR_DDL_PASS",sampleRoot=str(sample),sampleRetained=True,connectionsClosed=True,
    registeredProductionMigration=False,checks=checks,checkCount=len(checks),migrationSHA=MIGRATION.sha256,
    oldMigrations={m.id:m.sha256 for m in old},sourceSHA=hashlib.sha256((ROOT/"apps/api/app/core/migrations/lesson_plans.py").read_bytes()).hexdigest())
with target.open("x",encoding="utf-8") as stream: stream.write(json.dumps(record,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({k:record[k] for k in ("status","checkCount","sampleRoot","connectionsClosed","migrationSHA")},ensure_ascii=False))
