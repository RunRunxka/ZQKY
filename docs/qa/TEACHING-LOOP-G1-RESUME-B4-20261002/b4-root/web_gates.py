"""Run the root check/build only after the user stopped 5174; restore exact next-env bytes."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
root=Path.cwd().resolve()
batch=root/'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002'
out=batch/'b4-root'
label,candidate=sys.argv[1:3]
with socket.socket() as probe:
    assert probe.connect_ex(('127.0.0.1',5174))!=0, 'User-owned 5174 must be manually stopped before rebuild'
original=(out/'next-env.original.bin').read_bytes()
path=root/'apps/web/next-env.d.ts'
assert path.read_bytes()==original
receipt=out/(label+'-next-env.json')
assert not receipt.exists()
environment={**os.environ,'ZQKY_API_ORIGIN':'http://127.0.0.1:8001','PYTHONUTF8':'1'}
command=[sys.executable,str(out/'run_check.py'),'--label',label,'--candidate',candidate,'--',
    r'C:\Program Files\nodejs\node.exe',r'C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js','run','check']
result=dict(command=command,originalSHA256=hashlib.sha256(original).hexdigest())
try:
    completed=subprocess.run(command,cwd=root,env=environment,check=False)
    result['exit']=completed.returncode
finally:
    result['afterBuildBeforeRestoreSHA256']=hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_bytes(original)
    result['restoredSHA256']=hashlib.sha256(path.read_bytes()).hexdigest()
    result['exactOriginalBytesRestored']=path.read_bytes()==original
    receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
sys.exit(completed.returncode)
