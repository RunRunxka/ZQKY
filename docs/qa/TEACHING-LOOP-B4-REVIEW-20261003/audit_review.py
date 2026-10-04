"""Read-only B4 r21 candidate capture and review boundary verification."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
MANIFEST = ROOT / "docs/qa/TEACHING-LOOP-B4-RESUME-20261003/CANDIDATE-r21.json"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()

candidate = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
groups = ("files", "executableQaFiles", "sharedContractFiles", "buildFiles", "priorDailyEvidenceFiles")
checks = {}
for group in groups:
    entries = candidate[group]
    checks[group] = {"count": len(entries), "drift": [relative for relative, expected in entries.items()
        if not (ROOT / relative).is_file() or digest(ROOT / relative) != expected]}
protected = {}
for relative in ("docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002", "docs/qa/TEACHING-LOOP-B4-RESUME-20261003"):
    for path in (ROOT / relative).rglob("*"):
        if path.is_file():
            protected[path.relative_to(ROOT).as_posix()] = digest(path)
result = {
    "head": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
    "version": candidate["version"], "manifestSha256": digest(MANIFEST), "candidateChecks": checks,
    "buildId": candidate["buildId"], "nextEnvSha256": digest(ROOT / "apps/web/next-env.d.ts"),
    "protectedEvidenceCount": len(protected), "protectedEvidence": protected,
    "scope": "Code review and next-stage documentation; no product changes, no listeners/browser, no B5, no Git writes or cleanup.",
}
mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
if mode == "baseline":
    output = OUT / "BASELINE.json"
    if output.exists():
        raise SystemExit("Baseline exists; refusing replacement.")
else:
    baseline = json.loads((OUT / "BASELINE.json").read_text(encoding="utf-8"))
    result.update({
        "headUnchanged": result["head"] == baseline["head"],
        "branchUnchanged": result["branch"] == baseline["branch"],
        "manifestUnchanged": result["manifestSha256"] == baseline["manifestSha256"],
        "nextEnvUnchanged": result["nextEnvSha256"] == baseline["nextEnvSha256"],
        "protectedEvidenceDrift": [path for path, expected in baseline["protectedEvidence"].items() if protected.get(path) != expected],
        "protectedEvidenceAdditions": sorted(set(protected) - set(baseline["protectedEvidence"])),
    })
    output = OUT / "FINAL-VERIFICATION.json"
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "protectedEvidence"}, ensure_ascii=False, indent=2))
if any(value["drift"] for value in checks.values()) or result.get("protectedEvidenceDrift") or result.get("protectedEvidenceAdditions") or any(result.get(key) is False for key in ("headUnchanged", "branchUnchanged", "manifestUnchanged", "nextEnvUnchanged")):
    raise SystemExit(1)
