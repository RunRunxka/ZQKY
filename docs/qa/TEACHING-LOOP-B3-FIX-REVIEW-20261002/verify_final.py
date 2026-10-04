"""Read-only candidate and documentation checks for this review delivery."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")

baseline = json.loads((EVIDENCE / "BASELINE.json").read_text(encoding="utf-8-sig"))
manifest_path = ROOT / "docs/qa/TEACHING-LOOP-B3-FIX-20261002/FROZEN-CANDIDATE.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
mismatches = []
for relative, expected in manifest["files"].items():
    path = ROOT / relative
    actual = sha(path) if path.is_file() else None
    if actual != expected:
        mismatches.append({"path": relative, "expected": expected, "actual": actual})

doc_paths = [
    "docs/CURRENT_STATUS.md", "docs/README.md", "docs/NEXT_SESSION_START.md",
    "docs/PLAN.md", "docs/qa/README.md", "docs/design/teaching-loop-v1/README.md",
    "docs/design/teaching-loop-v1/B4_总控启动提示词.md",
    "docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/REVIEW.md",
    "docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/frontend/REPORT.md",
    "docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/scores/RESULT.md",
    "docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/jobs-questions/RESULT.md",
]
output_path = EVIDENCE / "FINAL-VERIFICATION.json"
output_path.write_text("{}\n", encoding="utf-8")
link_failures = []
checked_links = 0
for relative in doc_paths:
    path = ROOT / relative
    if not path.is_file():
        link_failures.append({"document": relative, "target": "document_missing"})
        continue
    content = path.read_text(encoding="utf-8-sig")
    content = re.sub(r"(?ms)^(```|~~~).*?^\1[^\n]*$", "", content)
    for target in re.findall(r"\[[^\]\n]*\]\(<?([^\n)>]+)>?\)", content):
        if target.startswith(("https://", "http://", "#", "codex://", "mailto:")):
            continue
        target = re.sub(r":\d+$", "", target.split("#", 1)[0])
        target_path = Path(target)
        resolved = target_path if target_path.is_absolute() else path.parent / target_path
        checked_links += 1
        if not resolved.exists():
            link_failures.append({"document": relative, "target": target})

doc_diff = git("-c", "core.safecrlf=false", "diff", "--check", "--", *doc_paths)
all_diff = git("-c", "core.safecrlf=false", "diff", "--check")
result = {
    "head": git("rev-parse", "HEAD").stdout.strip(),
    "branch": git("branch", "--show-current").stdout.strip(),
    "headUnchanged": git("rev-parse", "HEAD").stdout.strip() == baseline["head"],
    "branchUnchanged": git("branch", "--show-current").stdout.strip() == baseline["branch"],
    "frozenCount": len(manifest["files"]),
    "frozenMismatches": mismatches,
    "reviewedFrozenSha256": sha(manifest_path),
    "frozenManifestUnchanged": sha(manifest_path) == baseline["reviewedFrozenSha256"],
    "nextEnvSha256": sha(ROOT / "apps/web/next-env.d.ts"),
    "nextEnvUnchanged": sha(ROOT / "apps/web/next-env.d.ts") == baseline["nextEnvSha256"],
    "checkedLocalLinks": checked_links,
    "linkFailures": link_failures,
    "documentationDiffCheckExitCode": doc_diff.returncode,
    "documentationDiffCheckOutput": doc_diff.stdout + doc_diff.stderr,
    "wholeWorkspaceDiffCheckExitCode": all_diff.returncode,
    "wholeWorkspaceDiffCheckOutput": all_diff.stdout + all_diff.stderr,
    "scope": "Review evidence and next-stage documentation only. No product fix, B4, commit, push, deployment or temp-directory deletion.",
}
output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
if mismatches or link_failures or not all((result["headUnchanged"], result["branchUnchanged"], result["frozenManifestUnchanged"], result["nextEnvUnchanged"])) or doc_diff.returncode:
    raise SystemExit(1)
