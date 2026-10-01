"""V00 · B3-r4/r3 最终确认：定版 163/163 自洽 + r2→定版差异恰为两个文档。

运行（仓库根）：
  apps/api/.venv/Scripts/python.exe -X utf8 docs/qa/TEACHING-LOOP-B3/V00-probes/p36_final_confirm.py
退出码 0 = 定版 163/163 磁盘自洽、r2→定版差异恰为
`docs/qa/TEACHING-LOOP-B3/{EVIDENCE-COMMANDS.md,REPORT.md}`、产品/测试零变化；
退出码 1 = 存在不一致（明细逐条打印）。

同时记录 r3 与定版的关系（r3 为中间冻结；若两者只在同两个文档上不同，如实记录）。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
QA = REPO / "docs" / "qa" / "TEACHING-LOOP-B3"

DOCS = [
    "docs/qa/TEACHING-LOOP-B3/EVIDENCE-COMMANDS.md",
    "docs/qa/TEACHING-LOOP-B3/REPORT.md",
]
R2_PRODUCT_FILES = [
    "apps/web/src/contracts/scores.ts",
    "apps/web/src/services/assessments-api.ts",
]


def load(name: str) -> dict:
    return json.loads((QA / name).read_text(encoding="utf-8"))


def hash_file(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def diff(a: dict, b: dict) -> dict:
    fa, fb = a["files"], b["files"]
    return {
        "added": sorted(set(fb) - set(fa)),
        "removed": sorted(set(fa) - set(fb)),
        "changed": sorted(rel for rel in set(fa) & set(fb) if fa[rel] != fb[rel]),
    }


def main() -> int:
    final = load("FROZEN-B3.json")
    r2 = load("FROZEN-B3-r2.json")
    r3 = load("FROZEN-B3-r3.json")
    r4 = load("FROZEN-B3-r4.json")

    disk_ok, disk_bad = 0, []
    for rel, expected in final["files"].items():
        actual = hash_file(rel)
        if actual == expected:
            disk_ok += 1
        else:
            disk_bad.append({"file": rel, "manifest": expected[:16], "disk": actual[:16]})

    r2_to_final = diff(r2, final)
    r2_to_r3 = diff(r2, r3)
    r3_to_final = diff(r3, final)
    product_changed = [
        rel for rel in r2_to_final["changed"]
        if rel.startswith(("apps/", "tests/", "scripts/"))
    ]
    changed_files_all = sorted(r2_to_final["changed"])

    checks = {
        "finalRevision": final.get("revision"),
        "finalDeclared": final.get("fileCount"),
        "diskOk": disk_ok,
        "diskBad": disk_bad,
        "r2ToFinal": r2_to_final,
        "r2ToFinalProductChanged": product_changed,
        "r2ProductFilesUnchanged": {
            rel: hash_file(rel) == r2["files"][rel] == final["files"][rel]
            for rel in R2_PRODUCT_FILES
        },
        "finalEqualsR4": final["files"] == r4["files"],
        "r4Revision": r4.get("revision"),
        "r2ToR3": r2_to_r3,
        "r3ToFinal": r3_to_final,
        "r3ToFinalOnlyDocs": r3_to_final["changed"] == DOCS
        and r3_to_final["added"] == []
        and r3_to_final["removed"] == [],
    }

    passed = (
        disk_ok == len(final["files"])
        and not disk_bad
        and changed_files_all == DOCS
        and r2_to_final["added"] == []
        and r2_to_final["removed"] == []
        and product_changed == []
        and all(checks["r2ProductFilesUnchanged"].values())
        and checks["finalEqualsR4"]
    )
    payload = {"probe": "p36_final_confirm", "checks": checks, "verdict": "pass" if passed else "fail"}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    (HERE / "p36_final_confirm.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[p36_final_confirm] disk {disk_ok}/{len(final['files'])} "
        f"r2->final changed={changed_files_all} final==r4={checks['finalEqualsR4']} "
        f"r3==final={final['files'] == r3['files']} verdict={payload['verdict']}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
