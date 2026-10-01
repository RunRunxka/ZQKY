"""Archive explicitly inventoried historical documents, preserving their bytes."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "docs/archive/pre-20260929"
SNAPSHOT = ROOT / "docs/archive/snapshots/20261001-docs-focus"
OLD_QA = """acceptance-20260912 B-R05-EXT2 B-R05-EXT3 B-R05-EXT4 B-R05-EXT5
B-R05-EXTEND BOOKS-CS-FOLLOWUP CHAT-CONTENT-MATH-AND-FOLLOW-20260924
CHAT-CONTEXT-BUDGET chat-fixes-20260909 chat-home-20260909 chat-links-20260914
chat-models course-r11-20260914 docs-focus-20260915 docs-focus-20260920
H1-BOOKS-COMMIT-SAFETY H1-BOOKS-HARDEN H1-BOOKS-PIPELINE H1-COURSE-SESSIONS
handoff-20260910 main-review-20260922 model-accept-20260913 RAG-DELIVERY-20260926
RAG-I0-PREP RAG-REBUILD-v1 reading-r09-20260915 shell-accept-20260913
space-r05-20260918 UX-PERF-CLOSEOUT-20260923 UX-REGRESSION-FIX-20260923""".split()
SNAPSHOT_FILES = [
    "AGENTS.md", "README.md", "apps/api/AGENTS.md", "docs/CURRENT_STATUS.md",
    "docs/PROJECT_GUIDE.md", "docs/PLAN.md", "docs/API.md", "docs/ROUTES.md",
    "docs/MULTI_AGENT_COLLABORATION_PROPOSAL.md", "docs/modules/lesson-plan/README.md",
    "docs/design/teaching-loop-v1/README.md",
    "docs/replica/PAGE_MATRIX.md", "docs/replica/AI_INTERACTIONS.md",
    "docs/replica/MOTION_MATRIX.md", "docs/replica/NEXT_SESSION_START.md",
]


def bounded(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT.resolve()) or resolved == ROOT.resolve():
        raise RuntimeError(f"Out-of-workspace or root target: {path}")
    return resolved


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(source: Path, target: Path, operation: str) -> dict:
    return {"source": relative(source), "destination": relative(target),
            "operation": operation, "sha256": sha(source), "bytes": source.stat().st_size}


manifest_path = bounded(ARCHIVE / "MANIFEST.json")
if manifest_path.exists() or SNAPSHOT.exists():
    raise RuntimeError("Archive already exists; inspect instead of rerunning or overwriting.")

records = []
directory_moves = [(ROOT / "docs/qa" / name, ARCHIVE / "qa" / name) for name in OLD_QA]
directory_moves += [(ROOT / "docs/reviews", ARCHIVE / "reviews"),
                    (ROOT / "项目规划", ARCHIVE / "项目规划")]
for source, target in directory_moves:
    bounded(source)
    bounded(target)
    if not source.is_dir() or target.exists():
        raise RuntimeError(f"Unsafe/missing/conflicting move: {source} -> {target}")

# Discover exact old QA files pinned by recent frozen manifests. Their original
# path must remain available, in addition to their unmodified archive copy.
pinned = set()
for path in (ROOT / "docs/qa").rglob("*.json"):
    if "FROZEN" not in path.name or any(path.is_relative_to(source) for source, _ in directory_moves):
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError):
        continue
    files = data.get("files", {}) if isinstance(data, dict) else {}
    names = files.keys() if isinstance(files, dict) else (
        item.get("path") for item in files if isinstance(item, dict)
    ) if isinstance(files, list) else []
    for name in names:
        if not isinstance(name, str):
            continue
        original = ROOT / name
        if any(original.is_relative_to(source) for source, _ in directory_moves):
            pinned.add(name)

for name in SNAPSHOT_FILES:
    source = bounded(ROOT / name)
    target = bounded(SNAPSHOT / name)
    if not source.is_file():
        raise RuntimeError(f"Snapshot source missing: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = record(source, target, "snapshot_before_current_document_update")
    shutil.copy2(source, target)
    records.append(entry)

for source, target in directory_moves:
    files = sorted(path for path in source.rglob("*") if path.is_file())
    for path in files:
        bounded(path)
        records.append(record(path, target / path.relative_to(source), "move_historical_material"))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))

for name in sorted(pinned):
    original = bounded(ROOT / name)
    archived = next(target / original.relative_to(source)
                    for source, target in directory_moves if original.is_relative_to(source))
    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archived, original)

failures = [entry["destination"] for entry in records
            if sha(ROOT / entry["destination"]) != entry["sha256"]]
if failures:
    raise RuntimeError(f"Archive bytes changed: {failures}")
manifest = {
    "archivedAt": "2026-10-01", "focusFromInclusive": "2026-09-29",
    "headAtStart": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "scope": "Historical batches before cutoff plus exact pre-edit snapshots of current documents",
    "directories": [{"source": relative(source), "destination": relative(target)} for source, target in directory_moves],
    "compatibilityCopiesAtOriginalPath": sorted(pinned),
    "files": records,
    "preservation": "Every archived file verified by sha256; historical reports/frozen manifests not rewritten.",
}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"movedQADirectories": len(OLD_QA), "movedDirectories": len(directory_moves),
                  "verifiedFiles": len(records), "compatibilityCopies": sorted(pinned)}, ensure_ascii=False))
