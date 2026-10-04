"""One immutable isolated B6 quality command, PID/time/hash/first-failure retained."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
parser = argparse.ArgumentParser()
parser.add_argument("--label",required=True)
parser.add_argument("command",nargs=argparse.REMAINDER)
args = parser.parse_args()
assert args.label.replace("-","").isalnum()
command=args.command[1:] if args.command[:1]==["--"] else args.command
assert command
receipt,log=[OUT/(args.label+suffix) for suffix in ("-command.json",".log")]
assert not receipt.exists() and not log.exists(), "Preserve every first failure"
sample=Path(tempfile.mkdtemp(prefix="zqky-b5-b6-quality-"+args.label+"-"))
(sample/"empty-textbooks").mkdir()
isolated=dict(ZQKY_DATA_DIR=str(sample/"data"),ZQKY_ENV="test",PYTHONUTF8="1",PYTHONIOENCODING="utf8",PYTHONDONTWRITEBYTECODE="1",ZQKY_KEEP_TEST_DATA="1",ZQKY_QDRANT_URL="http://127.0.0.1:16333",ZQKY_EMBEDDING_BASE_URL="http://127.0.0.1:9",ZQKY_TEXTBOOK_SOURCE_DIR=str(sample/"empty-textbooks"),NODE_OPTIONS="--no-experimental-webstorage",B6_QUALITY_LABEL=args.label)
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
candidate=OUT.parent/"CANDIDATE-B6-base-v1.json"
c=json.loads(candidate.read_bytes())
source=lambda:{k:sha(ROOT/k) for k in c["sourceFiles"]}
qa_names=[p for p in OUT.glob("*") if p.suffix in {".py",".mjs"} or p.name=="case-specs.json"]
qa=lambda:{str(p.relative_to(ROOT)).replace("\\","/"):sha(p) for p in qa_names}
record=dict(label=args.label,startedAt=datetime.now(timezone.utc).isoformat(),runnerPID=os.getpid(),command=command,env=isolated,sampleRoot=str(sample),sampleRetained=True,candidateSHA=sha(candidate),sourceBefore=source(),qaBefore=qa(),runnerSHA=sha(Path(__file__)),status="running",appMainImportedByRunner=False)
save=lambda:receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf8",newline="\n")
save(); started=time.perf_counter()
with log.open("x",encoding="utf8",newline="\n") as stream:
    process=subprocess.Popen(command,cwd=ROOT,env={**os.environ,**isolated},stdout=stream,stderr=subprocess.STDOUT)
    record["pid"]=process.pid;save();code=process.wait()
record.update(status="complete",exitCode=code,childClosed=process.poll() is not None,logsClosed=True,elapsedMs=round((time.perf_counter()-started)*1000,3),finishedAt=datetime.now(timezone.utc).isoformat(),sourceAfter=source(),qaAfter=qa(),logSHA=sha(log))
record["sourceDrift"]=[k for k,h in record["sourceBefore"].items() if record["sourceAfter"].get(k)!=h]
record["qaDrift"]=[k for k,h in record["qaBefore"].items() if record["qaAfter"].get(k)!=h]
save();print(json.dumps({k:record[k] for k in ["label","pid","exitCode","elapsedMs","sampleRoot","sourceDrift","qaDrift"]},ensure_ascii=False),flush=True)
raise SystemExit(code)
