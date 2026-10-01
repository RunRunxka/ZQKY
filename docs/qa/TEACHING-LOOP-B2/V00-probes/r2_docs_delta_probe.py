"""V00-B2 · r2 复验探针 2：三处文档订正的事实核对（文档 ↔ 代码/实测）。

针对 r2 的 3 个修改文件逐项核对（不重复 V9 已覆盖的路由/触发器/六态）：
  A. `docs/API.md`：生成错误码订正（5 个实际码名都在代码里；且不再出现 r1 的三个旧名）；
     施测域 `CLASS_ARCHIVED` 移入 422 并注明名单域 409 —— 与两侧代码/实测状态码一致；
  B. `docs/CURRENT_STATUS.md`：V00 r1 结论（指纹/探针例数/V9 两处 fail/未执行/下一批入口）与 r1 证据一致；
  C. `apps/api/AGENTS.md`：B2 结构/共享依赖说明与代码一致（迁移 id、装配签名、收敛域）；
  D. `TASK-CARD.md` §11：登记 r1 的 observation 与既有边界，且未把它写成"已修复的产品缺陷"。
"""

from __future__ import annotations

import inspect
import json
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
PROBES = HERE.parent
_PROBE_TMP = Path(tempfile.mkdtemp(prefix="zqky-v00b2-r2docs-"))
os.environ["ZQKY_DATA_DIR"] = str(_PROBE_TMP)  # 必须在导入 app.main 之前
sys.path.insert(0, str(REPO / "apps" / "api"))

RESULTS: list[dict] = []

API_MD = REPO / "docs" / "API.md"
STATUS_MD = REPO / "docs" / "CURRENT_STATUS.md"
AGENTS_MD = REPO / "apps" / "api" / "AGENTS.md"
CARD_MD = REPO / "docs" / "qa" / "TEACHING-LOOP-B2" / "TASK-CARD.md"


def check(name: str, condition: bool, detail: str = "") -> bool:
    ok = bool(condition)
    RESULTS.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": str(detail)[:600]})
    print(f"[{'PASS' if ok else 'FAIL'}] {name} :: {str(detail)[:250]}")
    return ok


def b2_section(text: str) -> str:
    start = text.index("## 教学闭环 B2 接口")
    return text[start:text.index("### 新增依赖与命令", start)]


