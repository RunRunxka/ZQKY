"""B6-R01 author command only: immutable attempt, exact source and QA snapshots."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
label, kind = sys.argv[1:3]
run = HERE / label
run.mkdir(exist_ok=False)
new_test = 'apps/web/src/features/lesson-plan/b6-source-loading.test.tsx'
unit = ['apps/web/src/features/lesson-plan/model/g3-persistence.test.tsx','apps/web/src/features/lesson-plan/g3-history-copy.test.tsx',
    'apps/web/src/features/lesson-plan/g3-source-session.test.tsx','apps/web/src/features/lesson-plan/model/server-session.test.tsx',
    'apps/web/src/features/lesson-plan/model/lesson-operation.test.tsx','apps/web/src/features/lesson-plan/lesson-workspace.test.tsx',new_test]
commands = {
    'first': ['node','node_modules/vitest/vitest.mjs','run',new_test,'-t','opened metadata completes','--reporter=verbose'],
    'pending-first': ['node','node_modules/vitest/vitest.mjs','run',new_test,'-t','metadata refresh does not cancel','--reporter=verbose'],
    'unit': ['node','node_modules/vitest/vitest.mjs','run',*unit,'--reporter=verbose'],
    'types': ['node','node_modules/typescript/bin/tsc','--noEmit','--project','apps/web/tsconfig.json'],
    'lint': ['node','node_modules/eslint/bin/eslint.js','apps/web/src/features/lesson-plan/components/SourcePanel.tsx',new_test,'--max-warnings=0'],
}
command = commands[kind]
base = json.loads((HERE.parent/'CANDIDATE-B6-base-v1.json').read_bytes())
names = set(base['sourceFiles']) | {new_test}
qa = {str(p.relative_to(ROOT)).replace('\\','/') for p in HERE.glob('*.py')} | {str(p.relative_to(ROOT)).replace('\\','/') for p in HERE.glob('*.ts')}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
hashes = lambda files: {n:sha(ROOT/n) for n in sorted(files)}
own = run/'source'; own.mkdir()
for n in [*unit,'apps/web/src/features/lesson-plan/components/SourcePanel.tsx']:
    path = own/n; path.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(ROOT/n,path)
for n in qa:
    path = own/n; path.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(ROOT/n,path)
record = dict(task='B6-R01-AUTHOR-v1',label=label,kind=kind,command=command,cwd=str(ROOT),runnerPID=os.getpid(),
    startedAt=datetime.now(timezone.utc).isoformat(),sourceBefore=hashes(names),qaBefore=hashes(qa),status='RUNNING',
    servicesStarted=False,buildRun=False,nextTypegenRun=False,apiImports=False)
save = lambda: (run/'COMMAND.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(); start = time.perf_counter()
with (run/'output.log').open('xb') as stream:
    child = subprocess.Popen(command,cwd=ROOT,env={**os.environ,'NODE_OPTIONS':'--no-experimental-webstorage'},stdout=stream,stderr=subprocess.STDOUT)
    record['pid']=child.pid; save(); code=child.wait()
record.update(exitCode=code,status='COMPLETE',durationMs=round((time.perf_counter()-start)*1000,3),
    finishedAt=datetime.now(timezone.utc).isoformat(),sourceAfter=hashes(names),qaAfter=hashes(qa),childClosed=True,logClosed=True,
    logSHA=sha(run/'output.log'),nextEnvSHA=sha(ROOT/'apps/web/next-env.d.ts'))
record['sourceDrift']=[n for n,s in record['sourceBefore'].items() if record['sourceAfter'].get(n)!=s]
record['qaDrift']=[n for n,s in record['qaBefore'].items() if record['qaAfter'].get(n)!=s]
save()
print(json.dumps({k:record.get(k) for k in ('label','pid','exitCode','durationMs','sourceDrift','qaDrift')},ensure_ascii=False),flush=True)
raise SystemExit(code)
