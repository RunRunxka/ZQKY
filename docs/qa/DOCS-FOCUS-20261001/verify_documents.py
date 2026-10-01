"""Read-only verification of the document cleanup; writes only its own report."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
REPORT = Path(__file__).with_name("verification.json")
MANIFEST = ROOT / "docs/archive/pre-20260929/MANIFEST.json"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          encoding="utf-8", errors="replace")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
archive_failures = []
for entry in manifest["files"]:
    path = (ROOT / entry["destination"]).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        archive_failures.append({"path": entry["destination"], "reason": "missing_or_outside_workspace"})
    elif sha(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
        archive_failures.append({"path": entry["destination"], "reason": "bytes_or_sha256_changed"})

recent = ["docs/qa/RAG-QUALITY-v1", "docs/qa/TEACHING-LOOP-B0",
          "docs/qa/TEACHING-LOOP-B1", "docs/qa/TEACHING-LOOP-B2",
          "docs/qa/TEACHING-LOOP-B2-REVIEW-20261001", "docs/qa/TEACHING-LOOP-B3",
          "docs/qa/TEACHING-LOOP-B3-REVIEW-20261001"]
recent_changes = git("diff", "--name-only", "--", *recent).stdout.splitlines()
scope_changes = git("diff", "--name-only", "-z").stdout.split("\0")
scope_violations = [name for name in scope_changes if name and not (
    name in {"AGENTS.md", "README.md"} or name.startswith("docs/") or
    name.startswith("项目规划/") or name.startswith("apps/") and name.endswith("/AGENTS.md"))]

pins = []
quality = json.loads((ROOT / "docs/qa/RAG-QUALITY-v1/FROZEN-CANDIDATE.json").read_text(encoding="utf-8-sig"))
for name in manifest["compatibilityCopiesAtOriginalPath"]:
    expected = next(item["sha256"] for item in quality["files"] if item["path"] == name)
    path = ROOT / name
    pins.append({"path": name, "pass": path.is_file() and sha(path) == expected})

b3 = json.loads((ROOT / "docs/qa/TEACHING-LOOP-B3/FROZEN-B3.json").read_text(encoding="utf-8-sig"))
product_records = {name: value for name, value in b3["files"].items()
                   if name.startswith("apps/") and not name.endswith("AGENTS.md")}
product_drift = []
for name, value in product_records.items():
    expected = value["sha256"] if isinstance(value, dict) else value
    path = ROOT / name
    if not path.is_file() or sha(path) != expected:
        product_drift.append(name)

# Historical original bytes are intentionally excluded from link rewriting.
sources = {ROOT / "AGENTS.md", ROOT / "README.md"}
sources.update((ROOT / "docs").glob("*.md"))
sources.update((ROOT / "apps").rglob("AGENTS.md"))
sources.update((ROOT / "docs/replica").glob("*.md"))
sources.update((ROOT / "docs/modules").rglob("*.md"))
sources.update((ROOT / "docs/design/teaching-loop-v1").rglob("*.md"))
sources.update([ROOT / "docs/archive/README.md", ROOT / "docs/archive/pre-20260929/README.md",
                ROOT / "docs/qa/README.md", Path(__file__).with_name("README.md"),
                ROOT / "项目规划/README.md", ROOT / "docs/qa/RAG-REBUILD-v1/README.md"])
REPORT.write_text('{"verification":"pending"}\n', encoding="utf-8")
links_checked = 0
broken_links = []
unbalanced_fences = []
for path in sorted(sources):
    text = path.read_text(encoding="utf-8-sig")
    fence = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence is None:
                fence = token[0]
            elif token[0] == fence:
                fence = None
            continue
        if fence:
            continue
        for match in re.finditer(r"\]\(([^)\n]+)\)", line):
            target = match.group(1).strip()
            if target.startswith("<") and ">" in target:
                target = target[1:target.index(">")]
            else:
                target = re.split(r'\s+["\']', target, maxsplit=1)[0]
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not target or re.match(r"^(?:https?|mailto|app|plugin|codex|data|file):", target, re.I):
                continue
            target = re.sub(r":\d+(?::\d+)?$", "", target)
            resolved = (path.parent / target).resolve()
            links_checked += 1
            if not resolved.exists():
                broken_links.append({"source": relative(path), "line": line_number, "target": target})
    if fence:
        unbalanced_fences.append(relative(path))

diff_check = git("diff", "--check")
failures = bool(archive_failures or recent_changes or scope_violations or product_drift or
                broken_links or unbalanced_fences or any(not item["pass"] for item in pins) or
                diff_check.returncode)
result = {
    "checkedAt": "2026-10-01", "head": git("rev-parse", "HEAD").stdout.strip(),
    "focusFromInclusive": "2026-09-29", "result": "fail" if failures else "pass",
    "archive": {"filesChecked": len(manifest["files"]), "movedFiles": 679,
                "snapshots": len(manifest["files"]) - 679, "failures": archive_failures},
    "compatibilityCopies": pins,
    "currentDocumentLinks": {"documents": len(sources), "fileLinksChecked": links_checked,
                             "broken": broken_links, "unbalancedFences": unbalanced_fences},
    "retainedRecentEvidence": {"directories": len(recent), "trackedChanges": recent_changes},
    "productCode": {"b3FrozenFilesChecked": len(product_records), "drift": product_drift,
                    "outOfDocumentationScopeChanges": scope_violations},
    "gitDiffCheck": {"exitCode": diff_check.returncode, "output": diff_check.stdout + diff_check.stderr},
    "notRun": ["npm/check", "pytest", "Playwright", "real model/Word/Qdrant", "formal database migration"],
    "limitations": ["Historical document links are interpreted through MANIFEST; original bytes unchanged.",
                    "File-link validation does not validate web URLs or Markdown fragment anchors.",
                    "Current document edits are subsequent changes, not a refreeze of old candidates."],
}
REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(1 if failures else 0)
