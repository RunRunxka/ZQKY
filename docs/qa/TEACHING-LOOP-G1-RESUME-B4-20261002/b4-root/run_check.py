"""Own isolated command, full log and single-run receipt. Never starts a frontend."""
import argparse
import hashlib
import json
import os
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
out = root/'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root'
if not args.label.replace('-', '').replace('_','').isalnum():
    raise ValueError('invalid receipt label')
receipt = out/(args.label+'-command.json')
log = out/(args.label+'.log')
if receipt.exists() or log.exists():
    raise ValueError('never overwrite an earlier command or first failure')
sample = Path(tempfile.mkdtemp(prefix='zqky-b4-'+args.label+'-'))
isolated = dict(ZQKY_DATA_DIR=str(sample/'data'), ZQKY_ENV='test', PYTHONUTF8='1',
    ZQKY_QDRANT_URL='http://127.0.0.1:16333', ZQKY_EMBEDDING_BASE_URL='http://127.0.0.1:9',
    ZQKY_TEXTBOOK_SOURCE_DIR=str(sample/'empty-textbooks'), NODE_OPTIONS='--no-experimental-webstorage',
    PYTHONPATH=str(root/'apps/api'), ZQKY_KEEP_TEST_DATA='1')
(sample/'empty-textbooks').mkdir()
environment = {**os.environ, **isolated}
payload = dict(label=args.label, command=command, cwd=str(root), env=isolated, sampleRoot=str(sample),
    settingsCredentialsFile=None, startedAt=datetime.now(timezone.utc).isoformat(),
    branch=subprocess.check_output(['git','branch','--show-current']).decode().strip(),
    head=subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
    candidate=args.candidate, candidateSHA256=None, status='running')
if args.candidate:
    candidate_path = root/args.candidate
    payload['candidateSHA256'] = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
receipt.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
start = time.perf_counter()
print(json.dumps(dict(label=args.label,sampleRoot=str(sample),command=command),ensure_ascii=False),flush=True)
try:
    with log.open('w',encoding='utf-8') as output:
        process = subprocess.Popen(command,cwd=root,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        payload['pid'] = process.pid
        receipt.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for line in process.stdout:
            output.write(line)
            output.flush()
            print(line,end='',flush=True)
        code = process.wait()
    payload.update(exit=code,wallTimeMs=round((time.perf_counter()-start)*1000,3),status='complete',finishedAt=datetime.now(timezone.utc).isoformat(),logSHA256=hashlib.sha256(log.read_bytes()).hexdigest(),samplePreserved=True)
except BaseException as exc:
    payload.update(status='launcher_error',error=type(exc).__name__,wallTimeMs=round((time.perf_counter()-start)*1000,3))
    receipt.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raise
receipt.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:payload[k] for k in ('label','exit','wallTimeMs','sampleRoot','pid')},ensure_ascii=False),flush=True)
sys.exit(code)
