"""One explicitly owned production frontend; stop only the launched OS handle."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
label=sys.argv[1]
assert label.replace('-','').isalnum()
receipt=OUT/(label+'-service.json');log=OUT/(label+'.log');stop=OUT/(label+'.stop')
assert not any(path.exists() for path in (receipt,log,stop))
assert not [p for p in (ROOT/'apps/web').glob('.env*') if p.name!='.env.example'], 'Frontend startup would read a formal env file'
with socket.socket() as probe: probe.bind(('127.0.0.1',5174))
sample=Path(tempfile.mkdtemp(prefix='zqky-g2-frontend-'+label+'-'))
env=dict(os.environ,ZQKY_API_ORIGIN='http://127.0.0.1:8001',ZQKY_ENV='test',ZQKY_DATA_DIR=str(sample/'data'),NODE_OPTIONS='--no-experimental-webstorage')
node='C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
command=[node,str(ROOT/'scripts/run-web.mjs'),'start','5174']
record=dict(label=label,managerPid=os.getpid(),command=command,cwd=str(ROOT),port=5174,host='127.0.0.1',
    startedAtUtc=datetime.now(timezone.utc).isoformat(),buildId=(ROOT/'apps/web/.next/BUILD_ID').read_text().strip(),
    env={key:env[key] for key in ('ZQKY_API_ORIGIN','ZQKY_ENV','ZQKY_DATA_DIR','NODE_OPTIONS')},sampleRoot=str(sample),stopFile=str(stop),status='starting')
save=lambda:receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
save();child=None
try:
    with log.open('xb') as stream:
        child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        record.update(pid=child.pid,status='serving');save()
        while child.poll() is None:
            if stop.exists():
                record['ownedHandleTerminationRequested']=True;save()
                child.terminate();child.wait(timeout=15);break
            time.sleep(.2)
        record.update(exitCode=child.poll(),childClosed=child.poll() is not None)
    record.update(status='closed',logClosed=True,logSHA=hashlib.sha256(log.read_bytes()).hexdigest())
finally:
    record.update(finishedAtUtc=datetime.now(timezone.utc).isoformat(),sampleRetained=sample.exists(),stopRequested=stop.exists())
    save()
