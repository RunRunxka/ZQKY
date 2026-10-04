"""Freeze the stopped minimal B6-R01 product; distinguish prebuild from build."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

R = Path(__file__).resolve().parents[4]
B = R / 'docs/qa/TEACHING-LOOP-G3-B6-20261004'
p = argparse.ArgumentParser()
p.add_argument('--label', required=True)
p.add_argument('--with-build', action='store_true')
a = p.parse_args()
assert a.label.replace('-', '').isalnum()
target = B / ('CANDIDATE-' + a.label + '.json')
assert not target.exists()
gpath = B / 'CANDIDATE-G3-r2-qa5.json'
g = json.loads(gpath.read_bytes())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
names = set(g['sourceFiles']) | {x.relative_to(R).as_posix() for x in
         (R/'apps/web/src/features/lesson-plan').rglob('b6-*.test.tsx')}
source = {n: sha(R/n) for n in sorted(names)}
changed = [n for n,h in g['sourceFiles'].items() if source[n] != h]
assert changed == ['apps/web/src/features/lesson-plan/components/SourcePanel.tsx'], changed
added = sorted(names - set(g['sourceFiles']))
assert added == ['apps/web/src/features/lesson-plan/b6-source-loading.test.tsx'], added
shared = {n: sha(R/n) for n in g['sharedContractFiles']}
assert shared == g['sharedContractFiles']
assert (R/'apps/web/next-env.d.ts').read_bytes() == (B/'ctrl/next-env.opening.bin').read_bytes()
record = dict(version=a.label, at=datetime.now(timezone.utc).isoformat(),
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip(),
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=R).decode().strip(),
    sourceFiles=source, sourceCount=len(source), sharedContractFiles=shared, sharedContractCount=len(shared),
    sourceOrigin=gpath.relative_to(R).as_posix(), sourceOriginSHA=sha(gpath),
    productionChangesFromG3=changed, addedTestsFromG3=added,
    stoppedProduct=True, originalTaskStatus='B6_R01_PENDING_INDEPENDENT_ACCEPTANCE',
    nextEnvSHA=sha(R/'apps/web/next-env.d.ts'), gitWrites=False,
    executableQaFiles=g['executableQaFiles'], executableQaCount=len(g['executableQaFiles']),
    executableQAOrigin='G3 frozen inputs; B6 material writers are separately preparing, not frozen')
if a.with_build:
    build = {x.relative_to(R).as_posix(): sha(x) for x in (R/'apps/web/.next').rglob('*')
             if x.is_file() and 'cache' not in x.relative_to(R/'apps/web/.next').parts}
    record.update(buildFiles=build, buildCount=len(build),
        buildId=(R/'apps/web/.next/BUILD_ID').read_text().strip(),
        actualRewrites=json.loads((R/'apps/web/.next/routes-manifest.json').read_bytes())['rewrites'])
target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:record.get(k) for k in ('version','sourceCount','sharedContractCount','productionChangesFromG3','addedTestsFromG3','buildId','buildCount')},ensure_ascii=False))
print(json.dumps(dict(candidate=target.relative_to(R).as_posix(),SHA=sha(target)),ensure_ascii=False))
