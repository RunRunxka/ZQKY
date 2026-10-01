"""V00 · B3 指纹自核（163 文件 + 相对 G0 差异 + 文档-only 移动）。

运行（仓库根）：
  apps/api/.venv/Scripts/python.exe -X utf8 docs/qa/TEACHING-LOOP-B3/V00-probes/p31_fingerprint_b3.py
退出码 0 = 163/163 一致且差异清单与 FROZEN-B3.json 声明一致。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # docs/qa/TEACHING-LOOP-B3/V00-probes -> repo root
QA = REPO / "docs" / "qa" / "TEACHING-LOOP-B3"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hashes(files: dict[str, str]) -> tuple[int, list, list]:
    ok = 0
    missing = []
    mismatch = []
    for rel, expected in files.items():
        target = REPO / rel
        if not target.exists():
            missing.append(rel)
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest == expected:
            ok += 1
        else:
            mismatch.append({"file": rel, "expected": expected[:16], "actual": digest[:16]})
    return ok, missing, mismatch


def main() -> int:
    b3 = load(QA / "FROZEN-B3.json")
    before = load(QA / "FROZEN-B3-before-docs.json")
    g0 = load(QA / "FROZEN-G0.json")

    b3_files, before_files, g0_files = b3["files"], before["files"], g0["files"]
    ok, missing, mismatch = hashes(b3_files)
    checks = {
        "fileCountDeclared": b3.get("fileCount"),
        "fileCountActual": len(b3_files),
        "hashOk": ok,
        "missing": missing,
        "mismatch": mismatch,
    }

    added_vs_before = sorted(set(b3_files) - set(before_files))
    removed_vs_before = sorted(set(before_files) - set(b3_files))
    changed_vs_before = sorted(
        rel for rel in set(b3_files) & set(before_files) if b3_files[rel] != before_files[rel]
    )
    product_changed = [
        rel
        for rel in changed_vs_before
        if rel.startswith(("apps/", "tests/", "scripts/"))
    ]
    checks["docOnlyMove"] = {
        "added": added_vs_before,
        "removed": removed_vs_before,
        "changed": changed_vs_before,
        "productCodeChanged": product_changed,
    }

    added = sorted(set(b3_files) - set(g0_files))
    removed = sorted(set(g0_files) - set(b3_files))
    changed = sorted(
        rel for rel in set(b3_files) & set(g0_files) if b3_files[rel] != g0_files[rel]
    )
    manifest_added = sorted(b3["changedSinceG0"]["added"])
    manifest_changed = sorted(b3["changedSinceG0"]["changed"])
    manifest_removed = sorted(b3["changedSinceG0"]["removed"])
    checks["vsG0"] = {
        "computed": {"added": added, "changed": changed, "removed": removed},
        "manifest": {"added": manifest_added, "changed": manifest_changed, "removed": manifest_removed},
        "counts": {"added": len(added), "changed": len(changed), "removed": len(removed)},
    }

    passed = (
        not missing
        and not mismatch
        and checks["fileCountDeclared"] == checks["fileCountActual"] == ok
        and added_vs_before == ["docs/qa/TEACHING-LOOP-B3/REPORT.md"]
        and removed_vs_before == []
        and changed_vs_before == ["docs/CURRENT_STATUS.md"]
        and product_changed == []
        and added == manifest_added
        and changed == manifest_changed
        and removed == manifest_removed
    )
    payload = {
        "probe": "p31_fingerprint_b3",
        "baseCommit": b3.get("baseCommit"),
        "revision": b3.get("revision"),
        "hashSource": b3.get("hashSource"),
        "checks": checks,
        "verdict": "pass" if passed else "fail",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    (HERE / "p31_fingerprint_b3.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[p31_fingerprint_b3] {ok}/{len(b3_files)} "
        f"vsG0 +{len(added)} ~{len(changed)} -{len(removed)} verdict={payload['verdict']}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
