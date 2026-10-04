"""Freeze the reviewed B5 foundation before dispatching module writers."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
BATCH=OUT.parent.relative_to(ROOT).as_posix()
target=OUT/"B5-CONTRACT-FROZEN-v1.json"
if target.exists(): raise FileExistsError("new immutable contract version required")
names=[
    BATCH+"/B5-CONTRACT-v1.md", BATCH+"/B5-OPENAPI-v2.json", BATCH+"/B5-TASK-CARDS-v1.md",
    BATCH+"/ctrl/B5-WIRE-EXAMPLES-v2.json", BATCH+"/ctrl/B5-OLD-MIGRATIONS-v2.json",
    "apps/api/app/contracts/lesson_plans.py", "apps/api/app/core/migrations/lesson_plans.py",
    "apps/web/src/contracts/lesson-plans.ts", "apps/web/src/contracts/rag-v2.ts",
    "apps/web/src/services/lesson-plans-api.ts", "apps/web/src/features/lesson-plan/model/types.ts",
    "apps/web/src/features/chat/model/rag-v2.ts", "apps/web/src/features/chat/model/rag-evidence-null.test.ts",
    "apps/api/app/core/sqlite.py", "apps/api/tests/test_sqlite_commit_rollback.py",
    BATCH+"/g2-v00/B5-CONTRACT-REVIEW-v1.json", BATCH+"/g2-v00/B5-CONTRACT-REVIEW-v1.md",
]
review=json.loads((ROOT/names[-2]).read_text(encoding="utf-8"))
assert "STATIC_CONTRACT_REVIEW_APPROVED" in json.dumps(review),"independent static approval required"
labels=["b5-contract-probe-v2","b5-ddl-probe-v3","b5-foundation-typecheck-v2","b5-foundation-lint-v2",
        "b5-null-evidence-unit-v1","b5-sqlite-commit-tests-v1"]
checks=[]
for label in labels:
    relative=BATCH+"/ctrl/"+label+"-command.json"
    value=json.loads((ROOT/relative).read_text(encoding="utf-8"))
    assert value["exitCode"]==0 and not value["changedSources"],label
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in value["sourceAfter"].items()),label
    checks.append(dict(receipt=relative,exitCode=0,elapsedMs=value["elapsedMs"]))
    names.extend([relative,BATCH+"/ctrl/"+label+".log"])
for name in ("B5-DDL-PROBE-v2.json","B5-CONTRACT-PROBE-v2.json","B5-BASELINE-v1.json","G2-CLOSED-r4-v1.json"):
    names.append(BATCH+"/ctrl/"+name)
files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(set(names))}
nextenv=hashlib.sha256((ROOT/"apps/web/next-env.d.ts").read_bytes()).hexdigest()
assert nextenv=="0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc"
value=dict(contract="B5-v1",status="FROZEN_FOR_MODULE_IMPLEMENTATION",frozenAt=datetime.now(timezone.utc).isoformat(),
    branch="main",head="6aeb57280f6a7e0d7391cad4d150745479ea58ec",files=files,checks=checks,
    nextEnvSHA=nextenv,oldNineDeclarations="ctrl/B5-OLD-MIGRATIONS-v2.json",
    revisionHistory=[dict(revision="prepared-v1",status="not_frozen",reason="Initial-pointer four-column FK; nullable RAG projection; unique accepted proposal and base guard; COMMIT failure rollback. Original probes/logs retained."),
      dict(revision="frozen-v1",status="static_approved",reason="Independent static review, fresh v2 wire schemas and DDL probe, type/lint and meaningful regressions passed. No implemented API/browser or final B5 acceptance claimed.")])
with target.open("x",encoding="utf-8",newline="\n") as stream: stream.write(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(dict(status=value["status"],fileCount=len(files),sha256=hashlib.sha256(target.read_bytes()).hexdigest())))
