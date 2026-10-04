"""Read-only evidence audit. No application imports or service execution."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path.cwd().resolve()
BATCH = ROOT / "docs/qa/TEACHING-LOOP-G1-B4-20261002"
OUT = BATCH / "d00"


def read(name):
    return json.loads((BATCH / name).read_text(encoding="utf-8-sig"))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def xml_result(name):
    tree = ET.parse(BATCH / name)
    cases = tree.getroot().findall(".//testcase")
    failures = [x.attrib.get("name") for x in cases if x.find("failure") is not None]
    errors = [x.attrib.get("name") for x in cases if x.find("error") is not None]
    skipped = [x.attrib.get("name") for x in cases if x.find("skipped") is not None]
    return {
        "path": name,
        "sha256": digest(BATCH / name),
        "tests": len(cases),
        "failed": len(failures),
        "errors": len(errors),
        "skipped": len(skipped),
        "passed": len(cases) - len(failures) - len(errors) - len(skipped),
        "names": [x.attrib.get("name") for x in cases],
    }


r1 = read("CANDIDATE-g1-r1.json")
r2 = read("CANDIDATE-g1-r2.json")
protected = read("PROTECTED-EVIDENCE.json")
base = read("BASELINE.json")
paths = subprocess.check_output(
    ["rg", "--files", "--hidden", "apps", "tests", "scripts", "infra", "assets"], cwd=ROOT
).decode("utf-8").splitlines()
if (ROOT / ".github").exists():
    paths += subprocess.check_output(["rg", "--files", "--hidden", ".github"], cwd=ROOT).decode("utf-8").splitlines()
tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
paths += [p for p in tracked if p and ("/" not in p or p.split("/")[0] in {"apps", "tests", "scripts", "infra", "assets", ".github"})]
actual = {}
for raw in sorted(set(paths)):
    path = Path(raw)
    if any((part.startswith(".env") and part != ".env.example") or part in {".local-data", "__pycache__", ".venv", ".next", "node_modules", ".pytest_cache"} for part in path.parts):
        continue
    if path.suffix in {".pyc", ".tsbuildinfo"} or not (ROOT / path).is_file():
        continue
    actual[path.as_posix()] = digest(ROOT / path)

drift = [p for p, h in r2["files"].items() if actual.get(p) != h]
added = [p for p in actual if p not in r2["files"]]
old_drift = [p for p, h in protected.items() if not (ROOT / p).is_file() or digest(ROOT / p) != h]
common_drift = [p for p, h in r1["files"].items() if r2["files"].get(p) != h]
extension = sorted(set(r2["files"]) - set(r1["files"]))
next_equal = (ROOT / "apps/web/next-env.d.ts").read_bytes() == (BATCH / "next-env.original.bin").read_bytes()
changed = [p for p, h in r2["files"].items() if p in base["sourceFiles"] and h != base["sourceFiles"][p]]
new_tests = [p for p in r2["files"] if p not in base["sourceFiles"] and ("test_g1_" in p or p.endswith("AssessmentsWorkspace.test.tsx"))]
product = [p for p in changed if p.startswith("apps/") and not ("/tests/" in p or ".test." in p)]
modified_tests = [p for p in changed if p not in product]

xml_names = [
    "v00-jobs/independent-first.xml", "v00-score-qb/accepted-v2.xml",
    "v00-fe/component-third.xml", "v00-fe/real-api-third.xml",
    "root/jobs-first.xml", "g1-score/final.xml", "g1-qb/accepted.xml",
    "v00-score-qb/first.xml", "v00-score-qb/recheck.xml", "v00-score-qb/final.xml", "v00-score-qb/accepted.xml",
    "v00-fe/component-first.xml", "v00-fe/component-second.xml",
    "v00-fe/real-api-first.xml", "v00-fe/real-api-second.xml",
]
xml = [xml_result(n) for n in xml_names]
jobs_receipts = read("v00-jobs/receipts.json")
fe_receipts = read("v00-fe/component-receipts.json")
real_receipts = read("v00-fe/real-api-receipts.json")
qb_receipts = [json.loads(x) for x in (BATCH / "v00-score-qb/http-receipts.jsonl").read_text(encoding="utf-8-sig").splitlines() if x.strip()]
logs = {}
for name in ["root/g1-check-first.log", "root/g1-api-first.log", "root/closed-check-accepted.log", "root/closed-check-first.log", "root/closed-check-final.log"]:
    text = (BATCH / name).read_text(encoding="utf-8-sig")
    logs[name] = {"sha256": digest(BATCH / name), "bytes": (BATCH / name).stat().st_size, "summaryLines": [x for x in text.splitlines() if any(s in x for s in ["passed", "skipped", "Duration", "Compiled successfully", "AssertionError", '"participantTotals"'])]}

summary = {
    "task": "G1-D00", "version": "v1", "capturedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "read-only file/log/XML/receipt audit; no application or browser execution",
    "candidate": {"version": r2["version"], "sha256": digest(BATCH / "CANDIDATE-g1-r2.json"), "count": len(r2["files"]), "drift": drift, "added": added,
                  "r1CommonCount": len(r1["files"]), "r1CommonDrift": common_drift, "r2Extension": extension},
    "protected": {"count": len(protected), "drift": old_drift},
    "nextEnvOriginalEqual": next_equal,
    "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT).decode().strip(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
    "g1Changes": {"productFiles": product, "modifiedTests": modified_tests, "newTests": new_tests, "total": len(product) + len(modified_tests) + len(new_tests)},
    "xml": xml,
    "receiptCounts": {"jobs": len(jobs_receipts), "jobsGroups": dict(Counter(x.get("name") for x in jobs_receipts)), "component": len(fe_receipts), "componentGroups": dict(Counter(x.get("case") for x in fe_receipts)), "realApi": len(real_receipts), "scoreQb": len(qb_receipts), "scoreQbGroups": dict(Counter(x.get("kind") for x in qb_receipts))},
    "finalRunExit": {"jobs": read("v00-jobs/independent-first-run.json")["exitCode"], "scoreQb": int((BATCH / "v00-score-qb/accepted-v2.exit.txt").read_text().strip()), "component": read("v00-fe/component-third-command.json")["exitCode"], "realApi": read("v00-fe/real-api-third-command.json")["exitCode"]},
    "browserCollection": read("v00-fe/browser-collection-command.json"),
    "rootLogSummaries": logs,
    "closedDataEvidence": read("root/closed-data-check.json"),
    "resourcesEvidence": read("RESOURCES.json"),
    "allFirstFailureFilesPreserved": all((BATCH / p).is_file() for p in ["root/omml-first.log", "root/omml-r2.log", "root/g1-typecheck-first.log", "root/closed-check-first-source.py", "root/closed-check-second-source.py", "root/closed-check-first.log", "root/closed-check-final.log"]),
}
assert not drift and not added and not old_drift and not common_drift and next_equal
assert extension == ["apps/api/.env.example"]
assert len(product) == 13 and len(modified_tests) == 4 and len(new_tests) == 4
assert [(x["passed"], x["failed"], x["skipped"]) for x in xml[:4]] == [(52, 0, 0), (53, 0, 0), (20, 0, 0), (1, 0, 0)]
assert all(v == 0 for v in summary["finalRunExit"].values())
assert "1088 passed" in (BATCH / "root/g1-check-first.log").read_text(encoding="utf-8-sig")
assert "1599 passed, 1 skipped" in (BATCH / "root/g1-api-first.log").read_text(encoding="utf-8-sig")
assert summary["resourcesEvidence"]["B4"] == "not_started"
assert summary["resourcesEvidence"]["browserAndE2E"] == "not_run"
assert summary["allFirstFailureFilesPreserved"]
(OUT / "EVIDENCE-AUDIT.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"candidateCount": len(r2["files"]), "candidateDrift": len(drift), "protectedCount": len(protected), "protectedDrift": len(old_drift), "finalRuns": [x["passed"] for x in xml[:4]], "product": len(product), "modifiedTests": len(modified_tests), "newTests": len(new_tests), "browser": "not_run", "B4": "not_started"}, ensure_ascii=False))
