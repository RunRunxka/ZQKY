"""Candidate/file preservation for a read-only review; no application imports."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
MANIFEST = ROOT / "docs/qa/TEACHING-LOOP-G3-B6-20261004/CANDIDATE-B6-r1.json"
GROUPS = ("sourceFiles", "executableQaFiles", "sharedContractFiles", "buildFiles", "frozenB6ArtifactFiles")
AUTHORITY = ("docs/CURRENT_STATUS.md", "docs/NEXT_SESSION_START.md", "docs/PLAN.md",
             "docs/README.md", "docs/design/teaching-loop-v1/README.md", "docs/qa/README.md")

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                          text=True, encoding="utf-8").stdout.strip()

candidate = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
checks = {group: {"count": len(candidate[group]), "drift": [p for p, s in candidate[group].items()
                 if not (ROOT / p).is_file() or sha(ROOT / p) != s]} for group in GROUPS}
protected = {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / "docs/qa").rglob("*")
             if p.is_file() and OUT not in p.parents and p != ROOT / "docs/qa/README.md"}
result = {"head": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
          "manifestSha256": sha(MANIFEST), "buildId": candidate["buildId"],
          "nextEnvSha256": sha(ROOT / "apps/web/next-env.d.ts"), "candidateChecks": checks,
          "historicalQaCount": len(protected), "historicalQaFiles": protected,
          "authorityDocuments": {p: sha(ROOT / p) for p in AUTHORITY},
          "scope": "Read-only product review, isolated narrow probes, review and next-stage documents. No product fixes, services, browser, live models, formal data, cleanup or Git writes."}
mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
if mode == "baseline":
    target = OUT / "BASELINE.json"
    if target.exists():
        raise SystemExit("Refusing to replace opening baseline.")
else:
    baseline = json.loads((OUT / "BASELINE.json").read_text(encoding="utf-8"))
    result.update({"headUnchanged": result["head"] == baseline["head"],
                   "branchUnchanged": result["branch"] == baseline["branch"],
                   "manifestUnchanged": result["manifestSha256"] == baseline["manifestSha256"],
                   "nextEnvUnchanged": result["nextEnvSha256"] == baseline["nextEnvSha256"],
                   "historicalQaDrift": [p for p, s in baseline["historicalQaFiles"].items() if protected.get(p) != s],
                   "historicalQaAdditions": sorted(set(protected) - set(baseline["historicalQaFiles"])),
                   "authorityDocumentDeltas": {p: {"before": baseline["authorityDocuments"][p], "after": s}
                      for p, s in result["authorityDocuments"].items() if s != baseline["authorityDocuments"][p]}})
    target = OUT / "FINAL-VERIFICATION.json"
result["status"] = "fail" if (any(c["drift"] for c in checks.values())
    or result.get("historicalQaDrift") or result.get("historicalQaAdditions")
    or any(result.get(k) is False for k in ("headUnchanged", "branchUnchanged", "manifestUnchanged", "nextEnvUnchanged"))) else "pass"
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "historicalQaFiles"}, ensure_ascii=False, indent=2))
if result["status"] == "fail":
    raise SystemExit(1)
