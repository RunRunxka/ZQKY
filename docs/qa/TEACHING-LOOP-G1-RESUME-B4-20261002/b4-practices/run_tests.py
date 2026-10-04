"""Run only T80 author tests with pre-import isolation and raw stream receipts."""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

root=Path.cwd()
directory=Path(__file__).resolve().parent
run=sys.argv[1]
temp=Path(tempfile.mkdtemp(prefix="zqky-b4-t80-"))
(temp/"empty-textbooks").mkdir()
env=os.environ.copy()
env.update(ZQKY_ENV="test",ZQKY_DATA_DIR=str(temp/"data"),PYTHONUTF8="1",PYTHONIOENCODING="utf-8",
    ZQKY_QDRANT_URL="http://127.0.0.1:16333",ZQKY_EMBEDDING_BASE_URL="http://127.0.0.1:9",ZQKY_TEXTBOOK_SOURCE_DIR=str(temp/"empty-textbooks"))
command=[str(root/"apps/api/.venv/Scripts/python.exe"),"-m","pytest","tests/test_practices_selection.py","tests/test_practices_review_export.py","tests/test_practices_conversion.py","tests/test_practices_api.py","-ra"]
start=datetime.datetime.now(datetime.timezone.utc).isoformat();tick=time.perf_counter()
child=subprocess.Popen(command,cwd=root/"apps/api",env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
stdout,stderr=child.communicate()
elapsed=round((time.perf_counter()-tick)*1000)
(directory/(run+"-stdout.log")).write_bytes(stdout)
(directory/(run+"-stderr.log")).write_bytes(stderr)
(directory/(run+".log")).write_bytes(stdout+b"\n--- STDERR ---\n"+stderr)
output=stdout.decode("utf-8",errors="replace")
receipt=dict(task="B4-T80 v1 author self-check",run=run,command=command,cwd=str(root/"apps/api"),
    environment={k:env[k] for k in ("ZQKY_ENV","ZQKY_DATA_DIR","PYTHONUTF8","PYTHONIOENCODING","ZQKY_QDRANT_URL","ZQKY_EMBEDDING_BASE_URL","ZQKY_TEXTBOOK_SOURCE_DIR")},
    start=start,end=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsedMs=elapsed,pid=child.pid,exitCode=child.returncode,
    temp=str(temp),resources={"ownedListeners":[],"browser":False,"childExited":child.poll() is not None,"tempRetained":True},
    rawStdout=run+"-stdout.log",rawStderr=run+"-stderr.log",singleRunSummary=re.findall(r"\d+ (?:passed|failed|error(?:s)?|skipped)",output))
(directory/(run+"-command.json")).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
print(output[-15000:]);print(json.dumps({k:receipt[k] for k in ("exitCode","elapsedMs","pid","temp","singleRunSummary")},ensure_ascii=False))
sys.exit(child.returncode)
