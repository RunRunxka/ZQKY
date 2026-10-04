"""Own isolated command, full log and single-run receipt. Never starts a frontend."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--candidate')
parser.add_argument('command', nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ['--'] else args.command
if not command:
    raise ValueError('explicit command required')
root = Path.cwd().resolve()
out = root/'docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-root'
if not args.label.replace('-', '').replace('_','').isalnum():
    raise ValueError('invalid receipt label')
receipt = out/(args.label+'-command.json')
log = out/(args.label+'.log')
if receipt.exists() or log.exists():
    raise ValueError('never overwrite an earlier command or first failure')
configs = {
    (out.parent/'r14.external.config.ts').resolve(): ('ZQKY_B4_R14_RUN', 'first', 'r14-'),
    (out.parent/'b4-chat.external.config.ts').resolve(): ('ZQKY_B4_CHAT_RUN', 'resume-first', 'b4-chat-'),
    (out.parent/'b4-e2e.external.config.ts').resolve(): ('ZQKY_B4_QA_RUN', 'resume-first', 'b4-e2e-'),
}
configuration = None
for index, item in enumerate(command):
    if item == '--config':
        if index + 1 >= len(command):
            raise ValueError('explicit config path required')
        configuration = command[index + 1]
    elif item.startswith('--config='):
        configuration = item.split('=', 1)[1]
evidence = None
if configuration is not None:
    config_path = (root/configuration).resolve()
    if config_path not in configs:
        raise ValueError('only the three reviewed external test configs are authorized')
    variable, default, prefix = configs[config_path]
    run = os.environ.get(variable, default)
    if not re.fullmatch('[a-z0-9-]+', run):
        raise ValueError('invalid evidence run')
    evidence_dir = (out.parent/(prefix+run)).resolve()
    evidence_dir.relative_to(out.parent.resolve())
    if evidence_dir.exists():
        raise ValueError(f'never reuse an existing evidence directory: {evidence_dir}')
    evidence = dict(config=str(config_path), runVariable=variable, run=run, outputDirectory=str(evidence_dir))
elif len(command) > 2 and '@playwright' in command[1] and Path(command[1]).name == 'cli.js':
    raise ValueError('Playwright requires an explicit reviewed external config')
sample = Path(tempfile.mkdtemp(prefix='zqky-b4-'+args.label+'-'))
isolated = dict(ZQKY_DATA_DIR=str(sample/'data'), ZQKY_ENV='test', PYTHONUTF8='1',
    PYTHONIOENCODING='utf-8', ZQKY_QDRANT_URL='http://127.0.0.1:16333', ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9',
    ZQKY_TEXTBOOK_SOURCE_DIR=str(sample/'empty-textbooks'), NODE_OPTIONS='--no-experimental-webstorage',
    PYTHONPATH=str(root/'apps/api'), ZQKY_KEEP_TEST_DATA='1')
(sample/'empty-textbooks').mkdir()
environment = {**os.environ, **isolated}
payload = dict(label=args.label, command=command, cwd=str(root), env=isolated, sampleRoot=str(sample),
    settingsCredentialsFile=None, startedAt=datetime.now(timezone.utc).isoformat(),
    branch=subprocess.check_output(['git','branch','--show-current']).decode().strip(),
    head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
    candidate=args.candidate, candidateSHA256=None, evidence=evidence, status='running')
if args.candidate:
    candidate_path = root/args.candidate
    payload['candidateSHA256'] = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
receipt.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
start = time.perf_counter()
process = None
output = None
try:
    print(json.dumps(dict(label=args.label,sampleRoot=str(sample),command=command),ensure_ascii=False),flush=True)
    with log.open('x',encoding='utf-8') as output:
        process = subprocess.Popen(command,cwd=root,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        payload['pid'] = process.pid
        receipt.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for line in process.stdout:
            output.write(line)
            output.flush()
            print(line,end='',flush=True)
        code = process.wait()
        process.stdout.close()
    payload.update(exit=code, childExit=code, childClosed=True, stdoutClosed=process.stdout.closed,
        logsClosed=output.closed, wallTimeMs=round((time.perf_counter()-start)*1000,3), status='complete',
        finishedAt=datetime.now(timezone.utc).isoformat(), logSHA256=hashlib.sha256(log.read_bytes()).hexdigest(),
        samplePreserved=sample.exists(), descendantClosure='requires independent owned-service and port audit')
except BaseException as exc:
    cleanup_errors = []
    if process is not None:
        try:
            if process.poll() is None:
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    # Popen retains this launch's OS process handle; never target an arbitrary PID.
                    payload['ownedPopenTerminationRequested'] = True
                    process.terminate()
                    process.wait(timeout=10)
        except BaseException as cleanup_exc:
            cleanup_errors.append(repr(cleanup_exc))
        if process.stdout is not None:
            try:
                process.stdout.close()
            except BaseException as cleanup_exc:
                cleanup_errors.append(repr(cleanup_exc))
    payload.update(status='launcher_error', error=type(exc).__name__, firstFailure=repr(exc),
        cleanupErrors=cleanup_errors, childExit=process.poll() if process is not None else None,
        childClosed=process is None or process.poll() is not None,
        stdoutClosed=process is None or process.stdout is None or process.stdout.closed,
        logsClosed=output is None or output.closed, samplePreserved=sample.exists(),
        descendantClosure='not verified; CTRL must audit owned descendants and ports before next gate',
        finishedAt=datetime.now(timezone.utc).isoformat(),
        logSHA256=hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None,
        wallTimeMs=round((time.perf_counter()-start)*1000,3))
    receipt.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raise
receipt.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:payload[k] for k in ('label','exit','wallTimeMs','sampleRoot','pid')},ensure_ascii=False),flush=True)
sys.exit(code)
