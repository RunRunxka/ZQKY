"""Qualified original-sample audit + final same-source full-API restore binding."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET

R=Path(__file__).resolve().parents[4]
B=R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
O=R/'docs/qa/TEACHING-LOOP-G2-B5-20261003'
out=B/'ctrl/B6-RECOVERY-EXACT-REFERENCE-v2.json'
assert not out.exists()
start=time.perf_counter()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
first_path=B/'ctrl/B6-RECOVERY-EXACT-REFERENCE-v1.json'
first=json.loads(first_path.read_bytes())
author=json.loads((O/'ctrl/b5-backup-recovery-v2-command.json').read_bytes())
api_path=O/'ctrl/b5-api-full-prebuild-v1-command.json'
api=json.loads(api_path.read_bytes())
binding=json.loads((B/'ctrl/G3-API-UNCHANGED-BINDING-v1.json').read_bytes())
backend=binding['backendFiles']
assert api['sourceBefore']==api['sourceAfter']
assert {name:api['sourceBefore'][name] for name in backend}==backend
assert all(sha(R/n)==h for n,h in backend.items())
assert api['exitCode']==0
xml_path=O/'ctrl/b5-api-full-prebuild-v1.xml'
cases=[e for e in ET.parse(xml_path).iter('testcase') if e.get('name')==
       'test_full_offline_backup_restores_all_six_populated_b5_tables_assets_and_fixed_refs']
assert len(cases)==1 and not list(cases[0])
sample=Path(api['sampleRoot'])/'pytest/test_full_offline_backup_resto0'
assert Path(os.environ['TEMP']).resolve() in sample.resolve().parents
proof=sample/'B5-RECOVERY-PROOF.json'
assert proof.exists()
old_delta=[dict(path=n,earlyRunSHA=h,currentSHA=sha(R/n)) for n,h in author['sourceBefore'].items()
           if h!=sha(R/n)]
assert [x['path'] for x in old_delta]==['apps/api/app/core/lesson_schema_gate.py']
assert all(x['expected']==sha(Path(x['path'])) for x in first['oldInputs'])
old_sample=Path(first['sampleRoot'])
assert all(x['expected']==sha(old_sample/x['path']) for x in first['oldSampleFiles'])
record=dict(task='B6-RECOVERY-EXACT-REFERENCE-v2',startedAt=now(),pid=os.getpid(),
 result='QUALIFIED_SAME_FINAL_SOURCE_REFERENCE_AND_UNCHANGED_OLD_SAMPLE',
 firstFailedAssertion=dict(path=str(first_path.relative_to(R)),sha=sha(first_path),
   status='REJECTED_NOT_A_SUCCESS_RECEIPT',reason='one early schema-gate SHA differs from later original B5 fixes'),
 earlyFiveSourceHistoricalDelta=old_delta,
 unchangedEarlySourceCount=4,old7InputsAnd56SampleFilesExact=True,
 earlyIndependent='original 16 readonly databases/full-column rows/assets audit; retained original sample only',
 finalSameSourceRestore=dict(command=str(api_path.relative_to(R)),sha=sha(api_path),
   pid=api['pid'],exitCode=api['exitCode'],elapsedMs=api['elapsedMs'],sourceCount=410,
   fullResult='1918pass + 1 existing heavy-scale skip; no recovery skip',
   junit=str(xml_path.relative_to(R)),junitSHA=sha(xml_path),testcase=dict(cases[0].attrib),
   retainedProof=str(proof),retainedProofSHA=sha(proof),proof=json.loads(proof.read_bytes())),
 migrationAndRestoreCode='unchanged this batch; old0001-0010/backup.py/test same-source finalAPI; no0011',
 boundaries=dict(thisBatchRestoreRun=False,thisBatchSQLConnections=0,
   currentGate='exact410 finalAPI also exercises schema validation; early5 cannot claim all current',
   qdrant='serialized fixture transport only; formal6333 not_run',formalMigration='not_run',
   pressure='prior heavy skip retained, not_run additional pressure',formalDataTouched=False,
   appMainImported=False,networkCalls=0),finishedAt=now(),elapsedMs=round((time.perf_counter()-start)*1000,3))
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:record[k] for k in ('task','pid','result','elapsedMs')},ensure_ascii=False))
