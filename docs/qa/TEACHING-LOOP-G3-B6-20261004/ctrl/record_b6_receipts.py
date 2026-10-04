"""Read-only receipt/source binding, exact full rounds, no pooling."""
import argparse
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

R=Path(__file__).resolve().parents[4]
B=R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--command',action='append',required=True)
a=p.parse_args();out=B/'ctrl'/(a.label+'.json');assert not out.exists()
cp=B/'CANDIDATE-B6-R01-r2-built.json';c=json.loads(cp.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for name in a.command:
 path=B/'ctrl'/(name+'-command.json');r=json.loads(path.read_bytes())
 assert r['exitCode']==0 and not r['changedSources'] and not r['changedQA']
 # check uses the corresponding stopped prebuild source; hashes must match final source.
 assert all(r['sourceBefore'].get(n)==h==r['sourceAfter'].get(n) for n,h in c['sourceFiles'].items())
 assert r['nextEnvAfterSHA']==c['nextEnvSHA']
 rows.append(dict(path=path.relative_to(R).as_posix(),SHA=sha(path),label=name,pid=r['pid'],
  elapsedMs=r['elapsedMs'],candidateAtExecution=r['candidate'],source942Exact=True,
  logsClosed=r['logsClosed'],childClosed=r['childClosed'],sampleRoot=r['sampleRoot'],sampleRetained=True))
record=dict(at=datetime.now(timezone.utc).isoformat(),candidate=cp.relative_to(R).as_posix(),candidateSHA=sha(cp),
 buildId=c['buildId'],commands=rows,noPooling=True,networkRequests=0,applicationImported=False)
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(path=out.relative_to(R).as_posix(),SHA=sha(out),commands=len(rows)),ensure_ascii=False))
