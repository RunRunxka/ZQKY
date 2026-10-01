"""V00 · B3-r2 指纹复算（163 文件 + r1→r2 差异 + 文档登记散列核对）。

运行（仓库根）：
  apps/api/.venv/Scripts/python.exe -X utf8 docs/qa/TEACHING-LOOP-B3/V00-probes/p32_fingerprint_r2.py
退出码 0 = r2 清单 163/163 自洽且 r1→r2 差异恰 2 个产品文件；
退出码 1 = 存在不一致（明细逐条打印）。

注意：本探针把"磁盘与清单不一致的文件"与"r1/r2 清单差异"分开报告，
用于区分"候选移动"与"清单登记过期"。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
QA = REPO / "docs" / "qa" / "TEACHING-LOOP-B3"


def load(name: str) -> dict:
    return json.loads((QA / name).read_text(encoding="utf-8"))


def hash_file(rel: str) -> str | None:
    target = REPO / rel
    if not target.exists():
        return None
    return hashlib.sha256(target.read_bytes()).hexdigest()


def main() -> int:
    r1 = load("FROZEN-B3-r1.json")
    r2 = load("FROZEN-B3-r2.json")
    b3 = load("FROZEN-B3.json")

    r2_files = r2["files"]
    disk_ok, disk_bad = 0, []
    for rel, expected in r2_files.items():
        actual = hash_file(rel)
        if actual == expected:
            disk_ok += 1
        else:
            disk_bad.append(
                {"file": rel, "manifest": expected[:16], "disk": (actual or "MISSING")[:16]}
            )

    r1_files = r1["files"]
    added = sorted(set(r2_files) - set(r1_files))
    removed = sorted(set(r1_files) - set(r2_files))
    changed = sorted(
        rel for rel in set(r1_files) & set(r2_files) if r1_files[rel] != r2_files[rel]
    )
    product_changed = [
        rel for rel in changed if rel.startswith(("apps/", "tests/", "scripts/"))
    ]

    # 与 r2 清单不一致的文件中，哪些在 r1 清单里与 r2 完全相同（= 文档在两次冻结后被改写）
    stale_since_r1 = [
        item["file"] for item in disk_bad if r1_files.get(item["file"]) == r2_files[item["file"]]
    ]

    checks = {
        "r2Declared": r2.get("fileCount"),
        "r2Actual": len(r2_files),
        "diskOk": disk_ok,
        "diskBad": disk_bad,
        "r1ToR2": {"added": added, "removed": removed, "changed": changed},
        "productChanged": product_changed,
        "staleSinceR1": stale_since_r1,
        "b3ManifestEqualsR2": b3["files"] == r2_files,
        "r2Revision": r2.get("revision"),
        "b3Revision": b3.get("revision"),
    }
    # 判定：r2 的**产品部分**必须全对且差异恰为声明的 2 文件；
    # 若 diskBad 仅剩"r1/r2 清单相同、磁盘在其后被改写"的文档，记为 stale（不判 pass 也不吞掉）。
    product_all_ok = all(
        hash_file(rel) == expected for rel, expected in r2_files.items()
        if not rel.startswith("docs/qa/TEACHING-LOOP-B3/")
    )
    verdict = (
        "pass"
        if (disk_ok == len(r2_files) and changed == sorted(
            ["apps/web/src/contracts/scores.ts", "apps/web/src/services/assessments-api.ts"]
        ) and added == [] and removed == [])
        else ("stale_docs_only" if product_all_ok and set(stale_since_r1) == {i["file"] for i in disk_bad} else "fail")
    )
    payload = {
        "probe": "p32_fingerprint_r2",
        "checks": checks,
        "productAllOk": product_all_ok,
        "verdict": verdict,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    (HERE / "p32_fingerprint_r2.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[p32_fingerprint_r2] disk {disk_ok}/{len(r2_files)} stale={stale_since_r1} "
        f"r1->r2 +{len(added)} ~{len(changed)} -{len(removed)} verdict={verdict}"
    )
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
