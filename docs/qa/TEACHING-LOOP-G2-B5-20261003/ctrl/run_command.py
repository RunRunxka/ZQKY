"""One new isolated command and immutable evidence label; no service lifecycle."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding='utf-8')
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--candidate')
parser.add_argument('--restore-next-env', action='store_true')
parser.add_argument('--all-opening-sources', action='store_true')
parser.add_argument('--source', action='append', default=[])
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ['--'] else args.command
if not command or not args.label.replace('-', '').isalnum():
    raise ValueError('explicit command and safe immutable label required')
log, receipt = [OUT / (args.label + suffix) for suffix in ('.log', '-command.json')]
if log.exists() or receipt.exists():
    raise FileExistsError('never overwrite previous evidence')
sample = Path(tempfile.mkdtemp(prefix='zqky-g2-ctrl-' + args.label + '-'))
(sample / 'empty-textbooks').mkdir()
isolated = dict(ZQKY_DATA_DIR=str(sample / 'data'), ZQKY_ENV='test', PYTHONUTF8='1',
    PYTHONIOENCODING='utf-8', ZQKY_QDRANT_URL='http://127.0.0.1:16333',
    ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9', ZQKY_TEXTBOOK_SOURCE_DIR=str(sample / 'empty-textbooks'),
    NODE_OPTIONS='--no-experimental-webstorage', PYTHONPATH=str(ROOT / 'apps/api'), ZQKY_KEEP_TEST_DATA='1')
env = dict(os.environ, **isolated)
env['PATH'] = str(Path('C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin')) + os.pathsep + env['PATH']

def source_hashes():
    names = set(args.source)
    if args.all_opening_sources:
        names.update(json.loads((OUT/'BASELINE.json').read_text(encoding='utf-8'))['sourceBefore'])
    if args.candidate:
        names.update(json.loads((ROOT/args.candidate).read_text(encoding='utf-8'))['sourceFiles'])
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sorted(names)}

def qa_hashes():
    if not args.candidate:
        return {}
    names = json.loads((ROOT/args.candidate).read_text(encoding='utf-8'))['executableQaFiles']
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}

def save(value):
    receipt.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

next_env = ROOT / 'apps/web/next-env.d.ts'
opening = (OUT / 'next-env.original.bin').read_bytes()
record = dict(label=args.label, command=command, cwd=str(ROOT), env=isolated,
    startedAt=datetime.now(timezone.utc).isoformat(), sampleRoot=str(sample), sampleRetained=True,
    sourceBefore=source_hashes(), qaBefore=qa_hashes(), status='running', runnerSHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    candidate=args.candidate, candidateSHA=hashlib.sha256((ROOT / args.candidate).read_bytes()).hexdigest() if args.candidate else None,
    nextEnvBeforeSHA=hashlib.sha256(next_env.read_bytes()).hexdigest())
if args.restore_next_env and next_env.read_bytes() != opening:
    raise RuntimeError('next-env does not match this batch opening; preserve and resolve before building')
save(record)
started = time.perf_counter()
child = None
try:
    with log.open('x', encoding='utf-8') as stream:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        record['pid'] = child.pid
        save(record)
        code = child.wait()
    record.update(status='complete', exitCode=code, childClosed=child.poll() is not None, logsClosed=True)
finally:
    if args.restore_next_env:
        generated = next_env.read_bytes()
        snapshot = OUT / (args.label + '-next-env.generated.bin')
        with snapshot.open('xb') as stream:
            stream.write(generated)
        next_env.write_bytes(opening)
        record.update(nextEnvGeneratedSHA=hashlib.sha256(generated).hexdigest(), nextEnvRestoredExact=next_env.read_bytes() == opening)
    record.update(finishedAt=datetime.now(timezone.utc).isoformat(), elapsedMs=round((time.perf_counter()-started)*1000, 3),
        sourceAfter=source_hashes(), qaAfter=qa_hashes(), nextEnvAfterSHA=hashlib.sha256(next_env.read_bytes()).hexdigest(),
        logSHA=hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None)
    record['changedSources'] = [name for name, value in record['sourceBefore'].items() if record['sourceAfter'].get(name) != value]
    record['changedQA'] = [name for name, value in record['qaBefore'].items() if record['qaAfter'].get(name) != value]
    save(record)
print(json.dumps({key: record.get(key) for key in ('label', 'pid', 'exitCode', 'elapsedMs', 'changedSources', 'sampleRoot')}, ensure_ascii=False), flush=True)
raise SystemExit(record.get('exitCode', 1))
