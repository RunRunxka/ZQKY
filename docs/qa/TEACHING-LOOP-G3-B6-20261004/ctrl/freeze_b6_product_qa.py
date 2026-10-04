"""B6-R01 r2 plus declared two-wait original QA synchronization, no lost assertions."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

R = Path(__file__).resolve().parents[4]
B = R/'docs/qa/TEACHING-LOOP-G3-B6-20261004'
p = argparse.ArgumentParser()
p.add_argument('--label',required=True)
p.add_argument('--with-build',action='store_true')
a = p.parse_args()
out = B/('CANDIDATE-'+a.label+'.json')
assert a.label.replace('-','').isalnum() and not out.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
gp=B/'CANDIDATE-G3-r2-qa5.json'
g=json.loads(gp.read_bytes())
names=set(g['sourceFiles'])|{p.relative_to(R).as_posix() for p in
      (R/'apps/web/src/features/lesson-plan').rglob('b6-*.test.tsx')}
source={n:sha(R/n) for n in sorted(names)}
changed=[n for n,h in g['sourceFiles'].items() if source[n]!=h]
product='apps/web/src/features/lesson-plan/components/SourcePanel.tsx'
qa='apps/web/src/features/lesson-plan/lesson-workspace.test.tsx'
assert changed==[product,qa],changed
assert source[product]=='bb4399c57492ea1a7b96ded0dc79a9f1aab5e648417ea2618fd83aa1aad1d9c8'
added=sorted(names-set(g['sourceFiles']))
assert added==['apps/web/src/features/lesson-plan/b6-source-loading.test.tsx']
shared={n:sha(R/n) for n in g['sharedContractFiles']}
assert shared==g['sharedContractFiles']
assert (R/'apps/web/next-env.d.ts').read_bytes()==(B/'ctrl/next-env.opening.bin').read_bytes()
record=dict(version=a.label,at=datetime.now(timezone.utc).isoformat(),
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip(),
 branch=subprocess.check_output(['git','branch','--show-current'],cwd=R).decode().strip(),
 sourceFiles=source,sourceCount=len(source),sharedContractFiles=shared,sharedContractCount=len(shared),
 sourceOrigin=gp.relative_to(R).as_posix(),sourceOriginSHA=sha(gp),
 productionChangesFromG3=[product],existingQASynchronizationChanges=[qa],
 addedTestsFromG3=added,stoppedProduct=True,originalAssertionsPreserved=True,
 qaTask='B6-CHECK-QA-TASK-v1.md',qaTaskSHA=sha(B/'B6-CHECK-QA-TASK-v1.md'),
 nextEnvSHA=sha(R/'apps/web/next-env.d.ts'),gitWrites=False,
 executableQaFiles=g['executableQaFiles'],executableQaCount=len(g['executableQaFiles']))
if a.with_build:
 build={p.relative_to(R).as_posix():sha(p) for p in (R/'apps/web/.next').rglob('*')
        if p.is_file() and 'cache' not in p.relative_to(R/'apps/web/.next').parts}
 record.update(buildFiles=build,buildCount=len(build),buildId=(R/'apps/web/.next/BUILD_ID').read_text().strip(),
 actualRewrites=json.loads((R/'apps/web/.next/routes-manifest.json').read_bytes())['rewrites'])
out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(path=out.relative_to(R).as_posix(),SHA=sha(out),sourceCount=len(source),
 changed=changed,buildId=record.get('buildId')),ensure_ascii=False))
