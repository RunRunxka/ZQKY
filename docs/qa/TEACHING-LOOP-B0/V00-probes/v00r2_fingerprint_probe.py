"""r2 指纹对账探针（V00 / TEACHING-LOOP B0 r2）。

1) 复算 55 个候选文件 sha256，与 FROZEN-CANDIDATE.json（r2）逐一对账（期望 55/55）；
2) 自算 r1 → r2 的差异集合（逐文件 sha256 对比），与 r2 的 `changedSincePrevious` 比对
   （期望"不多不少"恰好相等）；
3) 打印差异文件清单与前后散列，作为 r2 窄复验的范围证据。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from _probe_common import EVIDENCE_DIR, REPO_ROOT

PROBE = "v00r2_fingerprint_probe"
QA = REPO_ROOT / "docs" / "qa" / "TEACHING-LOOP-B0"
R1 = QA / "FROZEN-CANDIDATE-r1.json"
R2 = QA / "FROZEN-CANDIDATE.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    r1 = json.loads(R1.read_text(encoding="utf-8"))
    r2 = json.loads(R2.read_text(encoding="utf-8"))

    ok = 0
    mismatched: list[dict] = []
    missing: list[str] = []
    for relative, expected in sorted(r2["files"].items()):
        path = REPO_ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        actual = sha256(path)
        if actual == expected:
            ok += 1
        else:
            mismatched.append({"path": relative, "r2": expected, "actual": actual})
    print(f"r2 记录 {r2['fileCount']} 个文件 / 条目 {len(r2['files'])}；一致 {ok}；不一致 {len(mismatched)}；缺失 {len(missing)}")
    for item in mismatched:
        print(f"  MISMATCH {item['path']}\n    r2={item['r2']}\n    actual={item['actual']}")
    for item in missing:
        print(f"  MISSING {item}")

    r1_files: dict[str, str] = r1["files"]
    r2_files: dict[str, str] = r2["files"]
    assert set(r1_files) == set(r2_files), "r1/r2 文件集合不同"
    computed = sorted(
        relative for relative in r1_files if r1_files[relative] != r2_files[relative]
    )
    declared = sorted(r2.get("changedSincePrevious") or [])
    print(f"自算 r1→r2 差异 {len(computed)} 项：{computed}")
    print(f"记录声明 changedSincePrevious {len(declared)} 项：{declared}")
    print(f"集合相等：{computed == declared}")
    print(f"多余（我算到但未声明）：{sorted(set(computed) - set(declared))}")
    print(f"遗漏（声明了我没算到）：{sorted(set(declared) - set(computed))}")

    payload = {
        "probe": PROBE,
        "r2_revision": r2.get("revision"),
        "r2_previous": r2.get("previousRevision"),
        "entries": len(r2["files"]),
        "identical": ok,
        "mismatched": mismatched,
        "missing": missing,
        "computed_changed": computed,
        "declared_changed": declared,
        "changed_sets_equal": computed == declared,
        "changed_hashes": {
            relative: {"r1": r1_files[relative], "r2": r2_files[relative]}
            for relative in computed
        },
    }
    out = EVIDENCE_DIR / f"{PROBE}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"证据：{out}")
    failed = bool(mismatched or missing) or computed != declared
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
