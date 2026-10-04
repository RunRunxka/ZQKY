"""Single isolated command; immutable labels and exact source/build provenance."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--candidate')
parser.add_argument('--restore-next-env', action='store_true')
parser.add_argument('--source', action='append', default=[])
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ['--'] else args.command
assert command and args.label.replace('-', '').isalnum()
log, receipt = [OUT / (args.label + suffix) for suffix in ('.log', '-command.json')]
assert not log.exists() and not receipt.exists(), 'Evidence labels are immutable'
sample = Path(tempfile.mkdtemp(prefix='zqky-g3-ctrl-' + args.label + '-'))
(sample / 'empty-textbooks').mkdir()
isolated = dict(ZQKY_DATA_DIR=str(sample / 'data'), ZQKY_ENV='test', PYTHONUTF8='1',
    PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', NODE_OPTIONS='--no-experimental-webstorage',
    ZQKY_QDRANT_URL='http://127.0.0.1:16333', ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9',
    ZQKY_TEXTBOOK_SOURCE_DIR=str(sample / 'empty-textbooks'), ZQKY_KEEP_TEST_DATA='1',
    ZQKY_API_ORIGIN='http://127.0.0.1:8001')
env = dict(os.environ, **isolated)
candidate_path = ROOT / args.candidate if args.candidate else None
candidate = json.loads(candidate_path.read_bytes()) if candidate_path else None
baseline = json.loads((OUT.parent / 'BASELINE-v1.json').read_bytes())
names = set(args.source) | set(candidate['sourceFiles'] if candidate else baseline['groups']['sourceFiles']['files'])
names.update(str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT / 'apps/web/src/features/lesson-plan').glob('**/g3-*.test.tsx'))
sha = lambda b: hashlib.sha256(b).hexdigest()
source_hashes = lambda: {name: sha((ROOT / name).read_bytes()) for name in sorted(names)}
qa_names = candidate['executableQaFiles'] if candidate else {}
qa_hashes = lambda: {name: sha((ROOT / name).read_bytes()) for name in qa_names}
next_env = ROOT / 'apps/web/next-env.d.ts'
opening = (OUT / 'next-env.opening.bin').read_bytes()
if args.restore_next_env:
    assert next_env.read_bytes() == opening, 'Preserve actual opening next-env before build'
record = dict(label=args.label, command=command, cwd=str(ROOT), env=isolated,
    startedAt=datetime.now(timezone.utc).isoformat(), sampleRoot=str(sample), sampleRetained=True,
    sourceBefore=source_hashes(), qaBefore=qa_hashes(), status='running',
    runnerSHA=sha(Path(__file__).read_bytes()), candidate=args.candidate,
    candidateSHA=sha(candidate_path.read_bytes()) if candidate_path else None,
    nextEnvBeforeSHA=sha(next_env.read_bytes()), runnerPID=os.getpid(), appMainImported=False)
save = lambda: receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
save()
started = time.perf_counter()
child = None
try:
    with log.open('x', encoding='utf-8') as stream:
        resolved = shutil.which(command[0]) or command[0]
        child = subprocess.Popen([resolved, *command[1:]], cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record['pid'] = child.pid
        save()
        code = child.wait()
    record.update(status='complete', exitCode=code, childClosed=child.poll() is not None, logsClosed=True)
finally:
    if args.restore_next_env:
        generated = next_env.read_bytes()
        with (OUT / (args.label + '-next-env.generated.bin')).open('xb') as stream:
            stream.write(generated)
        next_env.write_bytes(opening)
        record.update(nextEnvGeneratedSHA=sha(generated), nextEnvRestoredExact=next_env.read_bytes() == opening)
    record.update(finishedAt=datetime.now(timezone.utc).isoformat(),
        elapsedMs=round((time.perf_counter() - started) * 1000, 3), sourceAfter=source_hashes(),
        qaAfter=qa_hashes(), nextEnvAfterSHA=sha(next_env.read_bytes()),
        logSHA=sha(log.read_bytes()) if log.exists() else None)
    record['changedSources'] = [name for name, digest in record['sourceBefore'].items() if record['sourceAfter'].get(name) != digest]
    record['changedQA'] = [name for name, digest in record['qaBefore'].items() if record['qaAfter'].get(name) != digest]
    save()
print(json.dumps({k: record.get(k) for k in ('label', 'pid', 'exitCode', 'elapsedMs', 'changedSources', 'changedQA', 'sampleRoot')}, ensure_ascii=False), flush=True)
raise SystemExit(record.get('exitCode', 1))
