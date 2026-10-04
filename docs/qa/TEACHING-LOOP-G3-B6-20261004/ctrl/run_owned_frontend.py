"""ROOT-owned loopback Next process. No HTTP identity probes or browser data."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--port', type=int, default=5174)
args = parser.parse_args()
assert args.port == 5174 and args.label.replace('-', '').isalnum()
receipt, log, stop = [OUT / (args.label + suffix) for suffix in ('-service.json', '.log', '.stop')]
assert not any(p.exists() for p in (receipt, log, stop))
with socket.socket() as listener:
    listener.bind(('127.0.0.1', args.port))
record = dict(label=args.label, runnerPID=os.getpid(), host='127.0.0.1', port=args.port,
    startedAt=datetime.now(timezone.utc).isoformat(), status='starting', stopFile=str(stop),
    buildId=(ROOT / 'apps/web/.next/BUILD_ID').read_text().strip(),
    routesManifestSHA=hashlib.sha256((ROOT / 'apps/web/.next/routes-manifest.json').read_bytes()).hexdigest(),
    rewrites=json.loads((ROOT / 'apps/web/.next/routes-manifest.json').read_bytes())['rewrites'],
    command=[shutil.which('node'), 'scripts/run-web.mjs', 'start', str(args.port)],
    identityHTTPProbe='not_run_policy_boundary_preserved', browserDataAccess=False)
save = lambda: receipt.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
save()
env = dict(os.environ, NODE_OPTIONS='--no-experimental-webstorage', ZQKY_API_ORIGIN='http://127.0.0.1:8001')
with log.open('x', encoding='utf-8') as stream:
    child = subprocess.Popen(record['command'], cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    record.update(pid=child.pid, childSpawnedAt=datetime.now(timezone.utc).isoformat(), status='running'); save()
    while child.poll() is None and not stop.exists():
        time.sleep(0.2)
    if stop.exists() and child.poll() is None:
        # The retained Popen process handle identifies our child even if a numeric PID is reused.
        record['stopRequestedAt'] = datetime.now(timezone.utc).isoformat(); save()
        child.terminate()
    code = child.wait(timeout=20)
record.update(status='closed', exitCode=code, childClosed=True, logsClosed=True,
    finishedAt=datetime.now(timezone.utc).isoformat(), logSHA=hashlib.sha256(log.read_bytes()).hexdigest())
save()
print(json.dumps({k: record.get(k) for k in ('label', 'pid', 'status', 'exitCode')}, ensure_ascii=False))
