"""Read-only Playwright collection evidence; no browser/service or business call."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
label = sys.argv[1]
assert label in {'collection-original-r1', 'collection-fixed-r1'}
run = HERE / label
run.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
candidate_path = ROOT / os.environ['B6_CANDIDATE']
seed_path = ROOT / os.environ['B6_SEED']
candidate = json.loads(candidate_path.read_bytes())
seed = json.loads(seed_path.read_bytes())
assert seed['candidateSHA'] == sha(candidate_path) and seed['buildId'] == candidate['buildId']
config = HERE / 'browser.config.ts'
spec = HERE / 'five-fields.spec.ts'
if label == 'collection-original-r1':
    assert sha(config) == '525a225cd89c13b726b660ec5fbc97f6c84b9a5a20d9bb0d657242de1ae87b89'
    (run / 'browser.config.original.bin').write_bytes(config.read_bytes())
    r7 = HERE / 'browser-r7'
    r7_command = json.loads((r7 / 'COMMAND.json').read_bytes())
    stop = dict(task='B6-UI-QA-COLLECTION-v1', status='OWNED_CLI_ABORTED_NOT_ACCEPTANCE',
        reason='Expected one test, actual enrollment fifteen archived copies; no completed test result before stop.',
        pid=14720, parentPID=24380, workerPID=3948, browserRootPID=14448,
        verifiedLiveBeforeStop=dict(name='node.exe', command='C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe node_modules/@playwright/test/cli.js test --config H:\\备份xuexi\\智启课源\\docs\\qa\\TEACHING-LOOP-G3-B6-20261004\\b6-integration\\browser.config.ts'),
        exactOSBirthCaptured=False, runnerStartedAt=r7_command['startedAt'],
        exitMechanism='Verified own receipt PID and live parent/name/command, then taskkill.exe /PID 14720 /T /F for that exact owned CLI and descendants.',
        unknownUserBrowserStopped=False, rootServicesStopped=False, completedTestResults=0,
        resultJsonPresent=(r7 / 'browser-results.json').exists(), commandSHA=sha(r7 / 'COMMAND.json'),
        rawArtifacts={p.relative_to(r7).as_posix(): sha(p) for p in r7.rglob('*') if p.is_file()})
    (run / 'r7-stop-and-artifact-inventory.json').write_text(json.dumps(stop, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
hashes = lambda: {n: sha(ROOT / n) for n in candidate['sourceFiles']}
command = ['C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe',
    'node_modules/@playwright/test/cli.js', 'test', '--list', '--config', str(config)]
env = {**os.environ, 'B6_INTEGRATION_RUN': label, 'B6_INTEGRATION_SEED': str(seed_path),
    'B6_CANDIDATE': str(candidate_path), 'NODE_OPTIONS': '--no-experimental-webstorage'}
record = dict(label=label, command=command, cwd=str(ROOT), runnerPID=os.getpid(),
    startedAt=datetime.now(timezone.utc).isoformat(), candidateSHA=sha(candidate_path), seedSHA=sha(seed_path),
    sourceBefore=hashes(), qaBefore={p.name: sha(p) for p in [config, spec]},
    browserStarted=False, servicesStarted=False, businessExecuted=False, status='RUNNING')
receipt = run / 'COMMAND.json'
save = lambda: receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
save()
begin = time.perf_counter()
with (run / 'output.log').open('xb') as stream:
    child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    record['pid'] = child.pid
    save()
    code = child.wait()
log = (run / 'output.log').read_text(encoding='utf-8')
count = re.search(r'Total: (\d+) tests? in (\d+) files?', log)
record.update(exitCode=code, durationMs=round((time.perf_counter() - begin) * 1000, 3),
    finishedAt=datetime.now(timezone.utc).isoformat(), sourceAfter=hashes(), qaAfter={p.name: sha(p) for p in [config, spec]},
    childClosed=True, logClosed=True, logSHA=sha(run / 'output.log'), status='COMPLETE',
    enrolledTests=int(count[1]) if count else None, enrolledFiles=int(count[2]) if count else None)
record['sourceDrift'] = [n for n, h in record['sourceBefore'].items() if record['sourceAfter'].get(n) != h]
record['qaDrift'] = [n for n, h in record['qaBefore'].items() if record['qaAfter'].get(n) != h]
save()
print(json.dumps({k: record[k] for k in ['label', 'pid', 'exitCode', 'durationMs', 'enrolledTests', 'enrolledFiles', 'sourceDrift', 'qaDrift']}, ensure_ascii=False))
if label == 'collection-fixed-r1':
    assert record['enrolledTests'] == 1 and record['enrolledFiles'] == 1
raise SystemExit(code)
