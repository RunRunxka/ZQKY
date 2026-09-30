"""V10 变异后散列对账（V00 / TEACHING-LOOP B0）。

复算 FROZEN-CANDIDATE.json 中全部 55 个文件的 sha256，逐条对账；并单独打印
本轮变异实验涉及的两个文件的散列，证明候选未被污染。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from _probe_common import EVIDENCE_DIR, REPO_ROOT

PROBE = "v10_hash_reconcile"
FROZEN = REPO_ROOT / "docs" / "qa" / "TEACHING-LOOP-B0" / "FROZEN-CANDIDATE.json"
MUTATED = (
    "apps/api/app/services/jobs/engine.py",
    "apps/api/app/repositories/jobs/repository.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    files: dict[str, str] = frozen["files"]
    same: list[str] = []
    different: list[tuple[str, str, str]] = []
    missing: list[str] = []
    for relative, expected in sorted(files.items()):
        path = REPO_ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        actual = sha256(path)
        (same if actual == expected else different).append(  # type: ignore[arg-type]
            relative if actual == expected else (relative, expected, actual)
        )

    print(f"冻结记录声明 {frozen['fileCount']} 个文件；实际记录 {len(files)} 条")
    print(f"一致 {len(same)}；不一致 {len(different)}；缺失 {len(missing)}")
    for item in different:
        print(f"  DIFF {item[0]}\n    frozen={item[1]}\n    actual={item[2]}")
    for item in missing:
        print(f"  MISSING {item}")
    print("本轮变异涉及的候选文件：")
    for relative in MUTATED:
        actual = sha256(REPO_ROOT / relative)
        print(
            f"  {relative} sha256={actual} 与冻结一致={actual == files.get(relative)}"
        )
    payload = {
        "probe": PROBE,
        "declared": frozen["fileCount"],
        "entries": len(files),
        "identical": len(same),
        "different": [
            {"path": path, "frozen": expected, "actual": actual}
            for path, expected, actual in different
        ],
        "missing": missing,
        "mutated_files_reconciled": {
            relative: sha256(REPO_ROOT / relative) == files.get(relative) for relative in MUTATED
        },
    }
    out = EVIDENCE_DIR / f"{PROBE}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"证据：{out}")


if __name__ == "__main__":
    main()
