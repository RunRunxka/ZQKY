"""V00 · r2 指纹复算与 r1→r2 差异核对（只读）。

断言：
  A. FROZEN-G0.json（r2）106/106 sha256 与磁盘一致；
  B. r1→r2 差异 = 恰好 3 个文件（changed；0 added / 0 removed），其余 103 个文件散列不变；
  C. 三个变化文件在 r2 清单中的散列 = 磁盘实测（避免"清单与文件不同步"）。

运行：python docs/qa/TEACHING-LOOP-B3/V00-probes/p17_r2_fingerprint.py
退出码 0 = 全部一致。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
QA = ROOT / "docs/qa/TEACHING-LOOP-B3"
R2 = QA / "FROZEN-G0.json"
R1 = QA / "FROZEN-G0-r1.json"
EXPECTED_CHANGED = {
    "apps/api/app/core/migrations/teaching.py",
    "apps/api/tests/test_b2_migrations.py",
    "apps/api/tests/test_migrations.py",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    r2 = json.loads(R2.read_text(encoding="utf-8"))
    r1 = json.loads(R1.read_text(encoding="utf-8"))
    files2, files1 = r2["files"], r1["files"]

    missing, mismatch = [], []
    for rel, want in sorted(files2.items()):
        path = ROOT / rel
        if not path.is_file():
            missing.append(rel)
            continue
        got = sha256(path)
        if got != want:
            mismatch.append({"path": rel, "want": want, "got": got})

    added = sorted(set(files2) - set(files1))
    removed = sorted(set(files1) - set(files2))
    changed = sorted(rel for rel in set(files1) & set(files2) if files1[rel] != files2[rel])
    unchanged_count = sum(
        1 for rel in set(files1) & set(files2) if files1[rel] == files2[rel]
    )

    out = {
        "r2": {
            "fileCount": r2["fileCount"],
            "listed": len(files2),
            "hashedOk": len(files2) - len(missing) - len(mismatch),
            "missing": missing,
            "mismatch": mismatch,
        },
        "diffR1ToR2": {
            "added": added,
            "removed": removed,
            "changed": changed,
            "unchangedCount": unchanged_count,
            "equalsExpectedChanged": set(changed) == EXPECTED_CHANGED,
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    ok = (
        not missing
        and not mismatch
        and r2["fileCount"] == len(files2) == 106
        and not added
        and not removed
        and set(changed) == EXPECTED_CHANGED
        and unchanged_count == 103
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
