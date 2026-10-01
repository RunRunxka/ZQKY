"""V00 · B3-C10 边界反证（声明与事实一致性）。

逐条验证 B3 边界声明：
  (a) CSV 确实可用（直读 + 全链，见 p24；本探针只做直读复核）；
  (b) 导入预览的 missing/absent 明细**没有服务端字段**：ScoreImportView / ScoreImportRowView /
      ScoreImportRowList 契约中不存在 absentByClass / missingParticipantIds / 行级状态分类；
      前端在 ScoreImportReview.tsx 用 loadAllImportRows + groupAbsencesByClass /
      deriveMissingAcknowledgement 本地推导，服务端 422 SCORE_ACKNOWLEDGEMENT_MISMATCH 兜底；
  (c) 不存在"出勤校正"独立端点：assessments/scores 路由表中没有 attendance/correction 路径，
      AssessmentUpdateRequest 也没有 attendance 字段；校正路径 = 修正原表后重新上传（新批次）；
  (d) F10-QB 用例全部是 stub 替身：F10-QB 相关 *.test.* 与 services/question-bank-api.test.ts
      只 stub `fetch`（vi.stubGlobal）或纯函数零 mock，无真后端/真进程。

运行（在 apps/api 下）：
  .venv/Scripts/python.exe -X utf8 <abs>/p28_boundary_checks.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import b3lib as B  # noqa: E402

WEB = B.REPO / "apps" / "web" / "src"
F10_QB_TESTS = [
    WEB / "features" / "question-bank" / name
    for name in (
        # FROZEN-B3 中 F10-QB 新增/变更的测试文件（见 changedSinceG0）
        "GenerationPanel.test.tsx",
        "KnowledgeLinksPanel.test.tsx",
        "QuestionBankWorkspace.test.tsx",
        "QuestionDetailLinks.test.tsx",
        "ReviewWorkspace.test.tsx",
        "jobs.test.tsx",
        "generation-notice.test.ts",
        "knowledge-links.test.ts",
        "source-trace.test.ts",
    )
] + [WEB / "services" / "question-bank-api.test.ts"]


def route_paths() -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    for file in (B.API_DIR / "app" / "api" / "v1" / "assessments.py", B.API_DIR / "app" / "api" / "v1" / "scores.py"):
        text = file.read_text(encoding="utf-8")
        for match in re.finditer(r'@router\.(get|post|patch|put|delete)\(\s*\n?\s*"([^"]+)"', text):
            paths.append((match.group(1).upper(), match.group(2)))
    return paths


def main() -> int:
    verdict = B.Verdict("p28_boundary_checks")

    # ---------------- (a) CSV 可用（直读层复核；全链见 p24）
    from app.services.tabular import read_score_sheet

    csv_bytes = "学号,姓名,Q1,Q2,Q3\n0001,甲,2,2,5\n0002,乙,2,3,\n".encode("utf-8-sig")
    sheets = read_score_sheet(csv_bytes)
    verdict.expect("CSV 直读单表 name=CSV", [s.name for s in sheets], ["CSV"])
    verdict.expect("CSV 物理行数=3", sheets[0].max_row, 3)
    verdict.expect("CSV 物理列数=5", sheets[0].max_column, 5)
    verdict.expect(
        "CSV 无公式视图且末格空白",
        (sheets[0].rows[2][4].formula, sheets[0].rows[2][4].is_blank),
        (None, True),
    )

    # ---------------- (b) 服务端没有 missing/absent 明细字段
    import app.contracts.scores as scores_py

    view_fields = set(scores_py.ScoreImportView.model_fields)
    row_fields = set(scores_py.ScoreImportRowView.model_fields)
    verdict.check(
        "ScoreImportView 无 absent/missing 明细字段（只有汇总数字）",
        not (view_fields & {"absent_by_class", "absentByClass", "missing_participant_ids", "missingParticipantIds"}),
        sorted(view_fields),
    )
    verdict.expect(
        "ScoreImportView 只有 missingCellCount 汇总",
        "missing_cell_count" in view_fields,
        True,
    )
    verdict.check(
        "ScoreImportRowView 无行级状态/出勤分类字段",
        not (row_fields & {"status", "attendance", "missing", "absent", "cell_status", "cellStatus"}),
        sorted(row_fields),
    )
    review = (WEB / "features" / "assessments" / "ScoreImportReview.tsx").read_text(encoding="utf-8")
    hooks = (WEB / "features" / "assessments" / "hooks.ts").read_text(encoding="utf-8")
    verdict.check(
        "前端本地推导 missing（deriveMissingAcknowledgement）",
        "deriveMissingAcknowledgement" in review and "loadAllImportRows" in review,
        "ScoreImportReview.tsx",
    )
    verdict.check(
        "前端本地推导缺考（groupAbsencesByClass）",
        "groupAbsencesByClass" in review,
        "ScoreImportReview.tsx",
    )
    verdict.check(
        "承认范围推导读取全部原表行（最多 20 页）",
        "承认范围推导用" in hooks and "for (let page = 0; page < 20" in hooks,
        "hooks.ts loadAllImportRows",
    )
    verdict.check(
        "422 兜底存在（SCORE_ACKNOWLEDGEMENT_MISMATCH 处理）",
        "SCORE_ACKNOWLEDGEMENT_MISMATCH" in (B.API_DIR / "app" / "contracts" / "scores.py").read_text(encoding="utf-8")
        and "承认范围与预览不一致" in review,
        "ScoreImportReview.tsx",
    )

    # ---------------- (c) 无出勤校正独立端点
    paths = route_paths()
    verdict.note("assessments/scores 路由：" + json.dumps(paths, ensure_ascii=False))
    verdict.check(
        "路由表中无 attendance/correction 独立端点",
        not any(
            ("attendance" in path.lower() or "correction" in path.lower()) and "score-revisions/correct" not in path
            for _method, path in paths
        ),
        [f"{m} {p}" for m, p in paths if "attendance" in p.lower() or "correction" in p.lower()],
    )
    import app.contracts.assessments as assessments_py

    verdict.check(
        "AssessmentUpdateRequest 无 attendance 字段",
        "attendance" not in set(assessments_py.AssessmentUpdateRequest.model_fields),
        sorted(assessments_py.AssessmentUpdateRequest.model_fields),
    )
    verdict.check(
        "人次维护只有 POST /assessments/{id}/participants（新增/补录）",
        [p for _m, p in paths if "participants" in p] == ["/assessments/{assessment_id}/participants"],
        [f"{m} {p}" for m, p in paths if "participants" in p],
    )
    panel = (WEB / "features" / "assessments" / "ScorePanel.tsx").read_text(encoding="utf-8")
    verdict.check(
        "校正路径 = 修正原表后重新上传（新批次）",
        "上传并创建待校对批次" in panel and "上传成绩表" in panel,
        "ScorePanel.tsx",
    )
    service_text = (B.API_DIR / "app" / "services" / "scores" / "service.py").read_text(encoding="utf-8")
    imports_text = (B.API_DIR / "app" / "services" / "scores" / "imports.py").read_text(encoding="utf-8")
    verdict.check(
        "服务端冲突文案指向校正原表/出勤（非独立端点）",
        "请先校正出勤/原表后重建预览" in service_text
        or "请先校正出勤/原表后重建预览" in imports_text,
        "service.py / imports.py",
    )

    # ---------------- (d) F10-QB 用例全部是 stub 替身
    real_backend_patterns = ("spawn(", "127.0.0.1:", "TestClient", "uv run", "createServer")
    missing = [str(p) for p in F10_QB_TESTS if not p.exists()]
    verdict.expect("F10-QB 测试文件都在", missing, [])
    stub_fetch = []
    pure = []
    for file in F10_QB_TESTS:
        text = file.read_text(encoding="utf-8")
        has_fetch_stub = "vi.stubGlobal('fetch'" in text or 'vi.stubGlobal("fetch"' in text
        has_real = any(pattern in text for pattern in real_backend_patterns)
        if has_real:
            verdict.check(f"{file.name} 无真后端/真进程", False, "匹配到真后端模式")
        if has_fetch_stub:
            stub_fetch.append(file.name)
        else:
            pure.append(file.name)
    verdict.note(f"stub fetch 的 F10-QB 测试（{len(stub_fetch)}）：" + "、".join(stub_fetch))
    verdict.note(f"零 mock 的纯函数测试（{len(pure)}）：" + "、".join(pure))
    verdict.check(
        "F10-QB 交互/API 用例全部 stub fetch",
        set(stub_fetch)
        >= {
            "GenerationPanel.test.tsx",
            "KnowledgeLinksPanel.test.tsx",
            "QuestionBankWorkspace.test.tsx",
            "QuestionDetailLinks.test.tsx",
            "ReviewWorkspace.test.tsx",
            "jobs.test.tsx",
            "question-bank-api.test.ts",
        },
        stub_fetch,
    )
    verdict.check(
        "F10-QB 测试无真后端/真浏览器链",
        all(
            not any(pattern in p.read_text(encoding="utf-8") for pattern in real_backend_patterns)
            for p in F10_QB_TESTS
        ),
        "全部文件",
    )

    return verdict.finish(path=HERE / "p28_boundary_checks.json")


if __name__ == "__main__":
    sys.exit(main())
