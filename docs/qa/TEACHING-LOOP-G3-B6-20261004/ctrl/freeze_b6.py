"""Freeze B6 stopped QA/artifacts on the accepted unchanged G3 product/build."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import subprocess

R=Path(__file__).resolve().parents[4]
B=R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
out=B/'CANDIDATE-B6-r1.json'
assert not out.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
g_path=B/'CANDIDATE-G3-r2-qa5.json'
g=json.loads(g_path.read_bytes())
assert all(sha(R/n)==h for k in ('sourceFiles','sharedContractFiles','buildFiles') for n,h in g[k].items())
assert (R/'apps/web/next-env.d.ts').read_bytes()==(B/'ctrl/next-env.opening.bin').read_bytes()
required=['b6-integration/RESULT-v1.md','b6-quality/RESULT-v1.md','b6-exports/RESULT-v1.md']
assert all((B/n).exists() for n in required), 'All three author STOP reports required'
qa=set(g['executableQaFiles'])|{p.relative_to(R).as_posix() for p in B.rglob('*')
 if p.is_file() and p.suffix in ('.py','.ts','.tsx','.mjs','.cjs','.ps1')}
inputs={p.relative_to(R).as_posix():sha(p) for directory in ('b6-integration','b6-quality','b6-exports')
 for p in (B/directory).rglob('*') if p.is_file()}
record={k:g[k] for k in ('sourceFiles','sourceCount','sharedContractFiles','sharedContractCount',
                        'buildFiles','buildCount','buildId','actualRewrites','nextEnvSHA')}
record.update(task='B6-r1',at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip(),
 branch=subprocess.check_output(['git','branch','--show-current'],cwd=R).decode().strip(),
 productOrigin=g_path.relative_to(R).as_posix(),productOriginSHA=sha(g_path),productionChangesFromG3=[],
 executableQaFiles={n:sha(R/n) for n in sorted(qa)},executableQaCount=len(qa),
 frozenB6ArtifactFiles=inputs,frozenB6ArtifactCount=len(inputs),stoppedProduct=True,stoppedThreeLanes=True,
 G3='CLOSED',B6='PENDING_INDEPENDENT_LIMITED_TECHNICAL_AND_PREPARATION_ACCEPTANCE',
 live_run='awaiting explicit profile/model/count/budget',teacher_review='pending',
 originalPlanB6B7Overall='not_claimed_closed',gitWrites=False,
 authorStopEvidence={n:sha(B/n) for n in required},
 requirementMatrixSHA=sha(B/'B6-REMAINDER-MATRIX-v1.md'),taskCardsSHA=sha(B/'B6-TASK-CARDS-v1.md'))
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(candidate=str(out.relative_to(R)),SHA=sha(out),sourceCount=record['sourceCount'],
 executableQaCount=len(qa),artifactCount=len(inputs),buildId=record['buildId']),ensure_ascii=False))
