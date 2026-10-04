"""New B5 source/QA/build/frozen-contract and completed-evidence binding."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
BATCH=Path(__file__).resolve().parent.parent
BASE_PATH=BATCH/"ctrl/B5-BASELINE-v1.json"
BASE=json.loads(BASE_PATH.read_text(encoding="utf-8"))
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
assert BASE["g2ClosedReceiptSHA"]==sha(BATCH/"ctrl/G2-CLOSED-r4-v1.json")
mode,version=sys.argv[1:3]
assert mode in ("freeze","audit") and version.replace("-","").isalnum()
contract_path=BATCH/"ctrl/B5-CONTRACT-FROZEN-v1.json"
frozen=json.loads(contract_path.read_text(encoding="utf-8"))
started=time.perf_counter()
sys.stdout.reconfigure(encoding="utf-8")

def sources():
    folders=[name for name in ("apps","tests","scripts","infra","assets",".github") if (ROOT/name).exists()]
    names=subprocess.check_output(["rg","--files","--hidden",*folders],cwd=ROOT).decode("utf-8").splitlines()
    tracked=subprocess.check_output(["git","ls-files","-z"],cwd=ROOT).decode("utf-8").split("\0")
    names += [name for name in tracked if name and ("/" not in name.replace("\\","/") or name.split("/")[0] in folders)]
    result={}
    for name in sorted(set(names)):
        path=Path(name)
        if any((part.startswith(".env") and part!=".env.example") or part in
            (".local-data","__pycache__",".venv",".next",".next-test","node_modules",".pytest_cache") for part in path.parts):continue
        if path.suffix in (".pyc",".tsbuildinfo") or not (ROOT/path).is_file():continue
        result[path.as_posix()]=sha(ROOT/path)
    return result

def qa_sources():
    result={name:sha(ROOT/name) for name in BASE["qaBefore"]}
    for path in sorted(BATCH.rglob("*")):
        if path.is_file() and (path.suffix in (".py",".ts",".tsx",".js",".mjs",".cjs",".ps1") or path.name.endswith("tsconfig.json")):
            result[path.relative_to(ROOT).as_posix()]=sha(path)
    return result

def build_sources():
    directory=ROOT/"apps/web/.next"
    return {path.relative_to(ROOT).as_posix():sha(path) for path in sorted(directory.rglob("*")) if path.is_file()
        and "cache" not in path.relative_to(directory).parts and path.name not in ("trace","trace-build")}

def differences(old,new):return [name for name,digest in old.items() if new.get(name)!=digest]
def additions(old,new):return [name for name in new if name not in old]
def drift(files):return [name for name,digest in files.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=digest]
branch=subprocess.check_output(["git","branch","--show-current"],cwd=ROOT).decode().strip()
head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT).decode().strip()
assert (branch,head)==(BASE["branch"],BASE["head"])
protected_drift=drift(BASE["priorHistorical"])
# Baseline v1 retained backslash keys for two live authority documents.
# Their original approved bytes remain protected by the G2 exact-doc snapshot;
# current progress text may change only under CTRL document ownership.
authority_all={Path(name).as_posix():digest for name,digest in BASE["authorityDocumentsAtStart"].items()}
authorized_live={(BATCH/filename).relative_to(ROOT).as_posix() for filename in ("README.md","REPORT.md")}
authority={name:digest for name,digest in authority_all.items() if name in authorized_live}
assert set(authority)==authorized_live
g2_immutable={name:digest for name,digest in BASE["g2Evidence"].items() if Path(name).as_posix() not in authority}
g2_live={name:digest for name,digest in BASE["g2Evidence"].items() if Path(name).as_posix() in authority}
assert {Path(name).as_posix() for name in g2_live}==authorized_live
g2_authority_preservation={}
for name,digest in g2_live.items():
    normalized=Path(name).as_posix()
    assert digest==authority[normalized]
    archived=BATCH/"ctrl/G2-DOC-CLOSE-CANDIDATE-v2/after"/Path(name)
    assert archived.is_file() and sha(archived)==digest, "approved G2 authority bytes missing"
    g2_authority_preservation[normalized]=dict(approvedSHA=digest,archive=str(archived.relative_to(ROOT).as_posix()),currentSHA=sha(ROOT/name))
g2_drift=drift(g2_immutable)
contract_drift=drift(frozen["files"])
assert not contract_drift,"frozen B5 foundation changed; explicitly revise contract before candidate"
source,qa,build=sources(),qa_sources(),build_sources()
contracts={name:sha(ROOT/name) for name in frozen["files"]}
old_contract_drift=drift(BASE["contractsBefore"])
assert not old_contract_drift,"completed G2 common contract changed"
next_matches=(ROOT/"apps/web/next-env.d.ts").read_bytes()==(BATCH/"ctrl/next-env.original.bin").read_bytes()
manifest=json.loads((ROOT/"apps/web/.next/routes-manifest.json").read_text(encoding="utf-8"))
rewrites=manifest["rewrites"]
entries=rewrites if isinstance(rewrites,list) else [entry for group in rewrites.values() for entry in group]
api=[entry for entry in entries if entry.get("source","").startswith("/api/")]
assert api and all(entry["destination"].startswith("http://127.0.0.1:8001/") for entry in api)
build_id=(ROOT/"apps/web/.next/BUILD_ID").read_text().strip()
candidate_path=BATCH/("CANDIDATE-"+version+".json")
if mode=="freeze":
    assert not candidate_path.exists() and not protected_drift and not g2_drift and next_matches
    active=set()
    for path in BATCH.rglob("*-command.json"):
        if json.loads(path.read_text(encoding="utf-8-sig")).get("status")=="running":
            active.add((path.parent,path.name.removesuffix("-command.json")))
    for path in BATCH.rglob("*-service.json"):
        if json.loads(path.read_text(encoding="utf-8-sig")).get("status")!="closed":
            active.add((path.parent,path.name.removesuffix("-service.json")))
    prior={}
    for directory in ("g2-be","g2-fe","g2-v00","b5-be","b5-ai","b5-fe","b5-v00","b5-review","b5-doc-audit","ctrl"):
        for path in sorted((BATCH/directory).rglob("*")):
            if any(path.parent==folder and path.name.startswith(label) for folder,label in active):continue
            if path.is_file() and path.suffix not in (".py",".ts",".tsx",".js",".mjs",".cjs",".ps1"):
                prior[path.relative_to(ROOT).as_posix()]=sha(path)
    for path in sorted([*BATCH.glob("CANDIDATE-*.json"),*BATCH.glob("AUDIT-*.json")]):prior[path.relative_to(ROOT).as_posix()]=sha(path)
    value=dict(capturedAtUtc=datetime.now(timezone.utc).isoformat(),version=version,branch=branch,head=head,
        baselineSHA=sha(BASE_PATH),frozenContractSHA=sha(contract_path),sourceFiles=source,sourceCount=len(source),
        executableQaFiles=qa,executableQaCount=len(qa),sharedContractFiles=contracts,
        buildFiles=build,buildCount=len(build),buildId=build_id,actualApiRewrites=api,
        historicalCount=len(BASE["priorHistorical"]),completedG2Count=len(BASE["g2Evidence"]),immutableG2Count=len(g2_immutable),authorityPreservation=g2_authority_preservation,
        priorEvidence=prior,priorCount=len(prior),activeEvidenceExcluded=[str(folder.relative_to(ROOT)/label) for folder,label in sorted(active)],
        changedFromOpening=differences(BASE["sourceBefore"],source),addedFromOpening=additions(BASE["sourceBefore"],source),
        nextEnvSHA=sha(ROOT/"apps/web/next-env.d.ts"),elapsedMs=round((time.perf_counter()-started)*1000,3))
    with candidate_path.open("x",encoding="utf-8") as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(version=version,SHA=sha(candidate_path),source=len(source),qa=len(qa),contracts=len(contracts),build=len(build),prior=len(prior),historical=len(BASE["priorHistorical"]),completedG2=len(BASE["g2Evidence"]))))
else:
    expected=json.loads(candidate_path.read_text(encoding="utf-8"))
    value=dict(capturedAtUtc=datetime.now(timezone.utc).isoformat(),version=version,candidateSHA=sha(candidate_path),
        sourceDrift=differences(expected["sourceFiles"],source),sourceAdded=additions(expected["sourceFiles"],source),
        qaDrift=differences(expected["executableQaFiles"],qa),qaAdded=additions(expected["executableQaFiles"],qa),
        contractDrift=differences(expected["sharedContractFiles"],contracts),buildDrift=differences(expected["buildFiles"],build),
        buildAdded=additions(expected["buildFiles"],build),protectedDrift=protected_drift,completedG2Drift=g2_drift,
        priorDrift=drift(expected["priorEvidence"]),authorityPreservation=g2_authority_preservation,immutableG2Count=len(g2_immutable),baselineMatches=expected["baselineSHA"]==sha(BASE_PATH),
        frozenContractMatches=expected["frozenContractSHA"]==sha(contract_path),nextEnvMatches=next_matches,
        buildIdentityMatches=build_id==expected["buildId"] and api==expected["actualApiRewrites"],
        sourceCount=len(source),qaCount=len(qa),buildCount=len(build),historicalCount=len(BASE["priorHistorical"]),completedG2Count=len(BASE["g2Evidence"]),
        elapsedMs=round((time.perf_counter()-started)*1000,3))
    keys=("sourceDrift","sourceAdded","qaDrift","qaAdded","contractDrift","buildDrift","buildAdded","protectedDrift","completedG2Drift","priorDrift")
    failed=any(value[key] for key in keys) or not all(value[key] for key in ("baselineMatches","frozenContractMatches","nextEnvMatches","buildIdentityMatches"))
    value["exitCode"]=int(failed)
    label=sys.argv[3];assert label.replace("-","").isalnum()
    with (BATCH/("AUDIT-"+version+"-"+label+".json")).open("x",encoding="utf-8") as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
    print(json.dumps({key:value[key] for key in ("version","exitCode","elapsedMs",*keys)}))
    raise SystemExit(int(failed))
