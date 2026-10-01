"""V00-B2 · r2 复验探针 1：r2 指纹对账 + r1↔r2 精确差异核对（不多不少）。

只读：复算 r2 的 84 文件 sha256；与 `FROZEN-CANDIDATE-r1.json`（r1 记录，保留件）逐文件对比，
得到**实测差异集合**（新增/删除/修改），再与 r2 记录的 `changedSincePrevious` 与 CTRL 声明的
「新增 1 + 修改 3」三方核对；并独立确认 80 个未变文件在磁盘上仍等于 r1 散列。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
QA = REPO / "docs" / "qa" / "TEACHING-LOOP-B2"
RESULTS: list[dict] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:800]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:260]}")
    return ok


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(evidence: str) -> int:
    r2 = json.loads((QA / "FROZEN-CANDIDATE.json").read_text(encoding="utf-8"))
    r1_path = QA / "FROZEN-CANDIDATE-r1.json"
    r1 = json.loads(r1_path.read_text(encoding="utf-8")) if r1_path.is_file() else None

    check("r2.0 记录头一致（revision=r2 / fileCount=84 / 起点 SHA 未变 / 无 postVerificationDocChanges）",
          r2.get("revision") == "r2" and r2.get("fileCount") == 84 and len(r2["files"]) == 84
          and r2.get("baseCommit") == "0f4b8cb190c2265d819b90e5d6df4e3954ad1906"
          and r2.get("postVerificationDocChanges") is None,
          f"revision={r2.get('revision')} fileCount={r2.get('fileCount')} "
          f"base={r2.get('baseCommit')} pvdc={r2.get('postVerificationDocChanges')}")
    check("r2.1 r1 记录保留件存在且为 83 文件", r1 is not None and r1.get("fileCount") == 83,
          f"r1 fileCount={r1.get('fileCount') if r1 else None} revision={r1.get('revision') if r1 else None}")

    # ---- 复算 r2 全部文件
    missing, mismatched = [], []
    for rel, expected in sorted(r2["files"].items()):
        path = REPO / rel.replace("/", os.sep)
        if not path.is_file():
            missing.append(rel)
            continue
        actual = sha256(path)
        if actual != expected:
            mismatched.append({"path": rel, "expected": expected, "actual": actual})
    check("r2.2 84 文件 sha256 复算 100% 一致（0 缺失 / 0 不一致）",
          not missing and not mismatched,
          f"files={len(r2['files'])} missing={missing} mismatch={[m['path'] for m in mismatched]}")

    # ---- 实测差异集合（r1 → r2）
    r1_files, r2_files = r1["files"], r2["files"]
    added = sorted(set(r2_files) - set(r1_files))
    removed = sorted(set(r1_files) - set(r2_files))
    modified = sorted(rel for rel in (set(r1_files) & set(r2_files)) if r1_files[rel] != r2_files[rel])
    check("r2.3 实测差异集合 = 新增 1 + 修改 3 + 删除 0",
          added == ["apps/api/AGENTS.md"] and removed == []
          and modified == ["docs/API.md", "docs/CURRENT_STATUS.md",
                           "docs/qa/TEACHING-LOOP-B2/TASK-CARD.md"],
          f"added={added} removed={removed} modified={modified}")

    # ---- 与 r2 记录声明 + CTRL 声明三方核对
    declared = sorted(r2.get("changedSincePrevious") or [])
    check("r2.4 实测「修改」集合 == r2 记录 changedSincePrevious（逐项）",
          declared == modified, f"declared={declared} measured={modified}")
    check("r2.5 r2 未声明未实测的额外变化（文件数 83→84 恰为 +1）",
          len(r1_files) - len(r2_files) == -1 and len(r2_files) - len(r1_files) == 1, "")

    # ---- 未变文件在磁盘上仍等于 r1 散列（r1 结论可复用）
    drift = []
    for rel in sorted(set(r1_files) & set(r2_files)):
        if r2_files[rel] != r1_files[rel]:
            continue
        if sha256(REPO / rel.replace("/", os.sep)) != r1_files[rel]:
            drift.append(rel)
    check("r2.6 80 个未变文件在磁盘上与 r1 逐字节一致（r1 通过结论可直接复用）",
          not drift, f"drift={drift} unchanged={len(set(r1_files) & set(r2_files)) - len(modified)}")

    # ---- 我 r1 期保存的 baseline 与 r1 记录一致
    baseline_path = HERE.parent / "baseline-hashes.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_diff = sorted(rel for rel in r1_files if baseline.get(rel) != r1_files[rel])
    check("r2.7 我 r1 期复算的 83 个散列 == r1 记录（V00 r1 结论的取证链条未断）",
          not baseline_diff and len(baseline) == 83, f"diff={baseline_diff}")

    # ---- 零产品/测试/脚本变化（除 AGENTS.md 外的 apps/**、tests/**、scripts/** 全在未变集合里）
    product_changes = [
        rel for rel in added + modified + removed
        if rel.startswith(("apps/", "tests/", "scripts/")) and rel != "apps/api/AGENTS.md"
    ]
    check("r2.8 产品/测试/脚本零变化（apps/** 仅新增 AGENTS.md；tests/**、scripts/** 未动）",
          not product_changes, f"product_changes={product_changes}")

    # ---- 迁移/契约文件逐字节未动
    pivotal = [
        "apps/api/app/core/migrations/teaching.py",
        "apps/api/app/core/migrations/question_bank.py",
        "apps/api/app/contracts/papers.py",
        "apps/api/app/contracts/assessments.py",
        "apps/api/app/schemas/question_bank.py",
        "apps/api/app/main.py",
        "apps/api/tests/test_b2_migrations.py",
        "apps/api/tests/test_b2_contracts.py",
    ]
    pivotal_stable = [rel for rel in pivotal if r1_files.get(rel) != r2_files.get(rel)]
    check("r2.9 迁移/契约/main/CTRL 测试 8 个关键文件逐字节未变", not pivotal_stable,
          f"changed={pivotal_stable}")

    failed = [row for row in RESULTS if row["status"] == "FAIL"]
    print(f"\n== r2_fingerprint_diff_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[row['name'] for row in failed]} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"probe": "r2_fingerprint_diff_probe", "results": RESULTS},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"证据：{evidence}")
    return 1 if failed else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="")
    _args = parser.parse_args()
    raise SystemExit(main(_args.evidence))
