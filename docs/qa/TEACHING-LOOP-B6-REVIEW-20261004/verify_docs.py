"""Check actual file targets in new review/prompt and current entry documents."""
from pathlib import Path
import json
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
documents = [ROOT / "docs" / p for p in (
    "CURRENT_STATUS.md", "NEXT_SESSION_START.md", "PLAN.md", "README.md",
    "design/teaching-loop-v1/README.md", "qa/README.md",
    "design/teaching-loop-v1/B7_总控启动提示词_20261004.md",
)] + [OUT / p for p in ("REVIEW.md", "README.md", "edit/REVIEW.md", "sources/REVIEW.md", "quality/REVIEW.md")]
target = OUT / "DOCUMENT-CHECK.json"
target.write_text(json.dumps({"status": "running"}) + "\n", encoding="utf-8")
checked = 0
missing = []
for document in documents:
    for match in re.finditer(r"\[[^\]\n]*\]\(([^)\n]+)\)", document.read_text(encoding="utf-8-sig")):
        link = match.group(1).strip().strip("<>")
        if re.match(r"^(https?://|app:|codex:|#)", link):
            continue
        link = re.sub(r":\d+$", "", unquote(link.split("#", 1)[0]))
        path = Path(link)
        if not path.is_absolute():
            path = document.parent / path
        checked += 1
        if not path.is_file() and not path.is_dir():
            missing.append({"document": document.relative_to(ROOT).as_posix(), "target": link})
result = {"status": "pass" if not missing else "fail", "documents": len(documents),
          "fileLinksChecked": checked, "missing": missing}
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
if missing:
    raise SystemExit(1)
