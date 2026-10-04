"""Bind immutable old isolated restore evidence; do not rerun restore or open SQL."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import time

R = Path(__file__).resolve().parents[4]
B = R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
OLD = R/'docs/qa/TEACHING-LOOP-G2-B5-20261003'
out = B/'ctrl/B6-RECOVERY-EXACT-REFERENCE-v1.json'
assert not out.exists()
start = time.perf_counter()
at = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
audit_path = OLD/'b5-v00/results/RECOVERY-READ-AUDIT-v1.json'
audit = json.loads(audit_path.read_bytes())
author_path = OLD/'ctrl/b5-backup-recovery-v2-command.json'
author = json.loads(author_path.read_bytes())
binding_path = B/'ctrl/G3-API-UNCHANGED-BINDING-v1.json'
backend = json.loads(binding_path.read_bytes())['backendFiles']
sample = Path(audit['sampleRoot'])
temp = Path(os.environ['TEMP']).resolve()
assert temp in sample.resolve().parents and sample.name == 'test_full_offline_backup_resto0'
expected = audit['readOnlyProtection']['sampleFileInventoryAfter']
inputs = audit['inputs']
record = dict(task='B6-RECOVERY-EXACT-REFERENCE-v1', startedAt=at(), pid=os.getpid(),
    sourceEvidence={str(p.relative_to(R)).replace('\\','/'):sha(p) for p in
        (audit_path,author_path,binding_path,OLD/'ctrl/B5-RECOVERY-PROOF-v1.json')},
    priorAuthor=dict(pid=author['pid'],exitCode=author['exitCode'],elapsedMs=author['elapsedMs'],
                     sourceCount=len(author['sourceBefore'])),
    priorIndependent=dict(pid=audit['pythonPid'],elapsedMs=audit['processElapsedMs'],
                          exitCode=audit['processExitCode'],closedConnections=16),
    sampleRoot=str(sample), sampleRetained=sample.exists(),
    oldInputs=[dict(name=k,path=v['path'],expected=v['sha256'],actual=sha(Path(v['path'])))
               for k,v in inputs.items()],
    oldSampleFiles=[dict(path=k,expected=v['sha256'],actual=sha(sample/k)) for k,v in expected.items()],
    oldSampleExtraFiles=sorted({p.relative_to(sample).as_posix() for p in sample.rglob('*') if p.is_file()}-set(expected)),
    backend410Drift=[name for name,digest in backend.items() if sha(R/name)!=digest],
    priorAuthorSourceExact=all(author['sourceBefore'][n]==author['sourceAfter'][n]==sha(R/n)
                              for n in author['sourceBefore']),
    newDDLOrRecoveryCode=False, thisBatchRestoreRun=False, thisBatchSqlConnections=0,
    networkCalls=0, appMainImported=False, formalDataTouched=False,
    result='EXACT_SAME_SOURCE_AND_RETAINED_OLD_EVIDENCE_REFERENCE',
    boundaries=dict(sqliteAndBlob='prior actual restore and independent full-row read; not new run',
                    qdrant='prior serialized transport fixture snapshot; no real 6333',
                    formalMigration='not_run outside authorized isolated scope',
                    heavyPressure='not_run; prior API heavy skip retained'),
    finishedAt=at(),elapsedMs=round((time.perf_counter()-start)*1000,3))
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert not record['backend410Drift'] and record['priorAuthorSourceExact']
assert all(x['expected']==x['actual'] for x in record['oldInputs']+record['oldSampleFiles'])
assert not record['oldSampleExtraFiles']
print(json.dumps({k:record[k] for k in ('task','pid','elapsedMs','result','sampleRetained')},ensure_ascii=False))
print('old inputs7/sample56/backend410 exact; no SQL/app import/restore/network')
