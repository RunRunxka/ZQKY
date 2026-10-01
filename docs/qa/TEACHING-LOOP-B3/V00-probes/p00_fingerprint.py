"""P00 · FROZEN-G0 指纹复算 + changedSinceB2 交叉核对（只读）。

用法：python docs/qa/TEACHING-LOOP-B3/V00-probes/p00_fingerprint.py
输出 JSON 到 stdout，退出码 0=全部一致，1=存在差异。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # repo root
G0 = ROOT / "docs/qa/TEACHING-LOOP-B3/FROZEN-G0.json"
B2 = ROOT / "docs/qa/TEACHING-LOOP-B2/FROZEN-CANDIDATE.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    g0 = json.loads(G0.read_text(encoding="utf-8"))
    b2 = json.loads(B2.read_text(encoding="utf-8"))
    files = g0["files"]
    b2files = b2["files"]

    missing, mismatch, ok = [], [], 0
    measured = {}
    for rel, want in sorted(files.items()):
        p = ROOT / rel
        if not p.is_file():
            missing.append(rel)
            continue
        got = sha256(p)
        measured[rel] = got
        if got == want:
            ok += 1
        else:
            mismatch.append({"path": rel, "want": want, "got": got})

    # 反向：磁盘上未登记的候选相关文件（仅统计，不判失败）
    extra = []

    # 与 B2 冻结清单对比，独立推导 added/changed/removed
    added = sorted(set(files) - set(b2files))
    removed = sorted(set(b2files) - set(files))
    changed = sorted(
        r for r in (set(files) & set(b2files)) if files[r] != b2files[r]
    )
    claimed = g0.get("changedSinceB2", {})
    claim_added = sorted(claimed.get("added", []))
    claim_changed = sorted(claimed.get("changed", []))
    claim_removed = sorted(claimed.get("removed", []))

    diff_ok = (added == claim_added and changed == claim_changed and removed == claim_removed)

    out = {
        "g0_fileCount": g0["fileCount"],
        "listed": len(files),
        "hashed_ok": ok,
        "missing": missing,
        "mismatch": mismatch,
        "measured_extra_vs_b2": {
            "added": added,
            "changed": changed,
            "removed": removed,
        },
        "claimed_changedSinceB2": {
            "added": claim_added,
            "changed": claim_changed,
            "removed": claim_removed,
        },
        "diff_matches_claim": diff_ok,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if (not missing and not mismatch and diff_ok and ok == g0["fileCount"]) else 1


if __name__ == "__main__":
    sys.exit(main())