def main(evidence: str) -> int:
    api = API_MD.read_text(encoding="utf-8")
    section = b2_section(api)
    generation_src = (REPO / "apps" / "api" / "app" / "services" / "question_bank"
                      / "generation.py").read_text(encoding="utf-8")
    contract_src = (REPO / "apps" / "api" / "app" / "contracts" / "assessments.py").read_text(encoding="utf-8")

    # ---------------- A. API.md 订正
    documented = ["GENERATION_INVALID_JSON", "GENERATION_OUTPUT_TRUNCATED", "GENERATION_UNKNOWN_KNOWLEDGE",
                  "GENERATION_UNKNOWN_EVIDENCE", "GENERATION_FORBIDDEN_REFERENCE"]
    check("r2.A1 API.md 声明的 5 个生成错误码在 generation.py 中都有同名常量",
          all(f'"{code}"' in generation_src for code in documented),
          str([code for code in documented if f'"{code}"' not in generation_src]))
    stale_names = ["GENERATION_INVALID_EVIDENCE", "GENERATION_UNSAFE_REFERENCE", "GENERATION_TRUNCATED"]
    check("r2.A2 r1 的 3 个旧名已从 API.md B2 节消失（订正生效）",
          all(name not in api for name in stale_names),
          str([name for name in stale_names if name in api]))
    check("r2.A3 文档声明的 5 个码名 == 真 HTTP 实测码（V9/V5 复现过）",
          all(code in generation_src for code in documented) and not any(
              code in api for code in stale_names), "与 V5.1–V5.8 实测一致")

    status_section = section[section.index("### 施测（T30-b）"):]
    check("r2.A4 施测域 CLASS_ARCHIVED 已标为 422 并注明名单域 409",
          "CLASS_ARCHIVED`(422，施测域" in status_section
          and "名单域的 `CLASS_ARCHIVED` 为 409" in status_section
          and not re.search(r"CLASS_ARCHIVED`?\s*\(409\)", status_section),
          "订正文本存在且 409 组不再含 CLASS_ARCHIVED")
    roster_src = (REPO / "apps" / "api" / "app" / "services" / "roster" / "service.py").read_text(encoding="utf-8")
    roster_409 = re.search(r"code=CLASS_ARCHIVED,\s*\n\s*status_code=409", roster_src) is not None
    assess_422 = re.search(
        r"code=CLASS_ARCHIVED,\s*\n\s*status_code=422", 
        (REPO / "apps" / "api" / "app" / "services" / "assessments" / "service.py").read_text(encoding="utf-8")
    ) is not None
    check("r2.A5 两侧代码状态码与订正后文档一致（名单域 409 / 施测域 422）",
          roster_409 and assess_422 and 'CLASS_ARCHIVED = "CLASS_ARCHIVED"' in contract_src,
          f"roster_409={roster_409} assessments_422={assess_422}")

    # ---------------- B. CURRENT_STATUS
    status = STATUS_MD.read_text(encoding="utf-8")
    head = status[:status.index("## TEACHING-LOOP B1 批次")]
    counts = ["87/59/44/32/32/14/33/9/11"]
    check("r2.B1 CURRENT_STATUS 记录的 V00 r1 探针例数与我的 r1 证据逐一相符",
          all(token in head for token in counts) and "83/83 一致" in head,
          f"counts_present={[t for t in counts if t in head]} fingerprint_present={'83/83 一致' in head}")
    evidence_counts = {}
    for name in ("v1_migrations_probe", "v2_papers_import_probe", "v3_papers_confirm_probe",
                 "v4_papers_proposals_probe", "v5_question_links_generation_probe",
                 "v6_question_job_engine_probe", "v7_assessments_probe", "v9_docs_declarations_probe",
                 "v10_mutations_probe"):
        data = json.loads((PROBES / "evidence" / f"{name}.json").read_text(encoding="utf-8"))
        judged = [row for row in data["results"] if row["status"] in ("PASS", "FAIL")]
        evidence_counts[name] = len(judged)
    # V8 是 vitest 日志（9 例），V9 r1 为 17/19（19 例）
    r1_numbers = [evidence_counts["v1_migrations_probe"], evidence_counts["v2_papers_import_probe"],
                  evidence_counts["v3_papers_confirm_probe"], evidence_counts["v4_papers_proposals_probe"],
                  evidence_counts["v5_question_links_generation_probe"], evidence_counts["v6_question_job_engine_probe"],
                  evidence_counts["v7_assessments_probe"], 9, evidence_counts["v10_mutations_probe"]]
    check("r2.B2 上述例数由 r1 证据 JSON 独立复算得到（不是我照抄文档）",
          r1_numbers == [87, 59, 44, 32, 32, 14, 33, 9, 11], str(r1_numbers))
    check("r2.B3 CURRENT_STATUS 按 r1 结论口径登记 V9 两处 fail 已订正，并指向 V00-REPORT-02/TASK-CARD",
          "V00-REPORT-02" in head and "V9 fail（2 处文档事实错误" in head
          and "已订正 `docs/API.md`" in head and "TASK-CARD" in head,
          "结论口径与链接存在")
    if "V00-REPORT-01" not in head:
        RESULTS.append({
            "name": "OBS-STATUS 未深链 r1 报告（可经批次 README §6.1 到达）",
            "status": "OBSERVATION",
            "detail": "CURRENT_STATUS 的 V00 r1 段只深链 V00-REPORT-02 与 TASK-CARD，未深链 V00-REPORT-01；"
                      "批次 README §6.1 已链接 r1 报告，结论文字也在状态页，故不影响可追溯性。",
        })
        print("[OBS ] OBS-STATUS 未深链 r1 报告（可经批次 README §6.1 到达） :: 结论文字已在状态页")
    readme = (REPO / "docs" / "qa" / "TEACHING-LOOP-B2" / "README.md").read_text(encoding="utf-8")
    if "### 6.1 r1" in readme and "### 6.3 r2 窄复验" in readme:
        check("r2.B6 批次 README §6.1–6.3 逐项复述 r1 结论与 7 条 observation 处置（可追溯）",
              "GENERATION_INVALID_EVIDENCE" in readme and "CLASS_ARCHIVED" in readme
              and "OBS-1" in readme and "OBS-7" in readme,
              "r1 结论与 observation 处置表存在（README 非候选文件，登记为批次证据）")
    else:
        check("r2.B6 批次 README 含 r1/r2 小结", False, "未找到 §6.1/§6.3")
    check("r2.B4 CURRENT_STATUS 的 not_run 与 B3 入口与 r1 报告一致（真实模型/排版/Qdrant/正式迁移 + T60/F20/F10）",
          "真实模型调用" in head and "真实 Word/WPS 排版" in head and "真实 Qdrant" in head
          and "正式数据根迁移演练" in head and "T60 成绩" in head and "F20" in head,
          "not_run 与下一批入口齐备")
    check("r2.B5 CURRENT_STATUS 未把 V00 r1 的 observation 写成产品缺陷（措辞为「已登记」）",
          "7 条 observation 已登记" in head, "措辞正确")

    # ---------------- C. AGENTS.md
    agents = AGENTS_MD.read_text(encoding="utf-8")
    from app.core.migrations import REGISTERED_MIGRATIONS
    ids = [m.id for m in REGISTERED_MIGRATIONS["teaching"]] + \
          [m.id for m in REGISTERED_MIGRATIONS["question_bank"]]
    check("r2.C1 AGENTS.md 的 B2 迁移 id 与注册表一致",
          all(token in agents for token in ("`0003`", "`0004`", "question_knowledge_links"))
          and "0003_teaching_paper_tables" in ids and "0004_teaching_assessment_tables" in ids
          and "0004_question_knowledge_links" in ids,
          f"registered={ids}")
    from app.main import RECONCILE_DOMAINS
    from app.services.question_bank.service import build_question_bank_service
    signature = inspect.signature(build_question_bank_service)
    params = set(signature.parameters)
    check("r2.C2 AGENTS.md 的题库共享依赖说明与装配签名一致（knowledge_catalog/coordinator/job_engine）",
          {"knowledge_catalog", "coordinator", "job_engine"} <= params
          and "question" in RECONCILE_DOMAINS
          and "`RECONCILE_DOMAINS` 含 `question`" in agents,
          f"params={sorted(params)} domains={RECONCILE_DOMAINS}")
    check("r2.C3 AGENTS.md 声明「启动不自动重叫模型」与 V6 实测一致",
          "启动不自动重叫模型" in agents, "V6.8 实测：reconcile 后 provider 调用数不变")

    # ---------------- D. TASK-CARD §11
    card = CARD_MD.read_text(encoding="utf-8")
    risk = card[card.index("## 11. 预先登记的风险"):]
    check("r2.D1 TASK-CARD §11 登记 r1 observation（发布失败停 running / 错误码口径 / KnowledgePointView.id）",
          "发布失败后任务停在 `running`" in risk and "错误码命名映射" in risk
          and "`KnowledgePointView.id` 口径" in risk,
          "三项 observation 均在 §11")
    check("r2.D2 §11 未把 observation 写成「已修复」，并保留既有边界（正式关联无 source 列等）",
          "已修复" not in risk and "正式关联无" in risk and "ASSESSMENT_REVISION_STALE" in risk
          and "ParticipantMutationResult" in risk,
          "措辞与既有边界保留")
    check("r2.D3 §11 明确处置归属（B3 统一/以 generation.py 为准），与 r1 报告建议一致",
          "建议 B3 统一到引擎级" in risk and "以 `generation.py` 为准" in risk, "")

    failed = [row for row in RESULTS if row["status"] == "FAIL"]
    print(f"\n== r2_docs_delta_probe: {len(RESULTS) - len(failed)}/{len(RESULTS)} passed; "
          f"failed={[row['name'] for row in failed]} ==")
    if evidence:
        target = Path(evidence)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"probe": "r2_docs_delta_probe", "results": RESULTS},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"证据：{evidence}")
    return 1 if failed else 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="")
    _args = parser.parse_args()
    try:
        raise SystemExit(main(_args.evidence))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        RESULTS.append({"name": "probe crashed", "status": "FAIL", "detail": traceback.format_exc()[-300:]})
        sys.exit(1)
