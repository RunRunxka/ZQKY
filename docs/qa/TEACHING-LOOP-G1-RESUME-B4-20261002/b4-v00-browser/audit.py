"""Read-only frozen-source identity audit; accepts CTRL's explicit candidate.

No behavior test, main import, migration, listener or dependency mutation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

folder=Path(__file__).resolve().parent;repository=folder.parents[3]
parser=argparse.ArgumentParser();parser.add_argument("manifest");parser.add_argument("expected_sha256");parser.add_argument("output")
options=parser.parse_args();started=time.perf_counter()
manifest=Path(options.manifest).resolve();raw=manifest.read_bytes();identity=hashlib.sha256(raw).hexdigest()
assert identity==options.expected_sha256
candidate=json.loads(raw);groups={}
for key in ("files","executableQaFiles","sharedContractFiles"):
    expected=candidate.get(key,{});mismatches=[]
    for relative,sha in expected.items():
        target=(repository/relative).resolve()
        if not target.is_relative_to(repository):raise RuntimeError("Manifest path escapes repository")
        actual=hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
        if actual!=sha:mismatches.append(dict(path=relative,expected=sha,actual=actual))
    groups[key]=dict(count=len(expected),mismatches=mismatches)
nextenv=hashlib.sha256((repository/"apps/web/next-env.d.ts").read_bytes()).hexdigest()
output=Path(options.output).resolve()
if not output.is_relative_to(folder) or output.exists():raise RuntimeError("New QA receipt only")
result=dict(task="B4-V00-F v1 identity audit",manifest=str(manifest),manifestSHA256=identity,groups=groups,nextEnvSHA256=nextenv,nextEnvMatches=nextenv==candidate["nextEnvSHA256"],elapsedMs=round((time.perf_counter()-started)*1000),behaviorTest=False)
output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
assert all(not g["mismatches"] for g in groups.values()) and result["nextEnvMatches"],result
print(json.dumps(result,ensure_ascii=False))
