"""Run exactly one authorized QA command, keeping complete streams and temp roots.

No service lifecycle commands. Explicit existing runtimes supplied by CTRL.
No implicit repeated trials; a failed run stops and preserves all original files.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

folder=Path(__file__).resolve().parent
repository=folder.parents[3]
parser=argparse.ArgumentParser()
parser.add_argument("mode",choices=["seed","fe","browser","types"])
parser.add_argument("run")
parser.add_argument("--node")
parser.add_argument("--seed")
options=parser.parse_args()
if not re.fullmatch(r"[a-z0-9-]+",options.run):raise ValueError("Safe unique run ID required")
receipt_path=folder/(options.mode+"-"+options.run+"-command.json")
if receipt_path.exists():raise RuntimeError("Never overwrite a previous command receipt")
env=os.environ.copy()
if options.mode=="browser":
    if not options.seed:raise ValueError("Exact CTRL-owned seed required")
    seed_path=Path(options.seed).resolve();seed=json.loads(seed_path.read_text(encoding="utf-8"));temporary=Path(seed["dataDir"]).parent
    if not temporary.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not temporary.name.startswith("zqky-b4-v00-"):raise ValueError("Refusing unknown data root")
else:
    temporary=Path(tempfile.mkdtemp(prefix="zqky-b4-v00-"))
(temporary/"empty-textbooks").mkdir(exist_ok=True)
env.update(ZQKY_ENV="test",ZQKY_DATA_DIR=str(temporary/"data"),PYTHONUTF8="1",PYTHONIOENCODING="utf-8",
    ZQKY_QDRANT_URL="http://127.0.0.1:16333",ZQKY_EMBEDDING_BASE_URL="http://127.0.0.1:9",ZQKY_TEXTBOOK_SOURCE_DIR=str(temporary/"empty-textbooks"),NODE_OPTIONS="--no-experimental-webstorage",ZQKY_B4_V00_RUN=options.run)
python=repository/"apps/api/.venv/Scripts/python.exe"
if options.mode=="seed":
    command=[str(python),str(folder/"seed.py")]
else:
    if not options.node:raise ValueError("Explicit installed runtime required")
    runtime=Path(options.node).resolve()
    if not runtime.is_file():raise ValueError("Existing Node executable required")
    if options.mode=="fe":command=[str(runtime),str(repository/"node_modules/vitest/vitest.mjs"),"run","--config",str(folder/"vitest.config.ts"),"--reporter=verbose","--reporter=json","--outputFile",str(folder/("fe-"+options.run+"-results.json"))]
    elif options.mode=="types":command=[str(runtime),str(repository/"node_modules/typescript/bin/tsc"),"--project",str(folder/"tsconfig.json"),"--noEmit"]
    else:
        env.update(ZQKY_B4_V00_SEED=str(seed_path),ZQKY_B4_V00_OWNED_API="http://127.0.0.1:8001",ZQKY_B4_V00_PYTHON=str(python))
        command=[str(runtime),str(repository/"node_modules/@playwright/test/cli.js"),"test","--config",str(folder/"playwright.config.ts")]
start=datetime.datetime.now(datetime.timezone.utc).isoformat();tick=time.perf_counter()
child=subprocess.Popen(command,cwd=repository,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
stdout,stderr=child.communicate();elapsed=round((time.perf_counter()-tick)*1000)
prefix=options.mode+"-"+options.run
(folder/(prefix+"-stdout.log")).write_bytes(stdout);(folder/(prefix+"-stderr.log")).write_bytes(stderr)
(folder/(prefix+".log")).write_bytes(stdout+b"\n--- STDERR ---\n"+stderr)
receipt=dict(task="B4-V00-F v1",mode=options.mode,run=options.run,command=command,cwd=str(repository),start=start,end=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsedMs=elapsed,pid=child.pid,exitCode=child.returncode,
    environment={k:env[k] for k in ("ZQKY_ENV","ZQKY_DATA_DIR","PYTHONUTF8","PYTHONIOENCODING","ZQKY_QDRANT_URL","ZQKY_EMBEDDING_BASE_URL","ZQKY_TEXTBOOK_SOURCE_DIR","NODE_OPTIONS")},
    sources={str(p.relative_to(repository)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.suffix in {'.py','.ts','.tsx'}},
    resources=dict(ownedListeners=[],frontendLifecycle="user",backendLifecycle="CTRL",childExited=child.poll() is not None,tempRetained=True,temp=str(temporary)),rawStdout=prefix+"-stdout.log",rawStderr=prefix+"-stderr.log",singleRunSummary=re.findall(r"\d+ (?:passed|failed|error(?:s)?|skipped)",stdout.decode('utf-8',errors='replace')))
if options.mode=="browser":receipt.update(seed=str(seed_path),seedSHA256=hashlib.sha256(seed_path.read_bytes()).hexdigest())
if options.mode!="seed":receipt.update(nodeExecutable=str(runtime),nodeExecutableSHA256=hashlib.sha256(runtime.read_bytes()).hexdigest())
receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
print(stdout.decode("utf-8",errors="replace"));print(stderr.decode("utf-8",errors="replace"),file=sys.stderr)
print(json.dumps({k:receipt[k] for k in ("exitCode","elapsedMs","pid","singleRunSummary","resources")},ensure_ascii=False))
sys.exit(child.returncode)
