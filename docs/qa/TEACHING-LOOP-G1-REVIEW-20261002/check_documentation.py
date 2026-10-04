"""Check this review's local links and tracked whitespace without changing files."""
from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
documents = [
    "docs/CURRENT_STATUS.md", "docs/NEXT_SESSION_START.md", "docs/README.md",
    "docs/PLAN.md", "docs/qa/README.md", "docs/design/teaching-loop-v1/README.md",
    "docs/design/teaching-loop-v1/G1续验与B4启动提示词_20261002.md",
    "docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/REVIEW.md",
    "docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/jobs/RESULT.md",
    "docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/score-qb/RESULT.md",
    "docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/frontend/RESULT.md",
]
checked = 0
failures = []
for relative in documents:
    document = ROOT / relative
    text = document.read_text(encoding="utf-8-sig")
    text = re.sub(r"(?ms)^(```|~~~).*?^\1[^\n]*$", "", text)
    for raw in re.findall(r"\[[^\]\n]*\]\(<?([^\n)>]+)>?\)", text):
        if raw.startswith(("http://", "https://", "codex://", "mailto:", "#")):
            continue
        target = re.sub(r":\d+$", "", raw.split("#", 1)[0])
        path = Path(target)
        resolved = path if path.is_absolute() else document.parent / path
        checked += 1
        if not resolved.exists():
            failures.append({"document": relative, "target": raw})
check = subprocess.run(["git", "-c", "core.safecrlf=false", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
result = {"checkedLocalLinks": checked, "linkFailures": failures, "diffCheckExitCode": check.returncode, "diffCheckOutput": check.stdout + check.stderr}
(OUT / "DOCUMENTATION-CHECK.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
if failures or check.returncode:
    raise SystemExit(1)
