"""Declare authorized frontend/QA deltas seen by a long-lived unchanged API."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
R=Path(__file__).resolve().parents[4];B=R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
out=B/'ctrl/B6-SERVICE-SOURCE-ATTRIBUTION-v1.json';assert not out.exists()
sp=B/'ctrl/b6-shared-r1-service.json';s=json.loads(sp.read_bytes())
cp=B/'CANDIDATE-B6-R01-r2-built.json';c=json.loads(cp.read_bytes())
expected=['apps/web/src/features/lesson-plan/components/SourcePanel.tsx',
          'apps/web/src/features/lesson-plan/lesson-workspace.test.tsx']
assert s['status']=='closed' and s['serverClosed'] and s['watcherClosed'] and s['transportRestored'] and s['logClosed']
assert s['sourceDrift']==expected
assert all(s['sourceAfter'][n]==c['sourceFiles'][n] for n in s['sourceAfter'])
binding=json.loads((B/'ctrl/G3-API-UNCHANGED-BINDING-v1.json').read_bytes())
assert all(s['sourceBefore'][n]==h==s['sourceAfter'][n] for n,h in binding['backendFiles'].items())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=dict(at=datetime.now(timezone.utc).isoformat(),service=sp.relative_to(R).as_posix(),serviceSHA=sha(sp),
 candidate=cp.relative_to(R).as_posix(),candidateSHA=sha(cp),declaredServiceDrift=expected,
 productionDelta=expected[:1],QADelta=expected[1:],addedB6TestCoveredByFinalCandidate=c['addedTestsFromG3'],
 unchangedBackend410=True,sourceAfterMatchesCurrent=True,unexpectedSourceDelta=[],
 sampleRetained=s['sampleRetained'],sampleRoot=s['sampleRoot'],HTTPIdentityProbe='not_run',
 rootStopBirthAndCommandGuard='ctrl/b6-shared-r1-before-full153-stop-request.json')
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(path=out.relative_to(R).as_posix(),SHA=sha(out),expectedDelta=expected),ensure_ascii=False))
