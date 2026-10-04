"""Read-only opening inventory; no app imports or service/network operations."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]
BATCH = ROOT / "docs/qa/TEACHING-LOOP-G3-B6-20261004"
OLD_CANDIDATE = ROOT / "docs/qa/TEACHING-LOOP-G2-B5-20261003/CANDIDATE-B5-r8.json"
OLD_SHA = "c33c85698ba2be8e6b08fe432305622bf3635a1bc5bb0cc515472996ebbe2007"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8").strip()


def main() -> None:
    started = time.monotonic()
    output = BATCH / "BASELINE-v1.json"
    if output.exists():
        raise RuntimeError("Opening inventory is immutable; use a new version.")
    old_bytes = OLD_CANDIDATE.read_bytes()
    assert sha(old_bytes) == OLD_SHA
    old = json.loads(old_bytes)
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    status = git("-c", "core.quotepath=false", "status", "--short")
    groups = {}
    all_drift = []
    for name in ("sourceFiles", "executableQaFiles", "sharedContractFiles", "buildFiles", "priorEvidence"):
        expected = old[name]
        actual = {}
        drift = []
        for rel, expected_hash in expected.items():
            path = ROOT / rel
            digest = sha(path.read_bytes()) if path.is_file() else None
            actual[rel] = digest
            if digest != expected_hash:
                drift.append({"path": rel, "expected": expected_hash, "actual": digest})
        groups[name] = {"count": len(expected), "drift": drift, "files": actual}
        all_drift.extend(drift)
    old_qa = {}
    for path in sorted((ROOT / "docs/qa").rglob("*")):
        if not path.is_file() or path.is_relative_to(BATCH):
            continue
        old_qa[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    docs = {}
    before = BATCH / "ctrl/opening-documents"
    for rel in (
        "AGENTS.md", "apps/web/AGENTS.md", "apps/api/AGENTS.md",
        "apps/web/src/features/lesson-plan/AGENTS.md", "docs/CURRENT_STATUS.md",
        "docs/PROJECT_GUIDE.md", "docs/NEXT_SESSION_START.md", "docs/API.md",
        "docs/ROUTES.md", "docs/README.md", "docs/qa/README.md", "docs/PLAN.md",
        "docs/design/teaching-loop-v1/README.md",
        "docs/design/teaching-loop-v1/多Agent实施任务计划书_v2.0.md",
    ):
        data = (ROOT / rel).read_bytes()
        target = before / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        docs[rel] = sha(data)
    next_env = (ROOT / "apps/web/next-env.d.ts").read_bytes()
    (BATCH / "ctrl/next-env.opening.bin").write_bytes(next_env)
    assert sha(next_env) == "0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc"
    build_id = (ROOT / "apps/web/.next/BUILD_ID").read_text().strip()
    manifest = json.loads((ROOT / "apps/web/.next/routes-manifest.json").read_bytes())
    rewrites = manifest["rewrites"]
    assert branch == "main" and head == "6cb6a40db890390f0261d547213e319040f64785"
    record = {
        "task": "TEACHING-LOOP-G3-B6-20261004", "version": "OPENING-v1",
        "capturedAt": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "branch": branch, "head": head, "parent": git("rev-parse", "HEAD^"),
        "status": status, "oldCandidateSHA": OLD_SHA, "oldCandidateHead": old["head"],
        "groups": groups, "fiveGroupDrift": all_drift,
        "oldQaFiles": old_qa, "oldQaCount": len(old_qa),
        "openingDocuments": docs, "nextEnvSHA": sha(next_env),
        "buildId": build_id, "actualRewrites": rewrites,
        "appMainImported": False, "servicesStarted": False, "gitWrites": False,
        "elapsedMs": round((time.monotonic() - started) * 1000, 3),
    }
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "baseline": str(output.relative_to(ROOT)), "branch": branch, "head": head,
        "groups": {k: {"count": v["count"], "drift": v["drift"]} for k, v in groups.items()},
        "oldQaCount": len(old_qa), "buildId": build_id, "actualRewrites": rewrites,
        "nextEnvSHA": sha(next_env), "elapsedMs": record["elapsedMs"],
    }, ensure_ascii=False, indent=2))
    if all_drift:
        raise SystemExit("Opening drift requires attribution before product edits.")


if __name__ == "__main__":
    main()
