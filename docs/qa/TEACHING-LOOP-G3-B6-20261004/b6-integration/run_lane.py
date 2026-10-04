"""Own command evidence, fresh isolated TEMP, exact product and executable QA SHA."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
label, kind = sys.argv[1:3]
assert label.replace('-','').isalnum() and kind in {'api','browser'}
run = HERE / label
run.mkdir(exist_ok=False)
candidate_path = Path(os.environ['B6_CANDIDATE']) if kind == 'browser' else HERE.parent/'CANDIDATE-B6-base-v1.json'
if not candidate_path.is_absolute():
    candidate_path = ROOT / candidate_path
candidate = json.loads(candidate_path.read_bytes())
seed_path = None
seed = None
if kind == 'browser':
    seed_path = Path(os.environ['B6_SEED'])
    if not seed_path.is_absolute():
        seed_path = ROOT / seed_path
    seed = json.loads(seed_path.read_bytes())
    assert candidate.get('buildFiles') and candidate.get('buildId'), 'A ROOT-built candidate is required'
    assert seed['buildId'] == candidate['buildId'], 'Seed and built candidate must bind the same build'
    assert seed['candidateSHA'] == hashlib.sha256(candidate_path.read_bytes()).hexdigest(), 'ROOT seed must bind this exact candidate'
    assert seed['apiOrigin'] == 'http://127.0.0.1:8001' and seed['label'] == 'b6-shared-r1'
source_names = candidate['sourceFiles']
legacy_qa = json.loads((HERE.parent/'CANDIDATE-G3-r2-qa5.json').read_bytes())['executableQaFiles']
qa_names = set(legacy_qa) | {str(p.relative_to(ROOT)).replace('\\','/') for p in HERE.glob('*.py')} | {str(p.relative_to(ROOT)).replace('\\','/') for p in HERE.glob('*.ts')}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
hashes = lambda names: {n:sha(ROOT/n) for n in sorted(names)}
sample = Path(tempfile.mkdtemp(prefix='zqky-b5-b6-integration-'+label+'-'))
(sample/'empty-textbooks').mkdir()
isolated = dict(ZQKY_DATA_DIR=str(sample/'data'),ZQKY_ENV='test',PYTHONUTF8='1',PYTHONIOENCODING='utf-8',
    PYTHONDONTWRITEBYTECODE='1',ZQKY_KEEP_TEST_DATA='1',ZQKY_QDRANT_URL='http://127.0.0.1:16333',
    ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9',ZQKY_TEXTBOOK_SOURCE_DIR=str(sample/'empty-textbooks'),
    NODE_OPTIONS='--no-experimental-webstorage',B6_INTEGRATION_RUN=label)
if kind == 'browser':
    isolated.update(B6_CANDIDATE=str(candidate_path), B6_INTEGRATION_SEED=str(seed_path))
env = dict(os.environ, **isolated)
if kind == 'api':
    command = [str(ROOT/'apps/api/.venv/Scripts/python.exe'),str(HERE/'probe_chain.py'),str(run/'probe')]
else:
    command = ['C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe',
        'node_modules/@playwright/test/cli.js','test','--config',str(HERE/'browser.config.ts')]
record = dict(label=label,kind=kind,command=command,cwd=str(ROOT),runnerPID=os.getpid(),
    startedAt=datetime.now(timezone.utc).isoformat(),sampleRoot=str(sample),env=isolated,
    candidatePath=str(candidate_path),candidateSHA=sha(candidate_path),buildId=candidate['buildId'],
    seedPath=str(seed_path) if seed_path else None,seedSHA=sha(seed_path) if seed_path else None,
    sourceBefore=hashes(source_names),qaBefore=hashes(qa_names),
    servicesStarted=False,credentialsFile=None,appMainImported=False,gitWrites=False,status='RUNNING')
assert record['sourceBefore'] == source_names
receipt = run/'COMMAND.json'
save = lambda: receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save(); started = time.perf_counter()
own_snapshot = run/'qa-source'
own_snapshot.mkdir()
for path in [*HERE.glob('*.py'), *HERE.glob('*.ts')]:
    shutil.copyfile(path, own_snapshot/path.name)
try:
    with (run/'output.log').open('xb') as output:
        child = subprocess.Popen(command,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
        record['pid'] = child.pid; save()
        code = child.wait()
    record.update(exitCode=code,status='COMPLETE',childClosed=child.poll() is not None,logsClosed=True)
finally:
    record.update(finishedAt=datetime.now(timezone.utc).isoformat(),durationMs=round((time.perf_counter()-started)*1000,3),
        sourceAfter=hashes(source_names),qaAfter=hashes(qa_names),logSHA=sha(run/'output.log'),sampleRetained=sample.exists())
    record['sourceDrift'] = [n for n,s in record['sourceBefore'].items() if record['sourceAfter'].get(n)!=s]
    record['qaDrift'] = [n for n,s in record['qaBefore'].items() if record['qaAfter'].get(n)!=s]
    save()
print(json.dumps({k:record.get(k) for k in ('label','pid','exitCode','durationMs','sourceDrift','qaDrift','sampleRoot')},ensure_ascii=False),flush=True)
raise SystemExit(record.get('exitCode',1))
