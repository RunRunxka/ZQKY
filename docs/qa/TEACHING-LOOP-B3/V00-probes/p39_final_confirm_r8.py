"""V00 · B3 最终核对（r8 收口）：163/163、r2→定版=3 文档、正文不再硬编码定版 rN。

运行（仓库根）：
  apps/api/.venv/Scripts/python.exe -X utf8 docs/qa/TEACHING-LOOP-B3/V00-probes/p39_final_confirm_r8.py
退出码 0 = 全部成立；1 = 有任何不一致（明细打印）。
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
QA = REPO / "docs" / "qa" / "TEACHING-LOOP-B3"

DOCS = [
    "docs/CURRENT_STATUS.md",
    "docs/qa/TEACHING-LOOP-B3/EVIDENCE-COMMANDS.md",
    "docs/qa/TEACHING-LOOP-B3/REPORT.md",
]
#: 正文不得再出现的"硬编码定版修订号"写法（CTRL 承诺的改写口径）
FORBIDDEN = [
    r"定版 = `FROZEN-B3-r\d+\.json`",
    r"冻结为 r\d+",
    r"与 `FROZEN-B3-r\d+\.json` 逐字节等价",
    r"r1…r\d+ 全部保留",
    r"r1→r2→r3→r4→r\d+",
]
#: 若正文写到变更集大小（"差异恰 N 个文档"），必须与实测一致（属事实陈述，不禁止）
DOCS_COUNT_RE = re.compile(r"r2→定版差异恰(两个|三个|四个|五个)文档")


def load(name: str) -> dict:
    return json.loads((QA / name).read_text(encoding="utf-8"))


def main() -> int:
    final, r2, r8 = load("FROZEN-B3.json"), load("FROZEN-B3-r2.json"), load("FROZEN-B3-r8.json")
    f, a = final["files"], r2["files"]

    disk_ok = sum(
        1
        for rel, expected in f.items()
        if hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == expected
    )
    disk_bad = [
        rel
        for rel, expected in f.items()
        if hashlib.sha256((REPO / rel).read_bytes()).hexdigest() != expected
    ]
    changed = sorted(rel for rel in set(a) & set(f) if a[rel] != f[rel])
    product_changed = [r for r in changed if r.startswith(("apps/", "tests/", "scripts/"))]
    history = final.get("revisionHistory") or {}

    doc_texts = {rel: (REPO / rel).read_text(encoding="utf-8") for rel in DOCS}
    forbidden_hits = {
        rel: sorted(
            {match.group(0) for pattern in FORBIDDEN for match in re.finditer(pattern, text)}
        )
        for rel, text in doc_texts.items()
    }
    revision_history_refs = {rel: "revisionHistory" in text for rel, text in doc_texts.items()}
    word_to_count = {"两个": 2, "三个": 3, "四个": 4, "五个": 5}
    docs_count_claims = {
        rel: [
            {"claim": match.group(1), "count": word_to_count[match.group(1)]}
            for match in DOCS_COUNT_RE.finditer(text)
        ]
        for rel, text in doc_texts.items()
    }
    docs_count_consistent = all(
        claim["count"] == len(changed)
        for claims in docs_count_claims.values()
        for claim in claims
    )

    checks = {
        "diskOk": disk_ok,
        "diskBad": disk_bad,
        "r2ToFinalChanged": changed,
        "r2ToFinalIsExactly3Docs": changed == DOCS,
        "productTestScriptsChanged": product_changed,
        "finalEqualsR8": f == r8["files"],
        "revisionHistoryRevisions": sorted((history.get("revisions") or {}).keys()),
        "revisionHistoryDocsVsR2": history.get("docsChangedVsR2"),
        "revisionHistoryProductUnchanged": history.get("productTestUnchangedSinceR2"),
        "forbiddenHits": forbidden_hits,
        "revisionHistoryRefs": revision_history_refs,
        "docsCountClaims": docs_count_claims,
        "docsCountConsistent": docs_count_consistent,
    }
    passed = (
        disk_ok == len(f)
        and not disk_bad
        and changed == DOCS
        and product_changed == []
        and checks["finalEqualsR8"]
        and checks["revisionHistoryRevisions"] == [f"B3-r{i}" for i in range(1, 9)]
        and sorted(history.get("docsChangedVsR2") or []) == sorted(DOCS)
        and history.get("productTestUnchangedSinceR2") is True
        and all(not hits for hits in forbidden_hits.values())
        and all(revision_history_refs.values())
        and docs_count_consistent
    )
    payload = {"probe": "p39_final_confirm_r8", "checks": checks, "verdict": "pass" if passed else "fail"}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    (HERE / "p39_final_confirm_r8.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[p39_final_confirm_r8] disk {disk_ok}/{len(f)} r2->final={changed} "
        f"final==r8={checks['finalEqualsR8']} forbidden={forbidden_hits} verdict={payload['verdict']}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
