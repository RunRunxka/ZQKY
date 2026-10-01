"""V00 · B3 最终 30 秒确认（r7 收口）：定版 163/163 + r2→定版恰 3 个文档 + 产品零变化。

运行（仓库根）：
  apps/api/.venv/Scripts/python.exe -X utf8 docs/qa/TEACHING-LOOP-B3/V00-probes/p37_final_confirm_r7.py
退出码 0 = 全部成立；1 = 有任何不一致（明细打印）。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
QA = REPO / "docs" / "qa" / "TEACHING-LOOP-B3"

EXPECTED_DOCS = [
    "docs/CURRENT_STATUS.md",
    "docs/qa/TEACHING-LOOP-B3/EVIDENCE-COMMANDS.md",
    "docs/qa/TEACHING-LOOP-B3/REPORT.md",
]


def load(name: str) -> dict:
    return json.loads((QA / name).read_text(encoding="utf-8"))


def hash_file(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def main() -> int:
    final = load("FROZEN-B3.json")
    r2 = load("FROZEN-B3-r2.json")
    r7 = load("FROZEN-B3-r7.json")
    f, a, s = final["files"], r2["files"], r7["files"]

    disk_ok, disk_bad = 0, []
    for rel, expected in f.items():
        actual = hash_file(rel)
        if actual == expected:
            disk_ok += 1
        else:
            disk_bad.append({"file": rel, "manifest": expected[:16], "disk": actual[:16]})

    changed = sorted(rel for rel in set(a) & set(f) if a[rel] != f[rel])
    added = sorted(set(f) - set(a))
    removed = sorted(set(a) - set(f))
    product_changed = [
        rel for rel in changed if rel.startswith(("apps/", "tests/", "scripts/"))
    ]
    history = final.get("revisionHistory") or {}

    checks = {
        "finalRevision": final.get("revision"),
        "finalDeclared": final.get("fileCount"),
        "diskOk": disk_ok,
        "diskBad": disk_bad,
        "r2ToFinal": {"added": added, "removed": removed, "changed": changed},
        "r2ToFinalIsExactly3Docs": added == [] and removed == [] and changed == EXPECTED_DOCS,
        "productTestScriptsChanged": product_changed,
        "finalEqualsR7": f == s,
        "r7Revision": r7.get("revision"),
        "revisionHistoryDeclaresDocsVsR2": history.get("docsChangedVsR2"),
        "revisionHistoryProductUnchanged": history.get("productTestUnchangedSinceR2"),
        "revisionHistoryHasR1R7": sorted(
            (history.get("revisions") or {}).keys()
        ),
    }
    passed = (
        disk_ok == len(f)
        and not disk_bad
        and checks["r2ToFinalIsExactly3Docs"]
        and product_changed == []
        and checks["finalEqualsR7"]
        and sorted(history.get("docsChangedVsR2") or []) == sorted(EXPECTED_DOCS)
        and history.get("productTestUnchangedSinceR2") is True
        and checks["revisionHistoryHasR1R7"] == [f"B3-r{i}" for i in range(1, 8)]
    )
    payload = {"probe": "p37_final_confirm_r7", "checks": checks, "verdict": "pass" if passed else "fail"}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    (HERE / "p37_final_confirm_r7.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[p37_final_confirm_r7] disk {disk_ok}/{len(f)} r2->final={changed} "
        f"final==r7={checks['finalEqualsR7']} verdict={payload['verdict']}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
