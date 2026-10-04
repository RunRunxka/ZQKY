"""Verify file targets of Markdown links in this review's delivery documents."""
from pathlib import Path
import json
import re
from urllib.parse import unquote

root = Path(__file__).resolve().parents[3]
out = Path(__file__).resolve().parent
documents = [
    root / "docs" / name for name in (
        "CURRENT_STATUS.md", "NEXT_SESSION_START.md", "README.md", "PLAN.md",
        "qa/README.md", "design/teaching-loop-v1/README.md",
        "design/teaching-loop-v1/B5_总控启动提示词_20261003.md",
    )
] + [out / name for name in (
    "README.md", "REVIEW.md", "analysis/RESULT.md", "frontend/RESULT.md", "practices/RESULT.md",
    "EVIDENCE-COMMANDS.md",
)]
checked = []
missing = []
for document in documents:
    for match in re.finditer(r"\[[^\]\n]*\]\(([^)\n]+)\)", document.read_text(encoding="utf-8-sig")):
        target = match.group(1).strip().strip("<>")
        if re.match(r"^(https?://|app:|codex:|#)", target):
            continue
        target = unquote(target.split("#", 1)[0])
        target = re.sub(r":\d+$", "", target)
        path = Path(target)
        if not path.is_absolute():
            path = document.parent / path
        item = {"document": document.relative_to(root).as_posix(), "target": target}
        checked.append(item)
        if not path.is_file() and not path.is_dir():
            missing.append(item)
result = {"documents": len(documents), "fileLinksChecked": len(checked), "missing": missing}
(out / "DOCUMENT-CHECK.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
if missing:
    raise SystemExit(1)
