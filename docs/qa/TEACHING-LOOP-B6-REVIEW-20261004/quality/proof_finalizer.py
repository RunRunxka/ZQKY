"""Run unchanged finalizer bytes on a new review-only 14/15 evidence copy.

app.core.sqlite import is supplied a stdlib read-only equivalent. No app.main,
environment/config or model code imports; fixed original SQL databases read only.
"""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import os
import runpy
import shutil
import sqlite3
import sys
import types

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
Q = ROOT / "docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality"
load = lambda p: json.loads(p.read_bytes())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
label = "fourteenproof"
run = OUT / "runs" / label
assert not run.exists(), "Preserve first proof"
run.mkdir(parents=True)
summary = load(Q / "runs/offline-third/SUMMARY.json")
assert len(summary["results"]) == 15
omitted = summary["results"][-1]["caseId"]
summary["results"] = summary["results"][:-1]
# Keep original declared counts and original 15-DOCX manifest: this exactly tests
# whether loss of one completed per-case result is detected before PASS15.
(run / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
shutil.copyfile(Q / "runs/offline-third/seed.json", run / "seed.json")
for entry in summary["results"]:
    source = Q / "runs/offline-third/quality-cases" / entry["caseId"]
    destination = run / "quality-cases" / entry["caseId"]
    destination.mkdir(parents=True)
    for file in source.iterdir():
        if file.is_file() and file.name != "case-bound-v3.json":
            shutil.copyfile(file, destination / file.name)
export = OUT / "exports" / label
export.mkdir(parents=True)
shutil.copyfile(Q / "exports/offline-third/DOCX-MANIFEST.json", export / "DOCX-MANIFEST.json")
source_finalizer = Q / "finalize_review_v3.py"
copy_finalizer = OUT / "finalize_review_v3.original.py"
assert not copy_finalizer.exists()
shutil.copyfile(source_finalizer, copy_finalizer)
assert sha(source_finalizer) == sha(copy_finalizer)

opened = []
def open_readonly(path):
    connection = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    opened.append(str(path))
    return connection

sqlite_stub = types.ModuleType("app.core.sqlite")
sqlite_stub.open_readonly = open_readonly
saved_module = sys.modules.get("app.core.sqlite")
saved_argv = sys.argv[:]
saved_env = {k: os.environ.get(k) for k in ["ZQKY_ENV", "PYTHONUTF8", "PYTHONDONTWRITEBYTECODE"]}
sys.modules["app.core.sqlite"] = sqlite_stub
sys.argv = [str(copy_finalizer), "--run", label]
os.environ.update(ZQKY_ENV="test", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
output = io.StringIO()
try:
    with contextlib.redirect_stdout(output):
        runpy.run_path(str(copy_finalizer), run_name="__main__")
finally:
    sys.argv = saved_argv
    if saved_module is None:
        del sys.modules["app.core.sqlite"]
    else:
        sys.modules["app.core.sqlite"] = saved_module
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
result = load(OUT / ("RESULTS-" + label + "-v1.json"))
proof = dict(originalFinalizerSHA=sha(source_finalizer), copiedUnmodifiedSHA=sha(copy_finalizer), sourceSummarySHA=sha(Q / "runs/offline-third/SUMMARY.json"), proofSummarySHA=sha(run / "SUMMARY.json"), originalCaseCount=15, actualProofResults=len(summary["results"]), omittedCaseId=omitted, printed=json.loads(output.getvalue()), generatedVerdict={k: result[k] for k in ["caseCount", "technicalStructure", "docxStructure", "teacherQuality"]}, generatedActualResultCount=len(result["results"]), readOnlyDatabases=opened, copiedSourceUnchanged=True, productAppMainImported=False, modelCalls=0, writesOnlyReviewDirectory=True, finalizerReadOnlyImportShim="stdlib sqlite3 mode=ro/query_only; only existing original SQL readback")
assert proof["generatedActualResultCount"] == 14
assert result["caseCount"] == 15 and result["technicalStructure"] == result["docxStructure"] == "PASS15"
(OUT / "FINALIZER-COUNTEREXAMPLE.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
print(json.dumps(proof, ensure_ascii=False))
