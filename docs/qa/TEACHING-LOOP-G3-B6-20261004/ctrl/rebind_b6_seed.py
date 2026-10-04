"""Offline binding of the retained unchanged API seed to a new frontend build."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

R = Path(__file__).resolve().parents[4]
B = R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
out = B/'ctrl/b6-shared-r1-seed-bound-b6r2.json'
assert not out.exists()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
cp = B/'CANDIDATE-B6-R01-r2-built.json'
c = json.loads(cp.read_bytes())
assert all(sha(R/n) == h for group in ('sourceFiles','sharedContractFiles','buildFiles')
           for n,h in c[group].items())
binding = json.loads((B/'ctrl/G3-API-UNCHANGED-BINDING-v1.json').read_bytes())
assert len(binding['backendFiles']) == 410
assert all(sha(R/n) == h == c['sourceFiles'][n] for n,h in binding['backendFiles'].items())
oldp = B/'ctrl/b6-shared-r1-seed-bound.json'
old = json.loads(oldp.read_bytes())
rawp = B/'ctrl/b6-shared-r1-seed.json'
assert sha(rawp) == old['rawSeedSHA']
service = json.loads((B/'ctrl/b6-shared-r1-service.json').read_bytes())
assert service['status'] == 'serving' and service['pid'] == 4056
new = {**old, 'candidate': cp.relative_to(R).as_posix(), 'candidateSHA': sha(cp),
       'buildId': c['buildId'], 'reboundAt': datetime.now(timezone.utc).isoformat(),
       'priorBinding': oldp.relative_to(R).as_posix(), 'priorBindingSHA': sha(oldp),
       'bindingKind': 'offline unchanged API410 plus actual new frontend build',
       'businessSeedReexecuted': False, 'httpIdentityProbe': 'not_run',
       'apiProcessPID': service['pid']}
out.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(path=out.relative_to(R).as_posix(),SHA=sha(out),buildId=c['buildId']),ensure_ascii=False))
