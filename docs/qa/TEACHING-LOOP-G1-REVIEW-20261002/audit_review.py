"""Read-only G1 review boundary capture and post-review comparison."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
MANIFEST = ROOT / "docs/qa/TEACHING-LOOP-G1-B4-20261002/CANDIDATE-g1-r2.json"
OLD = ROOT / "docs/qa/TEACHING-LOOP-G1-B4-20261002"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()

candidate = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
files = candidate["files"]
drift = [path for path, expected in files.items() if not (ROOT / path).is_file() or digest(ROOT / path) != expected]
old_hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): digest(path) for path in OLD.rglob("*") if path.is_file()}
result = {
    "head": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
    "candidateVersion": candidate["version"], "candidateCount": len(files), "candidateDrift": drift,
    "manifestSha256": digest(MANIFEST),
    "nextEnvSha256": digest(ROOT / "apps/web/next-env.d.ts"),
    "protectedEvidenceCount": len(old_hashes), "protectedEvidence": old_hashes,
    "scope": "Review and continuation prompt only; no product changes, no listener/browser, no G1 execution closure or B4 development, no commit/push/deletion.",
}
mode = sys.argv[1] if len(sys.argv) > 1 else "baseline"
if mode == "baseline":
    target = OUT / "BASELINE.json"
    if target.exists():
        raise SystemExit("Baseline already exists; refusing to replace.")
else:
    baseline = json.loads((OUT / "BASELINE.json").read_text(encoding="utf-8"))
    result["protectedEvidenceDrift"] = [path for path, expected in baseline["protectedEvidence"].items() if old_hashes.get(path) != expected]
    result["protectedEvidenceAdditions"] = sorted(set(old_hashes) - set(baseline["protectedEvidence"]))
    result["headUnchanged"] = result["head"] == baseline["head"]
    result["manifestUnchanged"] = result["manifestSha256"] == baseline["manifestSha256"]
    result["nextEnvUnchanged"] = result["nextEnvSha256"] == baseline["nextEnvSha256"]
    target = OUT / "FINAL-VERIFICATION.json"
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "protectedEvidence"}, ensure_ascii=False, indent=2))
if drift or result.get("protectedEvidenceDrift") or result.get("protectedEvidenceAdditions") or result.get("headUnchanged") is False or result.get("manifestUnchanged") is False or result.get("nextEnvUnchanged") is False:
    raise SystemExit(1)
