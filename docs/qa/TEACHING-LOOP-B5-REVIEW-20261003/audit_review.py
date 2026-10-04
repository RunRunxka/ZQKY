"""Read-only B5 r8 capture; no application imports or formal data access."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
MANIFEST = ROOT / "docs/qa/TEACHING-LOOP-G2-B5-20261003/CANDIDATE-B5-r8.json"

def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
        text=True, encoding="utf-8").stdout.strip()

candidate = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
checks = {}
for group in ("sourceFiles", "executableQaFiles", "sharedContractFiles", "buildFiles", "priorEvidence"):
    entries = candidate[group]
    checks[group] = {"count": len(entries), "drift": [relative for relative, expected in entries.items()
        if not (ROOT / relative).is_file() or digest(ROOT / relative) != expected]}

protected = {}
for path in (ROOT / "docs/qa").rglob("*"):
    if path.is_file() and OUT not in path.parents:
        protected[path.relative_to(ROOT).as_posix()] = digest(path)

result = {
    "head": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
    "version": candidate["version"], "manifestSha256": digest(MANIFEST), "candidateChecks": checks,
    "buildId": candidate["buildId"], "nextEnvSha256": digest(ROOT / "apps/web/next-env.d.ts"),
    "protectedOldQaCount": len(protected), "protectedOldQa": protected,
    "scope": "Review and next-stage documentation only; no product fixes, application starts, browser, extra identity HTTP, cleanup or Git writes.",
}
mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
if mode == "baseline":
    output = OUT / "BASELINE.json"
    if output.exists():
        raise SystemExit("Baseline already exists; refusing replacement.")
else:
    baseline = json.loads((OUT / "BASELINE.json").read_text(encoding="utf-8"))
    result.update({
        "headUnchanged": result["head"] == baseline["head"],
        "branchUnchanged": result["branch"] == baseline["branch"],
        "manifestUnchanged": result["manifestSha256"] == baseline["manifestSha256"],
        "nextEnvUnchanged": result["nextEnvSha256"] == baseline["nextEnvSha256"],
        "protectedOldQaDrift": [path for path, expected in baseline["protectedOldQa"].items() if protected.get(path) != expected],
        "protectedOldQaAdditions": sorted(set(protected) - set(baseline["protectedOldQa"])),
    })
    # Keep raw differences visible. Only exact, separately recorded changes are classified.
    declared_path = OUT / "DECLARED-DELTAS.json"
    declared = json.loads(declared_path.read_text(encoding="utf-8")) if declared_path.exists() else {}
    document_deltas = declared.get("authorityDocumentDeltas", {})
    accepted_documents = []
    invalid_declarations = []
    for path, change in document_deltas.items():
        if (path != "docs/qa/README.md"
                or change.get("beforeSha256") != baseline["protectedOldQa"].get(path)
                or change.get("afterSha256") != protected.get(path)
                or path not in result["protectedOldQaDrift"]):
            invalid_declarations.append(path)
        else:
            accepted_documents.append(path)
    historical = set(baseline["protectedOldQa"]) - set(accepted_documents)
    result["declaredAuthorityDocumentDeltas"] = {path: document_deltas[path] for path in accepted_documents}
    result["invalidDeltaDeclarations"] = invalid_declarations
    result["protectedHistoricalQaCount"] = len(historical)
    result["protectedHistoricalQaDrift"] = [path for path in result["protectedOldQaDrift"] if path in historical]
    head_delta = declared.get("externalHeadChange", {})
    result["externalHeadChange"] = head_delta
    result["externalHeadChangeVerified"] = bool(
        not result["headUnchanged"]
        and head_delta.get("beforeHead") == baseline["head"]
        and head_delta.get("afterHead") == result["head"]
        and git("show", "-s", "--format=%P", result["head"]) == baseline["head"]
        and not any(check["drift"] for check in checks.values()))
    result["preservationStatus"] = "pass_with_declared_deltas" if (
        not result["protectedHistoricalQaDrift"] and not invalid_declarations
        and not result["protectedOldQaAdditions"]
        and (result["headUnchanged"] or result["externalHeadChangeVerified"])
        and all(result[key] for key in ("branchUnchanged", "manifestUnchanged", "nextEnvUnchanged"))
        and not any(check["drift"] for check in checks.values())) else "fail"
    output = OUT / "FINAL-VERIFICATION.json"
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "protectedOldQa"}, ensure_ascii=False, indent=2))
if any(check["drift"] for check in checks.values()) or result.get("preservationStatus") == "fail":
    raise SystemExit(1)
