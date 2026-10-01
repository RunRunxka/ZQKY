"""V00 · B3 收口审计：定版自洽（163/163、r2→定版=3 文档、final=r7）与冻结文档归因核对。

运行（仓库根）：
  apps/api/.venv/Scripts/python.exe -X utf8 docs/qa/TEACHING-LOOP-B3/V00-probes/p38_closure_audit.py
退出码 0 = 清单自洽且冻结文档的修订归因与账本一致；
退出码 1 = 清单或归因存在问题（明细打印；本批 r7 收口的已知残留见报告 §追加）。

区分两类断言：
  A. 清单/磁盘（必须全真）：定版 163/163、r2→定版恰 3 文档、产品/测试/scripts 零变化、final == r7；
  B. 冻结文档文本归因（本批收口的观测面）：文内"定版 = rN / 冻结为 rN / r1…rN"等是否等于实际最大账本。
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

EXPECTED_DOCS = [
    "docs/CURRENT_STATUS.md",
    "docs/qa/TEACHING-LOOP-B3/EVIDENCE-COMMANDS.md",
    "docs/qa/TEACHING-LOOP-B3/REPORT.md",
]


def load(name: str) -> dict:
    return json.loads((QA / name).read_text(encoding="utf-8"))


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def main() -> int:
    final, r2, r7 = load("FROZEN-B3.json"), load("FROZEN-B3-r2.json"), load("FROZEN-B3-r7.json")
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

    evidence = read("docs/qa/TEACHING-LOOP-B3/EVIDENCE-COMMANDS.md")
    report_md = read("docs/qa/TEACHING-LOOP-B3/REPORT.md")
    status = read("docs/CURRENT_STATUS.md")

    claims = {
        # "定版 = `FROZEN-B3-rN.json`**，r2→定版…" 是本批终态的归因声明（历史步骤 r4 的叙述不计入）
        "evidence_final_claim_r": re.findall(
            r"定版 = `FROZEN-B3-r(\d+)\.json`\*\*，r2→定版", evidence
        ),
        "evidence_equivalence_r": re.findall(
            r"内容与 `FROZEN-B3-r(\d+)\.json` 逐字节等价", evidence
        ),
        "evidence_ledger_max_r": re.findall(r"r1…r(\d+) 全部保留", evidence),
        "report_frozen_at_r": re.findall(r"冻结为 r(\d+)", report_md),
        "report_docs_count": re.findall(r"r2→定版差异恰(两个|三个)文档", report_md),
        "status_ledger_max_r": re.findall(r"逐次修订 r1(?:→r\d+)*→r(\d+) 全部保留", status),
    }
    actual_max_r = 7  # 账本已登记 r1..r7（FROZEN-B3.json revisionHistory + r7 文件）

    attribution_ok = (
        claims["evidence_final_claim_r"] == [str(actual_max_r)]
        and claims["evidence_equivalence_r"] == [str(actual_max_r)]
        and claims["evidence_ledger_max_r"] == [str(actual_max_r)]
        and claims["report_frozen_at_r"] == [str(actual_max_r)]
        and claims["report_docs_count"] == ["三个"]
        and claims["status_ledger_max_r"] == [str(actual_max_r)]
    )
    ledger_ok = (
        disk_ok == len(f)
        and not disk_bad
        and changed == EXPECTED_DOCS
        and product_changed == []
        and f == r7["files"]
    )
    payload = {
        "probe": "p38_closure_audit",
        "ledger": {
            "diskOk": disk_ok,
            "diskTotal": len(f),
            "diskBad": disk_bad,
            "r2ToFinalChanged": changed,
            "productChanged": product_changed,
            "finalEqualsR7": f == r7["files"],
            "actualMaxRevision": actual_max_r,
            "ok": ledger_ok,
        },
        "docAttribution": {"claims": claims, "ok": attribution_ok},
        "verdict": (
            "pass" if ledger_ok and attribution_ok
            else ("ledger_ok_attribution_lag" if ledger_ok else "ledger_fail")
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    (HERE / "p38_closure_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[p38_closure_audit] ledger_ok={ledger_ok} attribution_ok={attribution_ok} "
        f"verdict={payload['verdict']}"
    )
    return 0 if ledger_ok and attribution_ok else 1


if __name__ == "__main__":
    sys.exit(main())
